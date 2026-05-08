from typing import Optional

from .base import ETFHoldingsScraper
from .ssga import SSGAScraper


def get_etf_scraper(fund_family: str) -> Optional[ETFHoldingsScraper]:
	"""
	Factory method to return the appropriate ETF holdings scraper
	based on the fund family name returned by yfinance.
	"""
	if not fund_family:
		return None

	# Normalization for more robust matching
	family = fund_family.lower()

	if "state street" in family or "spdr" in family:
		return SSGAScraper()

	# Add future providers here
	# if "vanguard" in family:
	#     return VanguardScraper()
	# if "blackrock" in family or "ishares" in family:
	#     return ISharesScraper()

	return None
