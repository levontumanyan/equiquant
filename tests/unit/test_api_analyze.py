from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.api import app

client = TestClient(app)


@pytest.fixture
def mock_orchestrator():
	"""Fixture providing mocked orchestrator dependencies."""
	with (
		patch("core.api.orchestrator_fetch_data") as mock_fetch,
		patch("core.api.run_bulk_analysis") as mock_analyze,
		patch("core.api.should_use_cache") as mock_cache,
	):
		# Setup mock_fetch as an async generator
		async def mock_fetch_gen(tickers):
			yield tickers

		mock_fetch.side_effect = mock_fetch_gen

		yield mock_fetch, mock_analyze, mock_cache


def test_analyze_tickers_all_cached(mock_orchestrator):
	"""
	Tests /api/analyze when all tickers are already cached.
	"""
	mock_fetch, mock_analyze, mock_cache = mock_orchestrator
	mock_cache.return_value = True
	mock_analyze.return_value = [
		{"symbol": "AAPL", "name": "Apple Inc.", "score": 85.0, "results": []}
	]

	payload = {"tickers": ["AAPL"], "profile": "growth", "benchmark_version": "1.0.0"}
	response = client.post("/api/analyze", json=payload)

	assert response.status_code == 200
	data = response.json()
	assert data[0]["symbol"] == "AAPL"
	assert data[0]["score"] == 85.0
	assert data[0]["name"] == "Apple Inc."

	# Verify fetch was NOT called for missing tickers
	mock_fetch.assert_not_called()
	# Verify analyze WAS called
	mock_analyze.assert_called_once()


def test_analyze_tickers_needs_fetching(mock_orchestrator):
	"""
	Tests /api/analyze when some tickers need fetching.
	"""
	mock_fetch, mock_analyze, mock_cache = mock_orchestrator
	mock_cache.return_value = False  # All need fetching
	mock_analyze.return_value = [
		{"symbol": "MSFT", "name": "Microsoft Corp.", "score": 75.0, "results": []}
	]

	payload = {"tickers": ["MSFT"], "profile": "balanced"}
	response = client.post("/api/analyze", json=payload)

	assert response.status_code == 200
	data = response.json()
	assert data[0]["symbol"] == "MSFT"
	assert data[0]["score"] == 75.0

	# Verify fetch WAS called
	mock_fetch.assert_called_once_with(["MSFT"])
	# Verify analyze WAS called
	mock_analyze.assert_called_once()


def test_analyze_tickers_empty_request():
	"""
	Tests /api/analyze with empty tickers list.
	"""
	payload = {"tickers": [], "profile": "balanced"}
	response = client.post("/api/analyze", json=payload)
	assert response.status_code == 400
	assert "No tickers provided" in response.json()["detail"]


# Removed invalid payload test as profile now has a default value.
