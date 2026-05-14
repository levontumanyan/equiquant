from typing import Optional

from core.openbb_client import get_openbb_data, load_cached_data
from core.schema import AssetData, AssetType

from .base import BaseProvider


class OpenBBProvider(BaseProvider):
	def _normalize(self, symbol: str, raw_data: dict) -> AssetData:
		asset_type = AssetType.STOCK
		if "fund_family" in raw_data or "nav_price" in raw_data:
			asset_type = AssetType.ETF
		elif raw_data.get("issue_type") == "etf":
			asset_type = AssetType.ETF

		return AssetData(
			symbol=raw_data.get("symbol", symbol),
			asset_type=asset_type,
			name=raw_data.get("name") or raw_data.get("long_name"),
			sector=raw_data.get("sector"),
			industry=raw_data.get("industry_category"),
			metrics=raw_data,
			raw_data=raw_data,
		)

	def get_data(self, symbol: str) -> Optional[AssetData]:
		raw_data = get_openbb_data(symbol)
		if not raw_data or "symbol" not in raw_data:
			return None
		return self._normalize(symbol, raw_data)

	def get_cached_data(self, symbol: str) -> Optional[AssetData]:
		raw_data = load_cached_data(symbol)
		if not raw_data or "symbol" not in raw_data:
			return None
		return self._normalize(symbol, raw_data)
