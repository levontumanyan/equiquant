#!/usr/bin/env python3
"""
Migration: backfill raw_provider_data from existing file cache.

Reads all JSON files from CACHE_DIR (yfinance) and upserts them into the
raw_provider_data table. Safe to re-run; uses ON CONFLICT DO UPDATE.
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import CACHE_DIR
from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROVIDER = "yfinance"


def run_migration(db_path: str = "market_analysis.db") -> None:
	"""
	Backfill raw_provider_data from the local yfinance file cache.

	Args:
		db_path: Path to the SQLite database file.
	"""
	db_manager = DatabaseManager(db_path)
	repo = DatabaseRepository(db_manager)

	cache_files = list(CACHE_DIR.glob("*.json"))
	if not cache_files:
		logger.warning(f"No cache files found in {CACHE_DIR}")
		return

	logger.info(f"Found {len(cache_files)} cached files to migrate")
	success = 0
	skipped = 0

	for cache_file in cache_files:
		symbol = cache_file.stem.upper()
		try:
			data = json.loads(cache_file.read_text())
			if not data or len(data) <= 1:
				skipped += 1
				continue
			repo.upsert_raw_provider_data(symbol, PROVIDER, data)
			success += 1
		except Exception as e:
			logger.warning(f"Skipping {symbol}: {e}")
			skipped += 1

	logger.info(f"Migration complete: {success} upserted, {skipped} skipped")
	db_manager.close()


if __name__ == "__main__":
	db_arg = sys.argv[1] if len(sys.argv) > 1 else "market_analysis.db"
	run_migration(db_arg)
