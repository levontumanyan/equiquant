import asyncio

from core.orchestrator import fetch_data


def test_fetch_data_progressive_backoff(mocker):
	# Mock fetch_openbb_data_bulk to return False (failure)
	mocker.patch("core.openbb_client.fetch_openbb_data_bulk", return_value=False)
	# Mock probe_api to always succeed to keep original test behavior (minimal sleeps)
	mocker.patch("core.openbb_client.probe_api", return_value=True)
	# Mock time.sleep to record sleep durations and not actually sleep
	mock_sleep = mocker.patch("time.sleep")

	# 3 batches of 20 tickers each (to trigger failures)
	tickers = ["T" + str(i) for i in range(60)]

	async def run_fetch():
		async for _ in fetch_data(tickers, batch_size=20, use_processes=False):
			pass

	asyncio.run(run_fetch())

	# Should have slept 6 times with progressive durations + 2 inter-batch sleeps
	# Note: asyncio.to_thread runs the blocking part in a thread, so time.sleep is called there.
	sleep_durations = [args.args[0] for args in mock_sleep.call_args_list]
	backoff_sleeps = [d for d in sleep_durations if d >= 5.0]
	assert backoff_sleeps == [5.0, 10.0, 20.0, 40.0, 60.0, 60.0]


def test_fetch_data_reset_cooldown(mocker):
	# Batch 1: Fail (5s sleep), then Succeed (breather sleep, reset cooldown)
	# Batch 2: Fail (5s sleep), Fail (10s sleep)
	mock_bulk = mocker.patch("core.openbb_client.fetch_openbb_data_bulk")
	mock_bulk.side_effect = [False, True, False, False]
	# Mock probe_api to always succeed
	mocker.patch("core.openbb_client.probe_api", return_value=True)

	mock_sleep = mocker.patch("time.sleep")

	# 2 batches of 20 tickers each
	tickers = ["T" + str(i) for i in range(40)]

	async def run_fetch():
		async for _ in fetch_data(tickers, batch_size=20, use_processes=False):
			pass

	asyncio.run(run_fetch())

	# Sleep durations should be:
	# 1. 5.0 (Batch 1, Attempt 1 fail)
	# 2. 5.0 (Batch 2, Attempt 1 fail) - reset!
	# 3. 10.0 (Batch 2, Attempt 2 fail)
	sleep_durations = [args.args[0] for args in mock_sleep.call_args_list]
	backoff_sleeps = [d for d in sleep_durations if d >= 5.0]
	assert backoff_sleeps == [5.0, 5.0, 10.0]


def test_fetch_data_max_cooldown(mocker):
	# Mock fetch_openbb_data_bulk to always return False
	mocker.patch("core.openbb_client.fetch_openbb_data_bulk", return_value=False)
	# Mock probe_api to always succeed
	mocker.patch("core.openbb_client.probe_api", return_value=True)
	mock_sleep = mocker.patch("time.sleep")

	# 4 batches to reach max cooldown and stabilize
	tickers = ["T" + str(i) for i in range(80)]  # 4 batches of 20

	async def run_fetch():
		async for _ in fetch_data(tickers, batch_size=20, use_processes=False):
			pass

	asyncio.run(run_fetch())

	# 4 batches * 2 attempts = 8 backoff sleeps + 3 inter-batch sleeps
	sleep_durations = [args.args[0] for args in mock_sleep.call_args_list]
	backoff_sleeps = [d for d in sleep_durations if d >= 5.0]
	assert backoff_sleeps == [5.0, 10.0, 20.0, 40.0, 60.0, 60.0, 60.0, 60.0]
