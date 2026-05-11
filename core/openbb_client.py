import json
import os
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from config import CACHE_DIR, PROXIES
from core.logger import get_logger
from core.stats import stats
from core.utils.market import get_last_market_close, is_market_closed

logger = get_logger(__name__)


class ProxyManager:
	"""
	Manages a pool of proxies and rotates them by updating environment variables.
	OpenBB Platform (and underlying libraries like requests/httpx/urllib3)
	typically respect HTTP_PROXY/HTTPS_PROXY environment variables.
	"""

	def __init__(self, proxies: List[str]):
		self.proxies = proxies
		self.current_index = -1

	def rotate(self) -> Optional[str]:
		"""Rotate to the next proxy in the list."""
		if not self.proxies:
			return None
		self.current_index = (self.current_index + 1) % len(self.proxies)
		proxy = self.proxies[self.current_index]
		os.environ["HTTP_PROXY"] = proxy
		os.environ["HTTPS_PROXY"] = proxy
		logger.info(f"Rotated to proxy: {proxy}")
		return proxy

	def clear(self):
		"""Clear proxy environment variables."""
		os.environ.pop("HTTP_PROXY", None)
		os.environ.pop("HTTPS_PROXY", None)


proxy_manager = ProxyManager(PROXIES)


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
	obb_func, symbol: str, provider: str, max_retries: int = 2
) -> Optional[Any]:
	"""
	Execute an OpenBB endpoint call with intra-ticker jitter and exponential backoff.
	"""
	# Intra-ticker jitter: tiny sleep before EVERY internal endpoint call
	# to avoid "burst" detection by Yahoo Finance.
	time.sleep(random.uniform(0.1, 0.3))

	func_name = getattr(obb_func, "__name__", str(obb_func))
	# Clean up endpoint name (e.g., 'equity.fundamental.metrics' -> 'fundamental_metrics')
	endpoint_path = getattr(obb_func, "__qualname__", func_name).split(".")
	endpoint_name = (
		"_".join(endpoint_path[-2:]) if len(endpoint_path) > 1 else func_name
	)

	for attempt in range(max_retries + 1):
		start_time = time.perf_counter()
		if attempt > 0:
			stats.retry_attempts += 1
		try:
			res = obb_func(symbol=symbol, provider=provider)
			duration = time.perf_counter() - start_time
			stats.record_request(endpoint_name, duration)

			# Standard OpenBB result has a .results attribute
			if res and hasattr(res, "results") and res.results:
				if attempt > 0:
					stats.retry_successes += 1
				return res

			# If results are empty, it might be a rate limit or missing data
			if attempt < max_retries:
				stats.record_error("empty_results")
				wait_time = (attempt + 1) * 2.5 + random.uniform(1.0, 2.0)
				logger.debug(
					f"Empty results for {symbol} on {func_name}. Retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})"
				)
				time.sleep(wait_time)
		except Exception as e:
			duration = time.perf_counter() - start_time
			# Classify error
			err_str = str(e).lower()
			error_type = "provider_error"
			if "429" in err_str or "rate limit" in err_str:
				error_type = "rate_limit"
				# Proactive proxy rotation on rate limit
				proxy_manager.rotate()
			elif "timeout" in err_str or "connection" in err_str:
				error_type = "network_error"

			stats.record_error(error_type)
			stats.record_request(endpoint_name, duration, success=False)

			if attempt < max_retries:
				wait_time = (attempt + 1) * 3.0 + random.uniform(1.0, 2.0)
				logger.debug(
					f"Fetch error for {symbol} on {func_name}: {e}. Retrying in {wait_time:.1f}s..."
				)
				time.sleep(wait_time)
			else:
				logger.debug(f"All retries failed for {symbol} on {func_name}: {e}")
				raise

	# If we exit the loop without returning, it means results were empty
	raise RuntimeError(f"No results returned for {symbol} after {max_retries} retries")


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

	proxy_manager.rotate()
	from openbb import obb

	provider = "yfinance"
	symbol_str = ",".join(to_fetch)

	logger.info(f"Bulk fetching data for {len(to_fetch)} symbols from OpenBB")
	stats.api_calls += 1
	stats.bulk_fetch_symbols += len(to_fetch)

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
					# Only update if the value is not None to avoid overwriting good data
					for k, v in data.items():
						if v is not None or k not in bulk_combined[symbol]:
							bulk_combined[symbol][k] = v

		# Endpoints are wrapped in individual try-except to avoid batch failure
		critical_success = True

		# 1. Fundamental Metrics
		try:
			merge_bulk_results(
				_fetch_with_retry(obb.equity.fundamental.metrics, symbol_str, provider)
			)
		except Exception as e:
			logger.warning(f"Bulk fetch (Fundamental Metrics) failed for batch: {e}")
			critical_success = False

		# 2. Company Profile
		try:
			merge_bulk_results(
				_fetch_with_retry(obb.equity.profile, symbol_str, provider)
			)
		except Exception as e:
			logger.warning(f"Bulk fetch (Profile) failed for batch: {e}")
			critical_success = False

		# 3. Analyst Consensus
		try:
			merge_bulk_results(
				_fetch_with_retry(obb.equity.estimates.consensus, symbol_str, provider)
			)
		except Exception as e:
			logger.warning(f"Bulk fetch (Consensus) failed for batch: {e}")

		# 4. Ownership Statistics
		try:
			merge_bulk_results(
				_fetch_with_retry(
					obb.equity.ownership.share_statistics, symbol_str, provider
				)
			)
		except Exception as e:
			logger.warning(f"Bulk fetch (Ownership) failed for batch: {e}")

		# 5. ETF Info (only for those that still lack a 'name' or look like ETFs)
		etf_candidates = [
			s
			for s, data in bulk_combined.items()
			if not data.get("name") or "fund_family" in str(data)
		]
		if etf_candidates:
			try:
				merge_bulk_results(
					_fetch_with_retry(obb.etf.info, ",".join(etf_candidates), provider)
				)
			except Exception:
				# Non-critical: some might not be ETFs
				pass

		# Save results to individual cache files
		CACHE_DIR.mkdir(parents=True, exist_ok=True)
		success_count = 0
		for symbol, data in bulk_combined.items():
			# We always save the cache file, even if it only contains {"symbol": S}
			# This acts as a negative cache to prevent immediate "one-by-one" retries
			cache_file = CACHE_DIR / f"{symbol}.json"
			cache_file.write_text(json.dumps(data, default=str, indent="\t"))
			if len(data) > 1:
				success_count += 1

		logger.info(
			f"Bulk fetch phase complete. Cached {len(bulk_combined)} files ({success_count} with data)."
		)
		stats.api_successes += 1
		return critical_success

	except Exception as e:
		logger.error(f"OpenBB bulk fetch critical failure: {e}")
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

	proxy_manager.rotate()
	# If not cached, fall back to single-fetch (though orchestrator should have bulk-fetched)
	from openbb import obb

	logger.info(f"Fetching fresh data for {ticker_symbol} from OpenBB (fallback)")
	stats.api_calls += 1
	stats.fallback_fetch_symbols += 1
	try:
		combined_data = {}
		provider = "yfinance"

		def merge_res(res):
			if not res or not hasattr(res, "results") or not res.results:
				return
			data = res.results[0].model_dump()
			if data:
				for k, v in data.items():
					if v is not None or k not in combined_data:
						combined_data[k] = v

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
			try:
				merge_res(_fetch_with_retry(obb.etf.info, ticker_symbol, provider))
			except Exception:
				# Normal for non-ETFs
				pass

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
