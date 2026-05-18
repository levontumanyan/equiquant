import os
import random
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from config import PROXIES
from core.logger import get_logger
from core.stats import stats

logger = get_logger(__name__)


class RateLimitError(Exception):
	"""Raised when OpenBB returns a 429 status code."""

	pass


class ProxyManager:
	"""Handles rotation and selection of HTTP proxies."""

	def __init__(self, proxies: List[str]):
		self.proxies = proxies
		self.current_idx = -1
		self._lock = threading.Lock()

	def refresh_proxies(self, proxies: List[str]):
		"""Update the internal proxy list."""
		with self._lock:
			self.proxies = proxies
			if self.current_idx >= len(proxies):
				self.current_idx = 0 if proxies else -1
			logger.info(f"Refreshed proxy list. Count: {len(proxies)}")

	def refresh_from_db(self, repo: Any) -> None:
		"""Refresh proxies using settings from the database."""
		proxies_str = repo.get_setting("proxies", "")
		new_proxies = [p.strip() for p in proxies_str.split(",") if p.strip()]
		self.refresh_proxies(new_proxies)

	def get_proxy(self) -> Optional[str]:
		if not self.proxies:
			return None
		with self._lock:
			if self.current_idx == -1:
				return None
			return self.proxies[self.current_idx]

	def rotate(self) -> None:
		if not self.proxies:
			return
		with self._lock:
			self.current_idx = (self.current_idx + 1) % len(self.proxies)
			proxy = self.proxies[self.current_idx]
			os.environ["HTTP_PROXY"] = proxy
			os.environ["HTTPS_PROXY"] = proxy
			logger.debug(f"Rotated to proxy: {proxy}")

	def clear(self) -> None:
		with self._lock:
			self.current_idx = -1
			os.environ.pop("HTTP_PROXY", None)
			os.environ.pop("HTTPS_PROXY", None)
			logger.debug("Cleared proxies")


proxy_manager = ProxyManager(PROXIES)


def _fetch_with_retry(func, symbol: str, provider: str, max_retries: int = 3) -> Any:
	"""Helper to execute an OpenBB function with retries and jittered backoff."""
	func_name = getattr(func, "__name__", str(func))
	# Note: test expects max_retries=1 to result in 2 calls
	for attempt in range(max_retries + 1):
		try:
			proxy = proxy_manager.get_proxy()
			if proxy:
				os.environ["HTTP_PROXY"] = proxy
				os.environ["HTTPS_PROXY"] = proxy

			res = func(symbol=symbol, provider=provider)
			if res is not None:
				return res

			logger.debug(f"Received None from {func_name} for {symbol}")
			if attempt == max_retries:
				raise RuntimeError(f"All retries failed for {symbol} via {func_name}")

		except Exception as e:
			err_str = str(e).lower()
			if any(
				x in err_str
				for x in ["429", "rate limit", "401", "unauthorized", "invalid crumb"]
			):
				# Test expects FAIL FAST (no retries) for 429 in individual fetches
				raise RateLimitError(f"Rate limited for {symbol}")

			logger.debug(f"Error fetching {symbol} via {func_name}: {e}")
			if attempt == max_retries:
				raise e
	return None


def _fetch_bulk_endpoints(
	obb: Any, symbol_str: str, provider: str, bulk_combined: Dict[str, Dict[str, Any]]
) -> bool:
	"""Fetch critical bulk endpoints for common stock data."""
	endpoints = [
		(obb.equity.fundamental.metrics, "Fundamental Metrics"),
		(obb.equity.profile, "Company Profile"),
		(obb.equity.estimates.consensus, "Analyst Consensus"),
		(obb.equity.ownership.share_statistics, "Share Statistics"),
	]

	critical_success = True
	for func, label in endpoints:
		try:
			logger.info(f"Bulk fetching {label}...")
			res = _fetch_with_retry_bulk(func, symbol_str, provider)
			if res and hasattr(res, "results") and res.results:
				for r in res.results:
					s = r.symbol.upper()
					if s in bulk_combined:
						# Safe merge: only overwrite if value is not None
						data = r.model_dump()
						for k, v in data.items():
							if v is not None or k not in bulk_combined[s]:
								bulk_combined[s][k] = v
			else:
				logger.warning(f"No results returned for bulk {label}")
				# If even basic profile fails, we mark partial failure
				if label == "Company Profile":
					critical_success = False
		except RateLimitError:
			raise
		except Exception as e:
			logger.error(f"Error in bulk fetch for {label}: {e}")
			critical_success = False

	return critical_success


def _fetch_with_retry_bulk(
	func, symbol_str: str, provider: str, max_retries: int = 2
) -> Any:
	"""Helper for bulk OpenBB calls with retry logic."""
	for attempt in range(max_retries):
		try:
			return func(symbol=symbol_str, provider=provider)
		except Exception as e:
			err_str = str(e).lower()
			if any(
				x in err_str
				for x in ["429", "rate limit", "401", "unauthorized", "invalid crumb"]
			):
				wait_time = (attempt + 1) * 3.0 + random.uniform(1.0, 2.0)  # nosec B311
				logger.warning(
					f"Rate limited during bulk fetch. Waiting {wait_time:.1f}s..."
				)
				time.sleep(wait_time)
				proxy_manager.rotate()
				if attempt == max_retries - 1:
					raise RateLimitError("Max retries reached for bulk fetch")
			else:
				raise e
	return None


def _fetch_etf_info_bulk(
	obb: Any, bulk_combined: Dict[str, Dict[str, Any]], provider: str
) -> None:
	"""Heuristically fetch ETF info for symbols that look like funds."""
	to_fetch_etf = []
	for s, data in bulk_combined.items():
		if "fund_family" in str(data) or not data.get("name"):
			to_fetch_etf.append(s)

	if to_fetch_etf:
		logger.info(f"Fetching ETF info for {len(to_fetch_etf)} potential funds...")
		for s in to_fetch_etf:
			try:
				res = _fetch_with_retry(obb.etf.info, s, provider)
				if res and hasattr(res, "results") and res.results:
					data = res.results[0].model_dump()
					for k, v in data.items():
						if v is not None or k not in bulk_combined[s]:
							bulk_combined[s][k] = v
			except Exception:
				pass  # nosec B110


def fetch_openbb_data_bulk(
	tickers: List[str],
) -> Tuple[bool, Dict[str, Dict[str, Any]]]:
	"""
	Bulk fetch data for multiple tickers to minimize API round-trips.
	This is significantly more efficient than fetching individually.
	All tickers are pre-filtered by the main process; no file-cache checks here.

	Args:
		tickers: List of ticker symbols to fetch.

	Returns:
		Tuple of (critical_success, data_dict) where data_dict maps symbol to raw payload.
	"""
	to_fetch = [t.upper() for t in tickers]

	if not to_fetch:
		return True, {}

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
			return False, {}

		_fetch_etf_info_bulk(obb, bulk_combined, provider)

		result = {s: d for s, d in bulk_combined.items() if len(d) > 1}
		logger.info(
			f"Bulk fetch phase complete. {len(result)}/{len(bulk_combined)} symbols with data."
		)
		stats.api_successes += 1
		return critical_success, result

	except Exception as e:
		logger.error(f"OpenBB bulk fetch critical failure: {e}")
		stats.errors += 1
		return False, {}


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
	Single-ticker live fetch fallback — no file-cache reads or writes.
	"""
	ticker_symbol = ticker_symbol.upper()

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
				pass  # nosec B110 - ETF info is optional, safely ignore failures

		if not combined_data:
			logger.warning(f"No data retrieved for {ticker_symbol}")
			time.sleep(random.uniform(2.0, 4.0))  # nosec B311 - jitter
			return {}

		stats.api_successes += 1
		time.sleep(random.uniform(0.6, 1.2))  # nosec B311 - jitter
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
		# Directly call the SDK to ensure a real network request
		obb.equity.profile(symbol=ticker, provider="yfinance")
		return True
	except Exception as e:
		err_str = str(e).lower()
		if any(
			x in err_str
			for x in ["429", "rate limit", "401", "unauthorized", "invalid crumb"]
		):
			logger.warning(f"Rate-limit probe failed for {ticker}.")
			return False
		# For other errors, assume the API is at least reachable or it's a transient data error
		logger.debug(f"Probe encountered non-rate-limit error for {ticker}: {e}")
		return True


def fetch_batch_with_backoff(
	batch_tickers: List[str], current_cooldown: float, db_path: Optional[str] = None
) -> Tuple[bool, float, Dict[str, Dict[str, Any]]]:
	"""
	Attempt to fetch a batch of tickers with retry and backoff using adaptive probing.

	Args:
		batch_tickers: List of ticker symbols to fetch.
		current_cooldown: Current cooldown duration in seconds.
		db_path: Optional path to the database for dynamic settings refresh.

	Returns:
		Tuple of (success, new_cooldown, data_dict) where data_dict maps symbol to raw payload.
	"""
	import time

	# Refresh proxies if DB path provided (useful for worker processes)
	if db_path:
		try:
			from core.database.manager import DatabaseManager
			from core.database.repository import DatabaseRepository

			db = DatabaseManager(db_path, skip_auto_seed=True)
			repo = DatabaseRepository(db)
			proxy_manager.refresh_from_db(repo)
			db.close()
		except Exception as e:
			logger.warning(f"Failed to refresh proxies from DB in worker: {e}")

	base_cooldown = 5.0
	max_cooldown = 60.0

	for attempt in range(2):
		try:
			success, data = fetch_openbb_data_bulk(batch_tickers)
			if success:
				return True, base_cooldown, data

			logger.warning(f"Batch fetch failure. Attempt {attempt + 1}/2")

			# 1. Initial Cooldown
			logger.info(f"Entering {current_cooldown}s cooldown...")
			stats.record_cooldown(current_cooldown)
			time.sleep(current_cooldown)

			# 2. Probing mechanism: verify health before resuming bulk operations
			probe_ticker = batch_tickers[0]
			probe_attempts = 0
			max_probe_attempts = 10
			while not probe_api(probe_ticker):
				probe_attempts += 1
				if probe_attempts >= max_probe_attempts:
					logger.error(
						f"Max probe attempts ({max_probe_attempts}) reached for {probe_ticker}. Aborting batch."
					)
					return False, current_cooldown, {}

				current_cooldown = min(current_cooldown * 2, max_cooldown)
				logger.warning(
					f"Rate-limit probe failed for {probe_ticker}. Extending cooldown to {current_cooldown}s..."
				)
				stats.record_cooldown(current_cooldown)
				time.sleep(current_cooldown)

			# Success: increment cooldown for next attempt's safety and log success
			current_cooldown = min(current_cooldown * 2, max_cooldown)
			logger.info(f"Probe successful for {probe_ticker}. Resuming bulk fetch.")

		except Exception as e:
			logger.warning(f"Fetch error for {batch_tickers}: {e}")
			time.sleep(current_cooldown)
			current_cooldown = min(current_cooldown * 2, max_cooldown)
			break
	return False, current_cooldown, {}
