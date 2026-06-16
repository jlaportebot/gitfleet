"""GitFleet CLI - Monitor a fleet of Git repositories."""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from gitfleet import __version__
from gitfleet.github import enrich_repos, extract_owner_repo_from_url
from gitfleet.health import evaluate_repo_health
from gitfleet.models import HealthGrade
from gitfleet.scanner import discover_repos

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="gitfleet")
def main() -> None:
    """GitFleet - Monitor and analyze a fleet of Git repositories."""
    pass


@main.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path), default=".")
@click.option("--max-depth", "-d", default=5, help="Maximum directory depth to scan")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def scan(path: Path, max_depth: int, json_output: bool) -> None:
    """Scan a directory for Git repositories and assess their health."""
    repos = discover_repos(path, max_depth=max_depth)

    if not repos:
        console.print("[yellow]No repositories found[/yellow]")
        return

    results = []
    for repo in repos:
        health = evaluate_repo_health(Path(repo.path))
        results.append(health)

    if json_output:
        output = [
            {
                "name": r.repo_path.split("/")[-1],
                "path": r.repo_path,
                "score": r.overall_score,
                "grade": r.grade.name if r.grade else "—",
                "checks": r.checks,
                "details": r.check_details,
            }
            for r in results
        ]
        console.print(json.dumps(output, indent=2))
        return

    # Display as table
    table = Table(title=f"GitFleet Scan Results ({len(results)} repositories)")
    table.add_column("Repository", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Grade", justify="center")
    table.add_column("Status")

    for health in results:
        name = Path(health.repo_path).name
        grade_color = _grade_color(health.grade)
        status = "✓ Passing" if health.is_passing else "✗ Failing"
        table.add_row(
            name,
            str(health.overall_score),
            f"[{grade_color}]{health.grade.name if health.grade else '—'}[/{grade_color}]",
            status,
        )

    console.print(table)

    # Summary
    passing = sum(1 for r in results if r.is_passing)
    failing = len(results) - passing
    avg_score = sum(r.overall_score for r in results) / len(results)

    summary_table = Table(title="Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", justify="right")
    summary_table.add_row("Total Repositories", str(len(results)))
    summary_table.add_row("Passing", f"[green]{passing}[/green]")
    summary_table.add_row("Failing", f"[red]{failing}[/red]")
    summary_table.add_row("Average Score", f"{avg_score:.1f}")
    console.print(summary_table)


@main.command()
@click.argument("repo_path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def health(repo_path: Path, json_output: bool) -> None:
    """Show detailed health report for a single repository."""
    health = evaluate_repo_health(repo_path)

    if json_output:
        output = {
            "path": health.repo_path,
            "score": health.overall_score,
            "grade": health.grade.name if health.grade else "—",
            "checks": health.checks,
            "details": health.check_details,
        }
        console.print(json.dumps(output, indent=2))
        return

    grade_color = _grade_color(health.grade)
    console.print(f"\n[bold]Repository:[/bold] {repo_path.name}")
    console.print(f"[bold]Path:[/bold] {health.repo_path}")
    console.print(f"[bold]Overall Score:[/bold] {health.overall_score}/100")
    grade_name = health.grade.name if health.grade else "—"
    console.print(f"[bold]Grade:[/bold] [{grade_color}]{grade_name}[/{grade_color}]")
    console.print(f"[bold]Status:[/bold] {'✓ Passing' if health.is_passing else '✗ Failing'}")
    console.print("\n[bold]Checks:[/bold]")
    check_table = Table()
    check_table.add_column("Check", style="cyan")
    check_table.add_column("Score", justify="right")
    check_table.add_column("Details")

    for check_name, score in health.checks.items():
        detail = health.check_details.get(check_name, "")
        check_table.add_row(
            check_name.replace("_", " ").title(),
            str(score),
            detail,
        )

    console.print(check_table)


@main.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path), default=".")
@click.option("--max-depth", "-d", default=5, help="Maximum directory depth to scan")
def list(path: Path, max_depth: int) -> None:
    """List all discovered Git repositories."""
    repos = discover_repos(path, max_depth=max_depth)

    if not repos:
        console.print("[yellow]No repositories found[/yellow]")
        return

    table = Table(title=f"Discovered Repositories ({len(repos)})")
    table.add_column("Name", style="cyan")
    table.add_column("Path")
    table.add_column("Remote URL")
    table.add_column("Default Branch")

    for repo in repos:
        table.add_row(
            repo.name,
            repo.path,
            repo.remote_url or "—",
            repo.default_branch,
        )

    console.print(table)


def _grade_color(grade: HealthGrade | None) -> str:
    """Get color for grade."""
    colors = {
        "A": "green",
        "B": "green",
        "C": "yellow",
        "D": "orange3",
        "F": "red",
    }
    if grade is None:
        return "white"
    return colors.get(grade.name, "white")


if __name__ == "__main__":
    main()


@main.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path), default=".")
@click.option("--max-depth", "-d", default=5, help="Maximum directory depth to scan")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def enrich(path: Path, max_depth: int, json_output: bool) -> None:
    """Enrich discovered repositories with GitHub metadata (stars, forks, description, etc.)."""
    repos = discover_repos(path, max_depth=max_depth)

    if not repos:
        console.print("[yellow]No repositories found[/yellow]")
        return

    console.print(f"[blue]Discovered {len(repos)} repositories, enriching from GitHub...[/blue]")
    enriched = enrich_repos(repos)

    # Filter to only show repos that were successfully enriched (have GitHub remotes)
    github_repos = [r for r in enriched if extract_owner_repo_from_url(r.remote_url or "")]

    if not github_repos:
        console.print("[yellow]No GitHub repositories found to enrich[/yellow]")
        return

    if json_output:
        output = [
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
        console.print(json.dumps(output, indent=2))
        return

    # Display as table
    table = Table(title=f"GitHub Enriched Repositories ({len(github_repos)})")
    table.add_column("Name", style="cyan")
    table.add_column("Language", style="magenta")
    table.add_column("Stars", justify="right", style="yellow")
    table.add_column("Forks", justify="right", style="blue")
    table.add_column("Description")

    for repo in github_repos:
        desc = repo.description or "—"
        MAX_DESC_LENGTH = 60
        if len(desc) > MAX_DESC_LENGTH:
            desc = desc[:MAX_DESC_LENGTH - 3] + "..."
        table.add_row(
            repo.name,
            repo.language or "—",
            str(repo.stars),
            str(repo.forks),
            desc,
        )

    console.print(table)
