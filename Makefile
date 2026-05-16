.PHONY: help lint format test check install setup clean db-shell ui-server ui-dev ui-stop ui-start ui-restart run populate-index

# Configuration
PROFILE ?= balanced
BENCHMARK_VERSION ?= 1.0.0
API_PORT ?= 8000
UI_PORT  ?= 8888

# Package Manager Detection
# Prefers pnpm if available globally, otherwise uses uv-provided npm
PM := $(shell command -v pnpm 2>/dev/null || echo "uv run npm")

help:
	@echo "EquiQuant: High-Performance Asset Valuation"
	@echo ""
	@echo "UI Development:"
	@echo "  make ui-server   Start the API backend (Uvicorn)"
	@echo "  make ui-dev      Start the React frontend (Vite)"
	@echo "  make ui-start    Start both API and UI servers"
	@echo "  make ui-stop     Kill running API and UI processes"
	@echo "  make ui-restart  Restart both API and UI servers"
	@echo ""
	@echo "CLI Usage:"
	@echo "  make run TICKERS=\"AAPL\"        Run analysis safely via uv"
	@echo "  ./analyze.py TICKER              Analyze a stock (auto-isolates)"
	@echo "  make populate-index INDEX=QQQ    Seed assets for an index"
	@echo ""
	@echo "Development & Quality:"
	@echo "  make check       Run linting and all tests"
	@echo "  make test        Run unit, integration, and acceptance tests"
	@echo "  make setup       Initialize development environment"
	@echo "  make db-shell    Open sqlite3 shell for data inspection"
	@echo "  make clean       Cleanup environment and temporary files"

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

check: lint test

# Setup
ensure-uv:
	@command -v uv >/dev/null 2>&1 || { echo "uv not found. Please install it first."; exit 1; }

install: ensure-uv
	@echo "Installing Python dependencies (Zero-Pollution)..."
	uv sync --no-dev
	@echo "Installing UI dependencies (using $(PM))..."
	@cd ui && $(PM) install
	@echo ""
	@echo "----------------------------------------------------------------"
	@echo "Installation Complete!"
	@echo "----------------------------------------------------------------"
	@echo "To start the Web Dashboard:   make ui-start"
	@echo "To analyze via CLI:           ./analyze.py AAPL"
	@echo ""
	@echo "To enable shell completions (Zsh):"
	@echo "  source <(./analyze.py --completion zsh)"
	@echo "----------------------------------------------------------------"

setup: ensure-uv
	@echo "Setting up development environment..."
	uv sync
	@cd ui && $(PM) install
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push
	@echo "Environment and git hooks installed."

# UI & API Management
ui-server: ensure-uv
	@echo "Starting EquiQuant API Server on http://0.0.0.0:$(API_PORT)"
	@uv run uvicorn core.api:app --reload --host 0.0.0.0 --port $(API_PORT)

ui-dev:
	@echo "Starting EquiQuant Frontend on http://0.0.0.0:$(UI_PORT)"
	@cd ui && $(PM) run dev -- --host 0.0.0.0 --port $(UI_PORT)

ui-stop:
	@echo "Stopping EquiQuant processes..."
	@lsof -ti:$(API_PORT) | xargs kill -9 2>/dev/null || true
	@lsof -ti:$(UI_PORT) | xargs kill -9 2>/dev/null || true

ui-start:
	@$(MAKE) ui-server & $(MAKE) ui-dev

ui-restart: ui-stop ui-start

# CLI Tools
run: ensure-uv
	uv run ./analyze.py $(TICKERS) $(FLAGS)

populate-index:
	@PYTHONPATH=. uv run scripts/populate_index.py $(INDEX)

db-shell:
	@sqlite3 market_analysis.db

clean:
	rm -rf .venv ui/node_modules
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
