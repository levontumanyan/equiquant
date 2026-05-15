import asyncio

from core.orchestrator import fetch_data


def test_fetch_data_progressive_backoff(mocker):
	mocker.patch("core.openbb_client.fetch_openbb_data_bulk", return_value=(False, {}))
	mocker.patch("core.openbb_client.probe_api", return_value=True)
	mock_sleep = mocker.patch("time.sleep")

	tickers = ["T" + str(i) for i in range(60)]

	async def run_fetch():
		async for _ in fetch_data(tickers, batch_size=20, use_processes=False):
			pass

	asyncio.run(run_fetch())

	sleep_durations = [args.args[0] for args in mock_sleep.call_args_list]
	backoff_sleeps = [d for d in sleep_durations if d >= 5.0]
	assert backoff_sleeps == [5.0, 10.0, 20.0, 40.0, 60.0, 60.0]


def test_fetch_data_reset_cooldown(mocker):
	mock_bulk = mocker.patch("core.openbb_client.fetch_openbb_data_bulk")
	mock_bulk.side_effect = [(False, {}), (True, {}), (False, {}), (False, {})]
	mocker.patch("core.openbb_client.probe_api", return_value=True)

	mock_sleep = mocker.patch("time.sleep")

	tickers = ["T" + str(i) for i in range(40)]

	async def run_fetch():
		async for _ in fetch_data(tickers, batch_size=20, use_processes=False):
			pass

	asyncio.run(run_fetch())

	sleep_durations = [args.args[0] for args in mock_sleep.call_args_list]
	backoff_sleeps = [d for d in sleep_durations if d >= 5.0]
	assert backoff_sleeps == [5.0, 5.0, 10.0]


def test_fetch_data_max_cooldown(mocker):
	mocker.patch("core.openbb_client.fetch_openbb_data_bulk", return_value=(False, {}))
	mocker.patch("core.openbb_client.probe_api", return_value=True)
	mock_sleep = mocker.patch("time.sleep")

	tickers = ["T" + str(i) for i in range(80)]

	async def run_fetch():
		async for _ in fetch_data(tickers, batch_size=20, use_processes=False):
			pass

	asyncio.run(run_fetch())

	sleep_durations = [args.args[0] for args in mock_sleep.call_args_list]
	backoff_sleeps = [d for d in sleep_durations if d >= 5.0]
	assert backoff_sleeps == [5.0, 10.0, 20.0, 40.0, 60.0, 60.0, 60.0, 60.0]
