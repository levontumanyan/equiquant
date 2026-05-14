import json
import time
from io import StringIO
from typing import List

import pandas as pd
import requests

from config import ROOT_DIR
from core.logger import get_logger

logger = get_logger(__name__)

CONSTITUENTS_CACHE_DIR = ROOT_DIR / "cache" / "constituents"


def get_constituents(index_name: str) -> List[str]:
	"""
	Fetch all constituents for a major index (NASDAQ100, SP500, DOW).
	Uses a cached approach to avoid frequent scraping.
	"""
	index_name = index_name.lower().strip()
	cache_file = CONSTITUENTS_CACHE_DIR / f"{index_name}.json"

	# 1. Check Cache (1 week validity)
	if cache_file.exists() and (time.time() - cache_file.stat().st_mtime) < 604800:
		try:
			logger.info(f"Using cached constituents for {index_name}")
			return json.loads(cache_file.read_text())
		except Exception as e:
			logger.warning(f"Failed to read constituents cache for {index_name}: {e}")
			pass

	# 2. Fetch Fresh Data
	logger.info(f"Fetching fresh constituents for {index_name} from Wikipedia")
	tickers = []

	try:
		if index_name == "nasdaq100":
			tickers = _fetch_wikipedia_with_headers(
				"https://en.wikipedia.org/wiki/Nasdaq-100", "Ticker"
			)
		elif index_name == "sp500":
			tickers = _fetch_wikipedia_with_headers(
				"https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "Symbol"
			)
		elif index_name == "dow":
			tickers = _fetch_wikipedia_with_headers(
				"https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average", "Symbol"
			)
		else:
			logger.warning(
				f"Index '{index_name}' not supported for constituent fetching."
			)
			return []

		if tickers:
			tickers = [
				t.replace(".", "-").strip().upper()
				for t in tickers
				if isinstance(t, str)
			]
			tickers = sorted(list(set(tickers)))  # Deduplicate and sort

			CONSTITUENTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
			cache_file.write_text(json.dumps(tickers, indent="\t"))
			logger.info(
				f"Successfully cached {len(tickers)} constituents for {index_name}"
			)
			return tickers

	except Exception as e:
		logger.error(f"Error fetching constituents for {index_name}: {e}")

	return []


def _fetch_wikipedia_with_headers(url: str, column_name: str) -> List[str]:
	"""Helper to extract tickers from Wikipedia using standard Browser headers."""
	headers = {
		"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
	}
	response = requests.get(url, headers=headers, timeout=10)
	response.raise_for_status()

	# Wrap the content in StringIO for pandas
	html_content = StringIO(response.text)
	tables = pd.read_html(html_content, flavor="html5lib")

	for table in tables:
		if column_name in table.columns:
			return table[column_name].tolist()
	return []
