import pytest

from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository


@pytest.fixture
def repo():
	db_manager = DatabaseManager(":memory:", skip_auto_seed=True)
	return DatabaseRepository(db_manager)


def _seed_pe_benchmark(repo):
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


def test_get_global_benchmarks_returns_seeded_entry(repo):
	"""Global benchmarks are loaded correctly from the DB."""
	_seed_pe_benchmark(repo)
	benchmarks = repo.get_global_benchmarks(asset_type="equity")
	assert len(benchmarks) == 1
	assert benchmarks[0]["metric"] == "pe_ratio"
	assert benchmarks[0]["best"] == 15
	assert benchmarks[0]["worst"] == 25


def test_global_benchmarks_no_sector_override(repo):
	"""Global benchmarks are returned as-is — no static sector patching."""
	_seed_pe_benchmark(repo)
	benchmarks = repo.get_global_benchmarks(asset_type="equity")
	assert benchmarks[0]["best"] == 15
	assert benchmarks[0]["worst"] == 25


def test_get_metric_history(repo):
	repo.insert_metric_history("AAPL", "pe_ratio", 28.5)
	repo.insert_metric_history("AAPL", "pe_ratio", 29.0)

	history = repo.get_metric_history("pe_ratio", symbol="AAPL")
	assert len(history) == 2
	values = [h["value"] for h in history]
	assert 28.5 in values
	assert 29.0 in values
