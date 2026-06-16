"""Web dashboard for GitFleet."""

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from gitfleet.github import enrich_repos, extract_owner_repo_from_url
from gitfleet.health import evaluate_repo_health
from gitfleet.models import RepoHealth, RepoInfo
from gitfleet.scanner import discover_repos

app = FastAPI(title="GitFleet Dashboard", version="0.1.0")

# Templates
TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class ScanRequest(BaseModel):
    path: str = "."
    max_depth: int = 5


class ScanResponse(BaseModel):
    repositories: list[RepoHealth]
    summary: dict[str, Any]


def scan_repositories(path: str, max_depth: int) -> list[RepoHealth]:
    """Scan repositories and return health data."""
    repos = discover_repos(Path(path), max_depth=max_depth)
    results = []
    for repo in repos:
        health = evaluate_repo_health(Path(repo.path))
        results.append(health)
    return results


def enrich_repositories(repos: list[RepoInfo]) -> list[RepoInfo]:
    """Enrich repositories with GitHub metadata."""
    return enrich_repos(repos)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Main dashboard page."""
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"title": "GitFleet Dashboard"},
    )


@app.get("/api/scan", response_model=ScanResponse)
async def api_scan(
    path: str = Query(default="."), max_depth: int = Query(default=5)
) -> ScanResponse:
    """Scan repositories and return health data as JSON."""
    results = scan_repositories(path, max_depth)

    passing = sum(1 for r in results if r.is_passing)
    failing = len(results) - passing
    avg_score = sum(r.overall_score for r in results) / len(results) if results else 0

    return ScanResponse(
        repositories=results,
        summary={
            "total": len(results),
            "passing": passing,
            "failing": failing,
            "average_score": round(avg_score, 1),
        },
    )


@app.get("/api/enrich")
async def api_enrich(
    path: str = Query(default="."), max_depth: int = Query(default=5)
) -> list[dict[str, Any]]:
    """Enrich repositories with GitHub metadata."""
    repos = discover_repos(Path(path), max_depth=max_depth)
    enriched = enrich_repositories(repos)

    github_repos = [r for r in enriched if extract_owner_repo_from_url(r.remote_url or "")]

    return [
        {
            "name": r.name,
            "path": r.path,
            "remote_url": r.remote_url,
            "description": r.description,
            "language": r.language,
            "stars": r.stars,
            "forks": r.forks,
            "default_branch": r.default_branch,
            "last_pushed": r.last_pushed.isoformat() if r.last_pushed else None,
        }
        for r in github_repos
    ]


@app.get("/api/health/{repo_path:path}")
async def api_health(repo_path: str) -> RepoHealth:
    """Get detailed health for a single repository."""
    return evaluate_repo_health(Path(repo_path))
