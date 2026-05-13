from unittest.mock import ANY, patch

import pandas as pd

from core.analysis.constituents import get_constituents


def test_get_constituents_nasdaq100():
	with patch("requests.get") as mock_get:
		mock_get.return_value.status_code = 200
		mock_get.return_value.text = (
			"<html><table><tr><th>Ticker</th></tr><tr><td>AAPL</td></tr></table></html>"
		)

		with patch("pandas.read_html") as mock_read_html:
			mock_read_html.return_value = [pd.DataFrame({"Ticker": ["AAPL", "MSFT"]})]

			# Mock cache file not existing to force fetch
			with patch("pathlib.Path.exists", return_value=False):
				tickers = get_constituents("nasdaq100")
			mock_read_html.assert_called_once_with(ANY, flavor="html5lib")

	assert "AAPL" in tickers
	assert "MSFT" in tickers
	assert len(tickers) == 2


def test_get_constituents_sp500():
	with patch("requests.get") as mock_get:
		mock_get.return_value.status_code = 200
		mock_get.return_value.text = "<html></html>"

		with patch("pandas.read_html") as mock_read_html:
			mock_read_html.return_value = [pd.DataFrame({"Symbol": ["AAPL", "AMZN"]})]

			# Mock cache file not existing to force fetch
			with patch("pathlib.Path.exists", return_value=False):
				tickers = get_constituents("sp500")

	assert "AMZN" in tickers


def test_get_constituents_dow():
	with patch("requests.get") as mock_get:
		mock_get.return_value.status_code = 200
		mock_get.return_value.text = "<html></html>"

		with patch("pandas.read_html") as mock_read_html:
			mock_read_html.return_value = [pd.DataFrame({"Symbol": ["GS", "V"]})]

			# Mock cache file not existing to force fetch
			with patch("pathlib.Path.exists", return_value=False):
				tickers = get_constituents("dow")

	assert "GS" in tickers


def test_get_constituents_unsupported():
	tickers = get_constituents("invalid_index_unique")
	assert tickers == []


def test_get_constituents_error():
	with patch("requests.get", side_effect=Exception("Network error")):
		# Use a unique name that hasn't been cached
		tickers = get_constituents("nasdaq100_error_test")
	assert tickers == []
