import json

import pytest

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
	mock_obb.equity.fundamental.metrics.__name__ = "metrics"
	mock_obb.equity.profile.__name__ = "profile"
	mock_obb.equity.estimates.consensus.__name__ = "consensus"
	mock_obb.equity.ownership.share_statistics.__name__ = "ownership"
	mock_obb.etf.info.__name__ = "etf_info"

	def mock_res(data):
		m = mocker.Mock()
		item = mocker.Mock()
		item.model_dump.return_value = data
		m.results = [item]
		return m

	mock_obb.equity.fundamental.metrics.return_value = mock_res(
		{"pe_ratio": 30.0, "symbol": "MSFT"}
	)
	mock_obb.equity.profile.return_value = mock_res(
		{"name": "Microsoft", "symbol": "MSFT"}
	)
	mock_obb.equity.estimates.consensus.return_value = mock_res(
		{"symbol": "MSFT", "recommendation": "buy"}
	)
	mock_obb.equity.ownership.share_statistics.return_value = mock_res(
		{"symbol": "MSFT"}
	)
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

	# Case 3: All retries fail (now raises provider exception if it hit one, or uses RuntimeError)
	mock_func.reset_mock()
	mock_func.side_effect = [None, None]
	with pytest.raises(Exception):
		_fetch_with_retry(mock_func, "AAPL", "yfinance", max_retries=1)
	assert mock_func.call_count == 2


def test_fetch_with_retry_rate_limit_fail_fast(mocker):
	from core.openbb_client import _fetch_with_retry, RateLimitError

	mocker.patch("time.sleep")
	mock_func = mocker.Mock()

	# 429 error should fail fast (no retries)
	mock_func.side_effect = Exception("429 Too Many Requests")

	with pytest.raises(RateLimitError):
		_fetch_with_retry(mock_func, "AAPL", "yfinance", max_retries=2)

	# Should only be called once if it's a 429
	assert mock_func.call_count == 1


def test_fetch_openbb_data_bulk_rate_limit(mocker, tmp_path):
	from core.openbb_client import fetch_openbb_data_bulk

	cache_dir = tmp_path / "cache"
	cache_dir.mkdir()
	mocker.patch("core.openbb_client.CACHE_DIR", cache_dir)
	mocker.patch("time.sleep")

	mock_obb = mocker.patch("openbb.obb")
	mock_obb.equity.fundamental.metrics.__name__ = "metrics"
	mock_obb.equity.profile.__name__ = "profile"
	mock_obb.equity.estimates.consensus.__name__ = "consensus"
	mock_obb.equity.ownership.share_statistics.__name__ = "ownership"
	mock_obb.etf.info.__name__ = "etf_info"
	# Mock first endpoint to return 429
	mock_obb.equity.fundamental.metrics.side_effect = Exception("429 Rate Limit")

	success = fetch_openbb_data_bulk(["AAPL", "MSFT"])

	# Should return False immediately on rate limit
	assert success is False
	# Should not have proceeded to profile endpoint
	assert mock_obb.equity.profile.call_count == 0


def test_fetch_openbb_data_bulk(mocker, tmp_path):
	from core.openbb_client import fetch_openbb_data_bulk

	cache_dir = tmp_path / "cache"
	cache_dir.mkdir()
	mocker.patch("core.openbb_client.CACHE_DIR", cache_dir)
	mocker.patch("time.sleep")

	mock_obb = mocker.patch("openbb.obb")
	mock_obb.equity.fundamental.metrics.__name__ = "metrics"
	mock_obb.equity.profile.__name__ = "profile"
	mock_obb.equity.estimates.consensus.__name__ = "consensus"
	mock_obb.equity.ownership.share_statistics.__name__ = "ownership"
	mock_obb.etf.info.__name__ = "etf_info"

	def mock_bulk_res(data_list):
		m = mocker.Mock()
		items = []
		for d in data_list:
			item = mocker.Mock()
			item.model_dump.return_value = d
			items.append(item)
		m.results = items
		return m

	# Mock all endpoints to return data for both symbols
	symbols = ["AAPL", "MSFT"]
	mock_obb.equity.fundamental.metrics.return_value = mock_bulk_res(
		[{"symbol": "AAPL", "pe_ratio": 25}, {"symbol": "MSFT", "pe_ratio": 35}]
	)
	mock_obb.equity.profile.return_value = mock_bulk_res(
		[{"symbol": "AAPL", "name": "Apple"}, {"symbol": "MSFT", "name": "Microsoft"}]
	)
	mock_obb.equity.estimates.consensus.return_value = mock_bulk_res(
		[{"symbol": "AAPL"}, {"symbol": "MSFT"}]
	)
	mock_obb.equity.ownership.share_statistics.return_value = mock_bulk_res(
		[{"symbol": "AAPL"}, {"symbol": "MSFT"}]
	)
	mock_obb.etf.info.return_value.results = []

	success = fetch_openbb_data_bulk(symbols)

	assert success is True
	assert (cache_dir / "AAPL.json").exists()
	assert (cache_dir / "MSFT.json").exists()

	# Verify AAPL content
	content = json.loads((cache_dir / "AAPL.json").read_text())
	assert content["pe_ratio"] == 25
	assert content["name"] == "Apple"
