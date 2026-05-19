# Configuration (Database-Driven)

The "Investment Brain" stores all logic in `market_analysis.db`. You can visualize and manage these rules using the **Admin Dashboard** (`/admin` in the Web UI):

- **Benchmarks Explorer**: View master scoring rules (STOCK vs ETF).
- **Profile Manager**: View and edit investment strategies.
- **Sector Overrides**: View sector-specific valuation parameters.

## Strategic Weight Resolution Flow

When you run an analysis via the Dashboard or API, the system follows this path:

1. **Identify Rules**: Fetches metrics for the asset type (STOCK or ETF) from the `global_benchmarks` table.
2. **Apply Peer Logic**: Checks `sector_benchmarks` for scoring overrides based on the asset's sector.
3. **Resolve Importance**: Looks up the chosen profile in `profile_weights`. If a match is found, it overrides the baseline weight.
4. **Final Points Calculation**: `Points = Strength (0.0 to 1.0) * Resolved Weight`.
