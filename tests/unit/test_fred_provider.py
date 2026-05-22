import unittest
from unittest.mock import MagicMock, patch

from core.providers.fred_provider import FREDProvider
from core.schema import AssetType


class TestFREDProvider(unittest.TestCase):
	def setUp(self):
		self.provider = FREDProvider()
		self.provider.api_key = "test_api_key"

	@patch("requests.get")
	def test_fetch_series_success(self, mock_get):
		# Mock response for 10Y Treasury Yield
		mock_response = MagicMock()
		mock_response.json.return_value = {"observations": [{"value": "4.25"}]}
		mock_response.status_code = 200
		mock_get.return_value = mock_response

		val = self.provider.fetch_series("DGS10")
		self.assertEqual(val, 4.25)
		mock_get.assert_called_once()

	@patch("requests.get")
	def test_get_macro_snapshot(self, mock_get):
		# Mock response for multiple series
		mock_response = MagicMock()
		mock_response.json.return_value = {"observations": [{"value": "1.5"}]}
		mock_response.status_code = 200
		mock_get.return_value = mock_response

		data = self.provider.get_macro_snapshot()
		self.assertEqual(data.symbol, "MACRO")
		self.assertEqual(data.asset_type, AssetType.INDEX)
		# Should have all metrics from SERIES_MAP
		self.assertTrue(len(data.metrics) > 0)
		self.assertEqual(data.metrics.get("10y_treasury_yield"), 1.5)


if __name__ == "__main__":
	unittest.main()
