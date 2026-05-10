from unittest.mock import MagicMock, patch

from core.analysis.indices import get_index_components


def test_get_index_components_etf():
	# SPY is a well-known ETF, it should return top holdings (via scraper now if SSGA)
	components = get_index_components("SPY")
	assert len(components) > 1
	# SPY is SSGA, so it should use our new scraper
	assert any(t.isalpha() for t in components)


def test_get_index_components_with_scraper_mock():
	# Mock yfinance and the scraper factory
	with patch("yfinance.Ticker") as mock_yf:
		mock_yf.return_value.info = {"fundFamily": "State Street Investment Management"}

		with patch("core.analysis.indices.get_etf_scraper") as mock_factory:
			mock_scraper = MagicMock()
			mock_scraper.get_holdings.return_value = ["MOCK1", "MOCK2"]
			mock_factory.return_value = mock_scraper

			components = get_index_components("FAKE_SSGA_ETF")

	assert components == ["MOCK1", "MOCK2"]
	mock_scraper.get_holdings.assert_called_once_with("FAKE_SSGA_ETF")


def test_get_index_components_mutual_fund():
	# VFIAX is a mutual fund tracking S&P 500
	components = get_index_components("VFIAX")
	assert len(components) > 1
	assert "AAPL" in components or "MSFT" in components or "NVDA" in components


def test_get_index_components_fallback():
	# ^GSPC is an index, yfinance usually fails to give holdings via funds_data
	# It should return the ticker itself as fallback
	components = get_index_components("^GSPC")
	assert components == ["^GSPC"]


def test_get_index_components_major_index():
	# Test major index like SP500
	with patch("core.analysis.indices.get_constituents") as mock_get:
		mock_get.return_value = ["AAPL", "MSFT"]
		components = get_index_components("SP500")
	assert components == ["AAPL", "MSFT"]


def test_get_index_components_db_error():
	mock_repo = MagicMock()
	mock_repo.get_index.return_value = None
	mock_repo.upsert_index.side_effect = Exception("DB Error")

	# Should not raise exception, just log it
	components = get_index_components("SPY", repo=mock_repo)
	assert isinstance(components, list)
