import logging
from typing import Any, Dict, List, Optional

from core.database.repository import DatabaseRepository

from .providers.openbb_provider import OpenBBProvider
from .schema import AssetData, AssetType

logger = logging.getLogger(__name__)


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


def get_asset_from_db(repo: DatabaseRepository, symbol: str) -> Optional[AssetData]:
	"""
	Reconstruct AssetData from the latest database records.
	"""
	meta = repo.get_asset(symbol)
	if not meta:
		return None

	metrics = repo.get_latest_metrics(symbol)
	if not metrics:
		return None

	return AssetData(
		symbol=meta["symbol"],
		asset_type=AssetType(meta["asset_type"])
		if meta["asset_type"]
		else AssetType.UNKNOWN,
		name=meta["name"],
		sector=meta["sector"],
		industry=meta["industry"],
		metrics=metrics,
		raw_data=metrics,  # For now, metrics and raw_data share the same source in DB
	)


def get_stock_data(
	ticker_symbol: str, repo: Optional[DatabaseRepository] = None
) -> Optional[AssetData]:
	"""
	Master function:
	1. Checks DB (raw_provider_data) for an existing payload if repo is provided.
	2. Falls back to OpenBB live fetch if absent, then persists payload to DB.

	Args:
		ticker_symbol: The ticker symbol to fetch.
		repo: Optional database repository for cache lookup and persistence.

	Returns:
		AssetData if successful, None otherwise.
	"""
	symbol = ticker_symbol.upper()

	if repo:
		asset = get_asset_from_db(repo, symbol)
		if asset:
			return asset

	provider = OpenBBProvider()
	asset = provider.get_data(symbol)
	if asset and repo:
		try:
			repo.upsert_raw_provider_data(symbol, "yfinance", asset.raw_data)
		except Exception as e:
			logger.warning(f"Failed to cache raw data for {symbol}: {e}")
	return asset


def get_cached_stock_data(
	ticker_symbol: str, repo: Optional[DatabaseRepository] = None
) -> Optional[AssetData]:
	"""
	Load asset data strictly from the DB cache (raw_provider_data). No network call.

	Args:
		ticker_symbol: The ticker symbol to load.
		repo: Database repository for cache lookup.

	Returns:
		AssetData if found in cache, None otherwise.
	"""
	if not repo:
		return None
	symbol = ticker_symbol.upper()
	cached = repo.get_raw_provider_data(symbol)
	if not cached:
		return None
	provider = OpenBBProvider()
	return provider._normalize(symbol, cached["data"])
