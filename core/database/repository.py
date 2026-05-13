import logging
from typing import List, Optional

from core.stats import InstrumentedLock, stats

from .manager import DatabaseManager

logger = logging.getLogger(__name__)


class DatabaseRepository:
	def __init__(self, db_manager: DatabaseManager):
		self.db = db_manager
		self._lock = InstrumentedLock("database_repository", stats)

	def upsert_asset(
		self,
		symbol: str,
		name: Optional[str] = None,
		asset_type: Optional[str] = None,
		sector: Optional[str] = None,
		industry: Optional[str] = None,
	):
		"""Insert or update an asset."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"""
				INSERT INTO assets (symbol, name, asset_type, sector, industry, last_updated)
				VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
				ON CONFLICT(symbol) DO UPDATE SET
					name = COALESCE(excluded.name, assets.name),
					asset_type = COALESCE(excluded.asset_type, assets.asset_type),
					sector = COALESCE(excluded.sector, assets.sector),
					industry = COALESCE(excluded.industry, assets.industry),
					last_updated = CURRENT_TIMESTAMP
			""",
				(symbol, name, asset_type, sector, industry),
			)
			conn.commit()

	def upsert_index(self, symbol: str, name: str, is_etf: bool = False):
		"""Insert or update an index."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"""
				INSERT INTO indices (symbol, name, is_etf, last_updated)
				VALUES (?, ?, ?, CURRENT_TIMESTAMP)
				ON CONFLICT(symbol) DO UPDATE SET
					name = excluded.name,
					is_etf = excluded.is_etf,
					last_updated = CURRENT_TIMESTAMP
			""",
				(symbol, name, is_etf),
			)
			conn.commit()

	def update_index_constituents(self, index_symbol: str, constituents: List[str]):
		"""Replace all constituents for an index."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()

			# First ensure assets exist (minimal entry)
			for symbol in constituents:
				cursor.execute(
					"""
					INSERT OR IGNORE INTO assets (symbol, last_updated)
					VALUES (?, CURRENT_TIMESTAMP)
				""",
					(symbol,),
				)

			# Remove old constituents
			cursor.execute(
				"DELETE FROM index_constituents WHERE index_symbol = ?", (index_symbol,)
			)

			# Add new ones
			for symbol in constituents:
				cursor.execute(
					"""
					INSERT INTO index_constituents (index_symbol, asset_symbol)
					VALUES (?, ?)
				""",
					(index_symbol, symbol),
				)

			conn.commit()

	def get_index_constituents(self, index_symbol: str) -> List[str]:
		"""Get constituents for an index from the DB."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"""
				SELECT asset_symbol FROM index_constituents
				WHERE index_symbol = ?
			""",
				(index_symbol,),
			)
			return [row[0] for row in cursor.fetchall()]

	def get_index(self, symbol: str) -> Optional[dict]:
		"""Get index metadata."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute("SELECT * FROM indices WHERE symbol = ?", (symbol,))
			row = cursor.fetchone()
			return dict(row) if row else None

	def upsert_financial_statement(
		self,
		symbol: str,
		statement_type: str,
		period_type: str,
		fiscal_date: str,
		metric_key: str,
		value: float,
	):
		"""Insert or update a financial statement line item."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"""
				INSERT INTO financial_statements (symbol, statement_type, period_type, fiscal_date, metric_key, value)
				VALUES (?, ?, ?, ?, ?, ?)
				ON CONFLICT(symbol, statement_type, period_type, fiscal_date, metric_key) DO UPDATE SET
					value = excluded.value
			""",
				(symbol, statement_type, period_type, fiscal_date, metric_key, value),
			)
			conn.commit()

	def create_analysis_snapshot(
		self,
		symbol: str,
		profile: str,
		total_score: float,
		results_json: str,
		benchmark_version: str = "1.0.0",
	):
		"""Create a new analysis snapshot."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"""
				INSERT INTO analysis_snapshots (symbol, profile, total_score, results_json, benchmark_version)
				VALUES (?, ?, ?, ?, ?)
			""",
				(symbol, profile, total_score, results_json, benchmark_version),
			)
			conn.commit()

	def get_historical_scores(self, symbol: str, profile: str) -> List[dict]:
		"""Get historical analysis snapshots for a specific symbol and profile."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"""
				SELECT timestamp, total_score, results_json, benchmark_version FROM analysis_snapshots
				WHERE symbol = ? AND profile = ?
				ORDER BY timestamp DESC
			""",
				(symbol, profile),
			)
			return [dict(row) for row in cursor.fetchall()]

	def upsert_sector_benchmark(
		self,
		sector: str,
		metric_key: str,
		benchmark_type: str,
		value_a: float,
		value_b: float,
		version: str = "1.0.0",
	):
		"""Insert or update a sector-specific benchmark."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"""
				INSERT INTO sector_benchmarks (sector, metric_key, benchmark_type, value_a, value_b, last_updated, version)
				VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
				ON CONFLICT(sector, metric_key, version) DO UPDATE SET
					benchmark_type = excluded.benchmark_type,
					value_a = excluded.value_a,
					value_b = excluded.value_b,
					last_updated = CURRENT_TIMESTAMP
			""",
				(sector, metric_key, benchmark_type, value_a, value_b, version),
			)
			conn.commit()

	def get_sector_benchmarks(self, sector: str, version: str = "1.0.0") -> List[dict]:
		"""Get all benchmarks for a specific sector and version."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"SELECT * FROM sector_benchmarks WHERE sector = ? AND version = ?",
				(sector, version),
			)
			return [dict(row) for row in cursor.fetchall()]

	def insert_metric_history(self, symbol: str, metric_key: str, value: float):
		"""Insert a new metric record."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"""
				INSERT INTO metrics_history (symbol, metric_key, value)
				VALUES (?, ?, ?)
			""",
				(symbol, metric_key, value),
			)
			conn.commit()

	def upsert_profile(self, name: str, description: Optional[str] = None):
		"""Insert or update an investor profile."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"""
				INSERT INTO investor_profiles (name, description)
				VALUES (?, ?)
				ON CONFLICT(name) DO UPDATE SET
					description = COALESCE(excluded.description, investor_profiles.description)
			""",
				(name, description),
			)
			conn.commit()

	def upsert_profile_weight(self, profile_name: str, metric_key: str, weight: float):
		"""Insert or update a weight for a profile."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"""
				INSERT INTO profile_weights (profile_name, metric_key, weight)
				VALUES (?, ?, ?)
				ON CONFLICT(profile_name, metric_key) DO UPDATE SET
					weight = excluded.weight
			""",
				(profile_name, metric_key, weight),
			)
			conn.commit()

	def get_profile_weights(self, profile_name: str) -> dict:
		"""Get all weights for a specific profile as a dictionary."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"SELECT metric_key, weight FROM profile_weights WHERE profile_name = ?",
				(profile_name,),
			)
			return {row["metric_key"]: row["weight"] for row in cursor.fetchall()}

	def upsert_global_benchmark(
		self,
		asset_type: str,
		metric_key: str,
		name: str,
		formula_type: str,
		unit: Optional[str],
		is_decimal: bool,
		display_key: Optional[str],
		params_json: str,
		weight: float,
		version: str = "1.0.0",
	):
		"""Insert or update a global benchmark."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"""
				INSERT INTO global_benchmarks (asset_type, metric_key, name, formula_type, unit, is_decimal, display_key, params_json, weight, version)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				ON CONFLICT(asset_type, metric_key, version) DO UPDATE SET
					name = excluded.name,
					formula_type = excluded.formula_type,
					unit = excluded.unit,
					is_decimal = excluded.is_decimal,
					display_key = excluded.display_key,
					params_json = excluded.params_json,
					weight = excluded.weight
			""",
				(
					asset_type,
					metric_key,
					name,
					formula_type,
					unit,
					is_decimal,
					display_key,
					params_json,
					weight,
					version,
				),
			)
			conn.commit()

	def get_global_benchmarks(
		self, asset_type: str, version: str = "1.0.0"
	) -> List[dict]:
		"""Get all benchmarks for a specific asset type and version, with params merged in."""
		import json

		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"SELECT * FROM global_benchmarks WHERE asset_type = ? AND version = ?",
				(asset_type, version),
			)
			rows = cursor.fetchall()

			benchmarks = []
			for row in rows:
				b = dict(row)
				# Rename columns to match what evaluate_metric expects
				b["metric"] = b.pop("metric_key")
				b["type"] = b.pop("formula_type")

				# Parse and merge params
				if b.get("params_json"):
					try:
						params = json.loads(b.pop("params_json"))
						b.update(params)
					except json.JSONDecodeError:
						pass
				benchmarks.append(b)

			return benchmarks

	def save_telemetry(self, duration_s: float, metrics: dict):
		"""Save session telemetry to the database."""
		import json

		total_tickers = metrics.get("total_tickers", 0)
		analyzed_tickers = metrics.get("analyzed_tickers", 0)
		cache_hits = metrics.get("cache_hits", 0)
		api_attempts = metrics.get("api_attempts", 0)
		errors = metrics.get("errors", 0)

		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			# Ensure columns exist if schema was older
			cursor.execute("PRAGMA table_info(session_telemetry)")
			existing_columns = {row["name"] for row in cursor.fetchall()}
			alter_statements = {
				"total_tickers": "ALTER TABLE session_telemetry ADD COLUMN total_tickers INTEGER",
				"analyzed_tickers": "ALTER TABLE session_telemetry ADD COLUMN analyzed_tickers INTEGER",
				"cache_hits": "ALTER TABLE session_telemetry ADD COLUMN cache_hits INTEGER",
				"api_attempts": "ALTER TABLE session_telemetry ADD COLUMN api_attempts INTEGER",
				"errors": "ALTER TABLE session_telemetry ADD COLUMN errors INTEGER",
			}

			for col_name, statement in alter_statements.items():
				if col_name not in existing_columns:
					cursor.execute(statement)

			cursor.execute(
				"""
				INSERT INTO session_telemetry (
					duration_s, total_tickers, analyzed_tickers, 
					cache_hits, api_attempts, errors, metrics_json
				)
				VALUES (?, ?, ?, ?, ?, ?, ?)
				""",
				(
					duration_s,
					total_tickers,
					analyzed_tickers,
					cache_hits,
					api_attempts,
					errors,
					json.dumps(metrics),
				),
			)
			conn.commit()
