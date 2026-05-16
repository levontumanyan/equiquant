from unittest.mock import patch

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
		patch(
			"core.database.repository.DatabaseRepository.should_use_db_cache"
		) as mock_cache,
	):
		# Setup mock_fetch as an async generator
		async def mock_fetch_gen(tickers, repo=None):
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

	# Verify fetch WAS called with tickers and repo
	mock_fetch.assert_called_once()
	assert mock_fetch.call_args.args[0] == ["MSFT"]
	assert "repo" in mock_fetch.call_args.kwargs
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


# ---------------------------------------------------------------------------
# /api/analyze/stream (SSE) tests
# ---------------------------------------------------------------------------

_MOCK_RESULT = {
	"symbol": "AAPL",
	"name": "Apple Inc.",
	"sector": "Technology",
	"industry": "Consumer Electronics",
	"score": 85.0,
	"results": [],
}


@pytest.fixture
def mock_stream_orchestrator():
	"""Fixture providing mocked orchestrator dependencies for the stream endpoint."""

	async def mock_fetch_gen(tickers, repo=None):
		# Yield one batch containing all tickers (mirrors fetch_data behaviour)
		yield tickers

	async def mock_stream_gen(tickers, profile, repo, benchmark_version, **kwargs):
		# Yield one result per ticker in the batch
		for _ in tickers:
			yield _MOCK_RESULT

	with (
		patch("core.api.orchestrator_fetch_data") as mock_fetch,
		patch("core.api.stream_bulk_analysis") as mock_stream,
		patch(
			"core.database.repository.DatabaseRepository.should_use_db_cache"
		) as mock_cache,
	):
		mock_fetch.side_effect = mock_fetch_gen
		mock_stream.side_effect = mock_stream_gen
		yield mock_fetch, mock_stream, mock_cache


def _parse_sse_lines(text: str) -> list[dict]:
	"""Parse raw SSE text into a list of {event, data} dicts."""
	events = []
	current: dict = {}
	for line in text.splitlines():
		if line.startswith("event:"):
			current["event"] = line[len("event:"):].strip()
		elif line.startswith("data:"):
			current["data"] = line[len("data:"):].strip()
		elif line == "" and current:
			events.append(current)
			current = {}
	if current:
		events.append(current)
	return events


def test_stream_all_cached(mock_stream_orchestrator):
	"""SSE stream yields a result event and a done event when cache is warm."""
	mock_fetch, mock_stream, mock_cache = mock_stream_orchestrator
	mock_cache.return_value = True

	payload = {"tickers": ["AAPL"], "profile": "balanced"}
	with client.stream("POST", "/api/analyze/stream", json=payload) as response:
		assert response.status_code == 200
		body = response.read().decode()

	events = _parse_sse_lines(body)
	event_types = [e["event"] for e in events]

	assert "result" in event_types
	assert "done" in event_types
	mock_fetch.assert_not_called()


def test_stream_needs_fetching(mock_stream_orchestrator):
	"""SSE stream emits a status event when tickers need fetching."""
	mock_fetch, mock_stream, mock_cache = mock_stream_orchestrator
	mock_cache.return_value = False

	payload = {"tickers": ["MSFT"], "profile": "growth"}
	with client.stream("POST", "/api/analyze/stream", json=payload) as response:
		assert response.status_code == 200
		body = response.read().decode()

	events = _parse_sse_lines(body)
	event_types = [e["event"] for e in events]

	assert "status" in event_types
	assert "result" in event_types
	assert "done" in event_types
	mock_fetch.assert_called_once()


def test_stream_empty_tickers():
	"""SSE stream returns 400 for empty ticker list."""
	payload = {"tickers": [], "profile": "balanced"}
	response = client.post("/api/analyze/stream", json=payload)
	assert response.status_code == 400
	assert "No tickers provided" in response.json()["detail"]


def test_stream_result_schema(mock_stream_orchestrator):
	"""Each result event deserialises to a valid AssetAnalysis shape."""
	import json as _json

	mock_fetch, mock_stream, mock_cache = mock_stream_orchestrator
	mock_cache.return_value = True

	payload = {"tickers": ["AAPL"], "profile": "balanced"}
	with client.stream("POST", "/api/analyze/stream", json=payload) as response:
		body = response.read().decode()

	result_events = [e for e in _parse_sse_lines(body) if e.get("event") == "result"]
	assert len(result_events) == 1

	data = _json.loads(result_events[0]["data"])
	assert data["symbol"] == "AAPL"
	assert data["score"] == 85.0
	assert "results" in data
