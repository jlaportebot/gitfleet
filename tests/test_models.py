"""Tests for gitfleet.models."""

from datetime import datetime, timezone

import pytest

from gitfleet.models import (
    BranchInfo,
    CommitInfo,
    HealthGrade,
    RepoHealth,
    RepoInfo,
    SyncStatus,
)

DEFAULT_COMMITS_BEHIND = 5
TEST_SCORE = 85


class TestHealthGrade:
    def test_grade_from_score_a(self):
        assert HealthGrade.from_score(95) == HealthGrade.A
        assert HealthGrade.from_score(90) == HealthGrade.A

    def test_grade_from_score_b(self):
        assert HealthGrade.from_score(85) == HealthGrade.B
        assert HealthGrade.from_score(80) == HealthGrade.B

    def test_grade_from_score_c(self):
        assert HealthGrade.from_score(75) == HealthGrade.C
        assert HealthGrade.from_score(70) == HealthGrade.C

    def test_grade_from_score_d(self):
        assert HealthGrade.from_score(65) == HealthGrade.D
        assert HealthGrade.from_score(60) == HealthGrade.D

    def test_grade_from_score_f(self):
        assert HealthGrade.from_score(55) == HealthGrade.F
        assert HealthGrade.from_score(0) == HealthGrade.F

    def test_grade_boundary_conditions(self):
        assert HealthGrade.from_score(90) == HealthGrade.A
        assert HealthGrade.from_score(89) == HealthGrade.B
        assert HealthGrade.from_score(80) == HealthGrade.B
        assert HealthGrade.from_score(79) == HealthGrade.C
        assert HealthGrade.from_score(70) == HealthGrade.C
        assert HealthGrade.from_score(69) == HealthGrade.D
        assert HealthGrade.from_score(60) == HealthGrade.D
        assert HealthGrade.from_score(59) == HealthGrade.F


class TestRepoInfo:
    def test_repo_info_creation(self):
        repo = RepoInfo(
            path="/home/user/project",
            name="project",
            remote_url="https://github.com/user/project.git",
            default_branch="main",
        )
        assert repo.path == "/home/user/project"
        assert repo.name == "project"
        assert repo.remote_url == "https://github.com/user/project.git"
        assert repo.default_branch == "main"

    def test_repo_info_optional_fields(self):
        repo = RepoInfo(path="/home/user/project", name="project")
        assert repo.remote_url is None
        assert repo.default_branch == "main"


class TestBranchInfo:
    def test_branch_info_creation(self):
        now = datetime.now(timezone.utc)
        branch = BranchInfo(
            name="feature/new-ui",
            is_current=False,
            is_merged=True,
            last_commit_date=now,
            commits_ahead=0,
            commits_behind=DEFAULT_COMMITS_BEHIND,
        )
        assert branch.name == "feature/new-ui"
        assert branch.is_merged is True
        assert branch.commits_behind == DEFAULT_COMMITS_BEHIND

    def test_branch_info_defaults(self):
        branch = BranchInfo(name="main")
        assert branch.is_current is False
        assert branch.is_merged is False
        assert branch.commits_ahead == 0
        assert branch.commits_behind == 0
        assert branch.last_commit_date is None


class TestCommitInfo:
    def test_commit_info_creation(self):
        now = datetime.now(timezone.utc)
        commit = CommitInfo(
            sha="abc123",
            message="Add new feature",
            author="John Doe <john@example.com>",
            date=now,
            is_merge=False,
        )
        assert commit.sha == "abc123"
        assert commit.is_merge is False


class TestSyncStatus:
    def test_sync_status_clean(self):
        status = SyncStatus(
            is_clean=True,
            untracked_files=[],
            modified_files=[],
            staged_files=[],
            deleted_files=[],
        )
        assert status.is_clean is True
        assert status.has_changes is False

    def test_sync_status_dirty(self):
        status = SyncStatus(
            is_clean=False,
            untracked_files=["new_file.py"],
            modified_files=["main.py"],
            staged_files=["config.yaml"],
            deleted_files=[],
        )
        assert status.is_clean is False
        assert status.has_changes is True
        assert "new_file.py" in status.untracked_files
        assert "main.py" in status.modified_files
        assert "config.yaml" in status.staged_files


class TestRepoHealth:
    def test_repo_health_creation(self):
        health = RepoHealth(
            repo_path="/home/user/project",
            overall_score=TEST_SCORE,
            grade=HealthGrade.B,
            checks={},
            timestamp=datetime.now(timezone.utc),
        )
        assert health.overall_score == TEST_SCORE
        assert health.grade == HealthGrade.B

    def test_repo_health_grade_auto_calculation(self):
        health = RepoHealth(
            repo_path="/home/user/project",
            overall_score=92,
            grade=None,
            checks={},
            timestamp=datetime.now(timezone.utc),
        )
        assert health.grade == HealthGrade.A

    def test_repo_health_is_passing(self):
        health_passing = RepoHealth(
            repo_path="/home/user/project",
            overall_score=75,
            grade=HealthGrade.C,
            checks={},
            timestamp=datetime.now(timezone.utc),
        )
        health_failing = RepoHealth(
            repo_path="/home/user/project",
            overall_score=55,
            grade=HealthGrade.F,
            checks={},
            timestamp=datetime.now(timezone.utc),
        )
        assert health_passing.is_passing is True
        assert health_failing.is_passing is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
