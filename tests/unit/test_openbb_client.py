import json

from core.openbb_client import get_openbb_data


def test_get_openbb_data_cache_hit(mocker, tmp_path):
	# Setup cache dir
	cache_dir = tmp_path / "cache"
	cache_dir.mkdir()
	mocker.patch("core.openbb_client.CACHE_DIR", cache_dir)

	ticker = "AAPL"
	cache_file = cache_dir / f"{ticker}.json"
	mock_data = {"symbol": "AAPL", "price": 150}
	cache_file.write_text(json.dumps(mock_data))

	# Ensure file is fresh
	mocker.patch("os.path.exists", return_value=True)
	mocker.patch("time.time", return_value=cache_file.stat().st_mtime + 100)

	result = get_openbb_data(ticker)
	assert result["symbol"] == "AAPL"


def test_get_openbb_data_fetch_logic(mocker, tmp_path):
	# Mock OpenBB Platform and cache dir
	cache_dir = tmp_path / "cache"
	cache_dir.mkdir()
	mocker.patch("core.openbb_client.CACHE_DIR", cache_dir)

	# Mock the obb calls directly in the openbb package
	mock_obb = mocker.patch("openbb.obb")

	mock_metrics = mocker.Mock()
	mock_metrics.to_dict.return_value = {"pe_ratio": [30.0], "symbol": ["MSFT"]}
	mock_obb.equity.fundamental.metrics.return_value = mock_metrics

	mock_profile = mocker.Mock()
	mock_profile.to_dict.return_value = [{"name": "Microsoft", "symbol": "MSFT"}]
	mock_obb.equity.profile.return_value = mock_profile

	# Mock other calls to return empty/none
	mock_obb.equity.estimates.consensus.return_value.to_dict.return_value = []
	mock_obb.equity.ownership.share_statistics.return_value.to_dict.return_value = []
	mock_obb.etf.info.return_value.to_dict.return_value = []

	mocker.patch("time.sleep")  # Disable rate limit sleep

	result = get_openbb_data("MSFT")
	assert result["symbol"] == "MSFT"
	assert result["name"] == "Microsoft"
	assert result["pe_ratio"] == 30.0
	assert (cache_dir / "MSFT.json").exists()
