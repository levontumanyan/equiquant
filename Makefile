.PHONY: help lint format test test-unit test-integration test-acceptance \
	test-container coverage check install setup podman-init pr \
	ui-server ui-dev stop start ui-restart \
	db-shell backup restore clean ensure-uv

# Configuration
PROFILE ?= balanced
BENCHMARK_VERSION ?= 1.0.0
API_PORT ?= 8000
UI_PORT  ?= 8888
BACKUP_DIR ?= $(shell if [ -d "/Users/levontumanyan/Library/CloudStorage/GoogleDrive-ltfibonacci@gmail.com" ]; then echo "/Users/levontumanyan/Library/CloudStorage/GoogleDrive-ltfibonacci@gmail.com/My Drive/equiquant_backups"; else echo "backups"; fi)

# Podman Configuration
PODMAN_CPUS ?= 1
PODMAN_MEMORY ?= 1024
PODMAN_DISK ?= 20

# Package Manager Detection
# Default to Zero-Pollution (uv-provided pnpm).
PM ?= uv run pnpm

help:
	@echo "EquiQuant: High-Performance Asset Valuation"
	@echo ""
	@echo "UI Development:"
	@echo "  make ui-server   Start the API backend (Uvicorn)"
	@echo "  make ui-dev      Start the React frontend (Vite)"
	@echo "  make start    Start both (Background, logs to logs/orchestrator.log)"
	@echo "  make dev      Start both (Foreground, multiplexed logs)"
	@echo "  make stop     Kill running API and UI processes"
	@echo "  make ui-restart  Restart both API and UI servers"
	@echo ""
	@echo "Development & Quality:"
	@echo "  make check       Run linting and all tests"
	@echo "  make test        Run unit, integration, and acceptance tests"
	@echo "  make test-container Run all tests inside a Podman container"
	@echo "  make setup       Initialize development environment"
	@echo "  make podman-init Initialize and start Podman machine"
	@echo "  make pr          Run container tests and create a PR"
	@echo "  make db-shell    Open sqlite3 shell for data inspection"
	@echo "  make backup      Backup market_analysis.db to backups/"
	@echo "  make restore     Restore database (defaults to latest backup, or FILE=<path>)"
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

test-container: podman-init
	@echo "Running tests inside Podman container..."
	podman build -t equiquant-dev -f .devcontainer/Dockerfile .
	podman run --rm \
		--userns=keep-id \
		-v $$(pwd):/workspaces/equiquant \
		-v /workspaces/equiquant/.venv \
		-v /workspaces/equiquant/ui/node_modules \
		-w /workspaces/equiquant \
		equiquant-dev make test

pr: test-container
	@echo "All checks passed in container. Pushing and creating PR..."
	git push -u origin HEAD --no-verify
	gh pr create --fill

coverage: ensure-uv
	uv run python -m pytest --cov=core --cov-report=term-missing

check: lint test

# Setup
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

podman-init:
	@echo "Ensuring Podman machine is initialized and running..."
	@if [ "$$(uname)" = "Darwin" ]; then \
		podman machine list --format "{{.Name}}" | grep -q "podman-machine-default" || \
		podman machine init --cpus $(PODMAN_CPUS) --memory $(PODMAN_MEMORY) --disk-size $(PODMAN_DISK) --rootful=false; \
		podman machine start || true; \
	fi

install: ensure-uv
	@echo "Installing Python dependencies (Zero-Pollution)..."
	uv sync --no-dev
	@echo "Priming OpenBB (Building extensions in main thread)..."
	@uv run python -c "from openbb import obb; _ = obb.equity"
	@echo "Installing UI dependencies (using pnpm)..."
	@cd ui && uv run pnpm install
	@echo ""
	@echo "----------------------------------------------------------------"
	@echo "Installation Complete!"
	@echo "----------------------------------------------------------------"
	@echo "To start the Web Dashboard:   make start"
	@echo "----------------------------------------------------------------"

setup: ensure-uv
	@echo "Setting up development environment..."
	uv sync
	@echo "Priming OpenBB (Building extensions in main thread)..."
	@uv run python -c "from openbb import obb; _ = obb.equity"
	@cd ui && uv run pnpm install
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push
	@echo "Environment and git hooks installed."

# UI & API Management
ui-server: ensure-uv
	@echo "Starting EquiQuant API Server on http://0.0.0.0:$(API_PORT)"
	@uv run uvicorn core.api:app --reload --reload-exclude ".venv" --reload-exclude "tests" --host 0.0.0.0 --port $(API_PORT)

ui-dev: ensure-uv
	@echo "Starting EquiQuant Frontend on http://0.0.0.0:$(UI_PORT)"
	@cd ui && uv run pnpm run dev -- --host 0.0.0.0 --port $(UI_PORT)

stop:
	@echo "Stopping EquiQuant processes..."
	@pkill -f "honcho start" 2>/dev/null || true
	@pkill -f "uvicorn core.api" 2>/dev/null || true
	@pkill -f "vite.*--port $(UI_PORT)" 2>/dev/null || true
	@sleep 0.5

start: ensure-uv stop
	@echo "Starting EquiQuant in background..."
	@mkdir -p logs
	@nohup uv run honcho start > logs/orchestrator.log 2>&1 &
	@echo "Servers are running. Check logs/orchestrator.log for details."
	@echo "API: http://localhost:$(API_PORT)"
	@echo "UI:  http://localhost:$(UI_PORT)"
	@echo "Use 'make stop' to shutdown."

dev: ensure-uv stop
	@echo "Ensuring OpenBB is primed (building extensions)..."
	@uv run python -c "from openbb import obb; _ = obb.equity"
	@uv run honcho start

ui-restart: stop start

# Tools
db-shell:
	@sqlite3 market_analysis.db

backup:
	@mkdir -p "$(BACKUP_DIR)"
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	sqlite3 market_analysis.db ".backup '$(BACKUP_DIR)/market_analysis_$$TIMESTAMP.db'"; \
	cp "$(BACKUP_DIR)/market_analysis_$$TIMESTAMP.db" "$(BACKUP_DIR)/market_analysis_latest.db"; \
	echo "Database backup created: $(BACKUP_DIR)/market_analysis_$$TIMESTAMP.db"; \
	echo "Latest backup link updated: $(BACKUP_DIR)/market_analysis_latest.db"

restore:
	@if [ -z "$(FILE)" ]; then \
		if [ -f "$(BACKUP_DIR)/market_analysis_latest.db" ]; then \
			FILE="$(BACKUP_DIR)/market_analysis_latest.db"; \
		else \
			echo "Usage: make restore FILE=path/to/backup.db"; \
			exit 1; \
		fi; \
	else \
		FILE="$(FILE)"; \
	fi; \
	if [ ! -f "$$FILE" ]; then \
		echo "Error: File '$$FILE' not found."; \
		exit 1; \
	fi; \
	echo "Restoring database from $$FILE..."; \
	sqlite3 market_analysis.db ".restore '$$FILE'"; \
	echo "Database restored successfully."

clean:
	@echo "Cleaning development and cache artifacts..."
	rm -rf .venv ui/node_modules
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
	rm -rf logs/*.log
	podman image prune -f || true
	@echo "Cleanup complete. (Note: market_analysis.db and global OpenBB cache preserved)"

clean-all-data: clean
	@echo "Wiping ALL data including local database and global OpenBB platform cache..."
	rm -f market_analysis.db
	rm -rf ~/.openbb_platform
	@echo "All data wiped."
