.PHONY: help lint format test check install setup clean db-shell install-completions install-zsh-completions install-bash-completions

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
	@echo "  make setup       Install all dependencies + completions + git hooks"
	@echo "  make install-completions  Install bash and zsh completions"
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

install: ensure-uv
	uv sync --no-dev
	@echo "User dependencies installed successfully."

setup: ensure-uv install-completions
	uv sync
	uv run pre-commit install
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

populate-index:
	@PYTHONPATH=. uv run scripts/populate_index.py $(INDEX)

clean:
	rm -rf .venv
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
