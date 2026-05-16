# ![EquiQuant Logo](./docs/assets/equiquant.png) EquiQuant

Programmatic financial analysis pipeline integrating quantitative benchmarks with extensible scoring methodologies.

> [!IMPORTANT]
> **Zero-Pollution Policy**: This project is strictly isolated via `uv`. It will NEVER touch your global Python site-packages or Node.js installation. Everything (including Node/npm) is managed in a local `.venv`.

# Quick Start

## 1. Install Everything (Zero-Pollution)
```bash
make install
```
*Sets up Python, Node.js, and all UI dependencies automatically.*

## 2. Launch the Dashboard
```bash
make start
```
*Access the UI at [http://localhost:8888](http://localhost:8888)*

## 3. Analyze via CLI
```bash
./analyze.py AAPL
```

# Installation

## Requirements
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- *That's it.* Node.js and Python are handled automatically by `uv`.

## For Users
```bash
make install
```

## For Developers
```bash
make setup
```
*Installs dev tools (pytest, ruff) and git hooks.*

# CLI Usage

```bash
./analyze.py TICKER [TICKERS...]  # Analyze stocks
./analyze.py -i QQQ               # Analyze index components
./analyze.py --db assets           # Inspect database
./analyze.py --history AAPL        # Show historical scores
```

# Features

- **Multi-Source Data**: Scalable architecture supporting multiple data providers.
- **Sector Intelligence**: Automatic sector-specific valuation benchmarks.
- **Web Dashboard**: Modern React interface for visualizing scoring results.
- **Zero-Pollution**: Isolated runtime for both Python and Node.js.

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
- `make test`: Run unit, integration, and acceptance tests.
- `make db-shell`: Direct SQLite access.
