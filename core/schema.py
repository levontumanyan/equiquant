from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class AssetType(Enum):
	STOCK = "STOCK"
	ETF = "ETF"
	INDEX = "INDEX"
	UNKNOWN = "UNKNOWN"


@dataclass
class AssetData:
	symbol: str
	asset_type: AssetType = AssetType.UNKNOWN
	name: Optional[str] = None
	sector: Optional[str] = None
	industry: Optional[str] = None
	metrics: Dict[str, Any] = field(default_factory=dict)
	sources: Dict[str, str] = field(default_factory=dict)
	raw_data: Dict[str, Any] = field(default_factory=dict)

	def get(self, key: str, default: Any = None) -> Any:
		"""
		Helper to get a metric or metadata field.
		Checks metrics first, then raw_data, then attributes.
		"""
		if key in self.metrics:
			return self.metrics[key]
		if key in self.raw_data:
			return self.raw_data[key]
		return getattr(self, key, default)

	@property
	def display_name(self) -> str:
		return self.name or self.symbol

	def merge(self, other: "AssetData", provider_name: str, overwrite: bool = False):
		"""
		Merge another AssetData into this one.

		Args:
			other: The AssetData to merge from.
			provider_name: The name of the provider providing the new data.
			overwrite: Whether to overwrite existing metrics.
		"""
		if not self.name and other.name:
			self.name = other.name
		if (
			self.asset_type == AssetType.UNKNOWN
			and other.asset_type != AssetType.UNKNOWN
		):
			self.asset_type = other.asset_type
		if not self.sector and other.sector:
			self.sector = other.sector
		if not self.industry and other.industry:
			self.industry = other.industry

		for k, v in other.metrics.items():
			if overwrite or k not in self.metrics or self.metrics[k] is None:
				self.metrics[k] = v
				self.sources[k] = provider_name

		# Merge raw data (keep it flat to avoid breaking consumers)
		if other.raw_data and isinstance(other.raw_data, dict):
			for k, v in other.raw_data.items():
				# Only overwrite if new value is not None or if current value is None
				if v is not None or k not in self.raw_data:
					self.raw_data[k] = v
