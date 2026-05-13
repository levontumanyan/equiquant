import json

from core.openbb_client import get_openbb_data
from core.stats import stats


def test_cache_hit_rate_bug_reproduction(mocker, tmp_path):
	"""
	Reproduce the bug where data fetched in the same session is incorrectly counted as a cache hit.
	"""
	# 1. Setup Mock Cache Directory
	cache_dir = tmp_path / "cache"
	cache_dir.mkdir()
	mocker.patch("core.openbb_client.CACHE_DIR", cache_dir)

	ticker = "REPRO"
	cache_file = cache_dir / f"{ticker}.json"
	mock_data = {"symbol": ticker, "price": 100}
	cache_file.write_text(json.dumps(mock_data))

	# 2. Mock should_use_cache to return True (simulating a fresh file on disk)
	mocker.patch("core.openbb_client.should_use_cache", return_value=True)

	# 3. Reset stats for clean test
	stats.cache_hits = 0
	stats.session_fetches.clear()

	# 4. Simulate that the ticker WAS fetched in this session (e.g., during bulk fetch)
	stats.record_fetch(ticker)
	assert stats.is_fetched(ticker) is True

	# 5. Call get_openbb_data
	# It should detect the file on disk (cache hit) but since it was fetched
	# in this session, it SHOULD NOT increment stats.cache_hits.
	get_openbb_data(ticker)

	# EXPECTATION: stats.cache_hits should be 0 because it was fetched in this session.
	# ACTUAL (Bug): stats.cache_hits will be 1.
	assert stats.cache_hits == 0, (
		f"Expected 0 cache hits for session-fetched ticker, but got {stats.cache_hits}"
	)
