from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
import yfinance as yf

from core.database.repository import DatabaseRepository
from core.logger import get_logger

from .constituents import get_constituents
from .etf import get_etf_scraper

logger = get_logger(__name__)


def get_index_components(
	index_ticker: str, repo: Optional[DatabaseRepository] = None
) -> List[str]:
	"""
	Fetch components of an index or ETF.
	1. Checks DB for existing constituents (if repo provided).
		- If data is fresh (< 7 days), returns it.
		- If data is stale, continues to fetch fresh data.
	2. Checks if it's a major index (SP500, NASDAQ100, DOW) for full lists.
	3. Tries to use a provider-specific scraper for full holdings.
	4. Falls back to yfinance funds_data (Top 10) for other ETFs.
	Returns a list of ticker symbols.
	"""
	index_ticker = index_ticker.upper().strip()

	# 1. Try DB first with staleness check
	if repo:
		index_meta = repo.get_index(index_ticker)
		if index_meta and index_meta.get("last_updated"):
			last_updated = datetime.strptime(
				index_meta["last_updated"], "%Y-%m-%d %H:%M:%S"
			)
			if datetime.utcnow() - last_updated < timedelta(days=7):
				db_constituents = repo.get_index_constituents(index_ticker)
				if db_constituents:
					logger.info(
						"Found fresh constituents for %s in DB (updated %s)",
						index_ticker,
						index_meta["last_updated"],
					)
					return db_constituents
			else:
				logger.info(
					f"DB constituents for {index_ticker} are stale. Refreshing..."
				)

	# 2. Try major index full constituent fetching
	mapping = {
		"SP500": "sp500",
		"S&P500": "sp500",
		"NASDAQ100": "nasdaq100",
		"NDX100": "nasdaq100",
		"DOW": "dow",
		"DJIA": "dow",
	}

	constituents = []
	is_etf = True

	if index_ticker in mapping:
		is_etf = False
		constituents = get_constituents(mapping[index_ticker])

	# 3. Try Provider-Specific ETF Scrapers
	if not constituents:
		try:
			ticker_obj = yf.Ticker(index_ticker)
			fund_family = ticker_obj.info.get("fundFamily")
			scraper = get_etf_scraper(fund_family)

			if scraper:
				logger.info(f"Found scraper for {index_ticker} (Family: {fund_family})")
				constituents = scraper.get_holdings(index_ticker)
				if constituents:
					logger.info(
						f"Successfully fetched {len(constituents)} holdings for {index_ticker}"
					)

			# 4. Fallback to yfinance top holdings
			if not constituents:
				funds_data = ticker_obj.funds_data
				if funds_data is not None:
					top_holdings = funds_data.top_holdings
					if (
						isinstance(top_holdings, pd.DataFrame)
						and not top_holdings.empty
					):
						symbols = top_holdings.index.tolist()
						constituents = [
							str(s).upper() for s in symbols if s and isinstance(s, str)
						]
						logger.info(
							f"Fell back to yfinance top {len(constituents)} holdings for {index_ticker}"
						)
		except Exception as e:
			logger.warning(f"Error fetching ETF holdings for {index_ticker}: {e}")

	# 4. Save to DB if we found something OR if it was stale (to update timestamp)
	if repo:
		try:
			# If we have constituents, update them.
			# If we don't, we still update the index metadata to refresh last_updated
			repo.upsert_index(index_ticker, index_ticker, is_etf=is_etf)
			if constituents:
				repo.update_index_constituents(index_ticker, constituents)
				logger.info(
					f"Persisted {len(constituents)} constituents for {index_ticker} to DB"
				)
			else:
				# If refresh failed to find anything, clear constituents in DB
				# to avoid returning stale data next time
				repo.update_index_constituents(index_ticker, [])
		except Exception as e:
			logger.error(f"Failed to persist constituents to DB: {e}")

	return constituents if constituents else [index_ticker]
