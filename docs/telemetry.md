# Telemetry & Monitoring

`EquiQuant` includes a comprehensive telemetry system designed to monitor performance, resource utilization, and data quality across every analysis run. This data is persisted in the local SQLite database for historical analysis and real-time debugging.

---

## 📊 Overview

The telemetry system tracks metrics across several categories:

1.  **Performance & I/O**: Wall-clock duration, network latency per endpoint, and local scoring overhead.
2.  **Efficiency**: Cache hit rates, API usage, and batching ratios.
3.  **Concurrency**: Thread pool utilization, worker latency, and mutex contention.
4.  **Resilience**: Error topology, rate limit encounters, and retry success rates.
5.  **Data Quality**: Coverage density per metric key.

---

## 🏗 Architecture

Telemetry is orchestrated by the `SessionStats` class in `core/stats.py`.

-   **Instrumentation**: Key components (Database, Providers, ThreadPool) are instrumented to record events.
-   **Persistence**: At the end of every run, telemetry is saved to the `session_telemetry` table in `market_analysis.db`.
-   **Visualization**: Diagnostics are displayed in the terminal at the end of every run and can be inspected via the CLI.

---

## 🛠 Usage & Inspection

### Real-Time Diagnostics
Every analysis run concludes with a "Performance & I/O Telemetry" and "Efficiency & Resource Footprint" summary in the terminal.

### Historical Inspection
You can view historical session telemetry using the `--db telemetry` flag:

```bash
./analyze.py --db telemetry
```

This displays a table of recent runs:
-   **Dur**: Total duration.
-   **Tickers**: Requested vs. Analyzed counts.
-   **Cache**: Cache hit rate percentage.
-   **API**: Number of external calls.
-   **Err**: Total error count.

### Advanced SQL Analysis
Since telemetry is stored as a JSON blob alongside key columns, you can perform advanced analysis using SQL:

```sql
-- Find sessions with highest mutex contention
SELECT 
    timestamp, 
    duration_s,
    json_extract(metrics_json, '$.threading.mutex_wait_time_total_s') as contention
FROM session_telemetry 
ORDER BY contention DESC 
LIMIT 5;
```

---

## 📈 Key Metrics Reference

| Metric | Source | Description |
| :--- | :--- | :--- |
| `io_time_s` | Network | Cumulative time spent waiting for HTTP responses. |
| `cache_rate_pct` | Cache | Percentage of requests served from the local DB. |
| `mutex_wait_time` | Locking | Time threads spent waiting for database locks. |
| `data_density` | Quality | Percentage of tickers that had a specific metric available. |
| `peak_workers` | Threads | Maximum number of concurrent worker threads used. |

---

## 🛠 Maintenance

Telemetry records are lightweight, but for long-running deployments, you can prune old records:

```bash
sqlite3 market_analysis.db "DELETE FROM session_telemetry WHERE timestamp < date('now', '-90 days');"
```
