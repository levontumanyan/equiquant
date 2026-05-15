.PHONY: help lint format test check install setup clean db-shell install-completions install-zsh-completions install-bash-completions

# Default profile
PROFILE ?= balanced
BENCHMARK_VERSION ?= 1.0.0
API_PORT ?= 8000
UI_PORT ?= 8888

help:
	@echo "Market Analysis CLI (Strictly Isolated via uv)"
	@echo ""
	@echo "Usage:"
	@echo "  make run TICKERS=\"AAPL\"        Run analysis safely via uv"
	@echo "  ./analyze.py TICKER              Analyze a stock (auto-isolates)"
	@echo "  ./analyze.py --index QQQ         Analyze all components of an index"
	@echo "  ./analyze.py --db assets         Inspect database assets"
	@echo ""
	@echo "Installation (Never pollutes global Python):"
	@echo "  make install     Install user dependencies (local .venv only)"
	@echo "  make setup       Install all dependencies + completions + git hooks"
	@echo "  make install-completions  Install bash and zsh completions"
	@echo ""
	@echo "Development Tasks (via make):"
	@echo "  make check       Run all quality checks (lint, format, test)"
	@echo "  make test-unit   Run unit tests (fast)"
	@echo "  make test-integration Run integration tests (database)"
	@echo "  make test-acceptance Run acceptance tests (E2E)"
	@echo "  make test        Run all tests"
	@echo "  make db-shell    Open sqlite3 shell"
	@echo "  make clean       Cleanup temp files"

# Quality Checks
lint: ensure-uv
	uv run ruff check .
	uv run ruff format --check .

format: ensure-uv
	uv run ruff check --fix .
	uv run ruff format .

test-unit: ensure-uv
	uv run python -m pytest -q --disable-warnings tests/unit

test-integration: ensure-uv
	uv run python -m pytest -q --disable-warnings tests/integration

test-acceptance: ensure-uv
	uv run python -m pytest -q --disable-warnings tests/acceptance

test: test-unit test-integration test-acceptance

coverage: ensure-uv
	uv run python -m pytest --cov=core --cov-report=term-missing

run: ensure-uv
	uv run ./analyze.py $(TICKERS) $(FLAGS)

check: lint test

# Setup & Installation
ensure-uv:
	@command -v uv >/dev/null 2>&1 || { \
		if [ "$$(uname)" = "Darwin" ] && command -v brew >/dev/null 2>&1; then \
			echo "uv not found. Installing via Homebrew..."; \
			brew install uv; \
		else \
			echo "uv not found. Please install it first: https://docs.astral.sh/uv/getting-started/installation/"; \
			exit 1; \
		fi; \
	}

install: ensure-uv install-completions
	uv sync --no-dev
	@echo "User dependencies and completions installed successfully."

setup: ensure-uv install-completions
	uv sync
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push
	@echo "Development environment, completions, and git hooks installed successfully."

install-completions: install-zsh-completions install-bash-completions

install-zsh-completions:
	@mkdir -p ~/.zsh/completions
	@ln -sf $$(pwd)/scripts/completions/_analyze ~/.zsh/completions/_analyze
	@echo "Symlinked zsh completion (_analyze) to ~/.zsh/completions/_analyze"
	@echo "To activate zsh completions, ensure ~/.zsh/completions is in your fpath and run: autoload -Uz compinit && compinit"

install-bash-completions:
	@mkdir -p ~/.bash_completion.d
	@ln -sf $$(pwd)/scripts/completions/analyze.bash ~/.bash_completion.d/analyze
	@echo "Symlinked bash completion (analyze.bash) to ~/.bash_completion.d/analyze"
	@echo "To activate bash completions, add the following to your ~/.bashrc or ~/.bash_profile:"
	@echo "  if [ -f ~/.bash_completion.d/analyze ]; then . ~/.bash_completion.d/analyze; fi"

# Development Tools
db-shell:
	@sqlite3 market_analysis.db

ui-server: ensure-uv
	@echo "Starting EquiQuant API Server on http://localhost:$(API_PORT)"
	@uv run uvicorn core.api:app --reload --port $(API_PORT)

ui-dev:
	@echo "Starting EquiQuant Frontend on http://localhost:$(UI_PORT)"
	@cd ui && npm install && VITE_API_BASE_URL=http://localhost:$(API_PORT) npm run dev -- --port $(UI_PORT)

ui-stop:
	@echo "Stopping EquiQuant servers..."
	@lsof -ti:$(API_PORT) | xargs kill -9 2>/dev/null || true
	@lsof -ti:$(UI_PORT) | xargs kill -9 2>/dev/null || true
	@echo "Servers stopped."

ui-restart: ui-stop
	@$(MAKE) ui-server & $(MAKE) ui-dev

populate-index:
	@PYTHONPATH=. uv run scripts/populate_index.py $(INDEX)

clean:
	rm -rf .venv
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
