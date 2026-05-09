.PHONY: help lint format test check install setup clean db-shell install-completions

# Default profile
PROFILE ?= balanced
BENCHMARK_VERSION ?= 1.0.0

help:
	@echo "Market Analysis CLI"
	@echo ""
	@echo "Usage:"
	@echo "  ./analyze.py TICKER              Analyze a stock"
	@echo "  ./analyze.py --index QQQ         Analyze all components of an index"
	@echo "  ./analyze.py --db assets         Inspect database assets"
	@echo ""
	@echo "Installation:"
	@echo "  make install     Install user dependencies (minimal)"
	@echo "  make setup       Install all dependencies + git hooks (development)"
	@echo "  make install-completions  Install zsh completions"
	@echo ""
	@echo "Development Tasks (via make):"
	@echo "  make check       Run all quality checks (lint, format, test)"
	@echo "  make lint        Check code style"
	@echo "  make format      Auto-format code"
	@echo "  make test        Run unit tests"
	@echo "  make db-shell    Open sqlite3 shell"
	@echo "  make clean       Cleanup temp files"

# Quality Checks
lint:
	uv run pre-commit run --all-files ruff
	uv run pre-commit run --all-files ruff-format

format:
	uv run pre-commit run --all-files ruff
	uv run pre-commit run --all-files ruff-format

test:
	uv run pre-commit run --all-files pytest

check:
	uv run pre-commit run --all-files

# Setup & Installation
install:
	uv sync --no-dev
	@echo "User dependencies installed successfully."

setup:
	uv sync
	uv run pre-commit install
	@echo "Development environment and git hooks installed successfully."

install-completions:
	@mkdir -p ~/.zsh/completions
	@ln -sf $$(pwd)/scripts/completions/_analyze ~/.zsh/completions/_analyze
	@echo "Symlinked _analyze to ~/.zsh/completions/_analyze"
	@echo "To activate, restart your shell or run: autoload -Uz compinit && compinit"

# Development Tools
db-shell:
	@sqlite3 market_analysis.db

populate-index:
	@PYTHONPATH=. uv run scripts/populate_index.py $(INDEX)

clean:
	rm -rf .venv
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
