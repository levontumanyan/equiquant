# Architecture

EquiQuant is designed as a modular pipeline for financial analysis.

- `analyze.py`: The main CLI entry point that orchestrates the entire flow.
- `core/`:
	- `orchestrator.py`: Manages the high-level execution pipeline (fetch -> evaluate -> report).
	- `analysis/`: Contains logic for index constituent fetching and data preprocessing.
	- `reporting/`: Pluggable reporting system supporting multiple formats (CSV, TXT).
	- `providers/`: Data acquisition layer that abstracts various financial APIs.
	- `ui/`: Handles terminal output formatting and interactive database inspection.
	- `scorers.py`: Pure mathematical scoring functions used by the evaluation engine.
	- `database/`: SQLite management and repository layers for persistence.
