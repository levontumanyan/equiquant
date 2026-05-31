-- Initial schema: all tables at their current (final) column layout.
-- Uses CREATE TABLE IF NOT EXISTS throughout so this migration is a no-op
-- on any database that already has the tables.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS assets (
	symbol       TEXT PRIMARY KEY,
	name         TEXT,
	asset_type   TEXT,
	sector       TEXT,
	industry     TEXT,
	exchange     TEXT,
	currency     TEXT,
	last_updated DATETIME
);

CREATE TABLE IF NOT EXISTS indices (
	symbol       TEXT PRIMARY KEY,
	name         TEXT,
	is_etf       BOOLEAN,
	last_updated DATETIME
);

CREATE TABLE IF NOT EXISTS index_constituents (
	index_symbol TEXT,
	asset_symbol TEXT,
	weight       REAL,
	PRIMARY KEY (index_symbol, asset_symbol),
	FOREIGN KEY (index_symbol) REFERENCES indices(symbol),
	FOREIGN KEY (asset_symbol) REFERENCES assets(symbol)
);

CREATE TABLE IF NOT EXISTS financial_statements (
	id             INTEGER PRIMARY KEY AUTOINCREMENT,
	symbol         TEXT,
	statement_type TEXT,
	period_type    TEXT,
	fiscal_date    DATE,
	metric_key     TEXT,
	value          REAL,
	FOREIGN KEY (symbol) REFERENCES assets(symbol),
	UNIQUE(symbol, statement_type, period_type, fiscal_date, metric_key)
);

CREATE TABLE IF NOT EXISTS analysis_snapshots (
	id                INTEGER PRIMARY KEY AUTOINCREMENT,
	symbol            TEXT,
	timestamp         DATETIME DEFAULT CURRENT_TIMESTAMP,
	profile           TEXT,
	total_score       REAL,
	results_json      TEXT,
	benchmark_version TEXT DEFAULT '1.0.0',
	FOREIGN KEY (symbol) REFERENCES assets(symbol)
);

CREATE TABLE IF NOT EXISTS raw_provider_data (
	symbol    TEXT     NOT NULL,
	provider  TEXT     NOT NULL,
	timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
	data_json TEXT     NOT NULL,
	PRIMARY KEY (symbol, provider),
	FOREIGN KEY (symbol) REFERENCES assets(symbol)
);

CREATE TABLE IF NOT EXISTS document_index (
	id            INTEGER PRIMARY KEY AUTOINCREMENT,
	symbol        TEXT,
	doc_type      TEXT,
	fiscal_year   INTEGER,
	fiscal_period TEXT,
	file_path     TEXT,
	file_hash     TEXT,
	download_date DATETIME DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY (symbol) REFERENCES assets(symbol)
);

CREATE TABLE IF NOT EXISTS metrics_history (
	symbol     TEXT,
	metric_key TEXT,
	value      REAL,
	timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY (symbol) REFERENCES assets(symbol)
);

CREATE TABLE IF NOT EXISTS investor_profiles (
	name        TEXT PRIMARY KEY,
	description TEXT
);

-- range_min / range_max carry no DEFAULT so that NULL means
-- "use benchmark default" rather than a placeholder value.
CREATE TABLE IF NOT EXISTS profile_metric_settings (
	profile_name TEXT,
	metric_key   TEXT,
	weight       REAL    DEFAULT 1.0,
	range_min    REAL,
	range_max    REAL,
	formula      TEXT,
	is_penalty   BOOLEAN DEFAULT 0,
	PRIMARY KEY (profile_name, metric_key),
	FOREIGN KEY (profile_name) REFERENCES investor_profiles(name)
);

CREATE TABLE IF NOT EXISTS global_benchmarks (
	asset_type   TEXT,
	metric_key   TEXT,
	name         TEXT,
	formula_type TEXT,
	unit         TEXT,
	is_decimal   BOOLEAN,
	display_key  TEXT,
	params_json  TEXT,
	weight       REAL,
	is_penalty   BOOLEAN DEFAULT 0,
	version      TEXT DEFAULT '1.0.0',
	PRIMARY KEY (asset_type, metric_key, version)
);

CREATE TABLE IF NOT EXISTS groups (
	name        TEXT PRIMARY KEY,
	description TEXT,
	is_system   BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS group_constituents (
	group_name TEXT,
	symbol     TEXT,
	PRIMARY KEY (group_name, symbol),
	FOREIGN KEY (group_name) REFERENCES groups(name) ON DELETE CASCADE,
	FOREIGN KEY (symbol)     REFERENCES assets(symbol)
);

CREATE TABLE IF NOT EXISTS app_settings (
	key          TEXT PRIMARY KEY,
	value        TEXT,
	category     TEXT,
	description  TEXT,
	is_secret    BOOLEAN DEFAULT 0,
	last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sec_cik_mapping (
	ticker       TEXT PRIMARY KEY,
	cik          TEXT     NOT NULL,
	title        TEXT,
	last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS session_telemetry (
	id               INTEGER PRIMARY KEY AUTOINCREMENT,
	timestamp        DATETIME DEFAULT CURRENT_TIMESTAMP,
	duration_s       REAL,
	total_tickers    INTEGER,
	analyzed_tickers INTEGER,
	cache_hits       INTEGER,
	api_attempts     INTEGER,
	errors           INTEGER,
	metrics_json     TEXT
);

CREATE TABLE IF NOT EXISTS fx_rates (
	from_currency TEXT     NOT NULL,
	to_currency   TEXT     NOT NULL,
	rate          REAL     NOT NULL,
	updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (from_currency, to_currency)
);

CREATE TABLE IF NOT EXISTS portfolios (
	id          INTEGER PRIMARY KEY AUTOINCREMENT,
	name        TEXT UNIQUE NOT NULL,
	description TEXT,
	created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
	updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS banks (
	id   INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
	id           INTEGER PRIMARY KEY AUTOINCREMENT,
	portfolio_id INTEGER NOT NULL,
	name         TEXT    NOT NULL,
	bank_id      INTEGER NOT NULL,
	UNIQUE(portfolio_id, name, bank_id),
	FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
	FOREIGN KEY (bank_id)      REFERENCES banks(id)      ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transactions (
	id                INTEGER PRIMARY KEY AUTOINCREMENT,
	portfolio_id      INTEGER NOT NULL,
	account_id        INTEGER,
	symbol            TEXT    NOT NULL,
	transaction_type  TEXT    NOT NULL,
	quantity          REAL    NOT NULL,
	price_per_share   REAL    NOT NULL,
	transaction_date  TEXT    NOT NULL,
	fees              REAL    DEFAULT 0.0,
	currency          TEXT    NOT NULL DEFAULT 'USD',
	total_amount      REAL,
	dividend_amount   REAL,
	total_cost_cad    REAL,
	notes             TEXT,
	created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
	FOREIGN KEY (account_id)   REFERENCES accounts(id)   ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS portfolio_holdings (
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
