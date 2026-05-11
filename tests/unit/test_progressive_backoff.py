from core.orchestrator import run_bulk_analysis


def test_run_bulk_analysis_progressive_backoff(mocker):
	# Mock fetch_openbb_data_bulk to return False (failure)
	mocker.patch("core.openbb_client.fetch_openbb_data_bulk", return_value=False)
	# Mock time.sleep to record sleep durations and not actually sleep
	mock_sleep = mocker.patch("time.sleep")
	# Mock analyze_asset to avoid deep analysis
	mocker.patch(
		"core.orchestrator.analyze_asset", return_value={"symbol": "MOCK", "score": 0}
	)

	# 3 batches of 20 tickers each (to trigger failures)
	tickers = ["T" + str(i) for i in range(60)]

	run_bulk_analysis(tickers, "balanced", max_workers=1)

	# Should have slept 6 times with progressive durations
	# Each batch gets 2 attempts.
	# Batch 1: 5s, 10s
	# Batch 2: 20s, 40s
	# Batch 3: 45s (max), 45s (max)
	assert mock_sleep.call_count == 6
	sleep_durations = [args.args[0] for args in mock_sleep.call_args_list]
	assert sleep_durations == [5.0, 10.0, 20.0, 40.0, 45.0, 45.0]


def test_run_bulk_analysis_reset_cooldown(mocker):
	# Batch 1: Fail (5s sleep), then Succeed (breather sleep, reset cooldown)
	# Batch 2: Fail (5s sleep), Fail (10s sleep)
	mock_bulk = mocker.patch("core.openbb_client.fetch_openbb_data_bulk")
	mock_bulk.side_effect = [False, True, False, False]

	mock_sleep = mocker.patch("time.sleep")
	mocker.patch(
		"core.orchestrator.analyze_asset", return_value={"symbol": "MOCK", "score": 0}
	)

	# 2 batches of 20 tickers each
	tickers = ["T" + str(i) for i in range(40)]

	run_bulk_analysis(tickers, "balanced", max_workers=1)

	# Sleep durations:
	# 1. 5.0 (failure)
	# 2. random(3, 5) (success)
	# 3. 5.0 (failure) - reset!
	# 4. 10.0 (failure)

	assert mock_sleep.call_count == 4
	d1 = mock_sleep.call_args_list[0][0][0]
	d2 = mock_sleep.call_args_list[1][0][0]
	d3 = mock_sleep.call_args_list[2][0][0]
	d4 = mock_sleep.call_args_list[3][0][0]

	assert d1 == 5.0
	assert 3.0 <= d2 <= 5.0
	assert d3 == 5.0
	assert d4 == 10.0


def test_run_bulk_analysis_max_cooldown(mocker):
	# Mock fetch_openbb_data_bulk to always return False
	mocker.patch("core.openbb_client.fetch_openbb_data_bulk", return_value=False)
	mock_sleep = mocker.patch("time.sleep")
	mocker.patch(
		"core.orchestrator.analyze_asset", return_value={"symbol": "MOCK", "score": 0}
	)

	# 4 batches to reach max cooldown and stabilize
	tickers = ["T" + str(i) for i in range(80)]  # 4 batches of 20

	run_bulk_analysis(tickers, "balanced", max_workers=1)

	# 4 batches * 2 attempts = 8 sleeps
	assert mock_sleep.call_count == 8
	sleep_durations = [args.args[0] for args in mock_sleep.call_args_list]
	assert sleep_durations == [5.0, 10.0, 20.0, 40.0, 45.0, 45.0, 45.0, 45.0]
