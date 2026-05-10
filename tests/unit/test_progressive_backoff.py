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

	run_bulk_analysis(tickers, "balanced")

	# Should have slept 3 times with progressive durations
	# First: 5s
	# Second: 10s
	# Third: 20s
	assert mock_sleep.call_count == 3
	sleep_durations = [args.args[0] for args in mock_sleep.call_args_list]
	assert sleep_durations == [5.0, 10.0, 20.0]


def test_run_bulk_analysis_reset_cooldown(mocker):
	# Mock fetch_openbb_data_bulk to return False, then True, then False
	mock_bulk = mocker.patch("core.openbb_client.fetch_openbb_data_bulk")
	mock_bulk.side_effect = [False, True, False]

	mock_sleep = mocker.patch("time.sleep")
	mocker.patch(
		"core.orchestrator.analyze_asset", return_value={"symbol": "MOCK", "score": 0}
	)

	# 3 batches of 20 tickers each
	tickers = ["T" + str(i) for i in range(60)]

	run_bulk_analysis(tickers, "balanced")

	# Sleep durations:
	# 1. 5.0 (failure)
	# 2. random(3, 5) (success)
	# 3. 5.0 (failure) - reset!

	assert mock_sleep.call_count == 3
	d1 = mock_sleep.call_args_list[0][0][0]
	d2 = mock_sleep.call_args_list[1][0][0]
	d3 = mock_sleep.call_args_list[2][0][0]

	assert d1 == 5.0
	assert 3.0 <= d2 <= 5.0
	assert d3 == 5.0


def test_run_bulk_analysis_max_cooldown(mocker):
	# Mock fetch_openbb_data_bulk to always return False
	mocker.patch("core.openbb_client.fetch_openbb_data_bulk", return_value=False)
	mock_sleep = mocker.patch("time.sleep")
	mocker.patch(
		"core.orchestrator.analyze_asset", return_value={"symbol": "MOCK", "score": 0}
	)

	# Many batches to reach max cooldown
	# 5, 10, 20, 40, 45, 45
	tickers = ["T" + str(i) for i in range(120)]  # 6 batches of 20

	run_bulk_analysis(tickers, "balanced")

	assert mock_sleep.call_count == 6
	sleep_durations = [args.args[0] for args in mock_sleep.call_args_list]
	assert sleep_durations == [5.0, 10.0, 20.0, 40.0, 45.0, 45.0]
