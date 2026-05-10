import pytest

from core.data import get_stock_data, load_benchmarks
from core.database import DatabaseManager, DatabaseRepository
from core.orchestrator import run_bulk_analysis
from core.profiles import get_profile_weights


@pytest.fixture
def repo(tmp_path):
	db_file = tmp_path / "test_market_integration.db"
	manager = DatabaseManager(str(db_file))
	repo = DatabaseRepository(manager)

	# Seed the DB with some basic profiles for tests
	repo.upsert_profile("balanced", "Balanced")
	repo.upsert_profile_weight("balanced", "trailingPE", 2.0)
	repo.upsert_profile("growth", "Growth")
	repo.upsert_profile_weight("growth", "revenueGrowth", 2.5)

	yield repo
	manager.close()


def test_load_benchmarks_no_repo():
	# Test that it returns empty list if no repo provided
	assert load_benchmarks("STOCK") == []


def test_run_bulk_analysis(mocker, repo):
	# Mock analyze_asset to avoid hitting the network/provider
	mock_res = {"symbol": "AAPL", "score": 80.0}
	mocker.patch("core.orchestrator.analyze_asset", return_value=mock_res)

	callback_called = False

	def callback(res):
		nonlocal callback_called
		callback_called = True

	results = run_bulk_analysis(
		["AAPL"], "balanced", progress_callback=callback, repo=repo
	)

	assert len(results) == 1
	assert results[0]["symbol"] == "AAPL"
	assert callback_called


def test_get_profile_weights_invalid(repo):
	# Test fallback to balanced if profile not found
	weights = get_profile_weights(repo, "invalid_profile_name")
	assert isinstance(weights, dict)
	assert len(weights) > 0  # Should fallback to balanced which has weights
	assert weights.get("trailingPE") == 2.0


def test_get_stock_data(mocker):
	# Mock the provider to avoid real API calls
	mocker.patch("core.data.OpenBBProvider.get_data", return_value="mocked_data")
	assert get_stock_data("AAPL") == "mocked_data"
