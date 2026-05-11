import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DatabaseManager:
	def __init__(self, db_path: str = "market_analysis.db"):
		self.db_path = Path(db_path)
		self.conn: Optional[sqlite3.Connection] = None
		self._lock = threading.Lock()
		self.initialize()

	def initialize(self):
		"""Initialize the database and create tables if they don't exist."""
		with self._lock:
			self.db_path.parent.mkdir(parents=True, exist_ok=True)
			# Use check_same_thread=False to allow cross-thread connection usage.
			# Access MUST be serialized using self._lock.
			self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
			self.conn.row_factory = sqlite3.Row
			self._create_tables()

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

		# Analysis Snapshots table
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

		# Sector Benchmarks table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS sector_benchmarks (
				sector TEXT,
				metric_key TEXT,
				benchmark_type TEXT,
				value_a REAL,
				value_b REAL,
				last_updated DATETIME,
				version TEXT DEFAULT '1.0.0',
				PRIMARY KEY (sector, metric_key, version)
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

		# Profile Weights table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS profile_weights (
				profile_name TEXT,
				metric_key TEXT,
				weight REAL,
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
				version TEXT DEFAULT '1.0.0',
				PRIMARY KEY (asset_type, metric_key, version)
			)
		""")

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
