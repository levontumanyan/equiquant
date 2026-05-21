import logging
from typing import Any, Dict, List, Optional

from core.database.repository import DatabaseRepository

from .providers.fred_provider import FREDProvider
from .providers.openbb_provider import OpenBBProvider
from .providers.sec_provider import SECProvider
from .schema import AssetData, AssetType

logger = logging.getLogger(__name__)


def get_provider(name: str, repo: Optional[DatabaseRepository] = None):
	"""Factory to get a provider instance by name."""
	name = name.lower()
	if name == "yfinance" or name == "openbb":
		return OpenBBProvider()
	if name == "sec":
		return SECProvider(repo=repo)
	if name == "fred":
		return FREDProvider(repo=repo)
	return None


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


def get_stock_data(  # noqa: C901
	ticker_symbol: str, repo: Optional[DatabaseRepository] = None
) -> Optional[AssetData]:
	"""
	Master function:
	1. Checks DB for existing cached data from ALL providers.
	2. If any primary data is missing or stale, fetches from respective providers.
	3. Merges and returns the combined AssetData.

	Args:
		ticker_symbol: The ticker symbol to fetch.
		repo: Optional database repository for cache lookup and persistence.

	Returns:
		AssetData if successful, None otherwise.
	"""
	symbol = ticker_symbol.upper()

	# Try loading from cache first
	asset = get_cached_stock_data(symbol, repo=repo)

	# If we have a repo, check for staleness of individual providers
	providers_to_fetch = []
	all_providers = ["openbb", "sec"]  # FRED is usually global, not per-ticker

	if repo:
		for p_name in all_providers:
			if not repo.should_use_db_cache(symbol, p_name):
				providers_to_fetch.append(p_name)
	else:
		# No repo means no cache, fetch everything
		providers_to_fetch = all_providers

	if not providers_to_fetch:
		return asset

	# Fetch missing/stale data
	for p_name in providers_to_fetch:
		provider = get_provider(p_name, repo=repo)
		if not provider:
			continue

		new_data = provider.get_data(symbol)
		if new_data:
			if repo:
				try:
					repo.upsert_raw_provider_data(symbol, p_name, new_data.raw_data)
				except Exception as e:
					logger.warning(f"Failed to cache {p_name} data for {symbol}: {e}")

			if not asset:
				asset = new_data
				for k in new_data.metrics.keys():
					asset.sources[k] = p_name
			else:
				asset.merge(new_data, p_name, overwrite=True)

	return asset


def get_cached_stock_data(
	ticker_symbol: str, repo: Optional[DatabaseRepository] = None
) -> Optional[AssetData]:
	"""
	Load asset data from the DB cache (raw_provider_data).
	Merges data from all available providers for the symbol.

	Args:
		ticker_symbol: The ticker symbol to load.
		repo: Database repository for cache lookup.

	Returns:
		Merged AssetData if found in cache, None otherwise.
	"""
	if not repo:
		return None

	symbol = ticker_symbol.upper()
	all_cached = repo.get_all_raw_provider_data(symbol)

	if not all_cached:
		return None

	merged_asset: Optional[AssetData] = None

	# Sort by priority (higher priority first)
	# We need to instantiate providers to get their priority
	provider_instances = {}
	for cached in all_cached:
		name = cached["provider"]
		if name not in provider_instances:
			provider_instances[name] = get_provider(name, repo=repo)

	# Sort cached entries by provider priority
	def get_priority(entry):
		p = provider_instances.get(entry["provider"])
		return p.priority if p else 100

	sorted_cached = sorted(all_cached, key=get_priority)

	for cached in sorted_cached:
		provider = provider_instances.get(cached["provider"])
		if not provider:
			continue

		asset = provider._normalize(symbol, cached["data"])
		if not merged_asset:
			merged_asset = asset
			# Track sources for initial asset
			for k in asset.metrics.keys():
				merged_asset.sources[k] = cached["provider"]
		else:
			merged_asset.merge(asset, cached["provider"])

	return merged_asset
