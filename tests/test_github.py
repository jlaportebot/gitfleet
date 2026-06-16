"""Tests for GitHub API integration."""

import subprocess
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from gitfleet.github import (
    GitHubRepoInfo,
    enrich_repo_info,
    enrich_repos,
    extract_owner_repo_from_url,
    fetch_github_repo_info,
)
from gitfleet.models import RepoInfo

# Test constants
EXPECTED_STARS = 100
EXPECTED_FORKS = 50
EXPECTED_WATCHERS = 20
EXPECTED_OPEN_ISSUES = 5
EXPECTED_STARS_2 = 42
EXPECTED_FORKS_2 = 10
EXPECTED_STARS_3 = 10
EXPECTED_STARS_4 = 20
EXPECTED_REPO_COUNT = 3


class TestExtractOwnerRepoFromURL:
    """Tests for extract_owner_repo_from_url function."""

    def test_https_url(self):
        """Test extracting from HTTPS URL."""
        result = extract_owner_repo_from_url("https://github.com/owner/repo.git")
        assert result == ("owner", "repo")

    def test_https_url_no_git(self):
        """Test extracting from HTTPS URL without .git suffix."""
        result = extract_owner_repo_from_url("https://github.com/owner/repo")
        assert result == ("owner", "repo")

    def test_ssh_url(self):
        """Test extracting from SSH URL."""
        result = extract_owner_repo_from_url("git@github.com:owner/repo.git")
        assert result == ("owner", "repo")

    def test_ssh_url_no_git(self):
        """Test extracting from SSH URL without .git suffix."""
        result = extract_owner_repo_from_url("git@github.com:owner/repo")
        assert result == ("owner", "repo")

    def test_non_github_url(self):
        """Test that non-GitHub URLs return None."""
        result = extract_owner_repo_from_url("https://gitlab.com/owner/repo")
        assert result is None

    def test_empty_url(self):
        """Test that empty URL returns None."""
        result = extract_owner_repo_from_url("")
        assert result is None

    def test_none_url(self):
        """Test that None URL returns None."""
        # The function expects str, so we test with empty string instead
        result = extract_owner_repo_from_url("")
        assert result is None


class TestFetchGitHubRepoInfo:
    """Tests for fetch_github_repo_info function."""

    @patch("gitfleet.github.subprocess.run")
    def test_successful_fetch(self, mock_run):
        """Test successful fetch of repo info."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "Test repo\nPython\n100\n50\n20\n5\nMIT\nmain\n"
                "2024-01-15T10:00:00Z\n2023-01-01T00:00:00Z\n"
                "2024-01-10T00:00:00Z\nhttps://example.com\n"
                "[\"topic1\", \"topic2\"]\nfalse\nfalse\npublic"
            ),
        )

        result = fetch_github_repo_info("owner", "repo")

        assert result is not None
        assert result.description == "Test repo"
        assert result.language == "Python"
        assert result.stars == EXPECTED_STARS
        assert result.forks == EXPECTED_FORKS
        assert result.watchers == EXPECTED_WATCHERS
        assert result.open_issues == EXPECTED_OPEN_ISSUES
        assert result.license == "MIT"
        assert result.default_branch == "main"
        assert result.pushed_at == datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        assert result.created_at == datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert result.updated_at == datetime(2024, 1, 10, 0, 0, 0, tzinfo=timezone.utc)
        assert result.homepage == "https://example.com"
        assert result.topics == ["topic1", "topic2"]
        assert result.archived is False
        assert result.disabled is False
        assert result.visibility == "public"

    @patch("gitfleet.github.subprocess.run")
    def test_failed_fetch(self, mock_run):
        """Test failed fetch returns None."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Not found")

        result = fetch_github_repo_info("owner", "repo")
        assert result is None

    @patch("gitfleet.github.subprocess.run")
    def test_timeout(self, mock_run):
        """Test timeout returns None."""
        mock_run.side_effect = subprocess.TimeoutExpired("gh", 30)

        result = fetch_github_repo_info("owner", "repo")
        assert result is None


class TestEnrichRepoInfo:
    """Tests for enrich_repo_info function."""

    def test_no_remote_url(self):
        """Test repo without remote URL returns unchanged."""
        repo = RepoInfo(path="/path/to/repo", name="repo", remote_url=None)
        result = enrich_repo_info(repo)
        assert result == repo

    def test_non_github_remote(self):
        """Test repo with non-GitHub remote returns unchanged."""
        repo = RepoInfo(
            path="/path/to/repo", name="repo", remote_url="https://gitlab.com/owner/repo"
        )
        result = enrich_repo_info(repo)
        assert result == repo

    @patch("gitfleet.github.fetch_github_repo_info")
    def test_successful_enrichment(self, mock_fetch):
        """Test successful enrichment with GitHub data."""
        mock_fetch.return_value = GitHubRepoInfo(
            description="Test description",
            language="Python",
            stars=EXPECTED_STARS_2,
            forks=EXPECTED_FORKS_2,
            default_branch="develop",
            pushed_at=datetime(2024, 1, 15, 10, 0, 0),
        )

        repo = RepoInfo(
            path="/path/to/repo",
            name="repo",
            remote_url="https://github.com/owner/repo",
            default_branch="main",
        )
        result = enrich_repo_info(repo)

        assert result.description == "Test description"
        assert result.language == "Python"
        assert result.stars == EXPECTED_STARS_2
        assert result.forks == EXPECTED_FORKS_2
        assert result.default_branch == "develop"
        assert result.last_pushed == datetime(2024, 1, 15, 10, 0, 0)
        assert result.path == "/path/to/repo"
        assert result.name == "repo"
        assert result.remote_url == "https://github.com/owner/repo"

    @patch("gitfleet.github.fetch_github_repo_info")
    def test_failed_enrichment(self, mock_fetch):
        """Test failed enrichment returns original repo."""
        mock_fetch.return_value = None

        repo = RepoInfo(
            path="/path/to/repo",
            name="repo",
            remote_url="https://github.com/owner/repo",
            default_branch="main",
        )
        result = enrich_repo_info(repo)

        assert result == repo


class TestEnrichRepos:
    """Tests for enrich_repos function."""

    @patch("gitfleet.github.fetch_github_repo_info")
    def test_enrich_multiple(self, mock_fetch):
        """Test enriching multiple repositories."""
        mock_fetch.side_effect = [
            GitHubRepoInfo(stars=EXPECTED_STARS_3, language="Python"),
            GitHubRepoInfo(stars=EXPECTED_STARS_4, language="Rust"),
            None,  # Third one fails
        ]

        repos = [
            RepoInfo(path="/p1", name="r1", remote_url="https://github.com/o/r1"),
            RepoInfo(path="/p2", name="r2", remote_url="https://github.com/o/r2"),
            RepoInfo(path="/p3", name="r3", remote_url="https://github.com/o/r3"),
        ]
        results = enrich_repos(repos)

        assert len(results) == EXPECTED_REPO_COUNT
        assert results[0].stars == EXPECTED_STARS_3
        assert results[0].language == "Python"
        assert results[1].stars == EXPECTED_STARS_4
        assert results[1].language == "Rust"
        assert results[2].stars == 0  # Unchanged (default)
        assert results[2].language is None  # Unchanged (default)
