import pytest
from fastapi.testclient import TestClient

from core.api import app


def test_health_check():
	"""Tests the /health endpoint without triggering lifespan."""
	with TestClient(app, raise_server_exceptions=True) as client:
		response = client.get("/health")
	assert response.status_code == 200
	assert response.json() == {
		"status": "online",
		"version": "0.1.0",
		"message": "EquiQuant API is running",
	}


def test_get_status_shape():
	"""Tests the /api/status response shape without asserting OpenBB state."""
	with TestClient(app) as client:
		response = client.get("/api/status")
	assert response.status_code == 200
	data = response.json()
	assert data["backend"] == "connected"
	assert data["database"] == "available"
	assert data["version"] == "0.1.0"
	assert "openbb" in data
	assert data["openbb"] in ("ready", "warming_up")


@pytest.mark.slow
def test_openbb_ready_after_lifespan(mocker):
	"""
	Verifies OpenBB is fully ready after the lifespan runs.
	Mocking signal.signal is necessary because TestClient runs lifespan in a thread.
	"""
	mocker.patch("signal.signal")
	with TestClient(app) as client:
		response = client.get("/api/status")
	assert response.status_code == 200
	assert response.json()["openbb"] == "ready"
