from functools import lru_cache
from typing import Any, Dict, List, Optional

from core.database.repository import DatabaseRepository

from .providers.openbb_provider import OpenBBProvider
from .schema import AssetData


def load_benchmarks(
	asset_type: str,
	sector: Optional[str] = None,
	repo: Optional[DatabaseRepository] = None,
	version: str = "1.0.0",
) -> List[Dict[str, Any]]:
	"""
	Load benchmarks for a specific asset type and optionally apply sector overrides from the DB.
	"""
	if not repo:
		return []

	try:
		# 1. Load Global Benchmarks for the asset type (STOCK or ETF)
		global_benchmarks = repo.get_global_benchmarks(asset_type, version=version)

		if not sector:
			return global_benchmarks

		# 2. Apply Sector Overrides from the database
		db_overrides = repo.get_sector_benchmarks(sector, version=version)
		if not db_overrides:
			return global_benchmarks

		# Convert DB format back to the dictionary format expected by the merge logic
		overrides = {}
		for row in db_overrides:
			m_key = row["metric_key"]
			b_type = row["benchmark_type"]
			if b_type == "best_worst":
				overrides[m_key] = {"best": row["value_a"], "worst": row["value_b"]}
			elif b_type == "target_width":
				overrides[m_key] = {"target": row["value_a"], "width": row["value_b"]}

		# Apply overrides to global defaults
		final_benchmarks = []
		for b in global_benchmarks:
			metric_key = b.get("metric")
			if metric_key in overrides:
				# Merge the global benchmark with sector-specific overrides
				merged = {**b, **overrides[metric_key]}
				final_benchmarks.append(merged)
			else:
				final_benchmarks.append(b)

		return final_benchmarks

	except Exception as e:
		print(f"[ERROR] Failed to load benchmarks for {asset_type} from DB: {e}")
		return []


@lru_cache(maxsize=100)
def get_stock_data(ticker_symbol: str) -> Optional[AssetData]:
	"""
	Master function:
	Fetches data using the configured providers and returns normalized AssetData.
	"""
	provider = OpenBBProvider()
	return provider.get_data(ticker_symbol.upper())


@lru_cache(maxsize=100)
def get_cached_stock_data(ticker_symbol: str) -> Optional[AssetData]:
	"""
	Strict offline loading. Does not fallback to network.
	"""
	provider = OpenBBProvider()
	return provider.get_cached_data(ticker_symbol.upper())
