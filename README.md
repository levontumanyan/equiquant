# EquiQuant

Programmatic financial analysis pipeline integrating quantitative benchmarks with extensible scoring methodologies.

## Quick Start

Analyze a stock:
```bash
./analyze.py AAPL
```

Analyze an index:
```bash
./analyze.py --index QQQ --export csv
```

## Installation

The project uses `uv` for dependency management.

### 1. Install `uv`
Follow instructions at [astral.sh/uv](https://astral.sh/uv).

### 2. Setup
```bash
make setup
```
This installs dependencies, shell completions, and git hooks. Use `make install` for a minimal runtime-only installation.

## CLI Usage

```bash
./analyze.py TICKER [TICKERS...]  # Analyze stocks
./analyze.py -f tickers.txt        # Analyze from file
./analyze.py --index QQQ           # Analyze index components
./analyze.py --db assets           # Inspect database
./analyze.py --history AAPL        # Show historical scores
```

## Features

- **Multi-Source Data**: Scalable architecture supporting multiple data providers.
- **Sector Intelligence**: Automatic sector-specific valuation benchmarks.
- **Zsh/Bash Completions**: Tab-complete tickers, indices, and profiles.
- **Database-Driven**: All scoring rules and profiles are stored in SQLite.

## Documentation

For more detailed information, see the `docs/` directory:
- [Architecture](docs/architecture.md)
- [Configuration & Weights](docs/configuration.md)
- [Scoring Methodologies](docs/scoring.md)
- [Database Schema](docs/DATABASE.md)
- [Data Providers](docs/PROVIDERS.md)

## Development

- `make check`: Run linting, formatting, and tests.
- `make test`: Run `pytest`.
- `make db-shell`: Direct SQLite access.
