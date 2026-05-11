# Project-Specific Instructions

## Code Standards
- **Indentation**: **Tabs** exclusively for all code (except YAML).
- **Quality**: Prioritize **targeted testing** (e.g., `make test-unit` or running a specific test file) during development. Only run `make check` (full suite) as a final verification before a PR or if specifically required. Rely on **pre-commit hooks** to catch linting and basic test failures during the commit process.
- **Functional & Modular**: Write pure functions whenever possible. Keep functions small and focused on a single responsibility. If a function exceeds ~50 lines, evaluate it for refactoring.
- **Documentation**: EVERY function and class must have a descriptive docstring using triple quotes (`"""`). Include a brief description of the purpose, parameters, and return value.
- **Performance**: Code must be highly efficient and optimized for speed. Performance is a first-class citizen; ensure modularity does not introduce unnecessary overhead.
- **Location**: Adopt the Encapsulated Sibling Pattern. Create worktrees as siblings to the main/ directory, contained within the master project folder.

## Architecture Mandates
- **Modularity**: All logic belongs in `core/`. `analyze.py` is for CLI orchestration only.
- **Functional Style**: Prefer pure functions. Every new logic component must be its own function.
- **Scalability**: New data sources inherit `BaseProvider`; new metrics update `mappings.py` and `AssetData`.
- **Lean Config**: Keep `benchmarks/` and `profiles/` focused. Use `sectors.json` for valuation overrides.

## Environment, Branching & Parallelism
- **Tooling**: Use `make` for development tasks (lint, format, test). For running the application, prefer direct CLI usage via `./analyze.py`.
- **Branching Strategy**: **STRICT MANDATE**: Always work in a new branch. NEVER work on `main` unless directly instructed.
	- **Naming**: Use semantic prefixes: `feat/`, `bug/`, `improvement/`, `docs/`, `refactor/`.
	- **Concurrency**: Use `git worktree` for all tasks to ensure parallel LLM sessions do not overwrite each other. Create worktrees in `../<branch-name>`.
- **Standard Workflow**:
	1. Ensure you are on `main` and run `git pull origin main`.
	2. Create a GitHub issue for the task using `gh issue create` if one doesn't already exist for the work you are doing.
	3. Create a new worktree and branch. Use a hyphenated name for the directory to keep the structure flat. `export DIR_NAME=$(echo "<branch-name>" | tr '/' '-')`, `git worktree add ../$DIR_NAME -b <branch-name> main`
	3. `git worktree add ../<branch-name> -b <branch-name> main`
	4. Identify the worktree root as WORKTREE_ROOT. Use this path as the cwd (Current Working Directory) for all tool calls and shell commands to avoid repetitive cd operations.
	5. Prompt to open a vscode window of that worktree `code ../<branch-name>`.
	6. Perform research, implementation, and testing within the worktree.
	7. Send periodic issue updates and a final summary upon completion as comments on the issue.
	8.  Perform a **Mandatory Functional Check** with `./analyze.py`. Use `make check` only for final end-to-end validation before PR.
	9.  If the user is satisfied with the changes(ask), from $WORKTREE_ROOT, push the branch (`git push -u origin HEAD`) and create a PR using explicit flags: `gh pr create --title "..." --body "..."`. Ensure the PR body contains "Closes #<issue_number>" to automate issue closure.
	10. Once the PR is created, **STOP** and ask the user if you should merge it or if they will handle it via the GitHub GUI.
	11. After the branch is merged and the session is closed, remove the worktree and the branch.

## Testing & Validation
- **Requirement**: Minimum **80% coverage** for the `core/` directory.
- **Granularity**: Every new function requires a corresponding unit test.
- **Verification**: Verify scoring changes against curves in `benchmarks.md`.

## Subagent & Data Access
- **Tool Configuration**: When using tools like `read_file`, `grep_search`, or `glob`, agents MUST set `respect_git_ignore: false` for paths involving `reports/` or `logs/`.
- **Fallbacks**: If a high-level tool (like `read_file`) fails due to ignore patterns, use `run_shell_command` with `cat` to ingest the data.
