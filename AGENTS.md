# Project-Specific Instructions

## Code Standards
- **Indentation**: **Tabs** exclusively for all code (except YAML).
- **Quality**: Prioritize **targeted testing** (e.g., `make test-unit` or running a specific test file) during development. Only run `make check` (full suite) as a final verification before a PR or if specifically required. Rely on **pre-commit hooks** to catch linting and basic test failures during the commit process.
- **Functional & Modular**: Write pure functions whenever possible. Keep functions small and focused on a single responsibility. If a function exceeds ~50 lines, evaluate it for refactoring. Whenever a function needs a significant update, consider creating a new one instead of modifying the existing one to preserve behavioral integrity.
- **Documentation**: EVERY function and class must have a descriptive docstring using triple quotes (`"""`). 
	- **Requirements**: Include a brief description of the purpose, detailed parameter descriptions (type and role), and return value specifications.
	- **Maintenance**: Documentation MUST be updated immediately whenever a function's logic or signature changes.
- **Performance**: Code must be highly efficient and optimized for speed. Performance is a first-class citizen; ensure modularity does not introduce unnecessary overhead.
- **Location**: Adopt the Encapsulated Sibling Pattern. Create worktrees as siblings to the main/ directory, contained within the master project folder.

## Architecture Mandates
- **Modularity**: All logic belongs in `core/`. `analyze.py` is for CLI orchestration only.
- **Functional Style**: Prefer pure functions. Every new logic component must be its own function.
- **Scalability**: New data sources inherit `BaseProvider`; new metrics update `mappings.py` and `AssetData`.
- **Lean Config**: Keep `benchmarks/` and `profiles/` focused. Use `sectors.json` for valuation overrides.

## Environment, Branching & Parallelism
- **Tooling**: Use `make` for development tasks (lint, format, test). For running the application, prefer direct CLI usage via `./analyze.py`.
- **STRICT MANDATE**: Use the worktree skill for all new tasks.
- **Identify** the worktree root as WORKTREE_ROOT. Use this path as the cwd (Current Working Directory) for all tool calls and shell commands to avoid repetitive cd operations.
- **Perform research**, implementation, and testing within the worktree.
- **Send periodic** issue updates and a final summary upon completion as comments on the issue.
- Perform a **Mandatory Functional Check** with `./analyze.py`. Use `make check` only for final end-to-end validation before PR.- If the user is satisfied with the changes(ask), from $WORKTREE_ROOT, push the branch (`git push -u origin HEAD`) and create a PR using explicit flags: `gh pr create --title "..." --body "..."`. Ensure the PR body contains "Closes #<issue_number>" to automate issue closure.
- Once the PR is created, **STOP** and ask the user if you should merge it or if they will handle it via the GitHub GUI.
- After the branch is merged and the session is closed, remove the worktree and the branch.

## Testing & Validation
- **Requirement**: Minimum **80% coverage** for the `core/` directory.
- **Granularity**: Every new function requires a corresponding unit test.
- **Security Integrity**: ALL findings from security scanners (Bandit, Semgrep, etc.) must be taken seriously. **Blanket ignores in configuration files are strictly prohibited.**
	- **Priority 1**: Refactor code to eliminate the vulnerability (e.g., add timeouts to requests, avoid `os.system`).
	- **Priority 2**: Use surgical, line-level suppressions (e.g., `# nosec B311`) ONLY when the finding is a confirmed false positive or the risk is provably non-existent (e.g., using `random` for network jitter).
	- **Requirement**: Every suppression MUST include a brief comment justifying why it is safe.
- When you try to test use always: `uv run python -m pytest ...`
- **Verification**: Verify scoring changes against curves in `benchmarks.md`.
- When you add any new `uv` package make sure to distinguish between dev level packages or user level. Most things should be in dev to keep the user install as small as possible.
- **UI Testing**: Use **Playwright** for all UI layout and regression testing to verify that components render correctly within their expected container boundaries. Ensure layout tests are included for new UI features.

## Subagent & Data Access
- **Debug Tools**: Use `tests/debug_raw_data.py <ticker>` to inspect raw OpenBB responses across multiple endpoints for troubleshooting.
- **Tool Configuration**: When using tools like `read_file`, `grep_search`, or `glob`, agents MUST set `respect_git_ignore: false` for paths involving `reports/` or `logs/`.
- **Fallbacks**: If a high-level tool (like `read_file`) fails due to ignore patterns, use `run_shell_command` with `cat` to ingest the data.
