import unittest
from unittest.mock import MagicMock, patch

from core.providers.sec_provider import SECProvider
from core.schema import AssetType


class TestSECProvider(unittest.TestCase):
	def setUp(self):
		self.repo = MagicMock()
		self.provider = SECProvider(repo=self.repo)

	@patch("requests.get")
	def test_fetch_company_facts_success(self, mock_get):
		mock_response = MagicMock()
		mock_response.json.return_value = {"facts": {"us-gaap": {}}}
		mock_response.status_code = 200
		mock_get.return_value = mock_response

		facts = self.provider.fetch_company_facts("0000320193")
		self.assertIn("facts", facts)
		mock_get.assert_called_once()

	def test_normalize_basic(self):
		facts = {
			"entityName": "Apple Inc.",
			"facts": {
				"us-gaap": {"NetIncomeLoss": {"units": {"USD": [{"val": 1000}]}}}
			},
		}
		asset = self.provider._normalize("AAPL", facts)
		self.assertEqual(asset.symbol, "AAPL")
		self.assertEqual(asset.name, "Apple Inc.")
		self.assertEqual(asset.metrics["net_income"], 1000)
		self.assertEqual(asset.asset_type, AssetType.STOCK)

	@patch("core.providers.sec_provider.get_cik")
	def test_get_data_no_cik(self, mock_get_cik):
		mock_get_cik.return_value = None
		data = self.provider.get_data("UNKNOWN")
		self.assertIsNone(data)


if __name__ == "__main__":
	unittest.main()
