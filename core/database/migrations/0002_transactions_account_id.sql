-- Migrate the transactions table to add account_id, currency, total_amount,
-- dividend_amount, and total_cost_cad columns.
-- Safe on fresh databases: the table will be empty so no data is lost.

PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS transactions_new;

CREATE TABLE transactions_new (
	id               INTEGER PRIMARY KEY AUTOINCREMENT,
	portfolio_id     INTEGER NOT NULL,
	account_id       INTEGER,
	symbol           TEXT    NOT NULL,
	transaction_type TEXT    NOT NULL,
	quantity         REAL    NOT NULL,
	price_per_share  REAL    NOT NULL,
	transaction_date TEXT    NOT NULL,
	fees             REAL    DEFAULT 0.0,
	currency         TEXT    NOT NULL DEFAULT 'USD',
	total_amount     REAL,
	dividend_amount  REAL,
	total_cost_cad   REAL,
	notes            TEXT,
	created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
	FOREIGN KEY (account_id)   REFERENCES accounts(id)   ON DELETE SET NULL
);

INSERT OR IGNORE INTO transactions_new
	(id, portfolio_id, symbol, transaction_type, quantity, price_per_share,
	 transaction_date, fees, notes, created_at, total_amount)
SELECT
	id, portfolio_id, symbol, transaction_type, quantity, price_per_share,
	transaction_date, fees, notes, created_at, quantity * price_per_share
FROM transactions;

DROP TABLE transactions;
ALTER TABLE transactions_new RENAME TO transactions;

PRAGMA foreign_keys = ON;
