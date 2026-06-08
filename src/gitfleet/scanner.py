"""Repository discovery and scanning."""

import contextlib
from pathlib import Path

import git

from gitfleet.models import RepoInfo


def is_git_repo(path: Path) -> bool:
    """Check if a path is a Git repository."""
    if not path.is_dir():
        return False
    return (path / ".git").exists()


def discover_repos(root: Path, max_depth: int = 5) -> list[RepoInfo]:
    """Discover all Git repositories under a root directory.

    Args:
        root: Root directory to search.
        max_depth: Maximum directory depth to search (default 5).

    Returns:
        List of RepoInfo for each discovered repository.
    """
    if not root.exists() or not root.is_dir():
        return []

    repos: list[RepoInfo] = []
    root = root.resolve()

    def _scan_dir(current: Path, depth: int) -> None:
        if depth > max_depth:
            return

        try:
            for entry in current.iterdir():
                if not entry.is_dir():
                    continue

                if is_git_repo(entry):
                    repo_info = scan_repo(entry)
                    repos.append(repo_info)
                    # Continue scanning subdirectories for nested repos

                _scan_dir(entry, depth + 1)
        except (PermissionError, OSError):
            # Skip directories we can't read
            pass

    _scan_dir(root, 0)
    return repos


def scan_repo(path: Path) -> RepoInfo:
    """Scan a single repository and extract metadata.

    Args:
        path: Path to the repository.

    Returns:
        RepoInfo with repository metadata.
    """
    repo = git.Repo(path)
    name = path.name

    # Get remote URL
    remote_url: str | None = None
    if repo.remotes:
        try:
            remote_url = repo.remotes.origin.url
        except (AttributeError, IndexError):
            if repo.remotes:
                remote_url = repo.remotes[0].url

    # Get default branch
    default_branch = "main"
    with contextlib.suppress(TypeError, ValueError):
        default_branch = repo.active_branch.name

    return RepoInfo(
        path=str(path.resolve()),
        name=name,
        remote_url=remote_url,
        default_branch=default_branch,
    )
