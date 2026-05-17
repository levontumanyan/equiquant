from core.io.parsers import parse_ticker_file
from core.orchestrator import analyze_asset
from core.providers.openbb_provider import OpenBBProvider
from core.schema import AssetData, AssetType


def test_analyze_asset_routing(mocker):
	# Create an ETF asset
	etf_asset = AssetData(symbol="SPY", asset_type=AssetType.ETF)

	# Mock load_benchmarks and get_profile_config
	mocker.patch(
		"core.orchestrator.load_benchmarks",
		return_value=[
			{"metric": "test", "weight": 1.0, "type": "threshold", "threshold": 0}
		],
	)
	mocker.patch(
		"core.orchestrator.get_profile_config",
		return_value={
			"test": {"weight": 1.0, "best": None, "worst": None, "formula": "threshold"}
		},
	)
	mocker.patch(
		"core.orchestrator.evaluate_metric", return_value={"score": 1.0, "weight": 1.0}
	)

	result = analyze_asset(etf_asset, "balanced")
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


def _mock_analyze_setup(mocker):
	"""Shared mock setup for analyze_asset tests."""
	mocker.patch(
		"core.orchestrator.load_benchmarks",
		return_value=[
			{"metric": "test", "weight": 1.0, "type": "threshold", "threshold": 0}
		],
	)
	mocker.patch(
		"core.orchestrator.get_profile_config",
		return_value={
			"test": {"weight": 1.0, "best": None, "worst": None, "formula": "threshold"}
		},
	)
	mocker.patch(
		"core.orchestrator.evaluate_metric",
		return_value={"score": 1.0, "weight": 1.0},
	)


def test_analyze_asset_market_cap_snake_case(mocker):
	"""market_cap from the snake_case key is passed through to the result."""
	_mock_analyze_setup(mocker)
	asset = AssetData(
		symbol="AAPL",
		asset_type=AssetType.STOCK,
		raw_data={"market_cap": 3_000_000_000_000},
	)
	result = analyze_asset(asset, "balanced")
	assert result["market_cap"] == 3_000_000_000_000


def test_analyze_asset_market_cap_camel_case_fallback(mocker):
	"""Falls back to marketCap when market_cap key is absent."""
	_mock_analyze_setup(mocker)
	asset = AssetData(
		symbol="MSFT",
		asset_type=AssetType.STOCK,
		raw_data={"marketCap": 2_500_000_000_000},
	)
	result = analyze_asset(asset, "balanced")
	assert result["market_cap"] == 2_500_000_000_000


def test_analyze_asset_market_cap_zero_not_masked(mocker):
	"""A legitimate market_cap of 0 is not treated as missing."""
	_mock_analyze_setup(mocker)
	asset = AssetData(
		symbol="TEST",
		asset_type=AssetType.STOCK,
		raw_data={"market_cap": 0, "marketCap": 999},
	)
	result = analyze_asset(asset, "balanced")
	assert result["market_cap"] == 0


def test_analyze_asset_market_cap_absent(mocker):
	"""Returns None when neither key is present in raw_data."""
	_mock_analyze_setup(mocker)
	asset = AssetData(symbol="TEST", asset_type=AssetType.STOCK, raw_data={})
	result = analyze_asset(asset, "balanced")
	assert result["market_cap"] is None


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
