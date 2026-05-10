import time

from core.stats import SessionStats


def test_session_stats_api_tracking():
	stats = SessionStats()

	# Test initial state
	assert stats.api_attempts == 0
	assert stats.api_successes == 0
	assert stats.api_calls == 0

	# Test incrementing attempts
	stats.api_attempts += 1
	assert stats.api_attempts == 1
	assert stats.api_calls == 1  # Legacy support

	# Test legacy setter
	stats.api_calls = 5
	assert stats.api_attempts == 5

	# Test successes
	stats.api_successes = 3

	# Test to_dict
	d = stats.to_dict()
	assert d["api_attempts"] == 5
	assert d["api_successes"] == 3
	assert "total_duration_s" in d


def test_session_stats_stages():
	stats = SessionStats()
	stats.start_stage("Test")
	time.sleep(0.1)
	stats.end_stage("Test")

	assert "Test" in stats.stage_times
	assert stats.stage_times["Test"] >= 0.1

	d = stats.to_dict()
	assert d["stage_durations_s"]["Test"] >= 0.1
