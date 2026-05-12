import json
import os

from config import CACHE_DIR
from core.openbb_client import get_openbb_data
from core.stats import stats


def test_smart_cache_logging(mocker):
	# Setup cache
	symbol = "SMART_TEST"
	cache_file = CACHE_DIR / f"{symbol}.json"
	cache_file.parent.mkdir(parents=True, exist_ok=True)
	with open(cache_file, "w") as f:
		json.dump({"symbol": symbol, "name": "Test"}, f)

	# Mock logger
	mock_logger = mocker.patch("core.openbb_client.logger")

	# 1. Test Historical Cache Hit (should log)
	# Ensure it's not in session_fetches
	if stats.is_fetched(symbol):
		stats.session_fetches.remove(symbol.upper())

	get_openbb_data(symbol)
	cache_hit_called = any(
		"Cache hit" in str(call) for call in mock_logger.info.call_args_list
	)
	assert cache_hit_called, "Logger should log historical cache hits"

	# 2. Test Session Fetch (should suppress log)
	mock_logger.reset_mock()
	stats.record_fetch(symbol)

	get_openbb_data(symbol)
	cache_hit_called = any(
		"Cache hit" in str(call) for call in mock_logger.info.call_args_list
	)
	assert not cache_hit_called, (
		"Logger should suppress Cache hit for session-fetched items"
	)

	# Cleanup
	if cache_file.exists():
		os.remove(cache_file)
