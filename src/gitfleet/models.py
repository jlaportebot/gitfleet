"""Data models for GitFleet."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum


class HealthGrade(IntEnum):
    """Health grade based on score."""

    A = 5
    B = 4
    C = 3
    D = 2
    F = 1

    # Grade thresholds
    GRADE_A_THRESHOLD = 90
    GRADE_B_THRESHOLD = 80
    GRADE_C_THRESHOLD = 70
    GRADE_D_THRESHOLD = 60

    @classmethod
    def from_score(cls, score: int) -> "HealthGrade":
        """Convert numeric score (0-100) to grade."""
        if score >= cls.GRADE_A_THRESHOLD:
            return cls.A
        if score >= cls.GRADE_B_THRESHOLD:
            return cls.B
        if score >= cls.GRADE_C_THRESHOLD:
            return cls.C
        if score >= cls.GRADE_D_THRESHOLD:
            return cls.D
        return cls.F


@dataclass(slots=True)
class RepoInfo:
    """Information about a Git repository."""

    path: str
    name: str
    remote_url: str | None = None
    default_branch: str = "main"
    description: str | None = None
    language: str | None = None
    stars: int = 0
    forks: int = 0
    last_pushed: datetime | None = None


@dataclass(slots=True)
class BranchInfo:
    """Information about a Git branch."""

    name: str
    is_current: bool = False
    is_merged: bool = False
    last_commit_date: datetime | None = None
    commits_ahead: int = 0
    commits_behind: int = 0
    upstream: str | None = None


@dataclass(slots=True)
class CommitInfo:
    """Information about a Git commit."""

    sha: str
    message: str
    author: str
    date: datetime
    is_merge: bool = False
    parents: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SyncStatus:
    """Working tree synchronization status."""

    is_clean: bool
    untracked_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    staged_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Check if there are any uncommitted changes."""
        return bool(
            self.untracked_files or self.modified_files or self.staged_files or self.deleted_files
        )

    @property
    def total_changes(self) -> int:
        """Total number of changed files."""
        return (
            len(self.untracked_files)
            + len(self.modified_files)
            + len(self.staged_files)
            + len(self.deleted_files)
        )


@dataclass(slots=True)
class RepoHealth:
    """Health assessment for a repository."""

    repo_path: str
    overall_score: int
    grade: HealthGrade | None = None
    checks: dict[str, int] = field(default_factory=dict)
    check_details: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.grade is None:
            self.grade = HealthGrade.from_score(self.overall_score)

    @property
    def is_passing(self) -> bool:
        """Check if health grade is C or better (exit code 0)."""
        return self.grade is not None and self.grade >= HealthGrade.C


@dataclass(slots=True)
class FleetSummary:
    """Aggregated summary across all repositories in the fleet."""

    total_repos: int
    healthy_repos: int
    unhealthy_repos: int
    avg_score: float
    repos_with_uncommitted: int
    repos_behind_remote: int
    repos_ahead_remote: int
    stale_branches_total: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def health_percentage(self) -> float:
        """Percentage of healthy repos (grade C or better)."""
        if self.total_repos == 0:
            return 100.0
        return (self.healthy_repos / self.total_repos) * 100
