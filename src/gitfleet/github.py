"""GitHub API integration for enriching repository metadata."""

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime

from gitfleet.models import RepoInfo


@dataclass(slots=True)
class GitHubRepoInfo:
    """Additional metadata from GitHub API."""

    description: str | None = None
    language: str | None = None
    stars: int = 0
    forks: int = 0
    watchers: int = 0
    open_issues: int = 0
    license: str | None = None
    default_branch: str | None = None
    pushed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    homepage: str | None = None
    topics: list[str] | None = None
    archived: bool = False
    disabled: bool = False
    visibility: str | None = None

    def __post_init__(self) -> None:
        if self.topics is None:
            self.topics = []


def extract_owner_repo_from_url(remote_url: str) -> tuple[str, str] | None:
    """Extract owner and repo name from a GitHub remote URL.

    Handles HTTPS, SSH, and git@github.com: formats.
    """
    if not remote_url:
        return None

    # Remove .git suffix
    url = remote_url.removesuffix(".git")

    # SSH format: git@github.com:owner/repo
    if url.startswith("git@github.com:"):
        path = url.split(":", 1)[1]
    # HTTPS format: https://github.com/owner/repo
    elif "github.com/" in url:
        path = url.split("github.com/", 1)[1]
    else:
        return None

    parts = path.split("/")
    MIN_PARTS = 2
    if len(parts) >= MIN_PARTS:
        return parts[0], parts[1]
    return None


def fetch_github_repo_info(owner: str, repo: str) -> GitHubRepoInfo | None:
    """Fetch repository metadata from GitHub API using gh CLI.

    Requires gh CLI to be authenticated.
    """
    try:
        # Use gh api to fetch repo info
        jq_query = (
            "(.description, .language, .stargazers_count, .forks_count, "
            '.watchers_count, .open_issues_count, .license?.spdx_id // "", '
            ".default_branch, .pushed_at, .created_at, .updated_at, "
            '.homepage // "", .topics // [], .archived, .disabled, .visibility)'
        )
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{owner}/{repo}",
                "--jq",
                jq_query,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            return None

        lines = result.stdout.strip().split("\n")
        MIN_FIELDS = 16
        if len(lines) < MIN_FIELDS:
            return None

        # Parse topics (JSON array)
        topics: list[str] = []
        try:
            topics = json.loads(lines[12]) if lines[12] else []
        except json.JSONDecodeError:
            topics = []

        # Parse datetime fields
        def parse_dt(s: str) -> datetime | None:
            if not s or s == "null":
                return None
            try:
                return datetime.fromisoformat(s.replace("Z", "+00:00"))
            except ValueError:
                return None

        return GitHubRepoInfo(
            description=lines[0] if lines[0] != "null" else None,
            language=lines[1] if lines[1] != "null" else None,
            stars=int(lines[2]) if lines[2].isdigit() else 0,
            forks=int(lines[3]) if lines[3].isdigit() else 0,
            watchers=int(lines[4]) if lines[4].isdigit() else 0,
            open_issues=int(lines[5]) if lines[5].isdigit() else 0,
            license=lines[6] if lines[6] else None,
            default_branch=lines[7] if lines[7] != "null" else None,
            pushed_at=parse_dt(lines[8]),
            created_at=parse_dt(lines[9]),
            updated_at=parse_dt(lines[10]),
            homepage=lines[11] if lines[11] else None,
            topics=topics,
            archived=lines[13].lower() == "true" if lines[13] else False,
            disabled=lines[14].lower() == "true" if lines[14] else False,
            visibility=lines[15] if lines[15] != "null" else None,
        )
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError, IndexError):
        return None


def enrich_repo_info(repo_info: RepoInfo) -> RepoInfo:
    """Enrich a RepoInfo with GitHub metadata if available.

    Returns a new RepoInfo with additional fields populated from GitHub API.
    If enrichment fails, returns the original RepoInfo unchanged.
    """
    if not repo_info.remote_url:
        return repo_info

    owner_repo = extract_owner_repo_from_url(repo_info.remote_url)
    if not owner_repo:
        return repo_info

    owner, repo = owner_repo
    gh_info = fetch_github_repo_info(owner, repo)
    if not gh_info:
        return repo_info

    # Create enriched RepoInfo
    return RepoInfo(
        path=repo_info.path,
        name=repo_info.name,
        remote_url=repo_info.remote_url,
        default_branch=gh_info.default_branch or repo_info.default_branch,
        description=gh_info.description,
        language=gh_info.language,
        stars=gh_info.stars,
        forks=gh_info.forks,
        last_pushed=gh_info.pushed_at,
    )


def enrich_repos(repos: list[RepoInfo]) -> list[RepoInfo]:
    """Enrich a list of repositories with GitHub metadata.

    Processes repositories sequentially to avoid rate limiting.
    """
    return [enrich_repo_info(repo) for repo in repos]
