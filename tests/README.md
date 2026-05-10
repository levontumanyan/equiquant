# Test Suite

This directory contains the automated tests for the Equiquant project. We use a three-tiered testing strategy to ensure both internal code correctness and external user-facing reliability.

## 1. Test Tiers

### Unit Tests (`tests/unit/`)
*   **Focus**: Internal logic, math, and individual module behavior.
*   **Isolation**: High. External dependencies (APIs, Database, File System) are **mocked**.
*   **Speed**: Extremely fast (milliseconds).
*   **When to run**: Constantly during development.

### Integration Tests (`tests/integration/`)
*   **Focus**: Interactions between modules, primarily the Database and Repository layers.
*   **Isolation**: Moderate. Uses a real (but temporary) SQLite database. Network calls are still usually mocked.
*   **Speed**: Moderate (seconds).
*   **When to run**: Before committing or when changing the database schema.

### Acceptance Tests (`tests/acceptance/`)
*   **Focus**: "User-Side" testing. Verifies that the CLI works as expected from a black-box perspective.
*   **Isolation**: Low. Invokes the real `analyze.py` via `subprocess`.
*   **Verification**: Checks exit codes, console output (stdout/stderr), and file generation (reports).
*   **Speed**: Slower (can take seconds per test).
*   **When to run**: Before merging a feature or releasing.

---

## 2. Infrastructure

*   **`conftest.py`**: Shared test configuration and fixtures. It automatically adds the project root to the Python path.
*   **`Makefile`**: Provides standard entry points for running different test suites.

---

## 3. Running Tests

The primary way to run tests is through the `Makefile`:

| Command | Description |
| :--- | :--- |
| `make test-unit` | Run all unit tests. |
| `make test-integration` | Run all integration tests. |
| `make test-acceptance` | Run all acceptance (E2E) tests. |
| `make test` | Run the full suite (Unit + Integration + Acceptance). |
| `make check` | Run linter, formatter, and all tests. |

### Manual Execution
If you need to run specific tests or pass extra arguments to pytest:
```bash
uv run python -m pytest tests/unit/test_logic.py
```

---

## 4. Best Practices

1.  **Indentation**: All test files MUST use **Tabs** for indentation (project standard).
2.  **Surgical Mocking**: In Unit tests, mock only what is necessary (e.g., `OpenBBProvider.get_data`). Avoid mocking internal helper functions unless they are computationally expensive.
3.  **No Mocking in Acceptance**: Acceptance tests should avoid mocking `core/` functions entirely. They should test the application as the user would.
4.  **Database Cleaning**: Integration and Acceptance tests should always use a clean or temporary database state. Use the fixtures provided in `tests/conftest.py`.
5.  **Coverage**: Aim for at least **80% coverage** in the `core/` directory. Coverage reports are generated automatically via `pytest-cov`.
