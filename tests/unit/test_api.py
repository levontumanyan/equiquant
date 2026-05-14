from fastapi.testclient import TestClient

from core.api import app

client = TestClient(app)


def test_health_check():
	"""
	Tests the /health endpoint.
	"""
	response = client.get("/health")
	assert response.status_code == 200
	assert response.json() == {
		"status": "online",
		"version": "0.1.0",
		"message": "EquiQuant API is running",
	}


def test_get_status():
	"""
	Tests the /api/status endpoint.
	"""
	response = client.get("/api/status")
	assert response.status_code == 200
	assert response.json() == {
		"backend": "connected",
		"database": "available",
		"version": "0.1.0",
	}
