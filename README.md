# Market-Analysis

Personal stock market analysis tool. A programmatic financial analysis pipeline integrating quantitative benchmarks with extensible scoring methodologies.

# Quick Start

Run analysis for one or more tickers:
```bash
make run TICKER="AAPL MSFT GOOGL"
```

# Features

- **Multi-Source Data**: Scalable architecture supporting multiple data providers (currently Yahoo Finance).
- **Stock & ETF Support**: Automatically detects asset type and applies relevant benchmarks.
- **Sector Intelligence**: Automatically applies sector-specific valuation benchmarks (e.g., Tech vs. Energy).
- **Bulk Analysis**: Analyze dozens of tickers at once from CLI arguments or external files.
- **Reporting**: Generates condensed terminal summary tables and exports full results to CSV or TXT.
- **Investment Profiles**: Tailor scoring weights based on strategy (Balanced, Growth, Dividend).

# Development & Automation

- `make run TICKER="NVDA"`: Run analysis for a single stock.
- `make run TICKER="AAPL MSFT GOOGL"`: Run bulk analysis for multiple stocks (displays a summary table).
- `make run FILE="tickers.txt"`: Load tickers from a text or CSV file.
- `make run TICKER="AAPL MSFT" EXPORT="report.csv"`: Export bulk analysis results to `reports/report.csv` (Horizontal CSV).
- `make run TICKER="AAPL MSFT" EXPORT="report.txt"`: Export bulk analysis results to `reports/report.txt` (Human-readable text).
- `make run INDEX="SPY"`: Analyze components of an index or ETF.
- `make run PROFILE="growth" TICKER="AAPL"`: Run analysis with a specific investment profile.
- `make check`: Run formatting, linting, tests, and coverage in sequence.
- `make test`: Run the test suite (`pytest`).
- `make coverage`: Run tests and display coverage report.
- `make format`: Automatically fix code formatting and linting issues.
- `make lint`: Check for code style and logical errors.
- `make setup`: Install git pre-commit hooks.

# Configuration (Database-Driven)

The "Investment Brain" stores all logic in `market_analysis.db`. You can visualize these rules using:
- `make db-benchmarks`: View master scoring rules (STOCK vs ETF).
- `make db-profiles`: View available investment strategies.
- `make db-sectors`: View sector-specific valuation overrides.

## Strategic Weight Resolution Flow

When you run an analysis (e.g., `make run TICKER=NVDA PROFILE=growth`), the system follows this exact path to calculate the score:

### 1. Identify Rules (`global_benchmarks` table)
The system fetches all metrics defined for the asset type (STOCK or ETF). Every metric has a **Baseline Weight** (column: `weight`) which acts as the default importance.

### 2. Apply Peer Logic (`sector_benchmarks` table)
If the asset has a sector (e.g., "Technology"), the system checks for scoring overrides. 
- **Engages:** `metric_key`, `value_a`, `value_b`.
- **Note:** This changes *how* a stock is judged (e.g., what P/E is considered "good"), but it does **not** change the weight.

### 3. Resolve Importance (`profile_weights` table)
The system looks up the chosen profile (e.g., "growth").
- **Engages:** `profile_name`, `metric_key`, `weight`.
- **Logic:** For each metric, the code performs a lookup:
  - **Match Found:** The **Profile Weight** completely replaces the baseline.
  - **No Match:** The system falls back to the **Baseline Weight** from `global_benchmarks`.

### 4. Final Points Calculation
For each metric, the final contribution is calculated as:
`Points = Strength (0.0 to 1.0) * Resolved Weight`

The sum of all points is divided by the sum of all resolved weights to produce the final percentage.

# Scoring Methodologies

## Sigmoid Score (`calculate_sigmoid_score`)
Maps a metric to an S-curve, providing a non-linear transition between `best` and `worst`. Diminishing returns on "good" values.

## Linear Score (`calculate_linear_score`)
Calculates a proportional score based on position between two bounds.

## Bell Curve Score (`calculate_bell_score`)
Uses a Gaussian distribution to reward values that cluster around a specific ideal target (e.g., Debt-to-Equity).

## Threshold Score (`calculate_threshold_score`)
A binary pass/fail mechanism (e.g., Dividend Yield > 2%).

# Architecture

The project follows a modular, functional architecture designed for high testability and scalability.

### Project Structure

- `analyze.py`: CLI entry point.
- `core/`: The engine of the application.
	- `orchestrator.py`: Orchestration of the analysis pipeline.
	- `analysis/`: Specialized logic for index fetching and data preprocessing.
	- `reporting/`: Pluggable reporting system (CSV/TXT).
	- `io/`: Input parsers for ticker files.
	- `ui/`: Terminal display and formatting logic.
	- `providers/`: Data acquisition layer with mapping support for multi-source scalability.
	- `schema.py`: Unified data models (`AssetData`).
	- `scorers.py`: Pure mathematical functions for different scoring curves.
	- `evaluation.py`: Core logic for mapping raw data to benchmarked scores.

### How to Extend

- **Add a Data Source**: Inherit from `BaseProvider` in `core/providers/` and implement `get_data`.
- **Add a New Metric**: 
	1. Add the field to `AssetData` in `core/schema.py`.
	2. Update the provider mapping in `core/providers/mappings.py`.
	3. Add the metric definition to `benchmarks/stock.json`.
- **Add a Scoring Methodology**: Add a new function to `core/scorers.py`, register it in the `SCORERS` map.
- **Add a Feature**: Create a new module in `core/` for new domains. Ensure standalone, testable functions.

# TODO

- [x] when market is closed, we should always hit the last price and then always just hit the cache not no reason to keep calling the API.
- [ ] let's start by calculating ourselves industry averages instead of relying on Google for example in order to understand the P/E ratio in the tech industry we can run the numbers ourselves.	
- [ ] Add an AI layer for LLM-based qualitative synthesis and sentiment analysis.
- [ ] Analyst Recommendations: Implementing buy/sell/hold synthesis.
- [ ] Human Language Ticker Search: Allowing "What's the status of Apple?" instead of just AAPL.
- [ ] Human company speech to ticker
- [ ] Advanced Sentiment Analysis: Adding an AI layer for qualitative news synthesis.
- [x] Add analyst recommendations (buy/sell/hold)
- [x] Shares short numbers
- [x] Add tests and automated quality checks.
- [x] Support passing multiple tickers to `analyze.py`.
- [x] Implement continuous linear/sigmoid scoring.
- [x] Support ETF/Index analysis.
- [x] Implement bulk reporting and CSV export.
- [x] Add different sectors for industry comparisons.
