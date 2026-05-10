import json
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from config import CACHE_DIR
from core.logger import get_logger
from core.stats import stats
from core.utils.market import get_last_market_close, is_market_closed

logger = get_logger(__name__)


def should_use_cache(ticker_symbol: str) -> bool:
	"""
	Check if a fresh cache file exists for the ticker.
	"""
	cache_file = CACHE_DIR / f"{ticker_symbol.upper()}.json"
	if not cache_file.exists():
		return False

	mtime = cache_file.stat().st_mtime
	age_seconds = time.time() - mtime

	# Condition A: Fresh cache (< 3 hours old)
	if age_seconds < 10800:
		return True

	# Condition B: Market is closed and cache was updated after the last market close
	now = datetime.now(ZoneInfo("UTC"))
	if is_market_closed(now):
		last_close = get_last_market_close(now)
		cache_time = datetime.fromtimestamp(mtime, tz=ZoneInfo("UTC"))
		if cache_time > last_close:
			return True

	return False


def _fetch_with_retry(
	obb_func, symbol: str, provider: str, max_retries: int = 1
) -> Optional[Any]:
	"""
	Execute an OpenBB endpoint call with intra-ticker jitter and exponential backoff.
	"""
	# Intra-ticker jitter: tiny sleep before EVERY internal endpoint call
	# to avoid "burst" detection by Yahoo Finance.
	time.sleep(random.uniform(0.1, 0.3))

	stats.http_requests += 1
	for attempt in range(max_retries + 1):
		try:
			res = obb_func(symbol=symbol, provider=provider)
			# Standard OpenBB result has a .results attribute
			if res and hasattr(res, "results") and res.results:
				return res

			# If results are empty, it might be a rate limit or missing data
			if attempt < max_retries:
				wait_time = (attempt + 1) * 2.0 + random.uniform(0.5, 1.0)
				func_name = getattr(obb_func, "__name__", str(obb_func))
				logger.debug(
					f"Empty results for {symbol} on {func_name}. Retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})"
				)
				time.sleep(wait_time)
		except Exception as e:
			func_name = getattr(obb_func, "__name__", str(obb_func))
			if attempt < max_retries:
				wait_time = (attempt + 1) * 3.0 + random.uniform(1.0, 2.0)
				logger.debug(
					f"Fetch error for {symbol} on {func_name}: {e}. Retrying in {wait_time:.1f}s..."
				)
				time.sleep(wait_time)
			else:
				logger.debug(f"All retries failed for {symbol} on {func_name}: {e}")

	return None


def fetch_openbb_data_bulk(ticker_symbols: List[str]) -> bool:
	"""
	Fetch data for multiple tickers in bulk to optimize API usage.
	Results are saved to individual cache files.
	"""
	if not ticker_symbols:
		return True

	ticker_symbols = [s.upper() for s in ticker_symbols]
	# Filter out what's already in cache
	to_fetch = [s for s in ticker_symbols if not should_use_cache(s)]

	if not to_fetch:
		logger.info("All symbols in bulk request already cached.")
		return True

	from openbb import obb

	provider = "yfinance"
	symbol_str = ",".join(to_fetch)

	logger.info(f"Bulk fetching data for {len(to_fetch)} symbols from OpenBB")
	stats.api_calls += 1

	try:
		# Data mapping: ticker -> combined_data dict
		bulk_combined: Dict[str, Dict[str, Any]] = {s: {"symbol": s} for s in to_fetch}

		def merge_bulk_results(res):
			if not res or not hasattr(res, "results") or not res.results:
				return
			for item in res.results:
				# Use model_dump() for Pydantic V2 models
				data = item.model_dump()
				symbol = data.get("symbol")
				if symbol and symbol in bulk_combined:
					bulk_combined[symbol].update(data)

		# 1. Fundamental Metrics
		merge_bulk_results(
			_fetch_with_retry(obb.equity.fundamental.metrics, symbol_str, provider)
		)

		# 2. Company Profile
		merge_bulk_results(_fetch_with_retry(obb.equity.profile, symbol_str, provider))

		# 3. Analyst Consensus
		merge_bulk_results(
			_fetch_with_retry(obb.equity.estimates.consensus, symbol_str, provider)
		)

		# 4. Ownership Statistics
		merge_bulk_results(
			_fetch_with_retry(
				obb.equity.ownership.share_statistics, symbol_str, provider
			)
		)

		# 5. ETF Info (only for those that still lack a 'name' or look like ETFs)
		etf_candidates = [
			s
			for s, data in bulk_combined.items()
			if not data.get("name") or "fund_family" in str(data)
		]
		if etf_candidates:
			merge_bulk_results(
				_fetch_with_retry(obb.etf.info, ",".join(etf_candidates), provider)
			)

		# Save results to individual cache files
		CACHE_DIR.mkdir(parents=True, exist_ok=True)
		success_count = 0
		for symbol, data in bulk_combined.items():
			if len(data) > 1:  # More than just the 'symbol' key we initialized with
				cache_file = CACHE_DIR / f"{symbol}.json"
				cache_file.write_text(json.dumps(data, default=str, indent="\t"))
				success_count += 1

		logger.info(f"Bulk fetch complete. Cached data for {success_count} symbols.")
		stats.api_successes += 1
		return success_count > 0

	except Exception as e:
		logger.error(f"OpenBB bulk fetch error: {e}")
		stats.errors += 1
		return False


def get_openbb_data(ticker_symbol: str) -> Dict[str, Any]:
	"""
	Fetch standardized data via OpenBB Platform using multiple endpoints.
	Handles intelligent caching based on market hours and robust rate limiting.
	"""
	ticker_symbol = ticker_symbol.upper()
	cache_file = CACHE_DIR / f"{ticker_symbol}.json"

	if should_use_cache(ticker_symbol):
		try:
			logger.info(f"Cache hit for {ticker_symbol}")
			stats.cache_hits += 1
			return json.loads(cache_file.read_text())
		except Exception as e:
			logger.warning(f"Failed to read cache for {ticker_symbol}: {e}")
			pass

	# If not cached, fall back to single-fetch (though orchestrator should have bulk-fetched)
	from openbb import obb

	logger.info(f"Fetching fresh data for {ticker_symbol} from OpenBB (fallback)")
	stats.api_calls += 1
	try:
		combined_data = {}
		provider = "yfinance"

		def merge_res(res):
			if not res or not hasattr(res, "results") or not res.results:
				return
			data = res.results[0].model_dump()
			if data:
				combined_data.update(data)

		# Endpoints
		merge_res(
			_fetch_with_retry(obb.equity.fundamental.metrics, ticker_symbol, provider)
		)
		merge_res(_fetch_with_retry(obb.equity.profile, ticker_symbol, provider))
		merge_res(
			_fetch_with_retry(obb.equity.estimates.consensus, ticker_symbol, provider)
		)
		merge_res(
			_fetch_with_retry(
				obb.equity.ownership.share_statistics, ticker_symbol, provider
			)
		)

		if (
			not combined_data
			or "fund_family" in str(combined_data)
			or not combined_data.get("name")
		):
			merge_res(_fetch_with_retry(obb.etf.info, ticker_symbol, provider))

		if not combined_data:
			logger.warning(f"No data retrieved for {ticker_symbol}")
			time.sleep(random.uniform(2.0, 4.0))
			return {}

		# Save to cache
		CACHE_DIR.mkdir(parents=True, exist_ok=True)
		cache_file.write_text(json.dumps(combined_data, default=str, indent="\t"))

		stats.api_successes += 1
		time.sleep(random.uniform(0.6, 1.2))
		return combined_data

	except Exception as e:
		logger.error(f"OpenBB overall error for {ticker_symbol}: {e}")
		stats.errors += 1
		return {}
