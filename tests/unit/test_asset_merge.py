import unittest

from core.schema import AssetData


class TestAssetDataMerge(unittest.TestCase):
	def test_merge_metrics(self):
		asset1 = AssetData(
			symbol="AAPL",
			metrics={"price": 150, "revenue": 1000},
			sources={"price": "yfinance", "revenue": "yfinance"},
		)

		asset2 = AssetData(
			symbol="AAPL",
			metrics={"revenue": 1100, "net_income": 200},
			sources={"revenue": "sec", "net_income": "sec"},
		)

		# Merge asset2 into asset1
		asset1.merge(asset2, provider_name="sec", overwrite=True)

		self.assertEqual(asset1.metrics["revenue"], 1100)  # Overwritten
		self.assertEqual(asset1.metrics["price"], 150)  # Preserved
		self.assertEqual(asset1.metrics["net_income"], 200)  # Added

		self.assertEqual(asset1.sources["revenue"], "sec")
		self.assertEqual(asset1.sources["price"], "yfinance")

	def test_merge_metadata(self):
		asset1 = AssetData(symbol="AAPL", name=None)
		asset2 = AssetData(symbol="AAPL", name="Apple Inc.")

		asset1.merge(asset2, provider_name="sec")
		self.assertEqual(asset1.name, "Apple Inc.")


if __name__ == "__main__":
	unittest.main()
