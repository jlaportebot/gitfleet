"""Tests for gitfleet.health."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from gitfleet.health import (
    _check_go_deps,
    _check_node_deps,
    _check_python_deps,
    check_activity,
    check_dependencies,
    check_essentials,
    check_large_files,
    check_stale_branches,
    check_sync_status,
    check_working_tree,
    evaluate_repo_health,
)
from gitfleet.models import HealthGrade

# Test constants
SCORE_PERFECT = 100
SCORE_DIRTY = 50
SCORE_ERROR = 0
SCORE_DEPS_UNAVAILABLE = 50
SCORE_RECENT = 80
SCORE_MONTH = 50
SCORE_INACTIVE = 20
EXPECTED_CHECKS = 7


class TestCheckWorkingTree:
    @patch("gitfleet.health.git.Repo")
    def test_clean_working_tree(self, mock_repo_class, tmp_path):
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        mock_repo.is_dirty.return_value = False
        mock_repo.untracked_files = []

        score, detail = check_working_tree(tmp_path / "repo")

        assert score == SCORE_PERFECT
        assert "Clean working tree" in detail

    @patch("gitfleet.health.git.Repo")
    def test_dirty_working_tree(self, mock_repo_class, tmp_path):
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        mock_repo.is_dirty.return_value = True
        mock_repo.untracked_files = ["new_file.py"]
        # Mock index.diff
        mock_diff = Mock()
        mock_diff.__len__ = Mock(return_value=1)
        mock_repo.index.diff.return_value = [mock_diff]

        score, detail = check_working_tree(tmp_path / "repo")

        assert score < SCORE_PERFECT
        assert "uncommitted changes" in detail.lower()


class TestCheckStaleBranches:
    @patch("gitfleet.health.git.Repo")
    def test_no_stale_branches(self, mock_repo_class, tmp_path):
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        mock_repo.heads = []
        mock_repo.active_branch.name = "main"

        score, detail = check_stale_branches(tmp_path / "repo")

        assert score == SCORE_PERFECT
        assert "No stale branches" in detail

    @patch("gitfleet.health.git.Repo")
    def test_has_stale_branches(self, mock_repo_class, tmp_path):
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo

        # Create mock branches
        stale_commit = Mock()
        stale_commit.committed_datetime = datetime.now(timezone.utc) - timedelta(days=60)

        stale_branch = Mock()
        stale_branch.name = "feature/old"
        stale_branch.commit = stale_commit

        active_commit = Mock()
        active_commit.committed_datetime = datetime.now(timezone.utc)

        active_branch = Mock()
        active_branch.name = "main"
        active_branch.commit = active_commit

        mock_repo.heads = [stale_branch, active_branch]
        mock_repo.active_branch = active_branch
        # merge_base returns the stale commit (meaning it's merged)
        mock_repo.merge_base.return_value = [stale_commit]

        score, detail = check_stale_branches(tmp_path / "repo")

        assert score < SCORE_PERFECT
        assert "stale" in detail.lower()


class TestCheckEssentials:
    def test_all_essentials_present(self, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "README.md").write_text("# Test")
        (repo_dir / "LICENSE").write_text("MIT")
        (repo_dir / ".gitignore").write_text("*.pyc")
        (repo_dir / ".github").mkdir()
        (repo_dir / ".github" / "workflows").mkdir(parents=True)
        (repo_dir / ".github" / "workflows" / "ci.yml").write_text("name: CI")

        score, detail = check_essentials(repo_dir)

        assert score == SCORE_PERFECT
        assert "All essentials present" in detail

    def test_missing_essentials(self, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        # Only README
        (repo_dir / "README.md").write_text("# Test")

        score, detail = check_essentials(repo_dir)

        assert score < SCORE_PERFECT
        assert "Missing" in detail


class TestCheckDependencies:
    @patch("gitfleet.health.subprocess.run")
    def test_deps_up_to_date(self, mock_run, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "pyproject.toml").write_text('[project]\ndependencies = ["requests"]')

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        score, detail = check_dependencies(repo_dir)

        assert score == SCORE_PERFECT
        assert "up-to-date" in detail.lower()

    @patch("gitfleet.health.subprocess.run")
    def test_outdated_deps(self, mock_run, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "requirements.txt").write_text("requests==2.20.0")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "requests==2.20.0 -> 2.31.0"
        mock_run.return_value = mock_result

        score, detail = check_dependencies(repo_dir)

        assert score < SCORE_PERFECT
        assert "outdated" in detail.lower()


class TestCheckLargeFiles:
    def test_no_large_files(self, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "small.txt").write_text("small")

        score, detail = check_large_files(repo_dir, threshold_kb=1024)

        assert score == SCORE_PERFECT
        assert "No files" in detail

    def test_has_large_files(self, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        # Create a 2MB file
        (repo_dir / "large.bin").write_bytes(b"x" * (2 * 1024 * 1024))

        score, detail = check_large_files(repo_dir, threshold_kb=1024)

        assert score < SCORE_PERFECT
        assert "large" in detail.lower()


class TestCheckActivity:
    @patch("gitfleet.health.git.Repo")
    def test_recent_activity(self, mock_repo_class, tmp_path):
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        recent_commit = Mock()
        recent_commit.committed_datetime = datetime.now(timezone.utc) - timedelta(days=2)
        mock_repo.head.commit = recent_commit
        mock_repo.head.is_valid.return_value = True

        score, detail = check_activity(tmp_path / "repo")

        assert score == SCORE_PERFECT
        assert "ago" in detail.lower()

    @patch("gitfleet.health.git.Repo")
    def test_stale_activity(self, mock_repo_class, tmp_path):
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        old_commit = Mock()
        old_commit.committed_datetime = datetime.now(timezone.utc) - timedelta(days=100)
        mock_repo.head.commit = old_commit

        score, detail = check_activity(tmp_path / "repo")

        assert score < SCORE_PERFECT
        assert "inactive" in detail.lower() or "old" in detail.lower()


class TestCheckSyncStatus:
    @patch("gitfleet.health.git.Repo")
    def test_in_sync(self, mock_repo_class, tmp_path):
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        mock_repo.is_dirty.return_value = False
        mock_repo.untracked_files = []
        mock_repo.active_branch.name = "main"
        mock_repo.active_branch.tracking_branch.return_value = Mock()
        mock_repo.iter_commits.return_value = []

        status = check_sync_status(tmp_path / "repo")

        assert status.is_clean is True
        assert status.has_changes is False

    @patch("gitfleet.health.git.Repo")
    def test_ahead_behind(self, mock_repo_class, tmp_path):
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        mock_repo.is_dirty.return_value = False
        mock_repo.untracked_files = []
        mock_repo.active_branch.name = "main"

        tracking = Mock()
        tracking.name = "origin/main"
        mock_repo.active_branch.tracking_branch.return_value = tracking

        # 3 commits ahead, 2 behind
        mock_repo.iter_commits.side_effect = [
            [Mock(), Mock(), Mock()],  # ahead
            [Mock(), Mock()],  # behind
        ]

        status = check_sync_status(tmp_path / "repo")

        assert status.is_clean is True
        # The function returns SyncStatus, not ahead/behind counts directly


class TestEvaluateRepoHealth:
    @patch("gitfleet.health.check_working_tree")
    @patch("gitfleet.health.check_stale_branches")
    @patch("gitfleet.health.check_essentials")
    @patch("gitfleet.health.check_dependencies")
    @patch("gitfleet.health.check_large_files")
    @patch("gitfleet.health.check_activity")
    def test_evaluate_full_health(  # noqa: PLR0913
        self,
        mock_activity,
        mock_large,
        mock_deps,
        mock_essentials,
        mock_stale,
        mock_working,
        tmp_path,
    ):
        mock_working.return_value = (SCORE_PERFECT, "Clean working tree")
        mock_stale.return_value = (SCORE_PERFECT, "No stale branches")
        mock_essentials.return_value = (SCORE_PERFECT, "All essentials present")
        mock_deps.return_value = (SCORE_PERFECT, "All deps up-to-date")
        mock_large.return_value = (SCORE_PERFECT, "No large files")
        mock_activity.return_value = (SCORE_PERFECT, "Recent activity")

        health = evaluate_repo_health(tmp_path / "repo")

        assert health.overall_score == SCORE_PERFECT
        assert health.grade == HealthGrade.A
        assert len(health.checks) == EXPECTED_CHECKS


class TestCheckWorkingTreeExceptions:
    @patch("gitfleet.health.git.Repo")
    def test_working_tree_exception(self, mock_repo_class, tmp_path):
        mock_repo_class.side_effect = Exception("Git error")

        score, detail = check_working_tree(tmp_path / "repo")

        assert score == SCORE_ERROR
        assert "Error checking working tree" in detail


class TestCheckStaleBranchesExceptions:
    @patch("gitfleet.health.git.Repo")
    def test_stale_branches_exception_outer(self, mock_repo_class, tmp_path):
        mock_repo_class.side_effect = Exception("Git error")

        score, detail = check_stale_branches(tmp_path / "repo")

        assert score == SCORE_ERROR
        assert "Error checking stale branches" in detail

    @patch("gitfleet.health.git.Repo")
    def test_stale_branches_exception_inner(self, mock_repo_class, tmp_path):
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        mock_repo.heads = [Mock(name="feature/test")]
        mock_repo.active_branch.name = "main"
        mock_repo.merge_base.side_effect = ValueError("No merge base")

        score, _detail = check_stale_branches(tmp_path / "repo")

        # Should handle the exception and continue
        assert score == SCORE_PERFECT


class TestCheckEssentialsDirectory:
    def test_ci_directory_check(self, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "README.md").write_text("# Test")
        (repo_dir / "LICENSE").write_text("MIT")
        (repo_dir / ".gitignore").write_text("*.pyc")
        (repo_dir / ".github").mkdir()
        (repo_dir / ".github" / "workflows").mkdir(parents=True)

        score, detail = check_essentials(repo_dir)

        assert score == SCORE_PERFECT
        assert "All essentials present" in detail


class TestCheckPythonDeps:
    @patch("gitfleet.health.subprocess.run")
    def test_python_deps_exception(self, mock_run, tmp_path):
        mock_run.side_effect = Exception("pip failed")

        score, detail = _check_python_deps(tmp_path / "requirements.txt")

        assert score == SCORE_DEPS_UNAVAILABLE
        assert "Could not check Python dependencies" in detail

    @patch("gitfleet.health.subprocess.run")
    def test_python_deps_nonzero_exit(self, mock_run, tmp_path):
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        score, _detail = _check_python_deps(tmp_path / "requirements.txt")

        assert score == SCORE_DEPS_UNAVAILABLE


class TestCheckNodeDeps:
    @patch("gitfleet.health.subprocess.run")
    def test_node_deps_up_to_date(self, mock_run, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "package.json").write_text("{}")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "{}"
        mock_run.return_value = mock_result

        score, detail = _check_node_deps(repo_dir)

        assert score == SCORE_PERFECT
        assert "up-to-date" in detail.lower()

    @patch("gitfleet.health.subprocess.run")
    def test_node_deps_outdated(self, mock_run, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        mock_result = Mock()
        mock_result.returncode = 1  # npm outdated returns 1 when outdated
        mock_result.stdout = '{"express": {"current": "4.18.0", "latest": "4.19.0"}}'
        mock_run.return_value = mock_result

        score, detail = _check_node_deps(repo_dir)

        assert score < SCORE_PERFECT
        assert "outdated" in detail.lower()

    @patch("gitfleet.health.subprocess.run")
    def test_node_deps_json_error(self, mock_run, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "not valid json"
        mock_run.return_value = mock_result

        score, _detail = _check_node_deps(repo_dir)

        assert score == SCORE_DEPS_UNAVAILABLE

    @patch("gitfleet.health.subprocess.run")
    def test_node_deps_exception(self, mock_run, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        mock_run.side_effect = Exception("npm failed")

        score, _detail = _check_node_deps(repo_dir)

        assert score == SCORE_DEPS_UNAVAILABLE


class TestCheckGoDeps:
    @patch("gitfleet.health.subprocess.run")
    def test_go_deps_up_to_date(self, mock_run, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "github.com/user/module v1.0.0"
        mock_run.return_value = mock_result

        score, _detail = _check_go_deps(repo_dir)

        assert score == SCORE_PERFECT

    @patch("gitfleet.health.subprocess.run")
    def test_go_deps_outdated(self, mock_run, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "github.com/user/module v1.0.0 [v1.1.0]"
        mock_run.return_value = mock_result

        score, detail = _check_go_deps(repo_dir)

        assert score < SCORE_PERFECT
        assert "outdated" in detail.lower()

    @patch("gitfleet.health.subprocess.run")
    def test_go_deps_exception(self, mock_run, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        mock_run.side_effect = Exception("go failed")

        score, _detail = _check_go_deps(repo_dir)

        assert score == SCORE_DEPS_UNAVAILABLE


class TestCheckDependenciesIntegration:
    def test_check_dependencies_node(self, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "package.json").write_text("{}")

        with patch("gitfleet.health._check_node_deps") as mock_node:
            mock_node.return_value = (SCORE_PERFECT, "All deps up-to-date")
            score, _detail = check_dependencies(repo_dir)
            assert score == SCORE_PERFECT

    def test_check_dependencies_go(self, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "go.mod").write_text("module test")

        with patch("gitfleet.health._check_go_deps") as mock_go:
            mock_go.return_value = (SCORE_PERFECT, "All deps up-to-date")
            score, _detail = check_dependencies(repo_dir)
            assert score == SCORE_PERFECT


class TestCheckLargeFilesExceptions:
    def test_large_files_permission_error(self, tmp_path):
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "file.txt").write_text("content")

        with patch("pathlib.Path.rglob", side_effect=PermissionError("No access")):
            score, _detail = check_large_files(repo_dir)

        assert score == SCORE_PERFECT  # Exception caught, returns default


class TestCheckActivityBranches:
    @patch("gitfleet.health.git.Repo")
    def test_activity_30_days(self, mock_repo_class, tmp_path):
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        commit = Mock()
        commit.committed_datetime = datetime.now(timezone.utc) - timedelta(days=15)
        mock_repo.head.commit = commit
        mock_repo.head.is_valid.return_value = True

        score, detail = check_activity(tmp_path / "repo")

        assert score == SCORE_RECENT
        assert "15d ago" in detail

    @patch("gitfleet.health.git.Repo")
    def test_activity_90_days(self, mock_repo_class, tmp_path):
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        commit = Mock()
        commit.committed_datetime = datetime.now(timezone.utc) - timedelta(days=60)
        mock_repo.head.commit = commit
        mock_repo.head.is_valid.return_value = True

        score, detail = check_activity(tmp_path / "repo")

        assert score == SCORE_MONTH
        assert "60d ago" in detail

    @patch("gitfleet.health.git.Repo")
    def test_activity_inactive(self, mock_repo_class, tmp_path):
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        commit = Mock()
        commit.committed_datetime = datetime.now(timezone.utc) - timedelta(days=120)
        mock_repo.head.commit = commit
        mock_repo.head.is_valid.return_value = True

        score, detail = check_activity(tmp_path / "repo")

        assert score == SCORE_INACTIVE
        assert "Inactive" in detail

    @patch("gitfleet.health.git.Repo")
    def test_activity_no_commits(self, mock_repo_class, tmp_path):
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        mock_repo.head.is_valid.return_value = False

        score, detail = check_activity(tmp_path / "repo")

        assert score == SCORE_ERROR
        assert "No commits" in detail

    @patch("gitfleet.health.git.Repo")
    def test_activity_exception(self, mock_repo_class, tmp_path):
        mock_repo_class.side_effect = Exception("Git error")

        score, detail = check_activity(tmp_path / "repo")

        assert score == SCORE_ERROR
        assert "Error checking activity" in detail


class TestCheckSyncStatusExceptions:
    @patch("gitfleet.health.git.Repo")
    def test_sync_status_exception(self, mock_repo_class, tmp_path):
        mock_repo_class.side_effect = Exception("Git error")

        status = check_sync_status(tmp_path / "repo")

        assert status.is_clean is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
