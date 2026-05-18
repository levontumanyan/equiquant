import json
import logging
from collections import defaultdict

from config import ROOT_DIR
from core.database.repository import DatabaseRepository

logger = logging.getLogger(__name__)

SEEDS_DIR = ROOT_DIR / "seeds"


class DatabaseSeeder:
	"""
	Handles seeding the database with initial configuration data.
	Data is loaded from JSON files in the seeds/ directory.
	"""

	def __init__(self, repo: DatabaseRepository):
		self.repo = repo

	def seed_all(self):
		"""Orchestrate the full seeding process."""
		logger.info("Starting database seeding...")
		self.seed_assets()
		self.seed_indices()
		self.seed_benchmarks()
		self.seed_sector_benchmarks()
		self.seed_profiles()
		self.seed_groups()
		self.seed_app_settings()
		logger.info("Database seeding complete.")

	def seed_app_settings(self):
		"""Seed application settings."""
		seed_file = SEEDS_DIR / "app_settings.json"
		if not seed_file.exists():
			logger.warning(f"Seed file not found: {seed_file}")
			return

		try:
			with open(seed_file, "r") as f:
				data = json.load(f)

			for row in data:
				self.repo.upsert_app_setting(
					key=row["key"],
					value=row["value"],
					category=row.get("category", "general"),
					description=row.get("description"),
				)
			logger.info(f"Seeded {len(data)} application settings.")
		except Exception as e:
			logger.error(f"Failed to seed application settings: {e}")

	def seed_assets(self):
		"""Seed the asset registry (ticker universe)."""
		seed_file = SEEDS_DIR / "assets.json"
		if not seed_file.exists():
			logger.warning(f"Seed file not found: {seed_file}")
			return
		try:
			data = json.loads(seed_file.read_text())
			for row in data:
				self.repo.upsert_asset(
					symbol=row["symbol"],
					name=row.get("name"),
					asset_type=row.get("asset_type"),
					sector=row.get("sector"),
					industry=row.get("industry"),
					exchange=row.get("exchange"),
					currency=row.get("currency"),
				)
			logger.info(f"Seeded {len(data)} assets.")
		except Exception as e:
			logger.error(f"Failed to seed assets: {e}")

	def seed_indices(self):
		"""Seed market indices and their constituents."""
		indices_file = SEEDS_DIR / "indices.json"
		constituents_file = SEEDS_DIR / "index_constituents.json"
		if not indices_file.exists() or not constituents_file.exists():
			logger.warning("Index seed files not found.")
			return
		try:
			indices = json.loads(indices_file.read_text())
			for idx in indices:
				self.repo.upsert_index(
					symbol=idx["symbol"],
					name=idx["name"],
					is_etf=bool(idx.get("is_etf", False)),
				)

			constituents = json.loads(constituents_file.read_text())
			by_index: dict = defaultdict(list)
			for row in constituents:
				by_index[row["index_symbol"]].append(row["asset_symbol"])
			for index_symbol, symbols in by_index.items():
				self.repo.update_index_constituents(index_symbol, symbols)

			logger.info(
				f"Seeded {len(indices)} indices and {len(constituents)} constituents."
			)
		except Exception as e:
			logger.error(f"Failed to seed indices: {e}")

	def seed_benchmarks(self):
		"""Seed global benchmarks for STOCK and ETF."""
		seed_file = SEEDS_DIR / "global_benchmarks.json"
		if not seed_file.exists():
			logger.warning(f"Seed file not found: {seed_file}")
			return

		try:
			with open(seed_file, "r") as f:
				data = json.load(f)

			for row in data:
				self.repo.upsert_global_benchmark(
					asset_type=row["asset_type"],
					metric_key=row["metric_key"],
					name=row["name"],
					formula_type=row["formula_type"],
					unit=row.get("unit"),
					is_decimal=bool(row.get("is_decimal", False)),
					display_key=row.get("display_key"),
					params_json=row.get("params_json"),
					weight=float(row.get("weight", 1.0)),
					version=row.get("version", "1.0.0"),
				)
			logger.info(f"Seeded {len(data)} global benchmarks.")
		except Exception as e:
			logger.error(f"Failed to seed global benchmarks: {e}")

	def seed_sector_benchmarks(self):
		"""Seed sector-specific benchmark overrides."""
		seed_file = SEEDS_DIR / "sector_benchmarks.json"
		if not seed_file.exists():
			logger.warning(f"Seed file not found: {seed_file}")
			return

		try:
			with open(seed_file, "r") as f:
				data = json.load(f)

			for row in data:
				self.repo.upsert_sector_benchmark(
					sector=row["sector"],
					metric_key=row["metric_key"],
					benchmark_type=row["benchmark_type"],
					value_a=row["value_a"],
					value_b=row["value_b"],
					version=row.get("version", "1.0.0"),
				)
			logger.info(f"Seeded {len(data)} sector benchmarks.")
		except Exception as e:
			logger.error(f"Failed to seed sector benchmarks: {e}")

	def seed_profiles(self):
		"""Seed investor profiles and their metric settings."""
		profiles_file = SEEDS_DIR / "investor_profiles.json"
		settings_file = SEEDS_DIR / "profile_metric_settings.json"

		if not profiles_file.exists() or not settings_file.exists():
			logger.warning("Profile seed files missing.")
			return

		try:
			with open(profiles_file, "r") as f:
				profiles = json.load(f)
			for p in profiles:
				self.repo.upsert_profile(p["name"], p.get("description"))

			raw = settings_file.read_text().strip()
			settings = json.loads(raw) if raw else []
			for s in settings:
				raw_min = s.get("range_min")
				raw_max = s.get("range_max")
				self.repo.upsert_profile_setting(
					profile_name=s["profile_name"],
					metric_key=s["metric_key"],
					weight=float(s.get("weight", 1.0)),
					range_min=float(raw_min) if raw_min is not None else None,
					range_max=float(raw_max) if raw_max is not None else None,
					formula=s.get("formula"),
				)
			logger.info(
				f"Seeded {len(profiles)} profiles and {len(settings)} settings."
			)
		except Exception as e:
			logger.error(f"Failed to seed profiles: {e}")

	def seed_groups(self):
		"""Seed default stock groups."""
		seed_file = SEEDS_DIR / "stock_groups.json"
		if not seed_file.exists():
			logger.warning(f"Seed file not found: {seed_file}")
			return

		try:
			with open(seed_file, "r") as f:
				data = json.load(f)

			for group in data:
				if group.get("is_system"):
					self.repo._upsert_system_group(
						name=group["name"],
						description=group.get("description"),
					)
				else:
					self.repo.upsert_group(
						name=group["name"],
						description=group.get("description"),
						is_system=False,
					)
				if "tickers" in group:
					self.repo.update_group_constituents(group["name"], group["tickers"])

			logger.info(f"Seeded {len(data)} stock groups.")
		except Exception as e:
			logger.error(f"Failed to seed stock groups: {e}")
