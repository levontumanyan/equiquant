import json
import os
import random
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from config import CACHE_DIR, PROXIES
from core.logger import get_logger
from core.stats import stats
from core.utils.market import get_last_market_close, is_market_closed

logger = get_logger(__name__)


class RateLimitError(Exception):
	"""Raised when a provider returns a 429 or rate limit error."""

	pass


class ProxyManager:
	"""
	Manages a pool of proxies and rotates them by updating environment variables.
	OpenBB Platform (and underlying libraries like requests/httpx/urllib3)
	typically respect HTTP_PROXY/HTTPS_PROXY environment variables.
	"""

	def __init__(self, proxies: List[str]):
		self.proxies = proxies
		self.current_index = -1
		self._lock = threading.Lock()

	def rotate(self) -> Optional[str]:
		"""Rotate to the next proxy in the list."""
		with self._lock:
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
		with self._lock:
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
	obb_func: Any,
	symbol: str,
	provider: str,
	max_retries: int = 1,
	endpoint_name: str = "unknown",
) -> Any:
	"""Internal helper to handle retries and classification of OpenBB errors."""
	func_name = getattr(obb_func, "__name__", "unknown_func")
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
				# Exponentially increasing wait time for empty results; B311 safe for non-cryptographic jitter.
				wait_time = (attempt + 1) * 3.5 + random.uniform(1.0, 3.0)  # nosec B311
				logger.debug(
					f"Empty results for {symbol} on {func_name}. Retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})"
				)
				time.sleep(wait_time)
		except Exception as e:
			duration = time.perf_counter() - start_time
			# Classify error
			err_str = str(e).lower()
			error_type = "provider_error"

			is_rate_limit = "429" in err_str or "rate limit" in err_str
			if is_rate_limit:
				error_type = "rate_limit"
				# Proactive proxy rotation on rate limit
				proxy_manager.rotate()
				stats.record_error(error_type)
				stats.record_request(endpoint_name, duration, success=False)
				logger.warning(
					f"Rate limit hit on {func_name} for {symbol}. Failing fast to trigger orchestrator backoff."
				)
				raise RateLimitError(f"Rate limit exceeded: {e}")

			stats.record_error(error_type)
			stats.record_request(endpoint_name, duration, success=False)

			if attempt < max_retries:
				# Adding jitter for retry backoff; B311 safe for this purpose.
				wait_time = (attempt + 1) * 3.0 + random.uniform(1.0, 2.0)  # nosec B311
				logger.debug(
					f"Fetch error for {symbol} on {func_name}: {e}. Retrying in {wait_time:.1f}s..."
				)
				time.sleep(wait_time)
			else:
				logger.debug(f"All retries failed for {symbol} on {func_name}: {e}")
				raise

	# If we exit the loop without returning, it means results were empty
	raise RuntimeError(f"No results returned for {symbol} after {max_retries} retries")


def _merge_bulk_results(res: Any, bulk_combined: Dict[str, Dict[str, Any]]) -> None:
	"""Merge bulk OpenBB results into the combined data dictionary."""
	if not res or not hasattr(res, "results") or not res.results:
		return
	for item in res.results:
		data = item.model_dump()
		symbol = data.get("symbol")
		if symbol and symbol in bulk_combined:
			for k, v in data.items():
				if v is not None or k not in bulk_combined[symbol]:
					bulk_combined[symbol][k] = v


def _fetch_etf_info_bulk(
	obb: Any, bulk_combined: Dict[str, Dict[str, Any]], provider: str
) -> None:
	"""Fetch ETF info for symbols that appear to be ETFs or lack basic info."""
	etf_candidates = [
		s
		for s, data in bulk_combined.items()
		if not data.get("name") or "fund_family" in str(data)
	]
	if etf_candidates:
		try:
			res = _fetch_with_retry(obb.etf.info, ",".join(etf_candidates), provider)
			_merge_bulk_results(res, bulk_combined)
		except RateLimitError:
			raise
		except Exception:
			# Non-critical: some might not be ETFs; B110 safe for this optional check.
			pass  # nosec B110


def _save_bulk_results_to_cache(bulk_combined: Dict[str, Dict[str, Any]]) -> int:
	"""Save results to individual cache files and return success count."""
	CACHE_DIR.mkdir(parents=True, exist_ok=True)
	success_count = 0
	for symbol, data in bulk_combined.items():
		cache_file = CACHE_DIR / f"{symbol}.json"
		cache_file.write_text(json.dumps(data, default=str, indent="	"))
		if len(data) > 1:
			stats.record_fetch(symbol)
			success_count += 1
	return success_count


def _fetch_bulk_endpoints(
	obb: Any, symbol_str: str, provider: str, bulk_combined: Dict
) -> bool:
	"Iterate through endpoints and populate bulk_combined dictionary."
	endpoints = [
		(obb.equity.fundamental.metrics, "Fundamental Metrics", True),
		(obb.equity.profile, "Company Profile", True),
		(obb.equity.estimates.consensus, "Analyst Consensus", False),
		(obb.equity.ownership.share_statistics, "Ownership Statistics", False),
	]

	critical_success = True
	for func, name, is_critical in endpoints:
		try:
			res = _fetch_with_retry(func, symbol_str, provider)
			_merge_bulk_results(res, bulk_combined)
			time.sleep(random.uniform(1.0, 2.0))  # nosec B311
		except RateLimitError:
			raise
		except Exception as e:
			logger.warning(f"Bulk fetch ({name}) failed for batch: {e}")
			if is_critical or (
				name == "Analyst Consensus" and "empty" not in str(e).lower()
			):
				critical_success = False
	return critical_success


def _save_bulk_results_to_cache(bulk_combined: Dict[str, Dict[str, Any]]) -> int:
	"Save results to individual cache files and return success count."
	CACHE_DIR.mkdir(parents=True, exist_ok=True)
	success_count = 0
	for symbol, data in bulk_combined.items():
		cache_file = CACHE_DIR / f"{symbol}.json"
		cache_file.write_text(json.dumps(data, default=str, indent="\t"))
		if len(data) > 1:
			stats.record_fetch(symbol)
			success_count += 1
	return success_count


def fetch_openbb_data_bulk(ticker_symbols: List[str]) -> bool:
	"Fetch data for multiple tickers in bulk to optimize API usage."
	if not ticker_symbols:
		return True

	ticker_symbols = [s.upper() for s in ticker_symbols]
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
		bulk_combined: Dict[str, Dict[str, Any]] = {s: {"symbol": s} for s in to_fetch}
		try:
			critical_success = _fetch_bulk_endpoints(
				obb, symbol_str, provider, bulk_combined
			)
		except RateLimitError as e:
			logger.error(f"Bulk fetch RATE LIMITED: {e}")
			return False

		_fetch_etf_info_bulk(obb, bulk_combined, provider)
		success_count = _save_bulk_results_to_cache(bulk_combined)

		logger.info(
			f"Bulk fetch phase complete. Cached {len(bulk_combined)} files ({success_count} with data)."
		)
		stats.api_successes += 1
		return critical_success

	except Exception as e:
		logger.error(f"OpenBB bulk fetch critical failure: {e}")
		stats.errors += 1
		return False


def _merge_single_res(res: Any, combined_data: Dict[str, Any]) -> None:
	"""Merge single OpenBB result into the combined data dictionary."""
	if not res or not hasattr(res, "results") or not res.results:
		return
	data = res.results[0].model_dump()
	if data:
		for k, v in data.items():
			if v is not None or k not in combined_data:
				combined_data[k] = v


def get_openbb_data(ticker_symbol: str) -> Dict[str, Any]:
	"""
	Fetch standardized data via OpenBB Platform using multiple endpoints.
	Handles intelligent caching based on market hours and robust rate limiting.
	"""
	ticker_symbol = ticker_symbol.upper()
	cache_file = CACHE_DIR / f"{ticker_symbol}.json"

	if should_use_cache(ticker_symbol):
		try:
			if not stats.is_fetched(ticker_symbol):
				logger.info(f"Cache hit for {ticker_symbol}")
				stats.cache_hits += 1
			return json.loads(cache_file.read_text())
		except Exception as e:
			logger.warning(f"Failed to read cache for {ticker_symbol}: {e}")

	proxy_manager.rotate()
	from openbb import obb

	logger.info(f"Fetching fresh data for {ticker_symbol} from OpenBB (fallback)")
	stats.api_calls += 1
	stats.fallback_fetch_symbols += 1
	try:
		combined_data = {}
		provider = "yfinance"
		endpoints = [
			obb.equity.fundamental.metrics,
			obb.equity.profile,
			obb.equity.estimates.consensus,
			obb.equity.ownership.share_statistics,
		]

		for func in endpoints:
			_merge_single_res(
				_fetch_with_retry(func, ticker_symbol, provider), combined_data
			)

		# Try ETF info if needed
		if (
			not combined_data
			or "fund_family" in str(combined_data)
			or not combined_data.get("name")
		):
			try:
				_merge_single_res(
					_fetch_with_retry(obb.etf.info, ticker_symbol, provider),
					combined_data,
				)
			except Exception:
				pass

		if not combined_data:
			logger.warning(f"No data retrieved for {ticker_symbol}")
			time.sleep(random.uniform(2.0, 4.0))
			return {}

		CACHE_DIR.mkdir(parents=True, exist_ok=True)
		cache_file.write_text(json.dumps(combined_data, default=str, indent="\t"))
		stats.api_successes += 1
		time.sleep(random.uniform(0.6, 1.2))
		return combined_data

	except Exception as e:
		logger.error(f"OpenBB overall error for {ticker_symbol}: {e}")
		stats.errors += 1
		return {}


def probe_api(ticker: str) -> bool:
	"""
	Execute a single, lightweight ticker fetch to probe if rate limit is still active.
	This bypasses the local cache to ensure a real network request.

	Args:
		ticker: The ticker symbol to use for the probe.

	Returns:
		True if the probe succeeds (or fails with a non-rate-limit error),
		False if rate limited.
	"""
	from openbb import obb

	ticker = ticker.upper().strip()
	proxy_manager.rotate()
	try:
		# Directly call the SDK to bypass our local CACHE_DIR logic
		obb.equity.profile(symbol=ticker, provider="yfinance")
		return True
	except Exception as e:
		err_str = str(e).lower()
		if "429" in err_str or "rate limit" in err_str:
			logger.warning(f"Rate-limit probe failed for {ticker}.")
			return False
		# For other errors, assume the API is at least reachable or it's a transient data error
		logger.debug(f"Probe encountered non-rate-limit error for {ticker}: {e}")
		return True
