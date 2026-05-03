.PHONY: run lint format test check setup clean

# Run the analysis for one or more tickers
# Usage: make run TICKER="AAPL MSFT" PROFILE="growth" EXPORT="report.csv" BENCHMARK_VERSION="1.0.0"
PROFILE ?= balanced
LOG_LEVEL ?= INFO
BENCHMARK_VERSION ?= 1.0.0
TICKER ?=
FILE ?=
EXPORT ?=
INDEX ?=
VERBOSE ?=

run:
	@LOG_LEVEL=$(LOG_LEVEL) uv run analyze.py $(TICKER) \
		$(if $(FILE),--file $(FILE)) \
		$(if $(EXPORT),--export $(EXPORT)) \
		$(if $(INDEX),--index $(INDEX)) \
		$(if $(VERBOSE),--verbose) \
		--profile $(PROFILE) \
		--benchmark-version $(BENCHMARK_VERSION)

# Run analysis against all stocks in the database
# Usage: make run-all-stocks PROFILE="growth" EXPORT="full_report.csv" BENCHMARK_VERSION="1.0.0"
run-all-stocks:
	@LOG_LEVEL=$(LOG_LEVEL) uv run analyze.py --all \
		$(if $(EXPORT),--export $(EXPORT)) \
		$(if $(VERBOSE),--verbose) \
		--profile $(PROFILE) \
		--benchmark-version $(BENCHMARK_VERSION)

# Show historical scores for one or more tickers
# Usage: make history TICKER=AAPL PROFILE=growth
history:
	@LOG_LEVEL=$(LOG_LEVEL) uv run analyze.py $(TICKER) --history --profile $(PROFILE)

# Run code linting and formatting checks
lint:
	uv run ruff check .
	uv run ruff format --check .

# Automatically fix linting issues and format code
format:
	uv run ruff check --fix .
	uv run ruff format .

# Run tests
test:
	uv run pytest

# Run tests with coverage report
coverage:
	uv run pytest --cov=core --cov-report=term-missing

# Comprehensive check: format, lint, and test
check: format lint test coverage

# Setup git hooks
setup:
	uv run pre-commit install
	@echo "Git hooks installed successfully via pre-commit."

# Database tools
db-shell:
	@sqlite3 market_analysis.db

db-summary:
	@echo "--- Database Summary ---"
	@echo "Assets:      $$(sqlite3 market_analysis.db 'SELECT COUNT(*) FROM assets;')"
	@echo "Indices:     $$(sqlite3 market_analysis.db 'SELECT COUNT(*) FROM indices;')"
	@echo "Snapshots:   $$(sqlite3 market_analysis.db 'SELECT COUNT(*) FROM analysis_snapshots;')"
	@echo "Financials:  $$(sqlite3 market_analysis.db 'SELECT COUNT(*) FROM financial_statements;')"
	@echo "------------------------"

db-assets:
	@PYTHONPATH=. uv run scripts/db_inspect.py assets

db-indices:
	@PYTHONPATH=. uv run scripts/db_inspect.py indices

db-snapshots:
	@PYTHONPATH=. uv run scripts/db_inspect.py snapshots

db-sectors:
	@PYTHONPATH=. uv run scripts/db_inspect.py sectors

db-profiles:
	@PYTHONPATH=. uv run scripts/db_inspect.py profiles

db-benchmarks:
	@PYTHONPATH=. uv run scripts/db_inspect.py benchmarks

db-stock-inventory:
	@PYTHONPATH=. uv run scripts/db_inspect.py inventory

populate-index:
	@PYTHONPATH=. uv run scripts/populate_index.py $(INDEX)

# Remove temporary files and the virtual environment
clean:
	rm -rf .venv
	find . -type d -name "__pycache__" -exec rm -rf {} +
