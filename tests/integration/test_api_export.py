from fastapi.testclient import TestClient

from core.api import app

client = TestClient(app)


def test_export_endpoint_csv():
	"""Verify that the /api/export endpoint returns a valid CSV file."""
	payload = {
		"results": [
			{
				"symbol": "AAPL",
				"name": "Apple Inc.",
				"asset_type": "equity",
				"score": 85.5,
				"results": [
					{"name": "P/E Ratio", "value": "25.4", "status": "80%"},
					{"name": "Debt/Equity", "value": "0.5", "status": "90%"},
				],
			}
		],
		"format": "csv",
		"profile": "balanced",
		"tickers": ["AAPL"],
	}

	response = client.post("/api/export", json=payload)

	assert response.status_code == 200
	assert response.headers["content-type"] == "application/octet-stream"
	cd = response.headers.get("content-disposition", "")
	assert "equiquant-analysis-aapl-balanced" in cd
	assert ".csv" in cd

	content = response.content.decode()
	assert "AAPL" in content
	assert "Apple Inc." in content
	assert "equity" in content
	assert "85.50" in content


def test_export_endpoint_txt():
	"""Verify that the /api/export endpoint returns a valid TXT file."""
	payload = {
		"results": [
			{
				"symbol": "AAPL",
				"name": "Apple Inc.",
				"asset_type": "equity",
				"score": 85.5,
				"results": [
					{
						"name": "P/E Ratio",
						"value": "25.4",
						"status": "80%",
						"score": 1.0,
						"weight": 1.0,
					}
				],
			}
		],
		"format": "txt",
		"profile": "balanced",
		"tickers": ["AAPL"],
	}

	response = client.post("/api/export", json=payload)

	assert response.status_code == 200
	cd = response.headers.get("content-disposition", "")
	assert "equiquant-analysis-aapl-balanced" in cd
	assert ".txt" in cd

	content = response.content.decode()
	assert "Analysis for Apple Inc. (AAPL)" in content
