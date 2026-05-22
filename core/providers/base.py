from abc import ABC, abstractmethod
from typing import Optional

from core.schema import AssetData


class BaseProvider(ABC):
	def __init__(self, priority: int = 10):
		self.priority = priority

	@abstractmethod
	def get_data(self, symbol: str) -> Optional[AssetData]:
		"""Fetch and return normalized AssetData."""
		pass
