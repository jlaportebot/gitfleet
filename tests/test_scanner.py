"""Tests for gitfleet.scanner."""

from pathlib import Path
from unittest.mock import Mock, patch

import git
import pytest

from gitfleet.scanner import discover_repos, is_git_repo, scan_repo

EXPECTED_REPO_COUNT_3 = 3
EXPECTED_REPO_COUNT_2 = 2


class TestIsGitRepo:
    def test_is_git_repo_true(self, tmp_path):
        repo_dir = tmp_path / "my_repo"
        repo_dir.mkdir()
        git.Repo.init(repo_dir)
        assert is_git_repo(repo_dir) is True

    def test_is_git_repo_false_no_git_dir(self, tmp_path):
        repo_dir = tmp_path / "not_a_repo"
        repo_dir.mkdir()
        assert is_git_repo(repo_dir) is False

    def test_is_git_repo_false_not_directory(self, tmp_path):
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")
        assert is_git_repo(file_path) is False


class TestDiscoverRepos:
    def test_discover_single_repo(self, tmp_path):
        repo_dir = tmp_path / "repo1"
        repo_dir.mkdir()
        git.Repo.init(repo_dir)
        repos = discover_repos(tmp_path)
        assert len(repos) == 1
        assert repos[0].name == "repo1"

    def test_discover_multiple_repos(self, tmp_path):
        for name in ["repo1", "repo2", "repo3"]:
            repo_dir = tmp_path / name
            repo_dir.mkdir()
            git.Repo.init(repo_dir)
        repos = discover_repos(tmp_path)
        assert len(repos) == EXPECTED_REPO_COUNT_3
        names = {r.name for r in repos}
        assert names == {"repo1", "repo2", "repo3"}

    def test_discover_nested_repos(self, tmp_path):
        parent = tmp_path / "parent"
        parent.mkdir()
        git.Repo.init(parent)

        child = parent / "child"
        child.mkdir()
        git.Repo.init(child)

        repos = discover_repos(tmp_path)
        assert len(repos) == EXPECTED_REPO_COUNT_2

    def test_discover_ignores_non_repos(self, tmp_path):
        (tmp_path / "not_a_repo").mkdir()
        (tmp_path / "also_not").mkdir()

        repo_dir = tmp_path / "real_repo"
        repo_dir.mkdir()
        git.Repo.init(repo_dir)

        repos = discover_repos(tmp_path)
        assert len(repos) == 1
        assert repos[0].name == "real_repo"

    def test_discover_empty_directory(self, tmp_path):
        repos = discover_repos(tmp_path)
        assert len(repos) == 0

    def test_discover_nonexistent_path(self):
        repos = discover_repos(Path("/nonexistent/path"))
        assert len(repos) == 0

    def test_discover_max_depth(self, tmp_path):
        # Create nested structure: root/level1/level2/level3/repo
        level1 = tmp_path / "level1"
        level1.mkdir()
        level2 = level1 / "level2"
        level2.mkdir()
        level3 = level2 / "level3"
        level3.mkdir()
        repo = level3 / "deep_repo"
        repo.mkdir()
        git.Repo.init(repo)

        repos = discover_repos(tmp_path, max_depth=2)
        assert len(repos) == 0  # Too deep

        repos = discover_repos(tmp_path, max_depth=3)
        assert len(repos) == 1


class TestScanRepo:
    @patch("gitfleet.scanner.git.Repo")
    def test_scan_repo_basic(self, mock_repo_class, tmp_path):
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        mock_repo.working_dir = str(tmp_path / "test_repo")
        mock_repo.remotes.origin.url = "https://github.com/user/test_repo.git"
        mock_repo.active_branch.name = "main"
        mock_repo.head.commit.hexsha = "abc123"
        mock_repo.head.commit.message = "Initial commit"
        mock_repo.head.commit.author.name = "Test User"
        mock_repo.head.commit.author.email = "test@example.com"
        mock_repo.head.commit.committed_datetime = 1234567890

        repo_info = scan_repo(tmp_path / "test_repo")

        assert repo_info.name == "test_repo"
        assert repo_info.remote_url == "https://github.com/user/test_repo.git"
        assert repo_info.default_branch == "main"

    @patch("gitfleet.scanner.git.Repo")
    def test_scan_repo_no_origin_remote(self, mock_repo_class, tmp_path):
        mock_repo = Mock()
        mock_repo_class.return_value = mock_repo
        mock_repo.working_dir = str(tmp_path / "test_repo")
        mock_repo.remotes = []  # No remotes
        mock_repo.active_branch.name = "main"

        repo_info = scan_repo(tmp_path / "test_repo")

        assert repo_info.remote_url is None
        assert repo_info.default_branch == "main"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
