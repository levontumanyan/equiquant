from core.orchestrator import _fetch_batch_with_backoff


def test_fetch_batch_with_backoff_success(mocker):
	mocker.patch("core.openbb_client.fetch_openbb_data_bulk", return_value=True)
	mock_probe = mocker.patch("core.openbb_client.probe_api")
	mock_sleep = mocker.patch("time.sleep")

	success, cooldown = _fetch_batch_with_backoff(["AAPL"], 5.0)

	assert success is True
	assert cooldown == 5.0  # Base cooldown returned on success
	assert mock_probe.call_count == 0
	assert mock_sleep.call_count == 0


def test_fetch_batch_with_backoff_probe_success_immediately(mocker):
	# Fail bulk once, then success on second attempt
	# But before second attempt, probe succeeds immediately
	mock_bulk = mocker.patch("core.openbb_client.fetch_openbb_data_bulk")
	mock_bulk.side_effect = [False, True]

	mock_probe = mocker.patch("core.openbb_client.probe_api", return_value=True)
	mock_sleep = mocker.patch("time.sleep")

	success, cooldown = _fetch_batch_with_backoff(["AAPL", "MSFT"], 5.0)

	assert success is True
	assert cooldown == 5.0  # Reset to base on final success
	assert mock_bulk.call_count == 2
	assert mock_probe.call_count == 1
	assert mock_sleep.call_count == 1
	assert mock_sleep.call_args_list[0][0][0] == 5.0


def test_fetch_batch_with_backoff_probe_fails_then_succeeds(mocker):
	# Fail bulk once
	# Initial sleep 5s
	# Probe fails once (doubles to 10s), then succeeds
	# Then bulk succeeds
	mock_bulk = mocker.patch("core.openbb_client.fetch_openbb_data_bulk")
	mock_bulk.side_effect = [False, True]

	mock_probe = mocker.patch("core.openbb_client.probe_api")
	mock_probe.side_effect = [False, True]

	mock_sleep = mocker.patch("time.sleep")

	success, cooldown = _fetch_batch_with_backoff(["AAPL", "MSFT"], 5.0)

	assert success is True
	assert mock_bulk.call_count == 2
	assert mock_probe.call_count == 2
	assert mock_sleep.call_count == 2
	assert mock_sleep.call_args_list[0][0][0] == 5.0
	assert mock_sleep.call_args_list[1][0][0] == 10.0


def test_fetch_batch_with_backoff_probe_hits_max_cooldown(mocker):
	# Fail bulk
	# Initial sleep 5s
	# Probe fails 5 times (10, 20, 40, 60, 60) then succeeds
	# Bulk still fails (second attempt)
	mocker.patch("core.openbb_client.fetch_openbb_data_bulk", return_value=False)

	mock_probe = mocker.patch("core.openbb_client.probe_api")
	mock_probe.side_effect = [
		False,
		False,
		False,
		False,
		False,
		True,
		True,
	]  # Success for second attempt probe too

	mock_sleep = mocker.patch("time.sleep")

	success, cooldown = _fetch_batch_with_backoff(["AAPL"], 5.0)

	assert success is False
	# Cooldown should be maxed out
	assert cooldown == 60.0

	# Attempt 1:
	# 1. sleep 5.0
	# 2. probe fail -> double to 10.0, sleep 10.0
	# 3. probe fail -> double to 20.0, sleep 20.0
	# 4. probe fail -> double to 40.0, sleep 40.0
	# 5. probe fail -> double to 60.0, sleep 60.0
	# 6. probe fail -> double to 60.0, sleep 60.0
	# 7. probe success

	# Attempt 2:
	# 1. sleep 60.0
	# 2. probe success immediately

	# Total sleeps: 1 + 5 + 1 = 7
	assert mock_sleep.call_count == 7
	durations = [args.args[0] for args in mock_sleep.call_args_list]
	assert durations == [5.0, 10.0, 20.0, 40.0, 60.0, 60.0, 60.0]
