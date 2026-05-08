# Pre-commit Hooks

This project uses the `pre-commit` library to ensure code quality by running linting, formatting, and tests automatically before every commit.

## Installation

The hooks are automatically set up when you run the project setup:

```bash
make setup
```

This will install the `pre-commit` hooks into your local `.git/hooks/` directory.

## What it does

When you run `git commit`, the following checks are performed:

1.  **Ruff Linter**: Automatically checks for Python errors and applies fixes where possible.
2.  **Ruff Formatter**: Ensures code follows the project's formatting standards (using tabs).
3.  **Pytest & Coverage**: Runs the full test suite and displays a coverage report. It requires a minimum coverage (as defined in `make check`) to pass.

The output is set to **verbose**, so you will see the detailed results of the tests and coverage directly in your terminal during the commit process.

## Manual Execution

The preferred way to run checks manually is using the `Makefile` targets, which ensure you are using the correct environment:

### Run all checks (Recommended)
```bash
make check
```

### Run specific checks
```bash
make test    # Runs pytest with coverage
make format  # Runs ruff and ruff-format
```

Alternatively, you can call `pre-commit` directly:

### Run on staged files
```bash
uv run pre-commit run
```

### Run on all files
```bash
uv run pre-commit run --all-files
```

## Skipping Hooks

If you need to bypass the hooks for a specific commit (not recommended), you can use:

```bash
git commit -m "your message" --no-verify
```
