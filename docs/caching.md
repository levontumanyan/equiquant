# Caching Architecture

EquiQuant uses a two-tier cache: a **file cache** for fast TTL-based fetch gating, and a **database cache** (`raw_provider_data`) as a persistent source of truth for re-scoring.

# File Cache (Tier 1 — fetch gating)

Location: `cache/yfinance/<SYMBOL>.json`
Managed by: `core/openbb_client.py`

The file cache controls whether a live API call is made. TTL is market-aware:

```
┌─────────────────────┬──────────────────────────────────────────────┐
│ Market state        │ Cache TTL                                    │
├─────────────────────┼──────────────────────────────────────────────┤
│ Open (9:30–16:00 ET)│ 15 minutes — refresh frequently              │
│ Closed              │ 12 hours — data doesn't change overnight     │
└─────────────────────┴──────────────────────────────────────────────┘
```

When a ticker's file is within TTL, the API call is skipped entirely. When stale or absent, `fetch_openbb_data_bulk` fetches from OpenBB/yfinance and writes a new JSON file.

**This is the only layer that makes API decisions.** The DB cache plays no role in fetch gating.

# DB Cache (Tier 2 — raw_provider_data)

Table: `raw_provider_data(symbol, provider, timestamp, data_json)`
Primary key: `(symbol, provider)` — always stores the **latest** payload only.

After every successful fetch batch, `_persist_batch_to_db` reads the fresh file cache and upserts into `raw_provider_data`. This happens in the main process (not the subprocess worker) to avoid SQLite cross-process issues.

The `timestamp` column records exactly when the payload was last written to the DB, so the UI can show data freshness without hitting the filesystem.

```
┌────────────────────────────────────────────────────────────────────┐
│ Purpose                                                            │
├────────────────────────────────────────────────────────────────────┤
│ • Source of truth for live UI re-scoring (no API hit needed)       │
│ • Enables applying different profiles/benchmarks on cached data    │
│ • Decouples the UI from the filesystem (no file path access)       │
└────────────────────────────────────────────────────────────────────┘
```

# Flow summary

```
API (core/api/init.py)
      │
      ├─ repo.should_use_db_cache(ticker)?  ──Yes──► data already in raw_provider_data
      │                                                        │
      │                                                        ▼
      │                                            run_bulk_analysis (reads from DB)
      │
      └─ No ──► fetch_data(missing, repo=repo)
                    │
                    └─► subprocess: fetch_openbb_data_bulk ──► returns Dict via IPC
                                                                        │
                                                          main process: upsert raw_provider_data
                                                                        │ (before yield)
                                                                        ▼
                                                            run_bulk_analysis (reads from DB)
                                                                        │
                                                                        ▼
                                                             analysis_snapshots (score history)
                                                             metrics_history (per-metric series)
```

# Timezone & machine agnosticism

- All internal time calculations use **UTC**.
- Market hours hardcoded to NYSE/NASDAQ: 9:30 AM – 4:00 PM Eastern Time.
- DST handled automatically via Python `zoneinfo` (`America/New_York`).
