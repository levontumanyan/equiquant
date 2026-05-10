# Configuration (Database-Driven)

The "Investment Brain" stores all logic in `market_analysis.db`. You can visualize these rules using the CLI:

- `./analyze.py --db benchmarks`: View master scoring rules (STOCK vs ETF).
- `./analyze.py --db profiles`: View available investment strategies.
- `./analyze.py --db sectors`: View sector-specific valuation overrides.

## Strategic Weight Resolution Flow

When you run an analysis (e.g., `./analyze.py NVDA --profile growth`), the system follows this path:

1. **Identify Rules**: Fetches metrics for the asset type (STOCK or ETF) from the `global_benchmarks` table.
2. **Apply Peer Logic**: Checks `sector_benchmarks` for scoring overrides based on the asset's sector.
3. **Resolve Importance**: Looks up the chosen profile in `profile_weights`. If a match is found, it overrides the baseline weight.
4. **Final Points Calculation**: `Points = Strength (0.0 to 1.0) * Resolved Weight`.
