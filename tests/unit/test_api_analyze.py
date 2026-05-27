from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core.api import app
from core.api.routers.analysis import _fetch_params

client = TestClient(app)


@pytest.fixture
def mock_orchestrator():
	"""Fixture providing mocked orchestrator dependencies."""
	with (
		patch("core.api.routers.analysis.orchestrator_fetch_data") as mock_fetch,
		patch("core.api.routers.analysis.run_bulk_analysis") as mock_analyze,
		patch(
			"core.database.repository.DatabaseRepository.should_use_db_cache"
		) as mock_cache,
	):
		# Setup mock_fetch as an async generator
		async def mock_fetch_gen(tickers, repo=None, **kwargs):
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
		{
			"symbol": "AAPL",
			"name": "Apple Inc.",
			"score": 85.0,
			"asset_type": "STOCK",
			"results": [],
		}
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
		{
			"symbol": "MSFT",
			"name": "Microsoft Corp.",
			"score": 75.0,
			"asset_type": "STOCK",
			"results": [],
		}
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
	"asset_type": "STOCK",
	"results": [],
}


@pytest.fixture
def mock_stream_orchestrator():
	"""Fixture providing mocked orchestrator dependencies for the stream endpoint."""

	async def mock_fetch_gen(tickers, repo=None, **kwargs):
		# Yield one batch containing all tickers (mirrors fetch_data behaviour)
		yield tickers

	async def mock_stream_gen(tickers, profile, repo, benchmark_version, **kwargs):
		# Yield one result per ticker in the batch
		for _ in tickers:
			yield _MOCK_RESULT

	with (
		patch("core.api.routers.analysis.orchestrator_fetch_data") as mock_fetch,
		patch("core.api.routers.analysis.stream_bulk_analysis") as mock_stream,
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
			current["event"] = line[len("event:") :].strip()
		elif line.startswith("data:"):
			current["data"] = line[len("data:") :].strip()
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


def test_stream_batch_context_uses_full_ticker_list(mock_stream_orchestrator):
	"""
	Regression: with context='batch' and mixed cached/missing tickers,
	stream_bulk_analysis must be called once with the full ticker list so
	batch-relative benchmarks are computed from the complete distribution.
	"""

	mock_fetch, mock_stream, mock_cache = mock_stream_orchestrator

	# AAPL cached, MSFT missing
	mock_cache.side_effect = lambda t: t == "AAPL"

	payload = {"tickers": ["AAPL", "MSFT"], "profile": "balanced", "context": "batch"}
	with client.stream("POST", "/api/analyze/stream", json=payload) as response:
		assert response.status_code == 200
		body = response.read().decode()

	events = _parse_sse_lines(body)
	event_types = [e["event"] for e in events]
	assert "result" in event_types
	assert "done" in event_types

	# stream_bulk_analysis must be called exactly once with the full list
	assert mock_stream.call_count == 1
	called_tickers = mock_stream.call_args.args[0]
	assert set(called_tickers) == {"AAPL", "MSFT"}


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


def test_stream_failed_ticker_yields_error(mock_stream_orchestrator):
	"""SSE stream yields an error event if a requested ticker fails to be fetched/analyzed."""
	import json as _json

	mock_fetch, mock_stream, mock_cache = mock_stream_orchestrator
	mock_cache.return_value = False

	async def empty_fetch(tickers, repo=None, **kwargs):
		return
		yield

	mock_fetch.side_effect = empty_fetch

	async def empty_stream(tickers, *args, **kwargs):
		return
		yield

	mock_stream.side_effect = empty_stream

	payload = {"tickers": ["INVALID"], "profile": "balanced"}
	with client.stream("POST", "/api/analyze/stream", json=payload) as response:
		assert response.status_code == 200
		body = response.read().decode()

	events = _parse_sse_lines(body)
	event_types = [e["event"] for e in events]

	assert "error" in event_types
	error_event = next(e for e in events if e["event"] == "error")
	error_data = _json.loads(error_event["data"])
	assert "Could not analyze ticker(s): INVALID" in error_data["message"]


# ---------------------------------------------------------------------------
# force_refresh tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _fetch_params dynamic batch sizing tests
# ---------------------------------------------------------------------------


def test_fetch_params_small_request_no_processes():
	"""Requests of 20 or fewer tickers skip subprocess workers entirely."""
	for n in [1, 5, 10, 20]:
		batch_size, use_processes = _fetch_params(n)
		assert use_processes is False, f"n={n} should not use processes"
		assert batch_size == 20


def test_fetch_params_large_request_uses_processes():
	"""Requests over 20 tickers use subprocess workers."""
	batch_size, use_processes = _fetch_params(21)
	assert use_processes is True


def test_fetch_params_batch_size_scales_with_count():
	"""Batch size scales linearly with ticker count, capped at 50."""
	assert _fetch_params(200)[0] == 20  # 200//10 = 20
	assert _fetch_params(300)[0] == 30  # 300//10 = 30
	assert _fetch_params(500)[0] == 50  # 500//10 = 50 (cap)
	assert _fetch_params(1000)[0] == 50  # capped at 50


def test_fetch_params_batch_size_floor():
	"""Batch size never falls below 20."""
	assert _fetch_params(21)[0] == 20  # 21//10 = 2, floor kicks in → 20
	assert _fetch_params(100)[0] == 20  # 100//10 = 10, floor kicks in → 20


def test_force_refresh_bypasses_cache(mock_orchestrator):
	"""When force_refresh=True, cached tickers are still fetched fresh."""
	mock_fetch, mock_analyze, mock_cache = mock_orchestrator
	mock_cache.return_value = True  # Cache says all hits…
	mock_analyze.return_value = [
		{
			"symbol": "AAPL",
			"name": "Apple Inc.",
			"score": 90.0,
			"asset_type": "STOCK",
			"results": [],
		}
	]

	payload = {"tickers": ["AAPL"], "profile": "balanced", "force_refresh": True}
	response = client.post("/api/analyze", json=payload)

	assert response.status_code == 200
	# …but fetch should still be called because force_refresh overrides the cache
	mock_fetch.assert_called_once()


def test_no_force_refresh_respects_cache(mock_orchestrator):
	"""When force_refresh is absent (default False), cache hits skip fetching."""
	mock_fetch, mock_analyze, mock_cache = mock_orchestrator
	mock_cache.return_value = True
	mock_analyze.return_value = [
		{
			"symbol": "AAPL",
			"name": "Apple Inc.",
			"score": 90.0,
			"asset_type": "STOCK",
			"results": [],
		}
	]

	payload = {"tickers": ["AAPL"], "profile": "balanced"}
	response = client.post("/api/analyze", json=payload)

	assert response.status_code == 200
	mock_fetch.assert_not_called()


def test_stream_force_refresh_bypasses_cache(mock_stream_orchestrator):
	"""SSE stream with force_refresh=True triggers fetch even for cached tickers."""
	mock_fetch, mock_stream, mock_cache = mock_stream_orchestrator
	mock_cache.return_value = True  # All cached…

	payload = {"tickers": ["AAPL"], "profile": "balanced", "force_refresh": True}
	with client.stream("POST", "/api/analyze/stream", json=payload) as response:
		assert response.status_code == 200
		body = response.read().decode()

	events = _parse_sse_lines(body)
	event_types = [e["event"] for e in events]
	assert "done" in event_types
	# …but fetch must still be called
	mock_fetch.assert_called_once()
