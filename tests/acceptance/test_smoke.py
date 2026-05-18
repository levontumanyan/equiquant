from fastapi.testclient import TestClient

from core.api import app

client = TestClient(app)


def test_api_analyze_single_asset():
	"""Verify that the /api/analyze endpoint works for a single asset."""
	payload = {"tickers": ["AAPL"], "profile": "balanced", "benchmark_version": "1.0.0"}
	response = client.post("/api/analyze", json=payload)

	assert response.status_code == 200
	data = response.json()
	assert isinstance(data, list)
	assert len(data) == 1
	assert data[0]["symbol"] == "AAPL"
	assert "score" in data[0]
	assert data[0]["score"] >= 0


def test_api_analyze_bulk_assets():
	"""Verify that the /api/analyze endpoint works for bulk assets."""
	payload = {
		"tickers": ["MSFT", "GOOGL"],
		"profile": "balanced",
		"benchmark_version": "1.0.0",
	}
	response = client.post("/api/analyze", json=payload)

	assert response.status_code == 200
	data = response.json()
	assert isinstance(data, list)
	assert len(data) == 2

	symbols = [item["symbol"] for item in data]
	assert "MSFT" in symbols
	assert "GOOGL" in symbols

	for item in data:
		assert "score" in item
		assert item["score"] >= 0
