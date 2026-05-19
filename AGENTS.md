# Project-Specific Instructions

## Code Standards
- **Indentation**: **Tabs** exclusively for all code (except YAML).
- **Quality**: Prioritize **targeted testing** (e.g., `make test-unit` or running a specific test file) during development. Only run `make check` (full suite) as a final verification before a PR or if specifically required. Rely on **pre-commit hooks** to catch linting and basic test failures during the commit process. If precommits aren't running then it's a critical issue and let the user know. The only exception is when you are directly asked to ignore them.
- **Functional & Modular**: Write pure functions whenever possible. Keep functions small and focused on a single responsibility. If a function exceeds ~50 lines, evaluate it for refactoring. Whenever a function needs a significant update, consider creating a new one instead of modifying the existing one to preserve behavioral integrity.
- **Documentation**: EVERY function and class must have a descriptive docstring using triple quotes (`"""`). 
	- **Requirements**: Include a brief description of the purpose, detailed parameter descriptions (type and role), and return value specifications.
	- **Maintenance**: Documentation MUST be updated immediately whenever a function's logic or signature changes.
- **Performance**: Code must be highly efficient and optimized for speed. Performance is a first-class citizen; ensure modularity does not introduce unnecessary overhead.
- **Location**: Adopt the Encapsulated Sibling Pattern. Create worktrees as siblings to the main/ directory, contained within the master project folder.

## Architecture Mandates
- **Modularity**: All logic belongs in `core/`.
- **API Orchestration**: All orchestration flows through `core/api.py`.
- **Functional Style**: Prefer pure functions. Every new logic component must be its own function.
- **Scalability**: New data sources inherit `BaseProvider`; new metrics update `mappings.py` and `AssetData`.
- **Lean Config**: Keep `seeds/` benchmarks and profiles focused.

## UI Commands

**Package manager**: `pnpm` (isolated via `uv`).

| Command | Effect |
|---|---|
| `make start` | Start **both** API backend (Uvicorn) and React frontend (Vite) |
| `make stop` | Kill both API and UI processes |
| `make ui-server` | Start the API backend only |
| `make ui-dev` | Start the React frontend only |
| `make ui-restart` | Stop then start both |

If `node_modules` is missing in the worktree, run `cd ui && pnpm install` first.

## Environment, Branching & Parallelism
- **Tooling**: Use `make` for development tasks (lint, format, test).
- **STRICT MANDATE**: Use the worktree skill for all new tasks.
- **Identify** the worktree root as WORKTREE_ROOT. Use this path as the cwd (Current Working Directory) for all tool calls and shell commands to avoid repetitive cd operations.
- **Perform research**, implementation, and testing within the worktree.
- **Send periodic** issue updates and a final summary upon completion as comments on the issue.
- **Perform UI/API Validation**: Verify changes via the Web Dashboard (`make start`) or API endpoints.
- If the user is satisfied with the changes (ask), from $WORKTREE_ROOT, use the PR target:
  `make pr TITLE="feat: your title (#issue)" BODY="Description. Closes #issue"`
- This target automatically validates the code in the rootless Podman environment, pushes the branch with `--no-verify` (bypassing local hooks as validation is handled by the container), and creates the PR.
- Once the PR is created, **STOP** and ask the user if you should merge it or if they will handle it via the GitHub GUI.
- After the branch is merged and the session is closed, remove the worktree and the branch.

## Testing & Validation

# Testing discipline (token-efficient workflow)

NEVER run the full test suite speculatively. Follow this strict sequence:

```
1. Write/modify code
2. Run ONLY the affected test file:
   uv run python -m pytest tests/unit/test_<module>.py -v
3. If that passes, run the unit suite:
   uv run python -m pytest tests/unit -q --disable-warnings
4. Optional: Run full suite in container for final verification:
   make test-container
5. Commit → pre-commit runs unit suite automatically (no need to re-run it)
6. Push → pre-push runs integration + acceptance + security scans automatically
```

- NEVER run `make check` or the integration suite during development iteration.
- Reserve `make check` only for a final sanity check before opening a PR, if at all.
- If you are making changes to a test, don't then run the whole suite to check if that test passes. Only check that particular test.

# Test authoring rules
- **Requirement**: Minimum **80% coverage** for the `core/` directory.
- **Granularity**: Every new function requires a corresponding unit test in `tests/unit/test_<module>.py`.
- **No flaky tests**: Never use `time.sleep` for thread synchronization — use `threading.Event` or barriers.
- **No empty tests**: Every test must have at least one `assert`. Tests with no assertions are forbidden.
- **No redundant tests**: Before writing a test, check if an equivalent one already exists.
- Always invoke pytest as: `uv run python -m pytest ...`

# Security
- ALL findings from Bandit/Semgrep must be taken seriously. **Blanket ignores in config files are strictly prohibited.**
	- **Priority 1**: Refactor to eliminate the vulnerability.
	- **Priority 2**: Surgical line-level suppression (e.g., `# nosec B311`) ONLY for confirmed false positives. Every suppression MUST include a justification comment.

- **Verification**: Verify scoring changes against curves in `benchmarks.md`.
- When you add any new `uv` package make sure to distinguish between dev level packages or user level. Most things should be in dev to keep the user install as small as possible.

## Subagent & Data Access
- **Debug Tools**: Use `tests/debug_raw_data.py <ticker>` to inspect raw OpenBB responses across multiple endpoints for troubleshooting.
- **Logs**: Server logs → `logs/server.log` (structured JSON, rotating). CLI runs → `logs/run_<timestamp>.log`. Level controlled via `LOG_LEVEL=DEBUG make start` (default: INFO).
- **Tool Configuration**: When using tools like `read_file`, `grep_search`, or `glob`, agents MUST set `respect_git_ignore: false` for paths involving `reports/` or `logs/`.
- **Fallbacks**: If a high-level tool (like `read_file`) fails due to ignore patterns, use `run_shell_command` with `cat` to ingest the data.

# Caching & DB Architecture (as of #118)

There is **no file cache** for provider data. Everything flows through SQLite.

## Two-tier DB cache
```
raw_provider_data(symbol, provider, timestamp, data_json)   ← source of truth
  PK: (symbol, provider) — always latest payload only
  Written by: fetch_openbb_data_bulk returns Dict via IPC → orchestrator writes BEFORE yield
  Read by: get_cached_stock_data(ticker, repo)

analysis_snapshots(symbol, profile, total_score, benchmark_version, timestamp)
  results_json is intentionally NULL — re-score from raw_provider_data instead
```

## TTL / freshness check
`repo.should_use_db_cache(symbol)` queries `raw_provider_data.timestamp`:
- Market open → 15 min TTL
- Market closed → 12 h TTL

## Fetch flow
1. `api.py` splits tickers via `repo.should_use_db_cache()`
2. Missing tickers → `fetch_data(tickers, repo=repo)` → subprocess fetches from OpenBB
3. Subprocess returns `Tuple[bool, float, Dict[str, Dict]]` via pickle IPC (no disk write)
4. Orchestrator writes dict to `raw_provider_data` **before** yielding the batch
5. `_tracked_analyze_asset` reads from DB via `get_cached_stock_data(ticker, repo)`

## DB schema — static config tables
`global_benchmarks`, `sector_benchmarks`, `investor_profiles`, `profile_metric_settings`, `groups`, `group_constituents`

Auto-seeded on every `DatabaseManager` init via `_auto_seed()`. Each table checked independently — seeded only if empty. Seed data in `seeds/*.json`, logic in `core/database/seeder.py`.
