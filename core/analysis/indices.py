from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import pandas as pd
import yfinance as yf

from core.database.repository import DatabaseRepository
from core.logger import get_logger

from .constituents import get_constituents
from .etf import get_etf_scraper

logger = get_logger(__name__)


def _get_from_db(
	index_ticker: str, repo: Optional[DatabaseRepository]
) -> Optional[List[str]]:
	"""Attempt to fetch constituents from the database if they are fresh."""
	if not repo:
		return None

	index_meta = repo.get_index(index_ticker)
	if not index_meta or not index_meta.get("last_updated"):
		return None

	last_updated = datetime.strptime(index_meta["last_updated"], "%Y-%m-%d %H:%M:%S")
	if datetime.utcnow() - last_updated < timedelta(days=7):
		db_constituents = repo.get_index_constituents(index_ticker)
		if db_constituents:
			logger.info(
				"Found fresh constituents for %s in DB (updated %s)",
				index_ticker,
				index_meta["last_updated"],
			)
			return db_constituents

	logger.info(
		f"DB constituents for {index_ticker} are stale or missing. Refreshing..."
	)
	return None


def _get_major_index_constituents(index_ticker: str) -> Tuple[List[str], bool]:
	"""Check if ticker is a major index and return constituents if so."""
	mapping = {
		"SP500": "sp500",
		"S&P500": "sp500",
		"NASDAQ100": "nasdaq100",
		"NDX100": "nasdaq100",
		"DOW": "dow",
		"DJIA": "dow",
	}

	if index_ticker in mapping:
		return get_constituents(mapping[index_ticker]), False
	return [], True


def _fetch_external_constituents(index_ticker: str) -> List[str]:
	"""Fetch constituents from external sources (scrapers or yfinance)."""
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
				return constituents

		# Fallback to yfinance top holdings
		funds_data = ticker_obj.funds_data
		if funds_data is not None and hasattr(funds_data, "top_holdings"):
			top_holdings = funds_data.top_holdings
			if isinstance(top_holdings, pd.DataFrame) and not top_holdings.empty:
				symbols = top_holdings.index.tolist()
				constituents = [
					str(s).upper() for s in symbols if s and isinstance(s, str)
				]
				logger.info(
					f"Fell back to yfinance top {len(constituents)} holdings for {index_ticker}"
				)
				return constituents
	except Exception as e:
		logger.warning(f"Error fetching ETF holdings for {index_ticker}: {e}")

	return []


def _save_to_db(
	index_ticker: str,
	constituents: List[str],
	is_etf: bool,
	repo: DatabaseRepository,
) -> None:
	"""Persist fetched constituents to the database."""
	try:
		repo.upsert_index(index_ticker, index_ticker, is_etf=is_etf)
		repo.update_index_constituents(index_ticker, constituents)
		if constituents:
			logger.info(
				f"Persisted {len(constituents)} constituents for {index_ticker} to DB"
			)
	except Exception as e:
		logger.error(f"Failed to persist constituents to DB: {e}")


def get_index_components(
	index_ticker: str, repo: Optional[DatabaseRepository] = None
) -> List[str]:
	"""
	Fetch components of an index or ETF.
	1. Checks DB for existing constituents (if repo provided).
	2. Checks if it's a major index (SP500, NASDAQ100, DOW) for full lists.
	3. Tries to use a provider-specific scraper for full holdings.
	4. Falls back to yfinance funds_data (Top 10) for other ETFs.
	Returns a list of ticker symbols.
	"""
	index_ticker = index_ticker.upper().strip()

	# 1. Try DB first
	db_constituents = _get_from_db(index_ticker, repo)
	if db_constituents:
		return db_constituents

	# 2. Try major index
	constituents, is_etf = _get_major_index_constituents(index_ticker)

	# 3. Try external sources
	if not constituents:
		constituents = _fetch_external_constituents(index_ticker)

	# 4. Save to DB
	if repo:
		_save_to_db(index_ticker, constituents, is_etf, repo)

	return constituents if constituents else [index_ticker]
