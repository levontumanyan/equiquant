import pytest

from core.openbb_client import get_openbb_data


def test_get_openbb_data_fetch_logic(mocker):
	"""get_openbb_data fetches live and returns the merged payload (no file write)."""
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

	mocker.patch("time.sleep")

	result = get_openbb_data("MSFT")
	assert result["symbol"] == "MSFT"
	assert result["name"] == "Microsoft"
	assert result["pe_ratio"] == 30.0


def test_fetch_with_retry_logic(mocker):
	from core.openbb_client import _fetch_with_retry

	mocker.patch("time.sleep")
	mock_func = mocker.Mock()

	mock_res = mocker.Mock()
	mock_res.results = [1, 2, 3]
	mock_func.return_value = mock_res

	result = _fetch_with_retry(mock_func, "AAPL", "yfinance")
	assert result == mock_res
	assert mock_func.call_count == 1

	mock_func.reset_mock()
	mock_func.side_effect = [None, mock_res]
	result = _fetch_with_retry(mock_func, "AAPL", "yfinance", max_retries=1)
	assert result == mock_res
	assert mock_func.call_count == 2

	mock_func.reset_mock()
	mock_func.side_effect = [None, None]
	with pytest.raises(Exception):
		_fetch_with_retry(mock_func, "AAPL", "yfinance", max_retries=1)
	assert mock_func.call_count == 2


def test_fetch_with_retry_rate_limit_fail_fast(mocker):
	from core.openbb_client import RateLimitError, _fetch_with_retry

	mocker.patch("time.sleep")
	mock_func = mocker.Mock()
	mock_func.side_effect = Exception("429 Too Many Requests")

	with pytest.raises(RateLimitError):
		_fetch_with_retry(mock_func, "AAPL", "yfinance", max_retries=2)

	assert mock_func.call_count == 1


def test_fetch_openbb_data_bulk_rate_limit(mocker):
	from core.openbb_client import fetch_openbb_data_bulk

	mocker.patch("time.sleep")

	mock_obb = mocker.patch("openbb.obb")
	mock_obb.equity.fundamental.metrics.__name__ = "metrics"
	mock_obb.equity.profile.__name__ = "profile"
	mock_obb.equity.estimates.consensus.__name__ = "consensus"
	mock_obb.equity.ownership.share_statistics.__name__ = "ownership"
	mock_obb.etf.info.__name__ = "etf_info"
	mock_obb.equity.fundamental.metrics.side_effect = Exception("429 Rate Limit")

	success, data = fetch_openbb_data_bulk(["AAPL", "MSFT"])

	assert success is False
	assert data == {}
	assert mock_obb.equity.profile.call_count == 0


def test_fetch_openbb_data_bulk(mocker):
	from core.openbb_client import fetch_openbb_data_bulk

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
			item.symbol = d.get("symbol")
			items.append(item)
		m.results = items
		return m

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

	success, data = fetch_openbb_data_bulk(["AAPL", "MSFT"])

	assert success is True
	assert "AAPL" in data
	assert "MSFT" in data
	assert data["AAPL"]["pe_ratio"] == 25
	assert data["AAPL"]["name"] == "Apple"
