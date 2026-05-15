from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core.api import app

client = TestClient(app)


@pytest.fixture
def mock_fetch():
	"""Fixture providing a mocked orchestrator_fetch_data function."""
	with patch("core.api.orchestrator_fetch_data") as mock_fetch:
		# Setup mock_fetch as an async generator
		async def mock_fetch_gen(tickers, repo=None):
			# Yield in batches to simulate real behavior
			if len(tickers) > 1:
				yield [tickers[0]]
				yield [tickers[1]]
			else:
				yield tickers

		mock_fetch.side_effect = mock_fetch_gen
		yield mock_fetch


def test_fetch_data_success(mock_fetch):
	"""
	Tests /api/fetch with successful fetching.
	"""
	payload = {"tickers": ["AAPL", "MSFT"]}
	response = client.post("/api/fetch", json=payload)

	assert response.status_code == 200
	assert response.json()["status"] == "success"
	assert response.json()["message"] == "Fetched data for 2/2 tickers"
	assert response.json()["tickers"] == ["AAPL", "MSFT"]

	mock_fetch.assert_called_once()
	assert mock_fetch.call_args.args[0] == ["AAPL", "MSFT"]
	assert "repo" in mock_fetch.call_args.kwargs


def test_fetch_data_empty():
	"""
	Tests /api/fetch with empty tickers list.
	"""
	payload = {"tickers": []}
	response = client.post("/api/fetch", json=payload)

	assert response.status_code == 200  # App returns 200 with error status in body
	assert response.json()["status"] == "error"
	assert "No tickers provided" in response.json()["message"]
