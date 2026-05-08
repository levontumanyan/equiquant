import json
import random
import time
from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo

from config import CACHE_DIR
from core.logger import get_logger
from core.stats import stats
from core.utils.market import get_last_market_close, is_market_closed

logger = get_logger(__name__)


def get_openbb_data(ticker_symbol: str) -> Dict[str, Any]:
	"""
	Fetch standardized data via OpenBB Platform using multiple endpoints.
	Handles intelligent caching based on market hours.
	"""
	ticker_symbol = ticker_symbol.upper()
	cache_file = CACHE_DIR / f"{ticker_symbol}.json"

	# 1. Determine if we can use the cache
	use_cache = False
	if cache_file.exists():
		mtime = cache_file.stat().st_mtime
		age_seconds = time.time() - mtime

		# Condition A: Fresh cache (< 3 hours old)
		if age_seconds < 10800:
			use_cache = True
		# Condition B: Market is closed and cache was updated after the last market close
		else:
			now = datetime.now(ZoneInfo("UTC"))
			if is_market_closed(now):
				logger.info(
					f"Market is currently closed. Checking post-close cache for {ticker_symbol}"
				)
				last_close = get_last_market_close(now)
				cache_time = datetime.fromtimestamp(mtime, tz=ZoneInfo("UTC"))
				if cache_time > last_close:
					logger.info(
						f"Market closed; using post-close cache for {ticker_symbol}"
					)
					use_cache = True

	if use_cache:
		try:
			logger.info(f"Cache hit for {ticker_symbol}")
			stats.cache_hits += 1
			return json.loads(cache_file.read_text())
		except Exception as e:
			logger.warning(f"Failed to read cache for {ticker_symbol}: {e}")
			pass

	# Delayed import to speed up startup on cache hits
	from openbb import obb

	# 2. Fetch fresh data

	logger.info(f"Fetching fresh data for {ticker_symbol} from OpenBB")
	stats.api_calls += 1
	try:
		combined_data = {}
		provider = "yfinance"

		# Helper to merge OpenBB result into combined_data
		def merge_res(res):
			data = res.to_dict()
			if not data:
				return

			# If it's a dict of lists (standard metrics format)
			if isinstance(data, dict) and any(
				isinstance(v, list) for v in data.values()
			):
				for k, v in data.items():
					if isinstance(v, list) and len(v) > 0:
						combined_data[k] = v[0]
					else:
						combined_data[k] = v
			# If it's a list of dicts (standard profile/consensus format)
			elif isinstance(data, list) and len(data) > 0:
				combined_data.update(data[0])
			# If it's just a dict
			elif isinstance(data, dict):
				combined_data.update(data)

		# Endpoint 1: Fundamental Metrics (Stocks)
		try:
			merge_res(
				obb.equity.fundamental.metrics(symbol=ticker_symbol, provider=provider)
			)
		except Exception as e:
			logger.debug(f"Metrics fetch failed for {ticker_symbol}: {e}")

		# Endpoint 2: Company Profile (Stocks)
		try:
			merge_res(obb.equity.profile(symbol=ticker_symbol, provider=provider))
		except Exception as e:
			logger.debug(f"Profile fetch failed for {ticker_symbol}: {e}")

		# Endpoint 3: Analyst Consensus (Stocks)
		try:
			merge_res(
				obb.equity.estimates.consensus(symbol=ticker_symbol, provider=provider)
			)
		except Exception as e:
			logger.debug(f"Consensus fetch failed for {ticker_symbol}: {e}")

		# Endpoint 4: Ownership Statistics (Stocks)
		try:
			merge_res(
				obb.equity.ownership.share_statistics(
					symbol=ticker_symbol, provider=provider
				)
			)
		except Exception as e:
			logger.debug(f"Ownership fetch failed for {ticker_symbol}: {e}")

		# Endpoint 5: ETF Info (if above fails or it is an ETF)
		if (
			not combined_data
			or "fund_family" in str(combined_data)
			or not combined_data.get("name")
		):
			try:
				merge_res(obb.etf.info(symbol=ticker_symbol, provider=provider))
			except Exception as e:
				logger.debug(f"ETF info fetch failed for {ticker_symbol}: {e}")

		if not combined_data:
			logger.warning(f"No data retrieved for {ticker_symbol}")
			# Still sleep to avoid hammering on consecutive failures
			time.sleep(random.uniform(1.0, 2.0))
			return {}

		# Save to cache
		CACHE_DIR.mkdir(parents=True, exist_ok=True)
		cache_file.write_text(json.dumps(combined_data, default=str, indent="\t"))

		# Record success
		stats.api_successes += 1

		# Light rate limiting
		time.sleep(random.uniform(0.6, 1.1))
		return combined_data

	except Exception as e:
		logger.error(f"OpenBB overall error for {ticker_symbol}: {e}")
		stats.errors += 1
		return {}
