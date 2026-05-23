import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from core.database.repository import DatabaseRepository
from core.orchestrator import fetch_data
from core.schema import AssetData


class TestHybridOrchestrator(unittest.IsolatedAsyncioTestCase):
	def setUp(self):
		self.repo = MagicMock(spec=DatabaseRepository)
		self.repo.db = MagicMock()
		self.repo.db.db_path = "test.db"
		# Mock should_use_db_cache to always return False (force fetch)
		self.repo.should_use_db_cache.return_value = False

	@patch(
		"core.providers.sec_provider.SECProvider.is_configured",
		new_callable=PropertyMock,
	)
	@patch(
		"core.providers.fred_provider.FREDProvider.is_configured",
		new_callable=PropertyMock,
	)
	@patch("core.providers.sec_provider.SECProvider.get_data")
	@patch("core.providers.fred_provider.FREDProvider.get_data")
	@patch("core.orchestrator._fetch_batch_process_worker")
	async def test_hybrid_fetch_data(
		self, mock_openbb, mock_fred, mock_sec, mock_fred_conf, mock_sec_conf
	):
		# Mock configuration to return True
		mock_fred_conf.return_value = True
		mock_sec_conf.return_value = True

		# 1. Mock SEC response
		mock_sec.side_effect = lambda symbol, **kwargs: AssetData(
			symbol=symbol,
			metrics={"net_income": 1000},
			raw_data={"entityName": "Test Co"},
		)

		# 2. Mock FRED response
		mock_fred.return_value = AssetData(
			symbol="MACRO", metrics={"10y_yield": 4.5}, raw_data={"val": 4.5}
		)

		# 3. Mock OpenBB response
		mock_openbb.return_value = (
			True,
			5.0,
			{"AAPL": {"price": 150, "symbol": "AAPL"}},
		)

		tickers = ["AAPL"]
		batches = []
		# Set use_processes=False for easier mocking and speed in unit tests
		async for batch in fetch_data(tickers, repo=self.repo, use_processes=False):
			batches.append(batch)

		self.assertEqual(len(batches), 1)
		self.assertEqual(batches[0], ["AAPL"])

		# Verify SEC was called
		mock_sec.assert_called()

		# Verify FRED was called
		mock_fred.assert_called_with("MACRO")

		# Verify DB upserts
		self.assertTrue(self.repo.upsert_raw_provider_data.called)

		# Check calls to upsert_raw_provider_data
		calls = self.repo.upsert_raw_provider_data.call_args_list
		providers = [c[0][1] for c in calls]
		self.assertIn("sec", providers)
		self.assertIn("fred", providers)
		self.assertIn("yfinance", providers)

	@patch(
		"core.providers.sec_provider.SECProvider.is_configured",
		new_callable=PropertyMock,
	)
	@patch(
		"core.providers.fred_provider.FREDProvider.is_configured",
		new_callable=PropertyMock,
	)
	@patch("core.providers.sec_provider.SECProvider.get_data")
	@patch("core.providers.fred_provider.FREDProvider.get_data")
	@patch("core.orchestrator.ProcessPoolExecutor")
	async def test_fetch_data_cancellation(
		self, mock_executor_class, mock_fred, mock_sec, mock_fred_conf, mock_sec_conf
	):
		"""
		Test that fetch_data terminates worker processes and shuts down the executor
		cleanly when the fetching task is cancelled.

		Parameters:
			mock_executor_class (MagicMock): Mocked ProcessPoolExecutor class.
			mock_fred (MagicMock): Mocked FRED get_data method.
			mock_sec (MagicMock): Mocked SEC get_data method.
			mock_fred_conf (PropertyMock): Mocked FRED configuration status.
			mock_sec_conf (PropertyMock): Mocked SEC configuration status.
		"""
		import asyncio
		from concurrent.futures import Future

		mock_fred_conf.return_value = False
		mock_sec_conf.return_value = False

		mock_pool = MagicMock()
		mock_executor_class.return_value = mock_pool

		# Mock submit() to return a real concurrent.futures.Future
		# to satisfy loop.run_in_executor and wrap_future assertions
		mock_pool.submit.return_value = Future()

		mock_process = MagicMock()
		mock_process.pid = 12345
		mock_pool._processes = {12345: mock_process}

		# Simulate cancellation by raising CancelledError during asyncio.sleep
		with patch("asyncio.sleep", side_effect=asyncio.CancelledError()):
			with self.assertRaises(asyncio.CancelledError):
				async for _ in fetch_data(
					["AAPL", "MSFT"], repo=self.repo, use_processes=True
				):
					pass

		# Verify that the process was terminated/killed
		mock_process.terminate.assert_called_once()
		# Verify that the executor was shutdown properly
		mock_pool.shutdown.assert_any_call(wait=False, cancel_futures=True)
		mock_pool.shutdown.assert_any_call(wait=True)


if __name__ == "__main__":
	unittest.main()
