# ETF Holdings Scraping Architecture

## Overview
The ETF Holdings Scraper provides a robust mechanism to retrieve 100% of an ETF's constituents, overcoming the 10-ticker limit inherent in standard `yfinance` metadata. It uses a provider-specific approach, targeting official fund manager data sources.

## Architecture
The system is located in `core/analysis/etf/` and follows a factory pattern:

1.  **`base.py`**: Defines the `ETFHoldingsScraper` abstract interface.
2.  **`factory.py`**: Maps `fundFamily` names (from `yfinance` info) to specific scraper implementations.
3.  **`ssga.py`**: Implementation for State Street Global Advisors (SPDR) ETFs.
    *   Targets direct download URLs (XLSX and CSV fallbacks).
    *   Features **Dynamic Header Parsing** to find the ticker column regardless of metadata rows.

## Integration
The scraper is integrated into `core/analysis/indices.py` via `get_index_components()`.

## Caching & Performance
To prevent redundant scraping and respect provider bandwidth, a **7-day time-to-live (TTL)** is enforced:
1.  **Freshness Check**: When an ETF analysis is requested, the database is checked for existing membership data.
2.  **TTL Enforcement**:
    *   If the data was updated **less than 7 days ago**, it is returned immediately from the DB.
    *   If the data is **older than 7 days** or missing, a fresh scrape is triggered.
3.  **Automatic Persistence**: Every fresh scrape automatically updates the `indices` metadata and `index_constituents` table, resetting the 7-day timer.

## Usage
To analyze an ETF and all its holdings, use the `--index` (or `-i`) flag:
```bash
make run INDEX=XME
```

## Adding New Providers
To support a new fund family (e.g., Vanguard, BlackRock/iShares):
1.  Create a new scraper class in `core/analysis/etf/` inheriting from `ETFHoldingsScraper`.
2.  Register the new scraper in `core/analysis/etf/factory.py` using a keyword match from the provider's official `fundFamily` name.
3.  Add corresponding unit tests in `tests/test_etf_scrapers.py`.

## Supported Providers
| Provider | Keywords | Data Source |
| :--- | :--- | :--- |
| **State Street (SSGA)** | "state street", "spdr" | Official ssga.com direct XLSX/CSV |
