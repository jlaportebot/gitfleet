"""Tests for gitfleet.cli."""

from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from gitfleet.cli import main
from gitfleet.models import HealthGrade, RepoHealth


class TestCLI:
    def test_cli_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "GitFleet" in result.output

    def test_cli_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    @patch("gitfleet.cli.discover_repos")
    def test_scan_command_no_repos(self, mock_discover, tmp_path):
        mock_discover.return_value = []
        runner = CliRunner()
        result = runner.invoke(main, ["scan", str(tmp_path)])
        assert result.exit_code == 0
        assert "No repositories found" in result.output

    @patch("gitfleet.cli.discover_repos")
    @patch("gitfleet.cli.evaluate_repo_health")
    def test_scan_command_with_repos(self, mock_eval, mock_discover, tmp_path):
        mock_repo = Mock()
        mock_repo.path = str(tmp_path / "repo1")
        mock_repo.name = "repo1"
        mock_discover.return_value = [mock_repo]

        mock_health = RepoHealth(
            repo_path=str(tmp_path / "repo1"),
            overall_score=85,
            grade=HealthGrade.B,
            checks={},
            check_details={},
        )
        mock_eval.return_value = mock_health

        runner = CliRunner()
        result = runner.invoke(main, ["scan", str(tmp_path)])
        assert result.exit_code == 0
        assert "repo1" in result.output
        assert "85" in result.output

    @patch("gitfleet.cli.discover_repos")
    @patch("gitfleet.cli.evaluate_repo_health")
    def test_scan_command_json_output(self, mock_eval, mock_discover, tmp_path):
        mock_repo = Mock()
        mock_repo.path = str(tmp_path / "repo1")
        mock_repo.name = "repo1"
        mock_discover.return_value = [mock_repo]

        mock_health = RepoHealth(
            repo_path=str(tmp_path / "repo1"),
            overall_score=85,
            grade=HealthGrade.B,
            checks={"working_tree": 100},
            check_details={"working_tree": "Clean"},
        )
        mock_eval.return_value = mock_health

        runner = CliRunner()
        result = runner.invoke(main, ["scan", str(tmp_path), "--json"])
        assert result.exit_code == 0
        assert "repo1" in result.output
        assert "85" in result.output

    @patch("gitfleet.cli.evaluate_repo_health")
    def test_health_command(self, mock_eval, tmp_path):
        repo_dir = tmp_path / "repo1"
        repo_dir.mkdir()

        mock_health = RepoHealth(
            repo_path=str(repo_dir),
            overall_score=92,
            grade=HealthGrade.A,
            checks={"working_tree": 100, "essentials": 100},
            check_details={"working_tree": "Clean", "essentials": "All present"},
        )
        mock_eval.return_value = mock_health

        runner = CliRunner()
        result = runner.invoke(main, ["health", str(repo_dir)])
        assert result.exit_code == 0
        assert "repo1" in result.output
        assert "92" in result.output

    @patch("gitfleet.cli.discover_repos")
    def test_list_command(self, mock_discover, tmp_path):
        mock_repo1 = Mock()
        mock_repo1.path = str(tmp_path / "repo1")
        mock_repo1.name = "repo1"
        mock_repo1.remote_url = "https://github.com/user/repo1.git"
        mock_repo1.default_branch = "main"

        mock_repo2 = Mock()
        mock_repo2.path = str(tmp_path / "repo2")
        mock_repo2.name = "repo2"
        mock_repo2.remote_url = None
        mock_repo2.default_branch = "master"

        mock_discover.return_value = [mock_repo1, mock_repo2]

        runner = CliRunner()
        result = runner.invoke(main, ["list", str(tmp_path)])
        assert result.exit_code == 0
        assert "repo1" in result.output
        assert "repo2" in result.output

    @patch("gitfleet.cli.discover_repos")
    @patch("gitfleet.cli.enrich_repos")
    def test_enrich_command_no_repos(self, mock_enrich, mock_discover, tmp_path):
        mock_discover.return_value = []
        runner = CliRunner()
        result = runner.invoke(main, ["enrich", str(tmp_path)])
        assert result.exit_code == 0
        assert "No repositories found" in result.output

    @patch("gitfleet.cli.discover_repos")
    @patch("gitfleet.cli.enrich_repos")
    def test_enrich_command_no_github_repos(self, mock_enrich, mock_discover, tmp_path):
        mock_repo = Mock()
        mock_repo.path = str(tmp_path / "repo1")
        mock_repo.name = "repo1"
        mock_repo.remote_url = "https://gitlab.com/user/repo1.git"  # Non-GitHub
        mock_discover.return_value = [mock_repo]
        mock_enrich.return_value = [mock_repo]

        runner = CliRunner()
        result = runner.invoke(main, ["enrich", str(tmp_path)])
        assert result.exit_code == 0
        assert "No GitHub repositories found to enrich" in result.output

    @patch("gitfleet.cli.discover_repos")
    @patch("gitfleet.cli.enrich_repos")
    def test_enrich_command_with_github_repos(self, mock_enrich, mock_discover, tmp_path):
        mock_repo = Mock()
        mock_repo.path = str(tmp_path / "repo1")
        mock_repo.name = "repo1"
        mock_repo.remote_url = "https://github.com/user/repo1.git"
        mock_repo.default_branch = "main"
        mock_repo.description = "Test description"
        mock_repo.language = "Python"
        mock_repo.stars = 42
        mock_repo.forks = 10
        mock_repo.last_pushed = None
        mock_discover.return_value = [mock_repo]
        mock_enrich.return_value = [mock_repo]

        runner = CliRunner()
        result = runner.invoke(main, ["enrich", str(tmp_path)])
        assert result.exit_code == 0
        assert "repo1" in result.output
        assert "Python" in result.output
        assert "42" in result.output
        assert "10" in result.output
        assert "Test description" in result.output

    @patch("gitfleet.cli.discover_repos")
    @patch("gitfleet.cli.enrich_repos")
    def test_enrich_command_json_output(self, mock_enrich, mock_discover, tmp_path):
        mock_repo = Mock()
        mock_repo.path = str(tmp_path / "repo1")
        mock_repo.name = "repo1"
        mock_repo.remote_url = "https://github.com/user/repo1.git"
        mock_repo.default_branch = "main"
        mock_repo.description = "Test description"
        mock_repo.language = "Python"
        mock_repo.stars = 42
        mock_repo.forks = 10
        mock_repo.last_pushed = None
        mock_discover.return_value = [mock_repo]
        mock_enrich.return_value = [mock_repo]

        runner = CliRunner()
        result = runner.invoke(main, ["enrich", str(tmp_path), "--json"])
        assert result.exit_code == 0
        assert "repo1" in result.output
        assert "Python" in result.output
        assert "42" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
