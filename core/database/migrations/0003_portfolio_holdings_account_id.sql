-- Migrate the portfolio_holdings table to add account_id and currency columns,
-- and update the UNIQUE constraint to include them.
-- Safe on fresh databases: the table will be empty so no data is lost.

PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS portfolio_holdings_new;

CREATE TABLE portfolio_holdings_new (
	id           INTEGER PRIMARY KEY AUTOINCREMENT,
	portfolio_id INTEGER NOT NULL,
	symbol       TEXT    NOT NULL,
	account_id   INTEGER,
	currency     TEXT    NOT NULL DEFAULT 'USD',
	total_shares REAL    NOT NULL DEFAULT 0,
	average_cost REAL    NOT NULL DEFAULT 0,
	last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
	UNIQUE(portfolio_id, symbol, account_id, currency),
	FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
	FOREIGN KEY (account_id)   REFERENCES accounts(id)   ON DELETE CASCADE
);

INSERT OR IGNORE INTO portfolio_holdings_new
	(id, portfolio_id, symbol, total_shares, average_cost, last_updated)
SELECT id, portfolio_id, symbol, total_shares, average_cost, last_updated
FROM portfolio_holdings;

DROP TABLE portfolio_holdings;
ALTER TABLE portfolio_holdings_new RENAME TO portfolio_holdings;

PRAGMA foreign_keys = ON;
