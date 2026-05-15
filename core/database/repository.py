import logging
from typing import Any, List, Optional

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

	def upsert_group(
		self, name: str, description: Optional[str] = None, is_system: bool = False
	):
		"""Insert or update a group. Raises ValueError if the name belongs to a system group."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute("SELECT is_system FROM groups WHERE name = ?", (name,))
			row = cursor.fetchone()
			if row and row["is_system"]:
				raise ValueError(f"Cannot modify system group '{name}'")
			cursor.execute(
				"""
				INSERT INTO groups (name, description, is_system)
				VALUES (?, ?, ?)
				ON CONFLICT(name) DO UPDATE SET
					description = COALESCE(excluded.description, groups.description)
			""",
				(name, description, is_system),
			)
			conn.commit()

	def update_group_constituents(self, group_name: str, symbols: List[str]):
		"""Replace all constituents for a group."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()

			# Ensure assets exist
			for symbol in symbols:
				cursor.execute(
					"INSERT OR IGNORE INTO assets (symbol, last_updated) VALUES (?, CURRENT_TIMESTAMP)",
					(symbol,),
				)

			# Remove old ones
			cursor.execute(
				"DELETE FROM group_constituents WHERE group_name = ?", (group_name,)
			)

			# Add new ones
			for symbol in symbols:
				cursor.execute(
					"INSERT INTO group_constituents (group_name, symbol) VALUES (?, ?)",
					(group_name, symbol),
				)

			conn.commit()

	def get_group_constituents(self, group_name: str) -> List[str]:
		"""Get constituents for a group from the DB."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"SELECT symbol FROM group_constituents WHERE group_name = ?",
				(group_name,),
			)
			return [row["symbol"] for row in cursor.fetchall()]

	def list_groups(self) -> List[dict]:
		"""Return all groups."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute("SELECT * FROM groups ORDER BY name")
			return [dict(row) for row in cursor.fetchall()]

	def delete_group(self, group_name: str) -> str:
		"""Delete a custom group. Returns 'deleted', 'not_found', or 'system'."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute("SELECT is_system FROM groups WHERE name = ?", (group_name,))
			row = cursor.fetchone()
			if not row:
				return "not_found"
			if row["is_system"]:
				return "system"
			cursor.execute("DELETE FROM groups WHERE name = ?", (group_name,))
			conn.commit()
			return "deleted"

	def get_asset(self, symbol: str) -> Optional[dict]:
		"""Get asset metadata."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute("SELECT * FROM assets WHERE symbol = ?", (symbol,))
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

	def should_use_db_cache(self, symbol: str, provider: str = "yfinance") -> bool:
		"""
		Check if raw_provider_data has a fresh enough payload for this symbol.
		TTL: 15 min when market open, 12 h when closed — mirrors the old file-cache TTL.

		Args:
			symbol: The asset ticker symbol.
			provider: The data provider name.

		Returns:
			True if the cached payload is within TTL, False otherwise.
		"""
		from datetime import datetime

		from core.utils.market import is_market_open

		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"SELECT timestamp FROM raw_provider_data WHERE symbol = ? AND provider = ?",
				(symbol.upper(), provider),
			)
			row = cursor.fetchone()

		if not row:
			return False

		try:
			ts = datetime.fromisoformat(row["timestamp"])
		except (ValueError, TypeError):
			return False

		# SQLite CURRENT_TIMESTAMP is UTC; compare as naive UTC to avoid local-time skew
		elapsed = (datetime.utcnow() - ts).total_seconds()
		if is_market_open():
			return elapsed < 900  # 15 min
		return elapsed < 43200  # 12 h

	def upsert_raw_provider_data(self, symbol: str, provider: str, data: dict) -> None:
		"""
		Insert or update the raw JSON payload for a symbol/provider pair.

		Args:
			symbol: The asset ticker symbol.
			provider: The data provider name (e.g. 'yfinance').
			data: The raw dict payload to persist.
		"""
		import json

		symbol = symbol.upper().strip()
		provider = provider.lower().strip()
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"""
				INSERT INTO raw_provider_data (symbol, provider, data_json)
				VALUES (?, ?, ?)
				ON CONFLICT(symbol, provider) DO UPDATE SET
					data_json = excluded.data_json,
					timestamp = CURRENT_TIMESTAMP
			""",
				(symbol, provider, json.dumps(data, default=str)),
			)
			conn.commit()

	def get_raw_provider_data(
		self, symbol: str, provider: Optional[str] = None
	) -> Optional[dict]:
		"""
		Retrieve the latest raw provider payload for a symbol.

		Args:
			symbol: The asset ticker symbol.
			provider: Optional provider name; returns most-recent entry if omitted.

		Returns:
			Dict with keys 'data', 'provider', 'timestamp', or None if not found.
		"""
		import json

		symbol = symbol.upper().strip()
		if provider:
			provider = provider.lower().strip()
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			if provider:
				cursor.execute(
					"""
					SELECT data_json, provider, timestamp FROM raw_provider_data
					WHERE symbol = ? AND provider = ?
				""",
					(symbol, provider),
				)
			else:
				cursor.execute(
					"""
					SELECT data_json, provider, timestamp FROM raw_provider_data
					WHERE symbol = ?
					ORDER BY timestamp DESC LIMIT 1
				""",
					(symbol,),
				)
			row = cursor.fetchone()
			if not row:
				return None
			return {
				"data": json.loads(row["data_json"]),
				"provider": row["provider"],
				"timestamp": row["timestamp"],
			}

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

	def bulk_save_analyses(
		self, analyses: List[dict], profile: str, benchmark_version: str = "1.0.0"
	):
		"""Perform a single bulk transaction to save multiple analysis results."""

		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			try:
				for res in analyses:
					# Upsert asset
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
						(
							res["symbol"],
							res.get("name"),
							res["asset_type"].value,
							res.get("sector"),
							res.get("industry"),
						),
					)

					# Insert metric history
					for r in res["results"]:
						metric_key = r.get("metric")
						val = r.get("raw_value")
						if metric_key and val is not None:
							try:
								cursor.execute(
									"""
									INSERT INTO metrics_history (symbol, metric_key, value)
									VALUES (?, ?, ?)
								""",
									(res["symbol"], metric_key, float(val)),
								)
							except (ValueError, TypeError):
								pass

					# Insert score snapshot — results_json intentionally omitted;
					# raw_provider_data is the source of truth for re-scoring
					cursor.execute(
						"""
						INSERT INTO analysis_snapshots (symbol, profile, total_score, benchmark_version)
						VALUES (?, ?, ?, ?)
					""",
						(
							res["symbol"],
							profile,
							res["score"],
							benchmark_version,
						),
					)
				conn.commit()
			except Exception as e:
				conn.rollback()
				raise e

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

	def get_effective_benchmarks(
		self,
		asset_type: str = "equity",
		sector: Optional[str] = None,
		version: str = "1.0.0",
	) -> List[dict]:
		"""
		Get benchmarks for an asset type, with optional sector-specific overrides.
		"""
		# Start with global benchmarks
		benchmarks = {
			b["metric"]: b for b in self.get_global_benchmarks(asset_type, version)
		}

		if sector:
			# Get sector overrides
			overrides = self.get_sector_benchmarks(sector, version)
			for ov in overrides:
				metric = ov["metric_key"]
				if metric in benchmarks:
					# Override specific values
					b = benchmarks[metric]
					if ov["benchmark_type"] == "best_worst":
						b["best"] = ov["value_a"]
						b["worst"] = ov["value_b"]
						b["type"] = "sigmoid"  # best_worst maps to sigmoid
					elif ov["benchmark_type"] == "target_width":
						b["target"] = ov["value_a"]
						b["width"] = ov["value_b"]
						b["type"] = "bell_curve"
					elif ov["benchmark_type"] == "threshold":
						b["threshold"] = ov["value_a"]
						b["type"] = "threshold"
				else:
					# New metric for this sector (less common but possible)
					# We might lack some metadata like 'name', so we use metric as name
					new_b = {
						"metric": metric,
						"name": metric.replace("_", " ").title(),
						"asset_type": asset_type,
						"weight": 1.0,
						"version": version,
					}
					if ov["benchmark_type"] == "best_worst":
						new_b.update(
							{
								"type": "sigmoid",
								"best": ov["value_a"],
								"worst": ov["value_b"],
							}
						)
					elif ov["benchmark_type"] == "target_width":
						new_b.update(
							{
								"type": "bell_curve",
								"target": ov["value_a"],
								"width": ov["value_b"],
							}
						)
					elif ov["benchmark_type"] == "threshold":
						new_b.update({"type": "threshold", "threshold": ov["value_a"]})

					benchmarks[metric] = new_b

		return list(benchmarks.values())

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

	def get_latest_metrics(self, symbol: str) -> dict:
		"""Get the most recent value for every metric key for a given symbol."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"""
				SELECT metric_key, value FROM metrics_history mh
				WHERE symbol = ? AND timestamp = (
					SELECT MAX(timestamp) FROM metrics_history 
					WHERE symbol = mh.symbol AND metric_key = mh.metric_key
				)
			""",
				(symbol,),
			)
			return {row["metric_key"]: row["value"] for row in cursor.fetchall()}

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

	def list_profiles(self) -> List[str]:
		"""Return all investor profile names."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute("SELECT name FROM investor_profiles ORDER BY name")
			return [row["name"] for row in cursor.fetchall()]

	def upsert_profile_setting(
		self,
		profile_name: str,
		metric_key: str,
		weight: float,
		range_min: float = 0.0,
		range_max: float = 100.0,
		formula: str = "sigmoid",
	):
		"""Insert or update metric settings for a profile."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"""
				INSERT INTO profile_metric_settings (profile_name, metric_key, weight, range_min, range_max, formula)
				VALUES (?, ?, ?, ?, ?, ?)
				ON CONFLICT(profile_name, metric_key) DO UPDATE SET
					weight = excluded.weight,
					range_min = excluded.range_min,
					range_max = excluded.range_max,
					formula = excluded.formula
			""",
				(profile_name, metric_key, weight, range_min, range_max, formula),
			)
			conn.commit()

	def get_profile_settings(self, profile_name: str) -> List[dict]:
		"""Get all metric settings for a specific profile."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			cursor.execute(
				"SELECT * FROM profile_metric_settings WHERE profile_name = ?",
				(profile_name,),
			)
			return [dict(row) for row in cursor.fetchall()]

	def create_profile(self, profile: Any):
		"""Create a new profile with weights, ranges, and formulas."""
		self.upsert_profile(profile.name)
		for metric_key, weight in profile.weights.items():
			range_data = profile.ranges.get(metric_key, {"min": 0, "max": 100})
			formula = profile.formulas.get(metric_key, "sigmoid")
			self.upsert_profile_setting(
				profile.name,
				metric_key,
				weight,
				range_data["min"],
				range_data["max"],
				formula,
			)

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

	def get_metric_history(
		self, metric_key: str, symbol: Optional[str] = None, limit: int = 100
	) -> List[dict]:
		"""Get historical data for a specific metric."""
		with self._lock:
			conn = self.db.get_connection()
			cursor = conn.cursor()
			if symbol:
				cursor.execute(
					"""
					SELECT timestamp, value FROM metrics_history 
					WHERE metric_key = ? AND symbol = ?
					ORDER BY timestamp DESC LIMIT ?
				""",
					(metric_key, symbol, limit),
				)
			else:
				# If no symbol, maybe return an average or some distribution?
				# For now, let's just return sample data from various symbols
				cursor.execute(
					"""
					SELECT timestamp, value, symbol FROM metrics_history 
					WHERE metric_key = ?
					ORDER BY timestamp DESC LIMIT ?
				""",
					(metric_key, limit),
				)
			return [dict(row) for row in cursor.fetchall()]

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
