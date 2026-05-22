import datetime
import logging
import os
from typing import Optional

import requests

from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository

logger = logging.getLogger(__name__)

CACHE_TTL_DAYS = 7


def _get_user_agent(repo: Optional[DatabaseRepository] = None) -> str:
	"""
	Retrieve the mandatory SEC User-Agent from the database or environment.
	"""
	if repo:
		ua = repo.get_setting("sec_user_agent")
		if ua:
			return ua

	return os.environ.get("SEC_USER_AGENT", "Equiquant admin@equiquant.com")


def sync_cik_mapping(repo: DatabaseRepository) -> bool:
	"""
	Download the latest ticker-to-CIK mapping from the SEC and sync to the DB.

	Returns:
		True if successful, False otherwise.
	"""
	url = "https://www.sec.gov/files/company_tickers.json"
	headers = {"User-Agent": _get_user_agent(repo), "Accept-Encoding": "gzip, deflate"}

	try:
		logger.info("Downloading SEC ticker-to-CIK mapping...")
		response = requests.get(url, headers=headers, timeout=10)
		response.raise_for_status()

		data = response.json()
		# SEC format is { "0": { "cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc." }, ... }
		mappings = []
		for entry in data.values():
			mappings.append(
				{
					"ticker": entry["ticker"].upper(),
					"cik": str(entry["cik_str"]).zfill(10),
					"title": entry["title"],
				}
			)

		logger.info(f"Syncing {len(mappings)} mappings to database...")
		repo.bulk_upsert_cik_mappings(mappings)
		return True
	except Exception as e:
		logger.error(f"Failed to sync SEC ticker mapping: {e}")
		return False


def get_cik(ticker: str, repo: Optional[DatabaseRepository] = None) -> Optional[str]:
	"""
	Resolve a ticker symbol to its SEC Central Index Key (CIK) via the database.
	Automatically triggers a sync if the database mapping is missing or expired.

	Args:
		ticker: The stock ticker symbol (e.g., 'AAPL').
		repo: Optional database repository. If not provided, one will be created.

	Returns:
		The 10-digit padded CIK string, or None if not found.
	"""
	ticker = ticker.upper().strip()

	# Handle repo initialization if not provided
	owns_repo = False
	if not repo:
		db_path = os.environ.get("DB_PATH", "market_analysis.db")
		db = DatabaseManager(db_path, skip_auto_seed=True)
		repo = DatabaseRepository(db)
		owns_repo = True

	try:
		# Check if we have data and if it's fresh
		count = repo.get_cik_mapping_count()
		last_updated = repo.get_cik_last_updated()

		should_sync = count == 0
		if not should_sync and last_updated:
			try:
				dt = datetime.datetime.fromisoformat(last_updated.replace(" ", "T"))
				elapsed = (datetime.datetime.utcnow() - dt).days
				if elapsed >= CACHE_TTL_DAYS:
					should_sync = True
			except Exception:
				should_sync = True

		if should_sync:
			sync_cik_mapping(repo)

		return repo.get_cik(ticker)
	finally:
		if owns_repo:
			repo.db.close()
