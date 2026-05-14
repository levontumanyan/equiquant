import pytest

from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository


@pytest.fixture
def repo():
	db_manager = DatabaseManager(":memory:")
	return DatabaseRepository(db_manager)


def test_get_effective_benchmarks(repo):
	# Add global benchmark
	repo.upsert_global_benchmark(
		asset_type="equity",
		metric_key="pe_ratio",
		name="P/E Ratio",
		formula_type="sigmoid",
		unit="x",
		is_decimal=False,
		display_key=None,
		params_json='{"best": 15, "worst": 25}',
		weight=1.0,
	)

	# Get global
	benchmarks = repo.get_effective_benchmarks(asset_type="equity")
	assert len(benchmarks) == 1
	assert benchmarks[0]["metric"] == "pe_ratio"
	assert benchmarks[0]["best"] == 15

	# Add sector override
	repo.upsert_sector_benchmark(
		sector="Technology",
		metric_key="pe_ratio",
		benchmark_type="best_worst",
		value_a=25.0,
		value_b=40.0,
	)

	# Get with sector override
	benchmarks = repo.get_effective_benchmarks(asset_type="equity", sector="Technology")
	assert len(benchmarks) == 1
	assert benchmarks[0]["metric"] == "pe_ratio"
	assert benchmarks[0]["best"] == 25.0
	assert benchmarks[0]["worst"] == 40.0
	assert benchmarks[0]["type"] == "sigmoid"


def test_get_metric_history(repo):
	repo.insert_metric_history("AAPL", "pe_ratio", 28.5)
	repo.insert_metric_history("AAPL", "pe_ratio", 29.0)

	history = repo.get_metric_history("pe_ratio", symbol="AAPL")
	assert len(history) == 2
	values = [h["value"] for h in history]
	assert 28.5 in values
	assert 29.0 in values
