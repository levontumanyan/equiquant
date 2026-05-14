# Code Scanning & Security Setup

This document outlines the static analysis and security scanning tools integrated into the Equiquant workflow.

## Local Scanning (Pre-commit)

We use `pre-commit` to run fast, local checks before code is committed.

### 1. Bandit (Python SAST)
- **Purpose**: Finds common security issues in Python code (e.g., unsafe imports, hardcoded passwords, insecure crypto).
- **Configuration**: Managed in `pyproject.toml` under `[tool.bandit]`.
- **Status**: **ACTIVE**.
- **Results**: Recent runs passed. We currently ignore `B101` (assert) as it is idiomatic in the project's testing and validation style.

### 2. Semgrep (General SAST)
- **Purpose**: Fast, multi-language static analysis using community rulesets.
- **Configuration**: Uses the `auto` config to detect relevant rules for the codebase.
- **Status**: **ACTIVE** (requires `setuptools` in the hook environment for Python 3.12+).

## Deferred Integrations

### 1. Secret Scanning (Issue #68)
- **Goal**: Detect hardcoded secrets before they reach the repository.
- **Planned Tools**: Gitleaks or detect-secrets.

### 2. CI/CD Workflows (Issue #65)
- **Goal**: Deep analysis on Pull Requests and main branch pushes.
- **Planned Tools**: 
    - **GitHub CodeQL**: Deep semantic analysis.
    - **Trivy**: Dependency and vulnerability scanning.

## How to Run Locally

```bash
uv run pre-commit run --all-files
```
