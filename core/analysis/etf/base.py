from abc import ABC, abstractmethod
from typing import List


class ETFHoldingsScraper(ABC):
	"""
	Abstract base class for ETF holdings scrapers.
	Each provider (SSGA, iShares, Vanguard, etc.) will implement this.
	"""

	@abstractmethod
	def get_holdings(self, ticker: str) -> List[str]:
		"""
		Fetch 100% of the holdings for a given ETF ticker.
		Returns a list of ticker symbols.
		"""
		pass
