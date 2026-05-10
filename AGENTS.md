# Project-Specific Instructions

## Code Standards
- **Indentation**: **Tabs** exclusively for all code (except YAML).
- **Quality**: Always run `make check` (format, lint, test, coverage) before finishing any task.

## Architecture Mandates
- **Modularity**: All logic belongs in `core/`. `analyze.py` is for CLI orchestration only.
- **Functional Style**: Prefer pure functions. Every new logic component must be its own function.
- **Scalability**: New data sources inherit `BaseProvider`; new metrics update `mappings.py` and `AssetData`.
- **Lean Config**: Keep `benchmarks/` and `profiles/` focused. Use `sectors.json` for valuation overrides.

## Environment, Branching & Parallelism
- **Tooling**: Use `make` for development tasks (lint, format, test). For running the application, prefer direct CLI usage via `./analyze.py` (with `uv run` if necessary) to leverage zsh completions.
- **Branching Strategy**: **STRICT MANDATE**: Always work in a new branch. NEVER work on `main`.
	- **Naming**: Use semantic prefixes: `feat/`, `bug/`, `improvement/`, `docs/`, `refactor/`. (e.g., `feat/api-integration`).
	- **Parallelism**: Use `git worktree` for parallel tasks. Create worktrees in `.worktrees/<branch-name>`.
- After changes are done in the branch, just switch to main and merge the changes locally, then push to remote.
- **Workflow**:
	1. Create a new branch/worktree for the task.
	2. Research and implementation.
	3. Verify with `make check`.
	4. **Mandatory Functional Check**: Run `./analyze.py` with appropriate flags and verify output.
	5. Once approved, merge to `main` locally and push. Do not push feature branches to remote unless instructed directly.

## Testing & Validation
- **Requirement**: Minimum **80% coverage** for the `core/` directory.
- **Granularity**: Every new function requires a corresponding unit test.
- **Verification**: Verify scoring changes against curves in `benchmarks.md`.

## Subagent & Data Access
- **Data Access**: Agents are explicitly authorized to read files in `reports/` and `logs/` even if they are ignored by `.gitignore`.
- **Tool Configuration**: When using tools like `read_file`, `grep_search`, or `glob`, agents MUST set `respect_git_ignore: false` for paths involving `reports/` or `logs/`.
- **Fallbacks**: If a high-level tool (like `read_file`) fails due to ignore patterns, use `run_shell_command` with `cat` to ingest the data.
