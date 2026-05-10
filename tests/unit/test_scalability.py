from core.io.parsers import parse_ticker_file
from core.orchestrator import analyze_asset
from core.providers.openbb_provider import OpenBBProvider
from core.schema import AssetData, AssetType


def test_analyze_asset_routing(mocker):
	# Mock get_stock_data to return an ETF
	etf_asset = AssetData(symbol="SPY", asset_type=AssetType.ETF)
	mocker.patch("core.orchestrator.get_stock_data", return_value=etf_asset)

	# Mock load_benchmarks and get_profile_weights
	mocker.patch(
		"core.orchestrator.load_benchmarks",
		return_value=[
			{"metric": "test", "weight": 1.0, "type": "threshold", "threshold": 0}
		],
	)
	mocker.patch("core.orchestrator.get_profile_weights", return_value={"test": 1.0})
	mocker.patch(
		"core.orchestrator.evaluate_metric", return_value={"score": 1.0, "weight": 1.0}
	)

	result = analyze_asset("SPY", "balanced")
	assert result["asset_type"] == AssetType.ETF
	assert result["symbol"] == "SPY"


def test_asset_data_schema():
	asset = AssetData(
		symbol="AAPL",
		asset_type=AssetType.STOCK,
		name="Apple Inc.",
		metrics={"pe": 30},
		raw_data={"sector": "Technology"},
	)
	assert asset.symbol == "AAPL"
	assert asset.get("pe") == 30
	assert asset.get("sector") == "Technology"
	assert asset.get("non_existent", "default") == "default"
	assert asset.display_name == "Apple Inc."


def test_asset_data_default_display_name():
	asset = AssetData(symbol="MSFT")
	assert asset.display_name == "MSFT"


def test_openbb_provider_mapping(mocker):
	mock_raw_data = {
		"symbol": "SPY",
		"name": "SPDR S&P 500 ETF Trust",
		"pe_ratio": 25.0,
		"dividend_yield": 0.015,
		"fund_family": "SPDR",
	}
	mocker.patch(
		"core.providers.openbb_provider.get_openbb_data", return_value=mock_raw_data
	)

	provider = OpenBBProvider()
	asset = provider.get_data("SPY")

	assert asset is not None
	assert asset.symbol == "SPY"
	assert asset.asset_type == AssetType.ETF
	assert asset.metrics["pe_ratio"] == 25.0


def test_asset_data_invalid_metrics():
	# Test AssetData with empty metrics
	asset = AssetData(symbol="TEST", metrics={})
	assert asset.metrics == {}
	assert asset.display_name == "TEST"


def test_asset_data_with_name():
	asset = AssetData(symbol="TEST", name="Test Asset")
	assert asset.display_name == "Test Asset"


def test_openbb_provider_routing_logic(mocker):
	provider = OpenBBProvider()

	# Mock get_openbb_data to return ETF data
	mock_etf = {"symbol": "SPY", "fund_family": "SPDR"}
	mocker.patch(
		"core.providers.openbb_provider.get_openbb_data", return_value=mock_etf
	)
	asset = provider.get_data("SPY")
	assert asset.asset_type == AssetType.ETF


def test_parse_ticker_file_txt(tmp_path):
	d = tmp_path / "subdir"
	d.mkdir()
	p = d / "tickers.txt"
	p.write_text("AAPL\nMSFT\n\n# Comment\nGOOGL")

	tickers = parse_ticker_file(str(p))
	assert tickers == ["AAPL", "MSFT", "GOOGL"]


def test_parse_ticker_file_csv(tmp_path):
	d = tmp_path / "subdir"
	d.mkdir()
	p = d / "tickers.csv"
	p.write_text("AAPL,Apple\nMSFT,Microsoft")

	tickers = parse_ticker_file(str(p))
	assert tickers == ["AAPL", "MSFT"]
