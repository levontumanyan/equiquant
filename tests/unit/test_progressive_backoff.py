import asyncio
from unittest.mock import patch

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


# ---------------------------------------------------------------------------
# Parallel coordinator (use_processes=True path) tests
# ---------------------------------------------------------------------------


class _ImmediateExecutor:
	"""Fake ProcessPoolExecutor: runs submitted callables synchronously in-process."""

	def __init__(self, *args, **kwargs):
		pass

	def submit(self, fn, *args, **kwargs):
		import concurrent.futures

		f = concurrent.futures.Future()
		try:
			f.set_result(fn(*args, **kwargs))
		except Exception as exc:
			f.set_exception(exc)
		return f

	def shutdown(self, *args, **kwargs):
		pass


def test_parallel_coordinator_shared_cooldown(mocker):
	"""
	With the round-based coordinator, a rate-limit in round N triggers a single
	shared asyncio.sleep (non-blocking) before retrying — not a time.sleep per worker.
	After the cooldown the retried batch succeeds.
	"""
	# Batch 0: rate-limited first time, succeeds on retry
	# Batch 1: succeeds immediately
	single_attempt_calls = iter(
		[
			(False, True, {}),  # batch 0, round 1 → rate limited
			(True, False, {"T20": {}}),  # batch 1, round 1 → success
			(True, False, {"T0": {}}),  # batch 0, round 2 (retry) → success
		]
	)

	mocker.patch(
		"core.orchestrator._fetch_batch_single_attempt_worker",
		side_effect=lambda tickers, db_path=None: next(single_attempt_calls),
	)
	mocker.patch("core.orchestrator.ProcessPoolExecutor", _ImmediateExecutor)

	async_sleep_calls: list = []

	async def fake_async_sleep(seconds):
		async_sleep_calls.append(seconds)

	async def anyio_run_sync(fn, *args, **kwargs):
		"""Return True for probe calls (functools.partial), None for enrichment."""
		import functools

		return True if isinstance(fn, functools.partial) else None

	tickers = ["T" + str(i) for i in range(40)]

	with (
		patch("asyncio.sleep", side_effect=fake_async_sleep),
		patch("anyio.to_thread.run_sync", side_effect=anyio_run_sync),
	):

		async def run_fetch():
			fetched = []
			async for batch in fetch_data(tickers, batch_size=20, use_processes=True):
				fetched.extend(batch)
			return fetched

		result = asyncio.run(run_fetch())

	# Cooldown fired exactly once for the shared rate-limit event (probe succeeded immediately)
	cooldown_sleeps = [s for s in async_sleep_calls if s >= 5.0]
	assert len(cooldown_sleeps) == 1
	assert cooldown_sleeps[0] == 5.0

	# Both batches ultimately yielded results
	assert set(result) == {"T" + str(i) for i in range(40)}


def test_parallel_coordinator_permanent_failure_skipped(mocker):
	"""
	A permanent failure (is_rate_limited=False, success=False) is logged and skipped —
	not retried and does not trigger a cooldown.
	"""
	single_attempt_calls = iter(
		[
			(False, False, {}),  # batch 0: permanent failure → skip
			(True, False, {"T20": {}}),  # batch 1: success
		]
	)

	mocker.patch(
		"core.orchestrator._fetch_batch_single_attempt_worker",
		side_effect=lambda tickers, db_path=None: next(single_attempt_calls),
	)
	mocker.patch("core.orchestrator.ProcessPoolExecutor", _ImmediateExecutor)

	async_sleep_calls: list = []

	async def fake_async_sleep(seconds):
		async_sleep_calls.append(seconds)

	async def anyio_run_sync(fn, *args, **kwargs):
		return None  # enrichment only; no probe expected here

	tickers = ["T" + str(i) for i in range(40)]

	with (
		patch("asyncio.sleep", side_effect=fake_async_sleep),
		patch("anyio.to_thread.run_sync", side_effect=anyio_run_sync),
	):

		async def run_fetch():
			fetched = []
			async for batch in fetch_data(tickers, batch_size=20, use_processes=True):
				fetched.extend(batch)
			return fetched

		result = asyncio.run(run_fetch())

	# No cooldown should fire for a permanent failure
	cooldown_sleeps = [s for s in async_sleep_calls if s >= 5.0]
	assert len(cooldown_sleeps) == 0

	# Only the successful batch is in results (T20..T39)
	assert set(result) == {"T" + str(i) for i in range(20, 40)}
