import logging
import sqlite3
from pathlib import Path
from typing import Optional

from core.stats import InstrumentedLock, stats

logger = logging.getLogger(__name__)


class DatabaseManager:
	def __init__(
		self, db_path: str = "market_analysis.db", skip_auto_seed: bool = False
	):
		self.db_path = Path(db_path)
		self.conn: Optional[sqlite3.Connection] = None
		self._lock = InstrumentedLock("database_manager", stats)
		self._skip_auto_seed = skip_auto_seed
		self.initialize()

	def initialize(self):
		"""Initialize the database and create tables if they don't exist."""
		with self._lock:
			self.db_path.parent.mkdir(parents=True, exist_ok=True)
			# Use check_same_thread=False to allow cross-thread connection usage.
			# Access MUST be serialized using self._lock.
			self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
			self.conn.row_factory = sqlite3.Row
			# Enable FK enforcement for the lifetime of this connection so CASCADE
			# deletes on portfolios/holdings/transactions work reliably.
			self.conn.execute("PRAGMA foreign_keys = ON")
			self._create_tables()
			if not self._skip_auto_seed:
				self._auto_seed()

	def _auto_seed(self):
		"""Seed and synchronize configuration tables.

		Benchmarks and Profiles are ALWAYS synchronized on startup to ensure
		code-level scoring improvements are reflected in the database.
		Other tables (Assets, Groups) are only seeded if empty.
		"""
		from core.database.repository import DatabaseRepository
		from core.database.seeder import DatabaseSeeder

		repo = DatabaseRepository(self)
		seeder = DatabaseSeeder(repo)
		cursor = self.conn.cursor()

		cursor.execute("SELECT COUNT(*) FROM assets")
		if cursor.fetchone()[0] == 0:
			logger.info("Seeding assets and indices...")
			seeder.seed_assets()
			seeder.seed_indices()

		# Always sync benchmarks to apply new logic/thresholds
		logger.info("Synchronizing global benchmarks...")
		seeder.seed_benchmarks()

		# Profiles are only seeded if empty to protect user customizations
		cursor.execute("SELECT COUNT(*) FROM investor_profiles")
		if cursor.fetchone()[0] == 0:
			logger.info("Seeding system profiles...")
			seeder.seed_profiles()

		cursor.execute("SELECT COUNT(*) FROM groups")
		if cursor.fetchone()[0] == 0:
			logger.info("Seeding stock groups...")
			seeder.seed_groups()

		cursor.execute("SELECT COUNT(*) FROM app_settings")
		if cursor.fetchone()[0] == 0:
			logger.info("Seeding application settings...")
			seeder.seed_app_settings()

	def _create_tables(self):
		"""Create schema tables."""
		cursor = self.conn.cursor()

		# Assets table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS assets (
				symbol TEXT PRIMARY KEY,
				name TEXT,
				asset_type TEXT,
				sector TEXT,
				industry TEXT,
				exchange TEXT,
				currency TEXT,
				last_updated DATETIME
			)
		""")

		# Indices table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS indices (
				symbol TEXT PRIMARY KEY,
				name TEXT,
				is_etf BOOLEAN,
				last_updated DATETIME
			)
		""")

		# Index Constituents table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS index_constituents (
				index_symbol TEXT,
				asset_symbol TEXT,
				weight REAL,
				PRIMARY KEY (index_symbol, asset_symbol),
				FOREIGN KEY (index_symbol) REFERENCES indices(symbol),
				FOREIGN KEY (asset_symbol) REFERENCES assets(symbol)
			)
		""")

		# Financial Statements table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS financial_statements (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				symbol TEXT,
				statement_type TEXT,
				period_type TEXT,
				fiscal_date DATE,
				metric_key TEXT,
				value REAL,
				FOREIGN KEY (symbol) REFERENCES assets(symbol),
				UNIQUE(symbol, statement_type, period_type, fiscal_date, metric_key)
			)
		""")

		# Analysis Snapshots table — score history only; results_json is deprecated (use raw_provider_data)
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS analysis_snapshots (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				symbol TEXT,
				timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
				profile TEXT,
				total_score REAL,
				results_json TEXT,
				benchmark_version TEXT DEFAULT '1.0.0',
				FOREIGN KEY (symbol) REFERENCES assets(symbol)
			)
		""")

		# Raw Provider Data table — source-of-truth JSON payloads per symbol/provider
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS raw_provider_data (
				symbol TEXT NOT NULL,
				provider TEXT NOT NULL,
				timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
				data_json TEXT NOT NULL,
				PRIMARY KEY (symbol, provider),
				FOREIGN KEY (symbol) REFERENCES assets(symbol)
			)
		""")

		# Document Index table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS document_index (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				symbol TEXT,
				doc_type TEXT,
				fiscal_year INTEGER,
				fiscal_period TEXT,
				file_path TEXT,
				file_hash TEXT,
				download_date DATETIME DEFAULT CURRENT_TIMESTAMP,
				FOREIGN KEY (symbol) REFERENCES assets(symbol)
			)
		""")

		# Metrics History table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS metrics_history (
				symbol TEXT,
				metric_key TEXT,
				value REAL,
				timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
				FOREIGN KEY (symbol) REFERENCES assets(symbol)
			)
		""")

		# Investor Profiles table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS investor_profiles (
				name TEXT PRIMARY KEY,
				description TEXT
			)
		""")

		# Profile Metric Settings table
		# range_min / range_max are NULL when the user has not customised the
		# scoring curve — NULL is the explicit "use benchmark default" sentinel,
		# which avoids ambiguity with legitimate values like (0.0, 100.0).
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS profile_metric_settings (
				profile_name TEXT,
				metric_key TEXT,
				weight REAL DEFAULT 1.0,
				range_min REAL,
				range_max REAL,
				formula TEXT,
				is_penalty BOOLEAN DEFAULT 0,
				PRIMARY KEY (profile_name, metric_key),
				FOREIGN KEY (profile_name) REFERENCES investor_profiles(name)
			)
		""")

		# Global Benchmarks table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS global_benchmarks (
				asset_type TEXT,
				metric_key TEXT,
				name TEXT,
				formula_type TEXT,
				unit TEXT,
				is_decimal BOOLEAN,
				display_key TEXT,
				params_json TEXT,
				weight REAL,
				is_penalty BOOLEAN DEFAULT 0,
				version TEXT DEFAULT '1.0.0',
				PRIMARY KEY (asset_type, metric_key, version)
			)
		""")

		# Groups table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS groups (
				name TEXT PRIMARY KEY,
				description TEXT,
				is_system BOOLEAN DEFAULT 0
			)
		""")

		# Group Constituents table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS group_constituents (
				group_name TEXT,
				symbol TEXT,
				PRIMARY KEY (group_name, symbol),
				FOREIGN KEY (group_name) REFERENCES groups(name) ON DELETE CASCADE,
				FOREIGN KEY (symbol) REFERENCES assets(symbol)
			)
		""")

		# Application Settings table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS app_settings (
				key TEXT PRIMARY KEY,
				value TEXT,
				category TEXT,
				description TEXT,
				is_secret BOOLEAN DEFAULT 0,
				last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
			)
		""")

		# SEC CIK Mapping table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS sec_cik_mapping (
				ticker TEXT PRIMARY KEY,
				cik TEXT NOT NULL,
				title TEXT,
				last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
			)
		""")

		# Session Telemetry table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS session_telemetry (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
				duration_s REAL,
				total_tickers INTEGER,
				analyzed_tickers INTEGER,
				cache_hits INTEGER,
				api_attempts INTEGER,
				errors INTEGER,
				metrics_json TEXT
			)
		""")

		# Portfolios table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS portfolios (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT UNIQUE NOT NULL,
				description TEXT,
				created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
				updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
			)
		""")

		# Portfolio Holdings table — cached derived state, updated on every transaction
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS portfolio_holdings (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				portfolio_id INTEGER NOT NULL,
				symbol TEXT NOT NULL,
				total_shares REAL NOT NULL DEFAULT 0,
				average_cost REAL NOT NULL DEFAULT 0,
				last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
				UNIQUE(portfolio_id, symbol),
				FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
			)
		""")

		# Transactions table — full immutable ledger
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS transactions (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				portfolio_id INTEGER NOT NULL,
				symbol TEXT NOT NULL,
				transaction_type TEXT NOT NULL,
				quantity REAL NOT NULL,
				price_per_share REAL NOT NULL,
				transaction_date TEXT NOT NULL,
				fees REAL DEFAULT 0.0,
				notes TEXT,
				created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
				FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
			)
		""")

		# Migration: add is_secret to app_settings if missing
		cursor.execute("PRAGMA table_info(app_settings)")
		if "is_secret" not in {row[1] for row in cursor.fetchall()}:
			cursor.execute(
				"ALTER TABLE app_settings ADD COLUMN is_secret BOOLEAN DEFAULT 0"
			)

		# Migration: add is_penalty to global_benchmarks if missing
		cursor.execute("PRAGMA table_info(global_benchmarks)")
		if "is_penalty" not in {row[1] for row in cursor.fetchall()}:
			cursor.execute(
				"ALTER TABLE global_benchmarks ADD COLUMN is_penalty BOOLEAN DEFAULT 0"
			)

		# Migration: add is_penalty to profile_metric_settings if missing
		cursor.execute("PRAGMA table_info(profile_metric_settings)")
		if "is_penalty" not in {row[1] for row in cursor.fetchall()}:
			cursor.execute(
				"ALTER TABLE profile_metric_settings ADD COLUMN is_penalty BOOLEAN DEFAULT 0"
			)

		# Migration: drop legacy profile_weights (superseded by profile_metric_settings)
		cursor.execute("DROP TABLE IF EXISTS profile_weights")

		# Migration: remove DEFAULT constraints from range_min/range_max so that
		# NULL means "not customised" rather than 0/100 placeholder values.
		# SQLite cannot ALTER COLUMN so we recreate the table when old defaults exist.
		cursor.execute("PRAGMA table_info(profile_metric_settings)")
		cols = {row[1]: row[4] for row in cursor.fetchall()}  # col_name → default_value
		if cols.get("range_min") == "0.0" or cols.get("range_max") == "100.0":
			cursor.execute("""
				CREATE TABLE IF NOT EXISTS profile_metric_settings_new (
					profile_name TEXT,
					metric_key TEXT,
					weight REAL DEFAULT 1.0,
					range_min REAL,
					range_max REAL,
					formula TEXT,
					PRIMARY KEY (profile_name, metric_key),
					FOREIGN KEY (profile_name) REFERENCES investor_profiles(name)
				)
			""")
			cursor.execute("""
				INSERT OR IGNORE INTO profile_metric_settings_new
				SELECT profile_name, metric_key, weight,
					CASE WHEN range_min = 0.0 AND range_max = 100.0 THEN NULL ELSE range_min END,
					CASE WHEN range_min = 0.0 AND range_max = 100.0 THEN NULL ELSE range_max END,
					formula
				FROM profile_metric_settings
			""")
			cursor.execute("DROP TABLE profile_metric_settings")
			cursor.execute(
				"ALTER TABLE profile_metric_settings_new RENAME TO profile_metric_settings"
			)

		self.conn.commit()

	def get_connection(self) -> sqlite3.Connection:
		"""Return the DB connection. Serialized access should be managed via DatabaseRepository lock."""
		if self.conn is None:
			self.initialize()
		return self.conn

	def close(self):
		"""Close the database connection."""
		with self._lock:
			if self.conn:
				self.conn.close()
				self.conn = None
