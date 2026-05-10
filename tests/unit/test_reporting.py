from core.reporting.csv_reporter import CSVReporter
from core.reporting.txt_reporter import TXTReporter
from core.schema import AssetType


def test_csv_reporter_export(tmp_path):
	output_path = tmp_path / "report.csv"
	reporter = CSVReporter()

	results = [
		{
			"symbol": "AAPL",
			"name": "Apple Inc.",
			"asset_type": AssetType.STOCK,
			"score": 85.5,
			"results": [
				{"name": "P/E Ratio", "value": "30.0x", "status": "80%"},
				{"name": "ROE", "value": "150%", "status": "100%"},
			],
		}
	]

	reporter.export(results, str(output_path))

	assert output_path.exists()
	content = output_path.read_text()
	assert "AAPL" in content
	assert "Apple Inc." in content
	assert "85.5" in content
	assert "P/E Ratio" in content


def test_txt_reporter_export(tmp_path):
	output_path = tmp_path / "report.txt"
	reporter = TXTReporter()

	results = [
		{
			"symbol": "AAPL",
			"name": "Apple Inc.",
			"asset_type": AssetType.STOCK,
			"score": 85.5,
			"results": [
				{
					"name": "P/E Ratio",
					"value": "30.0x",
					"status": "80%",
					"score": 1.6,
					"weight": 2.0,
				}
			],
		}
	]

	reporter.export(results, str(output_path))

	assert output_path.exists()
	content = output_path.read_text()
	assert "Analysis for Apple Inc. (AAPL)" in content
	assert "85.5" in content
