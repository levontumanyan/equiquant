import logging
import os
from typing import Optional

import requests

from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository
from core.providers.base import BaseProvider
from core.schema import AssetData, AssetType
from core.utils.rate_limit import rate_limit_manager

logger = logging.getLogger(__name__)


class FREDProvider(BaseProvider):
	"""
	Data provider for Federal Reserve Economic Data (FRED).
	Fetches macroeconomic indicators.
	"""

	# Key Series IDs
	SERIES_MAP = {
		"DGS10": "10y_treasury_yield",
		"FEDFUNDS": "fed_funds_rate",
		"CPIAUCSL": "cpi_inflation",
		"GDP": "gdp",
		"UNRATE": "unemployment_rate",
		"M2SL": "m2_money_supply",
		"SP500": "sp500_index",
		"T10Y2Y": "yield_curve_spread",
	}

	def __init__(self, repo: Optional[DatabaseRepository] = None):
		super().__init__(priority=5)  # Medium-high priority for macro
		self.repo = repo
		self.api_key = self._get_api_key()

	def _get_api_key(self) -> Optional[str]:
		"""Retrieve the FRED API key from the database or environment."""
		key = None
		try:
			if self.repo:
				key = self.repo.get_setting("fred_api_key")
			else:
				db_path = os.environ.get("DB_PATH", "market_analysis.db")
				db = DatabaseManager(db_path, skip_auto_seed=True)
				repo = DatabaseRepository(db)
				key = repo.get_setting("fred_api_key")
				db.close()
		except Exception as e:
			logger.debug(f"Failed to get FRED API key from DB: {e}")

		if not key:
			key = os.environ.get("FRED_API_KEY")

		# Handle placeholders or empty strings
		if key in (None, "", "your_fred_api_key_here"):
			return None

		return key

	@property
	def is_configured(self) -> bool:
		"""Check if the provider is correctly configured."""
		return bool(self.api_key)

	def fetch_series(self, series_id: str) -> Optional[float]:
		"""
		Fetch the latest value for a specific FRED series.
		"""
		if not self.is_configured:
			return None

		rate_limit_manager.get_bucket("fred").wait_for_token()
		url = "https://api.stlouisfed.org/fred/series/observations"
		params = {
			"series_id": series_id,
			"api_key": self.api_key,
			"file_type": "json",
			"sort_order": "desc",
			"limit": 1,
		}

		try:
			response = requests.get(url, params=params, timeout=10)
			response.raise_for_status()
			data = response.json()
			observations = data.get("observations", [])
			if observations:
				val = observations[0].get("value")
				if val and val != ".":
					return float(val)
		except Exception as e:
			logger.error(f"Failed to fetch FRED series {series_id}: {e}")

		return None

	def get_macro_snapshot(self) -> AssetData:
		"""
		Fetch a comprehensive snapshot of key macroeconomic indicators.
		"""
		metrics = {}
		for series_id, metric_key in self.SERIES_MAP.items():
			val = self.fetch_series(series_id)
			if val is not None:
				metrics[metric_key] = val

		return AssetData(
			symbol="MACRO",
			asset_type=AssetType.INDEX,
			name="Macroeconomic Indicators",
			metrics=metrics,
		)

	def get_data(self, symbol: str) -> Optional[AssetData]:
		"""
		FRED doesn't usually fetch by stock ticker.
		If symbol is 'MACRO', return the full snapshot.
		Otherwise, try to find a matching series ID.
		"""
		symbol = symbol.upper()
		if symbol == "MACRO":
			return self.get_macro_snapshot()

		# If it looks like a Series ID, try to fetch it
		val = self.fetch_series(symbol)
		if val is not None:
			return AssetData(
				symbol=symbol, asset_type=AssetType.INDEX, metrics={symbol.lower(): val}
			)

		return None
