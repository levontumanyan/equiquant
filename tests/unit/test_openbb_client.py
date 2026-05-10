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
	# OpenBB results have a .results attribute which is a list of objects
	mock_metric_item = mocker.Mock()
	mock_metric_item.model_dump.return_value = {"pe_ratio": 30.0, "symbol": "MSFT"}
	mock_metrics.results = [mock_metric_item]
	mock_obb.equity.fundamental.metrics.return_value = mock_metrics

	mock_profile = mocker.Mock()
	mock_profile_item = mocker.Mock()
	mock_profile_item.model_dump.return_value = {"name": "Microsoft", "symbol": "MSFT"}
	mock_profile.results = [mock_profile_item]
	mock_obb.equity.profile.return_value = mock_profile

	# Mock other calls to return empty/none
	mock_obb.equity.estimates.consensus.return_value.results = []
	mock_obb.equity.ownership.share_statistics.return_value.results = []
	mock_obb.etf.info.return_value.results = []

	mocker.patch("time.sleep")  # Disable rate limit sleep

	result = get_openbb_data("MSFT")
	assert result["symbol"] == "MSFT"
	assert result["name"] == "Microsoft"
	assert result["pe_ratio"] == 30.0
	assert (cache_dir / "MSFT.json").exists()


def test_fetch_with_retry_logic(mocker):
	from core.openbb_client import _fetch_with_retry

	mocker.patch("time.sleep")
	mock_func = mocker.Mock()

	# Case 1: Success on first try
	mock_res = mocker.Mock()
	mock_res.results = [1, 2, 3]
	mock_func.return_value = mock_res

	result = _fetch_with_retry(mock_func, "AAPL", "yfinance")
	assert result == mock_res
	assert mock_func.call_count == 1

	# Case 2: Fail once, then success
	mock_func.reset_mock()
	mock_func.side_effect = [None, mock_res]
	result = _fetch_with_retry(mock_func, "AAPL", "yfinance", max_retries=1)
	assert result == mock_res
	assert mock_func.call_count == 2

	# Case 3: All retries fail
	mock_func.reset_mock()
	mock_func.side_effect = [None, None]
	result = _fetch_with_retry(mock_func, "AAPL", "yfinance", max_retries=1)
	assert result is None
	assert mock_func.call_count == 2


def test_fetch_openbb_data_bulk(mocker, tmp_path):
	from core.openbb_client import fetch_openbb_data_bulk

	cache_dir = tmp_path / "cache"
	cache_dir.mkdir()
	mocker.patch("core.openbb_client.CACHE_DIR", cache_dir)
	mocker.patch("time.sleep")

	mock_obb = mocker.patch("openbb.obb")

	# Mock metrics for 2 symbols
	item1 = mocker.Mock()
	item1.model_dump.return_value = {"symbol": "AAPL", "pe_ratio": 25}
	item2 = mocker.Mock()
	item2.model_dump.return_value = {"symbol": "MSFT", "pe_ratio": 35}

	mock_res = mocker.Mock()
	mock_res.results = [item1, item2]
	mock_obb.equity.fundamental.metrics.return_value = mock_res

	# Mock others as empty
	mock_obb.equity.profile.return_value.results = []
	mock_obb.equity.estimates.consensus.return_value.results = []
	mock_obb.equity.ownership.share_statistics.return_value.results = []

	success = fetch_openbb_data_bulk(["AAPL", "MSFT"])

	assert success is True
	assert (cache_dir / "AAPL.json").exists()
	assert (cache_dir / "MSFT.json").exists()

	# Verify AAPL content
	content = json.loads((cache_dir / "AAPL.json").read_text())
	assert content["pe_ratio"] == 25
