from io import BytesIO
from typing import List

import pandas as pd
import requests

from core.logger import get_logger

from .base import ETFHoldingsScraper

logger = get_logger(__name__)


class SSGAScraper(ETFHoldingsScraper):
	"""
	Scraper for State Street Global Advisors (SPDR) ETFs.
	Downloads official holdings files from ssga.com.
	"""

	BASE_URL = "https://www.ssga.com/us/en/intermediary/etfs/library-content/products/fund-data/etfs/us/holdings-daily-us-en-{ticker}.xlsx"
	CSV_URL = "https://www.ssga.com/us/en/intermediary/etfs/library-content/products/fund-data/etfs/us/holdings-daily-us-en-{ticker}.csv"

	def get_holdings(self, ticker: str) -> List[str]:
		ticker = ticker.lower().strip()
		headers = {
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
		}

		# Try XLSX first
		url = self.BASE_URL.format(ticker=ticker)
		holdings = []
		try:
			logger.info(
				f"Attempting to fetch SSGA holdings for {ticker.upper()} via XLSX"
			)
			response = requests.get(url, headers=headers, timeout=15)
			if response.status_code == 200:
				holdings = self._parse_xlsx(response.content)

			if holdings:
				return holdings

			logger.warning(
				f"XLSX fetch returned no holdings for {ticker.upper()}. Trying CSV..."
			)
		except Exception as e:
			logger.warning(f"Error fetching XLSX for {ticker.upper()}: {e}")

		# Fallback to CSV
		url = self.CSV_URL.format(ticker=ticker)
		try:
			logger.info(
				f"Attempting to fetch SSGA holdings for {ticker.upper()} via CSV"
			)
			response = requests.get(url, headers=headers, timeout=15)
			if response.status_code == 200:
				return self._parse_csv(response.text)
			else:
				logger.error(
					f"CSV fetch failed for {ticker.upper()} (Status: {response.status_code})"
				)
		except Exception as e:
			logger.error(f"Error fetching CSV for {ticker.upper()}: {e}")

		return []

	def _parse_xlsx(self, content: bytes) -> List[str]:
		"""Parse SSGA Excel file."""
		try:
			# Load without skipping to find the header
			df_raw = pd.read_excel(BytesIO(content))
			return self._extract_with_dynamic_header(df_raw)
		except Exception as e:
			logger.error(f"Failed to parse SSGA XLSX: {e}")
			return []

	def _parse_csv(self, text: str) -> List[str]:
		"""Parse SSGA CSV file."""
		try:
			from io import StringIO

			df_raw = pd.read_csv(StringIO(text))
			return self._extract_with_dynamic_header(df_raw)
		except Exception as e:
			logger.error(f"Failed to parse SSGA CSV: {e}")
			return []

	def _extract_with_dynamic_header(self, df_raw: pd.DataFrame) -> List[str]:
		"""Find the header row dynamically and extract tickers."""
		ticker_cols = {"Ticker", "Symbol", "Identifier"}

		# 1. Check if current columns match
		if any(col in df_raw.columns for col in ticker_cols):
			return self._extract_tickers(df_raw)

		# 2. Iterate through rows to find the one that looks like a header
		for i, row in df_raw.iterrows():
			row_values = [str(v).strip() for v in row.values if v is not None]
			if any(col in row_values for col in ticker_cols):
				# Found the header row! Re-align dataframe
				new_header = row_values
				df_new = df_raw.iloc[i + 1 :].copy()
				df_new.columns = new_header
				return self._extract_tickers(df_new)

		logger.warning("Could not find dynamic header in SSGA file")
		return []

	def _extract_tickers(self, df: pd.DataFrame) -> List[str]:
		"""Common logic to extract tickers from SSGA dataframe."""
		# Potential column names for tickers
		ticker_cols = ["Ticker", "Symbol", "Identifier"]

		for col in ticker_cols:
			if col in df.columns:
				tickers = df[col].dropna().astype(str).tolist()
				# Clean up tickers (remove whitespace, uppercase)
				cleaned = [
					t.strip().upper() for t in tickers if t and isinstance(t, str)
				]
				# Remove metadata/header-like entries if they leaked in
				return [t for t in cleaned if t.isalpha() and len(t) <= 6]

		logger.warning("Could not find ticker column in SSGA file")
		return []
