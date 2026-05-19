# Architecture

EquiQuant is designed as a modular pipeline for financial analysis.

- `core/api/`: The main entry point (FastAPI) that orchestrates the entire flow.
- `core/`:
	- `orchestrator.py`: Manages the high-level execution pipeline (fetch -> evaluate).
	- `analysis/`: Contains logic for index constituent fetching and data preprocessing.
	- `reporting/`: Pluggable reporting system supporting multiple formats (CSV, TXT).
	- `providers/`: Data acquisition layer that abstracts various financial APIs.
	- `scorers.py`: Pure mathematical scoring functions used by the evaluation engine.
	- `database/`: SQLite management and repository layers for persistence.
	- `utils/`: Common utilities including display formatters.

# Database Schema

All tables are managed by `DatabaseManager._create_tables()`. The schema has two categories: **static config** (seeded once) and **runtime data** (written during fetch/analysis).

## Static Config Tables

```
┌──────────────────────────┬───────────────────────────────────────────────────┐
│ Table                    │ Purpose                                           │
├──────────────────────────┼───────────────────────────────────────────────────┤
│ global_benchmarks        │ Scoring definitions per metric (sigmoid params,   │
│                          │ weights) for STOCK and ETF asset types            │
│ sector_benchmarks        │ Per-sector overrides for global benchmark params  │
│ investor_profiles        │ Profile names and descriptions                    │
│ profile_metric_settings  │ Per-profile metric weights, ranges, and formulas  │
│ indices                  │ Known index/ETF symbols                           │
│ index_constituents       │ Membership mapping for each index                 │
└──────────────────────────┴───────────────────────────────────────────────────┘
```

## Runtime Data Tables

```
┌──────────────────────────┬───────────────────────────────────────────────────┐
│ Table                    │ Purpose                                           │
├──────────────────────────┼───────────────────────────────────────────────────┤
│ raw_provider_data        │ Latest raw JSON payload per (symbol, provider).   │
│                          │ Source of truth for UI live re-scoring.           │
│                          │ PK: (symbol, provider) — always latest only.      │
│                          │ Populated by orchestrator before yielding batch.  │
│ assets                   │ Asset metadata (name, sector, industry, type)     │
│ financial_statements     │ Historical financial statement line items         │
│ metrics_history          │ Time-series index of individual metric values     │
│ analysis_snapshots       │ Score history per (symbol, profile, version).     │
│                          │ results_json deprecated — use raw_provider_data.  │
│ document_index           │ Paths to downloaded filing documents              │
│ session_telemetry        │ Per-run performance metrics                       │
└──────────────────────────┴───────────────────────────────────────────────────┘
```

## Key Design Decisions

- `raw_provider_data` uses `PRIMARY KEY (symbol, provider)` — upsert semantics, one row per source. The `timestamp` column records last fetch time for UI freshness display.
- `analysis_snapshots.results_json` is intentionally left NULL for new rows. The full payload is in `raw_provider_data`; scores can be recomputed on demand.
- See `docs/caching.md` for the DB-only cache architecture and fetch flow.
