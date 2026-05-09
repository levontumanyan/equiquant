# Market-Analysis

Personal stock market analysis tool. A programmatic financial analysis pipeline integrating quantitative benchmarks with extensible scoring methodologies.

# Quick Start

Analyze a stock:
```bash
./analyze.py AAPL
```

Analyze an index:
```bash
./analyze.py --index QQQ --export csv
```

# Features

- **Multi-Source Data**: Scalable architecture supporting multiple data providers (currently Yahoo Finance).
- **Stock & ETF Support**: Automatically detects asset type and applies relevant benchmarks.
- **Sector Intelligence**: Automatically applies sector-specific valuation benchmarks (e.g., Tech vs. Energy).
- **Bulk Analysis**: Analyze dozens of tickers at once from CLI arguments or external files.
- **Reporting**: Generates condensed terminal summary tables and exports full results to CSV or TXT.
- **Investment Profiles**: Tailor scoring weights based on strategy (Balanced, Growth, Dividend).
- **Zsh Completions**: Tab-complete tickers, indices, and profiles directly from your shell.

# CLI Usage

The primary way to interact with the tool is via `./analyze.py`.

```bash
Usage:
  ./analyze.py TICKER [TICKERS...]  Analyze one or more stocks
  ./analyze.py -f tickers.txt        Analyze tickers from a file
  ./analyze.py --index QQQ           Analyze all components of an index
  ./analyze.py --all                 Analyze everything in the database
  ./analyze.py --profile growth      Use a specific investment profile
  ./analyze.py --db assets           Inspect the database (assets, indices, snapshots, etc.)
  ./analyze.py --history AAPL        Show historical scores
```

### Zsh Completions Setup

To enable completions, add the following to your `.zshrc`:

```zsh
fpath=(/path/to/Market-Analysis/scripts/completions $fpath)
autoload -Uz compinit && compinit
```

# Development & Automation

While `./analyze.py` is for running, the `Makefile` handles development tasks:

- `make check`: Run **all** quality checks (linting, formatting, tests, and coverage) via `pre-commit`.
- `make test`: Run the test suite (`pytest`).
- `make format`: Auto-format code.
- `make setup`: Install git pre-commit hooks.
- `make db-shell`: Open direct sqlite3 access.
- `make clean`: Cleanup temporary files.

# Configuration (Database-Driven)

The "Investment Brain" stores all logic in `market_analysis.db`. You can visualize these rules using:
- `./analyze.py --db benchmarks`: View master scoring rules (STOCK vs ETF).
- `./analyze.py --db profiles`: View available investment strategies.
- `./analyze.py --db sectors`: View sector-specific valuation overrides.

## Strategic Weight Resolution Flow

When you run an analysis (e.g., `./analyze.py NVDA --profile growth`), the system follows this path:

1. **Identify Rules**: Fetches metrics for the asset type (STOCK or ETF) from `global_benchmarks`.
2. **Apply Peer Logic**: Checks `sector_benchmarks` for scoring overrides based on the asset's sector.
3. **Resolve Importance**: Looks up the chosen profile in `profile_weights`. If a match is found, it overrides the baseline weight.
4. **Final Points Calculation**: `Points = Strength (0.0 to 1.0) * Resolved Weight`.

# Scoring Methodologies

- **Sigmoid Score**: S-curve for non-linear transitions.
- **Linear Score**: Proportional position between bounds.
- **Bell Curve Score**: Rewards values clustering around a specific target.
- **Threshold Score**: Binary pass/fail mechanism.

# Architecture

- `analyze.py`: CLI entry point.
- `core/`:
	- `orchestrator.py`: Pipeline management.
	- `analysis/`: Index fetching and data preprocessing.
	- `reporting/`: Pluggable CSV/TXT reporting.
	- `providers/`: Data acquisition layer.
	- `ui/`: Terminal display and database inspection.
	- `scorers.py`: Pure mathematical scoring functions.

# TODO

- [x] Zsh completions and reduced `make` usage.
- [ ] Industry average calculations instead of relying on external sector bounds.
- [ ] AI layer for LLM-based qualitative synthesis.
- [x] Analyst Recommendations & Short Interest tracking.
- [x] Bulk reporting and CSV export.
