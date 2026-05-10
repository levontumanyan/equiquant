# Project-Specific Instructions

## Code Standards
- **Indentation**: **Tabs** exclusively for all code (except YAML).
- **Quality**: Prioritize **targeted testing** (e.g., `make test-unit` or running a specific test file) during development. Only run `make check` (full suite) as a final verification before a PR or if specifically required. Rely on **pre-commit hooks** to catch linting and basic test failures during the commit process.

## Architecture Mandates
- **Modularity**: All logic belongs in `core/`. `analyze.py` is for CLI orchestration only.
- **Functional Style**: Prefer pure functions. Every new logic component must be its own function.
- **Scalability**: New data sources inherit `BaseProvider`; new metrics update `mappings.py` and `AssetData`.
- **Lean Config**: Keep `benchmarks/` and `profiles/` focused. Use `sectors.json` for valuation overrides.

## Environment, Branching & Parallelism
- **Tooling**: Use `make` for development tasks (lint, format, test). For running the application, prefer direct CLI usage via `./analyze.py`.
- **Branching Strategy**: **STRICT MANDATE**: Always work in a new branch. NEVER work on `main` unless directly instructed.
	- **Naming**: Use semantic prefixes: `feat/`, `bug/`, `improvement/`, `docs/`, `refactor/`.
	- **Concurrency**: Use `git worktree` for all tasks to ensure parallel LLM sessions do not overwrite each other. Create worktrees in `.worktrees/<branch-name>`.
- **Standard Workflow**:
	1. **Sync**: Ensure you are on `main` and run `git pull origin main`.
	2. **Issue**: Create a GitHub issue for the task using `gh issue create` if one doesn't already exist for the work you are doing.
	3. **Worktree**: Create a new worktree and branch: `git worktree add .worktrees/<branch-name> -b <branch-name> main`.
	4. **Implement**: Perform research, implementation, and testing within the worktree.
	5. Send periodic issue updates and a final summary upon completion as comments on the issue.
	6. **Verify**: Perform a **Mandatory Functional Check** with `./analyze.py`. Use `make check` only for final end-to-end validation before PR.
	7. **PR**: If the user is satisfied with the changes(ask), push the branch and create a PR using `gh pr create`. Ensure the PR body contains "Closes #<issue_number>" to automate issue closure.
	8. **Finalize**: Once the PR is created, **STOP** and ask the user if you should merge it or if they will handle it via the GitHub GUI.
## Testing & Validation
- **Requirement**: Minimum **80% coverage** for the `core/` directory.
- **Granularity**: Every new function requires a corresponding unit test.
- **Verification**: Verify scoring changes against curves in `benchmarks.md`.

## Subagent & Data Access
- **Data Access**: Agents are explicitly authorized to read files in `reports/` and `logs/` even if they are ignored by `.gitignore`.
- **Tool Configuration**: When using tools like `read_file`, `grep_search`, or `glob`, agents MUST set `respect_git_ignore: false` for paths involving `reports/` or `logs/`.
- **Fallbacks**: If a high-level tool (like `read_file`) fails due to ignore patterns, use `run_shell_command` with `cat` to ingest the data.
