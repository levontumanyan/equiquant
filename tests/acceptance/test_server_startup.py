import json
import subprocess
import time
import urllib.request

import pytest

TEST_PORT = 8099


def _wait_for_openbb(port: int, timeout: int = 45) -> dict:
	"""Poll /api/status until OpenBB is ready or timeout expires."""
	deadline = time.time() + timeout
	last_data = {}
	while time.time() < deadline:
		try:
			with urllib.request.urlopen(
				f"http://127.0.0.1:{port}/api/status", timeout=2
			) as r:
				last_data = json.loads(r.read())
				if last_data.get("openbb") == "ready":
					return last_data
		except Exception:
			pass
		time.sleep(1)
	return last_data


@pytest.fixture(scope="module")
def live_server():
	"""Spin up a real uvicorn process and tear it down after the module."""
	proc = subprocess.Popen(
		[
			"uv",
			"run",
			"uvicorn",
			"core.api:app",
			"--host",
			"127.0.0.1",
			"--port",
			str(TEST_PORT),
		],
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
	)
	yield proc
	proc.terminate()
	try:
		proc.wait(timeout=5)
	except subprocess.TimeoutExpired:
		proc.kill()


@pytest.mark.slow
def test_server_starts_and_openbb_warms_up(live_server):
	"""
	Verifies that a real uvicorn process starts and OpenBB is ready
	within 45 seconds — proving the asynchronous lifespan warmup works
	end-to-end with no threading/signal issues.
	"""
	data = _wait_for_openbb(TEST_PORT, timeout=45)
	assert data.get("backend") == "connected", "Server never became reachable"
	assert data.get("openbb") == "ready", (
		f"OpenBB not ready after 45s — got: {data.get('openbb')!r}. Check that the lifespan offloads OpenBB to a background thread."
	)


@pytest.mark.slow
def test_status_endpoint_structure(live_server):
	"""Verifies /api/status returns the expected keys once the server is up."""
	data = _wait_for_openbb(TEST_PORT, timeout=45)
	assert {"backend", "database", "version", "openbb"} <= data.keys()
	assert data["database"] == "available"
