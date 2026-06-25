# GitFleet

**Monitor and analyze a fleet of Git repositories — health, activity, and sync status across multiple projects**

```bash
pip install gitfleet
gitfleet scan .
```

[![PyPI](https://img.shields.io/pypi/v/gitfleet.svg)](https://pypi.org/project/gitfleet/)
[![Python](https://img.shields.io/pypi/pyversions/gitfleet.svg)](https://pypi.org/project/gitfleet/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Multi-repository scanning** — Discover all Git repositories under a directory tree
- **Health assessment** — Comprehensive checks for each repository:
  - Working tree status (uncommitted changes)
  - Stale branches (merged but not deleted)
  - Essential files (README, LICENSE, .gitignore, CI config)
  - Dependency freshness (Python, Node.js, Go)
  - Large file detection
  - Commit activity recency
  - Remote sync status
- **Web Dashboard** — Real-time interactive dashboard with sortable tables, summary cards, and detail views
- **Rich terminal output** — Beautiful tables with color-coded grades
- **JSON output** — Machine-readable format for CI/CD integration
- **Configurable thresholds** — Customize scan depth, file size limits, inactivity periods

## Installation

```bash
pip install gitfleet
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add gitfleet
```

## Usage

### Scan a directory for repositories

```bash
# Scan current directory (default)
gitfleet scan

# Scan specific path
gitfleet scan /path/to/projects

# Limit scan depth
gitfleet scan --max-depth 3

# JSON output for CI/CD
gitfleet scan --json
```

### Detailed health report for a single repository

```bash
gitfleet health /path/to/repo
gitfleet health /path/to/repo --json
```

### List all discovered repositories

```bash
gitfleet list
gitfleet list /path/to/projects
```

### Web Dashboard

```bash
# Start the web dashboard (FastAPI + Bootstrap)
gitfleet web

# Or run with uvicorn directly for production
uvicorn gitfleet.web:app --host 0.0.0.0 --port 8000
```

The web dashboard provides:
- **Real-time scanning** — Click "Scan" to analyze repos on-demand
- **Summary cards** — Total repos, passing, failing, average score
- **Sortable table** — Sort by score, grade, or name
- **Health checks** — Expandable view of all checks per repo
- **Detail view** — Click to see full health breakdown
- **Auto-scan on load** — Immediately analyzes repos on page load

## Health Checks

| Check | Weight | Description |
|-------|--------|-------------|
| Working Tree | 15% | Uncommitted, unstaged, or untracked changes |
| Stale Branches | 10% | Local branches already merged into default |
| Essentials | 20% | Missing README, LICENSE, .gitignore, or CI config |
| Dependencies | 15% | Outdated packages in requirements/pyproject.toml, package.json, go.mod |
| Large Files | 10% | Files exceeding size threshold (default 1MB) |
| Activity | 15% | Days since last commit |
| Sync Status | 15% | Working tree cleanliness |

## Grading

| Score | Grade | Status |
|-------|-------|--------|
| 90-100 | A | ✓ Passing |
| 80-89 | B | ✓ Passing |
| 70-79 | C | ✓ Passing |
| 60-69 | D | ✗ Failing |
| 0-59 | F | ✗ Failing |

Exit code is 0 for grades A-C, 1 for D-F (useful for CI gates).

## Example Output

```
GitFleet Scan Results (3 repositories)
┏━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Repository     ┃ Score ┃ Grade ┃ Status         ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━┩
│ project-a      │ 92    │ A     │ ✓ Passing      │
│ project-b      │ 78    │ C     │ ✓ Passing      │
│ project-c      │ 55    │ F     │ ✗ Failing      │
└────────────────┴───────┴───────┴────────────────┘

Summary
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Metric                   ┃ Value   ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ Total Repositories       │ 3       │
│ Passing                  │ 2       │
│ Failing                  │ 1       │
│ Average Score            │ 75.0    │
└──────────────────────────┴─────────┘
```

## Configuration

GitFleet uses sensible defaults but can be customized via command-line options:

- `--max-depth` — Maximum directory depth to scan (default: 5)
- `--json` — Output as JSON instead of table

## API Endpoints (Web Dashboard)

| Endpoint | Description |
|----------|-------------|
| `GET /` | Main dashboard HTML |
| `GET /api/scan` | Scan repos and return health data as JSON |
| `GET /api/enrich` | Enrich repos with GitHub metadata |
| `GET /api/health/{path}` | Detailed health for single repository |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## License

MIT