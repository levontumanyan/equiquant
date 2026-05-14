# ![EquiQuant Logo](./docs/assets/equiquant.png) EquiQuant

Programmatic financial analysis pipeline integrating quantitative benchmarks with extensible scoring methodologies.

> [!IMPORTANT]
> **Zero-Pollution Policy**: This project is strictly isolated via `uv`. It will NEVER touch your global Python site-packages. All dependencies are managed in a local `.venv` folder.

# Quick Start

Analyze a stock:
```bash
./analyze.py AAPL
```

Analyze an index:
```bash
./analyze.py --index QQQ --export csv
```

# Installation

## For Users (Minimal)

If you just want to run the tool:
```bash
make install
```
*Installs core runtime dependencies and shell completions.*

## For Developers (Full)

If you want to contribute, run tests, or modify the tool:
```bash
make setup
```

*Installs all dependencies (including dev tools) and git hooks.*

# CLI Usage

```bash
./analyze.py TICKER [TICKERS...]  # Analyze stocks
./analyze.py -f tickers.txt        # Analyze from file
./analyze.py --index QQQ           # Analyze index components
./analyze.py --db assets           # Inspect database
./analyze.py --history AAPL        # Show historical scores
```

# Features

- **Multi-Source Data**: Scalable architecture supporting multiple data providers.
- **Sector Intelligence**: Automatic sector-specific valuation benchmarks.
- **Zsh/Bash Completions**: Tab-complete tickers, indices, and profiles.
- **Database-Driven**: All scoring rules and profiles are stored in SQLite.

# Frontend Dashboard

EquiQuant includes a modern web dashboard for visualizing analysis results.

To run the dashboard:
1. Start the API server: `make ui-server`
2. Start the frontend: `make ui-dev`

For detailed instructions, see [Frontend Documentation](docs/FRONTEND.md).

# Documentation

For more detailed information, see the `docs/` directory:
- [Frontend Dashboard](docs/FRONTEND.md)
- [Architecture](docs/architecture.md)
- [Configuration & Weights](docs/configuration.md)
- [Scoring Methodologies](docs/scoring.md)
- [Database Schema](docs/DATABASE.md)
- [Data Providers](docs/PROVIDERS.md)

# Development

- `make check`: Run linting, formatting, and tests.
- `make test`: Run `pytest`.
- `make db-shell`: Direct SQLite access.
