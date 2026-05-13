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


def test_session_stats_request_tracking():
	stats = SessionStats()
	stats.record_request("https://api.example.com", 0.5)
	stats.record_request("https://api.example.com", 0.7)
	stats.record_request("https://other.com", 1.0)

	assert stats.http_requests == 3
	assert stats.io_time_total == 2.2
	assert stats.endpoint_counts["https://api.example.com"] == 2

	d = stats.to_dict()
	assert d["endpoints"]["https://api.example.com"]["count"] == 2
	assert d["endpoints"]["https://api.example.com"]["avg_latency_s"] == 0.6
	assert d["io_time_s"] == 2.2


def test_session_stats_cooldown():
	stats = SessionStats()
	stats.record_cooldown(1.5)
	assert stats.cooldown_time_total == 1.5
	assert stats.to_dict()["cooldown_time_s"] == 1.5


def test_session_stats_metric_coverage():
	stats = SessionStats()
	stats.record_metric_coverage("pe_ratio", True)
	stats.record_metric_coverage("pe_ratio", False)
	stats.record_metric_coverage("pe_ratio", True)

	assert stats.data_coverage["pe_ratio"]["present"] == 2
	assert stats.data_coverage["pe_ratio"]["missing"] == 1

	d = stats.to_dict()
	assert d["data_density_pct"]["pe_ratio"] == 66.7


def test_session_stats_artifacts():
	stats = SessionStats()
	stats.record_artifact("report.csv")
	stats.record_artifact("logs.txt")

	assert "report.csv" in stats.artifacts
	assert len(stats.artifacts) == 2
	assert "report.csv" in stats.to_dict()["artifacts"]


def test_session_stats_errors():
	stats = SessionStats()
	stats.record_error("timeout")
	stats.record_error("rate_limit")
	stats.record_error("timeout")

	assert stats.errors == 3
	assert stats.error_types["timeout"] == 2
	assert stats.rate_limit_errors == 1

	d = stats.to_dict()
	assert d["errors"] == 3
	assert d["rate_limit_errors"] == 1
	assert d["error_types"]["timeout"] == 2


def test_session_stats_fetches():
	stats = SessionStats()
	stats.record_fetch("AAPL")
	assert stats.is_fetched("AAPL")
	assert stats.is_fetched("aapl")
	assert not stats.is_fetched("MSFT")
