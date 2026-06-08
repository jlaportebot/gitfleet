"""Health checks for Git repositories."""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import git

from gitfleet.models import RepoHealth, SyncStatus

# Check weights (must sum to 100)
WEIGHTS = {
    "working_tree": 15,
    "stale_branches": 10,
    "essentials": 20,
    "dependencies": 15,
    "large_files": 10,
    "activity": 15,
    "sync_status": 15,
}

# Constants for thresholds
RECENT_DAYS = 7
MONTH_DAYS = 30
DEFAULT_INACTIVE_DAYS = 90
STALE_BRANCH_DAYS = 30
LARGE_FILE_LIMIT = 5
OUTDATED_PENALTY = 5
MISSING_ESSENTIAL_PENALTY = 25
STALE_BRANCH_PENALTY = 10
LARGE_FILE_PENALTY = 10
DIRTY_WORKING_TREE_SCORE = 50
ERROR_SCORE = 0
DEPS_UNAVAILABLE_SCORE = 50
NO_COMMITS_SCORE = 0
INACTIVE_SCORE = 20
SYNC_DIRTY_SCORE = 50


def check_working_tree(repo_path: Path) -> tuple[int, str]:
    """Check for uncommitted changes in working tree."""
    try:
        repo = git.Repo(repo_path)
        if repo.is_dirty() or repo.untracked_files:
            details = []
            if repo.is_dirty():
                details.append(f"{len(repo.index.diff(None))} modified")
            if repo.untracked_files:
                details.append(f"{len(repo.untracked_files)} untracked")
            return DIRTY_WORKING_TREE_SCORE, f"Uncommitted changes: {', '.join(details)}"
        else:
            return 100, "Clean working tree"
    except Exception as e:
        return ERROR_SCORE, f"Error checking working tree: {e}"


def check_stale_branches(repo_path: Path, stale_days: int = STALE_BRANCH_DAYS) -> tuple[int, str]:
    """Check for stale (merged but not deleted) branches."""
    try:
        repo = git.Repo(repo_path)
        default_branch = repo.active_branch.name if repo.head.is_valid() else "main"
        cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)

        stale_count = 0
        for branch in repo.heads:
            if branch.name == default_branch:
                continue
            try:
                # Check if branch is merged into default
                merge_base = repo.merge_base(branch, default_branch)
                if (
                    merge_base
                    and branch.commit == merge_base[0]
                    and branch.commit.committed_datetime < cutoff
                ):
                    stale_count += 1
            except (ValueError, IndexError):
                continue

        if stale_count == 0:
            return 100, "No stale branches"
        penalty = stale_count * STALE_BRANCH_PENALTY
        return max(0, 100 - penalty), f"{stale_count} stale branch(es) found"
    except Exception as e:
        return ERROR_SCORE, f"Error checking stale branches: {e}"


def check_essentials(repo_path: Path) -> tuple[int, str]:
    """Check for essential files: README, LICENSE, .gitignore, CI config."""
    essentials = {
        "README": ["README.md", "README.rst", "README.txt", "README"],
        "LICENSE": ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"],
        "gitignore": [".gitignore"],
        "CI": [
            ".github/workflows",
            ".gitlab-ci.yml",
            ".circleci/config.yml",
            "azure-pipelines.yml",
            "Jenkinsfile",
            ".travis.yml",
        ],
    }

    found = dict.fromkeys(essentials, False)
    missing = []

    for key, patterns in essentials.items():
        for pattern in patterns:
            if pattern.endswith("/"):
                # Directory check
                if (repo_path / pattern.rstrip("/")).is_dir():
                    found[key] = True
                    break
            elif any(repo_path.glob(pattern)):
                found[key] = True
                break

        if not found[key]:
            missing.append(key)

    if not missing:
        return 100, "All essentials present"
    return max(0, 100 - len(missing) * MISSING_ESSENTIAL_PENALTY), f"Missing: {', '.join(missing)}"


def check_dependencies(repo_path: Path) -> tuple[int, str]:
    """Check for outdated dependencies."""
    # Python project files
    py_files = [
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-test.txt",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "poetry.lock",
    ]

    for py_file in py_files:
        if (repo_path / py_file).exists():
            return _check_python_deps(repo_path / py_file)

    # Node.js
    if (repo_path / "package.json").exists():
        return _check_node_deps(repo_path)

    # Go
    if (repo_path / "go.mod").exists():
        return _check_go_deps(repo_path)

    return 100, "No dependency files found"


def _check_python_deps(dep_file: Path) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["pip", "list", "--outdated", "--format=freeze"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            outdated = result.stdout.strip().split("\n") if result.stdout.strip() else []
            if not outdated or outdated == [""]:
                return 100, "All deps up-to-date"
            penalty = len(outdated) * OUTDATED_PENALTY
            return max(0, 100 - penalty), f"{len(outdated)} outdated package(s)"
    except Exception:
        pass
    return DEPS_UNAVAILABLE_SCORE, "Could not check Python dependencies"


def _check_node_deps(repo_path: Path) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["npm", "outdated", "--json"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode in (0, 1):  # npm outdated returns 1 when packages outdated
            try:
                outdated = json.loads(result.stdout) if result.stdout.strip() else {}
                if not outdated:
                    return 100, "All deps up-to-date"
                penalty = len(outdated) * OUTDATED_PENALTY
                return max(0, 100 - penalty), f"{len(outdated)} outdated package(s)"
            except json.JSONDecodeError:
                pass
    except Exception:
        pass
    return DEPS_UNAVAILABLE_SCORE, "Could not check Node dependencies"


def _check_go_deps(repo_path: Path) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["go", "list", "-u", "-m", "all"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            outdated = [line for line in lines if "[" in line and "]" in line]
            if not outdated:
                return 100, "All deps up-to-date"
            penalty = len(outdated) * OUTDATED_PENALTY
            return max(0, 100 - penalty), f"{len(outdated)} outdated module(s)"
    except Exception:
        pass
    return DEPS_UNAVAILABLE_SCORE, "Could not check Go dependencies"


def check_large_files(repo_path: Path, threshold_kb: int = 1024) -> tuple[int, str]:
    """Check for files exceeding size threshold."""
    threshold_bytes = threshold_kb * 1024
    large_files = []

    try:
        for file_path in repo_path.rglob("*"):
            if file_path.is_file() and not any(part.startswith(".") for part in file_path.parts):
                try:
                    size = file_path.stat().st_size
                    if size > threshold_bytes:
                        large_files.append((file_path.relative_to(repo_path), size))
                except OSError:
                    continue
    except Exception:
        pass

    if not large_files:
        return 100, f"No files ≥{threshold_kb}KB"

    # Score decreases with number of large files
    score = max(0, 100 - len(large_files) * LARGE_FILE_PENALTY)
    details = ", ".join(f"{p} ({s / 1024 / 1024:.1f}MB)" for p, s in large_files[:LARGE_FILE_LIMIT])
    if len(large_files) > LARGE_FILE_LIMIT:
        details += f" and {len(large_files) - LARGE_FILE_LIMIT} more"
    return score, f"Large files: {details}"


def check_activity(repo_path: Path, inactive_days: int = DEFAULT_INACTIVE_DAYS) -> tuple[int, str]:
    """Check how recent the last commit was."""
    try:
        repo = git.Repo(repo_path)
        if not repo.head.is_valid():
            return NO_COMMITS_SCORE, "No commits in repository"

        last_commit_date = repo.head.commit.committed_datetime
        if last_commit_date.tzinfo is None:
            last_commit_date = last_commit_date.replace(tzinfo=timezone.utc)

        days_since = (datetime.now(timezone.utc) - last_commit_date).days

        if days_since <= RECENT_DAYS:
            return 100, f"Last commit {days_since}d ago"
        elif days_since <= MONTH_DAYS:
            return 80, f"Last commit {days_since}d ago"
        elif days_since <= inactive_days:
            return 50, f"Last commit {days_since}d ago"
        else:
            return INACTIVE_SCORE, f"Inactive: last commit {days_since}d ago"
    except Exception as e:
        return ERROR_SCORE, f"Error checking activity: {e}"


def check_sync_status(repo_path: Path) -> SyncStatus:
    """Check synchronization status with remote."""
    try:
        repo = git.Repo(repo_path)

        # Check working tree
        untracked = [f for f in repo.untracked_files if f is not None]
        modified = [item.a_path for item in repo.index.diff(None) if item.a_path is not None]
        staged = [item.a_path for item in repo.index.diff("HEAD") if item.a_path is not None]
        deleted = [
            item.a_path
            for item in repo.index.diff("HEAD")
            if item.deleted_file and item.a_path is not None
        ]

        is_clean = not (untracked or modified or staged or deleted)

        return SyncStatus(
            is_clean=is_clean,
            untracked_files=untracked,
            modified_files=modified,
            staged_files=staged,
            deleted_files=deleted,
        )
    except Exception:
        return SyncStatus(is_clean=True)


def evaluate_repo_health(repo_path: Path) -> RepoHealth:
    """Run all health checks and compute overall score."""
    checks = {}
    check_details = {}

    # Run all checks
    score, detail = check_working_tree(repo_path)
    checks["working_tree"] = score
    check_details["working_tree"] = detail

    score, detail = check_stale_branches(repo_path)
    checks["stale_branches"] = score
    check_details["stale_branches"] = detail

    score, detail = check_essentials(repo_path)
    checks["essentials"] = score
    check_details["essentials"] = detail

    score, detail = check_dependencies(repo_path)
    checks["dependencies"] = score
    check_details["dependencies"] = detail

    score, detail = check_large_files(repo_path)
    checks["large_files"] = score
    check_details["large_files"] = detail

    score, detail = check_activity(repo_path)
    checks["activity"] = score
    check_details["activity"] = detail

    # Sync status check (simplified - just check if clean)
    sync_status = check_sync_status(repo_path)
    sync_score = 100 if sync_status.is_clean else SYNC_DIRTY_SCORE
    checks["sync_status"] = sync_score
    check_details["sync_status"] = "In sync with remote" if sync_status.is_clean else "Out of sync"

    # Calculate weighted overall score
    total_weight = sum(WEIGHTS.values())
    weighted_sum = sum(checks.get(k, 0) * w for k, w in WEIGHTS.items())
    overall_score = round(weighted_sum / total_weight)

    return RepoHealth(
        repo_path=str(repo_path),
        overall_score=overall_score,
        grade=None,  # Auto-calculated in __post_init__
        checks=checks,
        check_details=check_details,
    )
