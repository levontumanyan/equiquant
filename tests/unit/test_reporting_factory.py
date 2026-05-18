import os

from core.reporting.factory import generate_report
from core.schema import AssetType


def test_generate_report_single_ticker(tmp_path):
	results = [
		{
			"symbol": "AAPL",
			"name": "Apple Inc.",
			"asset_type": AssetType.STOCK,
			"score": 85.5,
			"results": [],
			"benchmark_defs": {},
		}
	]

	reports_dir = tmp_path / "reports"
	output_path = generate_report(results, "csv", ["AAPL"], base_dir=str(reports_dir))

	assert os.path.exists(output_path)
	assert "equiquant-analysis-aapl-balanced" in os.path.basename(output_path)
	assert output_path.endswith(".csv")


def test_generate_report_index(tmp_path):
	results = [
		{
			"symbol": "AAPL",
			"name": "Apple Inc.",
			"asset_type": AssetType.STOCK,
			"score": 85.5,
			"results": [],
			"benchmark_defs": {},
		}
	]

	reports_dir = tmp_path / "reports"
	output_path = generate_report(
		results, "txt", ["AAPL", "MSFT"], index_name="VOO", base_dir=str(reports_dir)
	)

	assert os.path.exists(output_path)
	assert "equiquant-analysis-voo-balanced" in os.path.basename(output_path)
	assert output_path.endswith(".txt")


def test_generate_report_portfolio(tmp_path):
	results = [
		{
			"symbol": "AAPL",
			"name": "Apple Inc.",
			"asset_type": AssetType.STOCK,
			"score": 85.5,
			"results": [],
			"benchmark_defs": {},
		}
	]

	reports_dir = tmp_path / "reports"
	output_path = generate_report(
		results, "csv", ["AAPL", "MSFT", "GOOGL"], base_dir=str(reports_dir)
	)

	assert os.path.exists(output_path)
	assert "equiquant-analysis-portfolio-3-balanced" in os.path.basename(output_path)
	assert output_path.endswith(".csv")
