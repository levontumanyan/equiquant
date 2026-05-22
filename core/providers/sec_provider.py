import logging
from typing import Any, Dict, Optional

import requests

from core.database.repository import DatabaseRepository
from core.providers.base import BaseProvider
from core.schema import AssetData, AssetType
from core.utils.rate_limit import rate_limit_manager
from core.utils.sec import get_cik

logger = logging.getLogger(__name__)


class SECProvider(BaseProvider):
	"""
	Data provider for SEC EDGAR XBRL facts.
	Fetches raw fundamental data directly from the SEC.
	"""

	def __init__(self, repo: Optional[DatabaseRepository] = None):
		super().__init__(priority=1)  # High priority for fundamentals
		self.repo = repo
		self.user_agent = self._get_user_agent()

	def _get_user_agent(self) -> str:
		# Circular import safety: get from environment if possible,
		# or use a dedicated utility that doesn't depend on the full DB repo
		from core.utils.sec import _get_user_agent

		ua = _get_user_agent(self.repo)
		# Handle placeholders or empty strings
		# Rejecting only explicit placeholder or empty
		if not ua or "your_email" in ua.lower():
			return ""
		return ua

	@property
	def is_configured(self) -> bool:
		"""Check if the provider is correctly configured."""
		return bool(self.user_agent)

	def fetch_company_facts(self, cik: str) -> Dict[str, Any]:
		"""
		Fetch raw XBRL company facts from data.sec.gov.
		"""
		if not self.is_configured:
			return {}

		rate_limit_manager.get_bucket("sec").wait_for_token()
		url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
		headers = {"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"}

		try:
			response = requests.get(url, headers=headers, timeout=15)
			response.raise_for_status()
			return response.json()
		except Exception as e:
			logger.error(f"Failed to fetch SEC facts for CIK {cik}: {e}")
			return {}

	def _normalize(self, symbol: str, facts: Dict[str, Any]) -> AssetData:
		"""
		Normalize SEC XBRL facts into the AssetData schema.
		"""
		# For now, we'll store the raw facts in raw_data and a selection in metrics
		metrics = {}

		# Example mapping for common GAAP tags
		# The structure is: facts -> taxonomy (us-gaap) -> tag -> units -> USD -> list of values
		us_gaap = facts.get("facts", {}).get("us-gaap", {})

		target_metrics = {
			"NetIncomeLoss": "net_income",
			"Revenues": "revenue",
			"OperatingIncomeLoss": "operating_income",
			"Assets": "total_assets",
			"Liabilities": "total_liabilities",
			"StockholdersEquity": "equity",
			"CommonStockSharesOutstanding": "shares_outstanding",
		}

		for tag, metric_key in target_metrics.items():
			data = us_gaap.get(tag, {}).get("units", {}).get("USD") or us_gaap.get(
				tag, {}
			).get("units", {}).get("shares")

			if data:
				# Use the most recent value
				latest = data[-1]["val"]
				metrics[metric_key] = latest

		return AssetData(
			symbol=symbol,
			asset_type=AssetType.STOCK,  # SEC is primarily for stocks
			name=facts.get("entityName"),
			metrics=metrics,
			raw_data=facts,
		)

	def get_data(self, symbol: str) -> Optional[AssetData]:
		"""
		Fetch and normalize SEC data for a given ticker.
		"""
		if not self.is_configured:
			return None

		cik = get_cik(symbol, self.repo)
		if not cik:
			logger.warning(f"No CIK found for {symbol}")
			return None

		facts = self.fetch_company_facts(cik)
		if not facts or "facts" not in facts:
			return None

		return self._normalize(symbol, facts)
