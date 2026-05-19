import logging
from typing import Any, Dict, List, Optional

from core.database.repository import DatabaseRepository

from .providers.openbb_provider import OpenBBProvider
from .schema import AssetData, AssetType

logger = logging.getLogger(__name__)


def load_benchmarks(
	asset_type: str,
	repo: Optional[DatabaseRepository] = None,
	version: str = "1.0.0",
) -> List[Dict[str, Any]]:
	"""
	Load global benchmarks for a specific asset type from the DB.

	Sector-relative and batch-relative adjustments are computed separately in
	core/analysis/relative.py and passed as overrides at analysis time.

	Args:
		asset_type: Asset class string ('STOCK' or 'ETF').
		repo: Database repository to read from.
		version: Benchmark version string.

	Returns:
		List of benchmark definition dicts, or empty list if repo is absent.
	"""
	if not repo:
		return []

	try:
		return repo.get_global_benchmarks(asset_type, version=version)
	except Exception as e:
		logger.error(f"Failed to load benchmarks for {asset_type} from DB: {e}")
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
