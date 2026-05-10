import os

from core.openbb_client import ProxyManager


def test_proxy_manager_rotation():
	proxies = ["http://proxy1:8080", "http://proxy2:8080"]
	pm = ProxyManager(proxies)

	# Initial state
	assert "HTTP_PROXY" not in os.environ
	assert "HTTPS_PROXY" not in os.environ

	# Rotate 1
	pm.rotate()
	assert os.environ["HTTP_PROXY"] == "http://proxy1:8080"
	assert os.environ["HTTPS_PROXY"] == "http://proxy1:8080"

	# Rotate 2
	pm.rotate()
	assert os.environ["HTTP_PROXY"] == "http://proxy2:8080"
	assert os.environ["HTTPS_PROXY"] == "http://proxy2:8080"

	# Rotate 3 (Back to 1)
	pm.rotate()
	assert os.environ["HTTP_PROXY"] == "http://proxy1:8080"

	# Clear
	pm.clear()
	assert "HTTP_PROXY" not in os.environ
	assert "HTTPS_PROXY" not in os.environ


def test_proxy_manager_no_proxies():
	pm = ProxyManager([])
	pm.rotate()
	assert "HTTP_PROXY" not in os.environ
	assert "HTTPS_PROXY" not in os.environ
