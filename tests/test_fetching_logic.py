import asyncio
from unittest.mock import patch

import pytest

from core.orchestrator import fetch_data


@pytest.fixture
def mock_fetch_bulk():
	with patch("core.openbb_client.fetch_openbb_data_bulk") as mock:
		mock.return_value = True
		yield mock


@pytest.fixture
def mock_analyze():
	with patch("core.orchestrator.analyze_asset") as mock:
		yield mock


def test_fetch_separation_no_analysis(mock_fetch_bulk, mock_analyze):
	"""
	Verify that fetch_data calls the fetching logic but NEVER triggers analysis.
	"""
	tickers = ["AAPL", "MSFT", "GOOGL"]

	# Execute fetch
	async def run_fetch():
		async for _ in fetch_data(tickers, batch_size=2, use_processes=False):
			pass

	asyncio.run(run_fetch())

	# Verify fetching was called (3 tickers in batches of 2 = 2 calls)
	assert mock_fetch_bulk.call_count == 2

	# CRITICAL: Verify analyze_asset was NEVER called
	mock_analyze.assert_not_called()


def test_fetch_threading_concurrency():
	"""
	Verify that the fetch logic handles multiple tickers correctly.
	Note: We test the orchestrator's batching loop.
	"""
	tickers = [f"TICK{i}" for i in range(10)]

	with patch("core.openbb_client.fetch_batch_with_backoff") as mock_batch:
		# Return success and a dummy cooldown
		mock_batch.return_value = (True, 5.0)

		# Set small batch size to force multiple iterations
		async def run_fetch():
			async for _ in fetch_data(tickers, batch_size=3, use_processes=False):
				pass

		asyncio.run(run_fetch())

		# 10 tickers / 3 batch_size = 4 batches (3, 3, 3, 1)
		assert mock_batch.call_count == 4


@pytest.mark.parametrize(
	"tickers,batch_size,expected_calls",
	[
		(["A", "B", "C"], 1, 3),
		(["A", "B", "C"], 3, 1),
		(["A", "B", "C"], 5, 1),
	],
)
def test_batching_logic(tickers, batch_size, expected_calls):
	with patch("core.openbb_client.fetch_batch_with_backoff") as mock_batch:
		mock_batch.return_value = (True, 5.0)

		async def run_fetch():
			async for _ in fetch_data(
				tickers, batch_size=batch_size, use_processes=False
			):
				pass

		asyncio.run(run_fetch())
		assert mock_batch.call_count == expected_calls
