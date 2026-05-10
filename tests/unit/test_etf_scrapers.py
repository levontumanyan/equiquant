from unittest.mock import MagicMock, patch

from core.analysis.etf.factory import get_etf_scraper
from core.analysis.etf.ssga import SSGAScraper


def test_ssga_scraper_parse_csv():
	scraper = SSGAScraper()
	csv_content = """Header1,Header2,Header3
Metadata,Metadata,Metadata
Metadata,Metadata,Metadata
Metadata,Metadata,Metadata
Ticker,Name,Weight
AAPL,Apple Inc,5.0
MSFT,Microsoft Corp,4.0
INVALID,Invalid Asset,1.0
"""
	with patch("requests.get") as mock_get:
		mock_get.return_value.status_code = 200
		mock_get.return_value.text = csv_content

		# Force CSV by making XLSX fail
		with patch.object(SSGAScraper, "_parse_xlsx", return_value=[]):
			holdings = scraper.get_holdings("SPY")

	assert "AAPL" in holdings
	assert "MSFT" in holdings
	assert len(holdings) >= 2


def test_factory_routing():
	# Test known family
	scraper = get_etf_scraper("State Street Investment Management")
	assert isinstance(scraper, SSGAScraper)

	# Test normalization
	scraper = get_etf_scraper("SPDR Funds")
	assert isinstance(scraper, SSGAScraper)

	# Test unknown family
	scraper = get_etf_scraper("Unknown Family")
	assert scraper is None


def test_ssga_scraper_all_fail():
	scraper = SSGAScraper()
	with patch("requests.get") as mock_get:
		mock_get.return_value.status_code = 404
		holdings = scraper.get_holdings("INVALID_ETF")
	assert holdings == []


def test_ssga_scraper_xlsx_parsing_error():
	scraper = SSGAScraper()
	with patch("requests.get") as mock_get:
		mock_get.return_value.status_code = 200
		mock_get.return_value.content = b"not an excel file"

		# Fallback to CSV should happen if XLSX parsing fails
		with patch.object(SSGAScraper, "_parse_csv") as mock_parse_csv:
			mock_parse_csv.return_value = ["TICKER1"]
			holdings = scraper.get_holdings("SPY")

	assert "TICKER1" in holdings


def test_extract_with_dynamic_header_no_match():
	import pandas as pd

	scraper = SSGAScraper()
	df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
	holdings = scraper._extract_with_dynamic_header(df)
	assert holdings == []


def test_ssga_scraper_csv_fail():
	scraper = SSGAScraper()
	with patch("requests.get") as mock_get:
		# XLSX fails with 404
		mock_get.side_effect = [
			MagicMock(status_code=404),  # XLSX
			MagicMock(status_code=404),  # CSV
		]
		holdings = scraper.get_holdings("SPY")
	assert holdings == []


def test_ssga_scraper_csv_exception():
	scraper = SSGAScraper()
	with patch("requests.get") as mock_get:
		# XLSX fails with 404
		mock_get.side_effect = [
			MagicMock(status_code=404),  # XLSX
			Exception("Network Error"),  # CSV
		]
		holdings = scraper.get_holdings("SPY")
	assert holdings == []
