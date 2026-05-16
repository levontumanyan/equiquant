import pytest

from core.data import load_benchmarks
from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository
from core.orchestrator import analyze_asset


@pytest.fixture
def db_manager(tmp_path):
	db_file = tmp_path / "test_versioning.db"
	manager = DatabaseManager(str(db_file), skip_auto_seed=True)

	# Manually create tables
	conn = manager.get_connection()
	conn.execute(
		"CREATE TABLE IF NOT EXISTS investor_profiles (name TEXT PRIMARY KEY, description TEXT);"
	)
	conn.execute("""
		CREATE TABLE IF NOT EXISTS profile_metric_settings (
			profile_name TEXT,
			metric_key TEXT,
			weight REAL DEFAULT 1.0,
			range_min REAL DEFAULT 0.0,
			range_max REAL DEFAULT 100.0,
			formula TEXT DEFAULT 'sigmoid',
			PRIMARY KEY (profile_name, metric_key),
			FOREIGN KEY (profile_name) REFERENCES investor_profiles(name)
		);
	""")

	yield manager
	manager.close()


@pytest.fixture
def repo(db_manager):
	return DatabaseRepository(db_manager)


def test_benchmark_versioning(repo):
	"""Test that different versions of benchmarks can coexist and be retrieved."""
	# 1. Upsert version 1.0.0
	repo.upsert_global_benchmark(
		asset_type="STOCK",
		metric_key="pe_ratio",
		name="P/E Ratio",
		formula_type="sigmoid",
		unit="multiplier",
		is_decimal=False,
		display_key=None,
		params_json='{"best": 15, "worst": 30}',
		weight=1.0,
		version="1.0.0",
	)

	# 2. Upsert version 2.0.0 with different params
	repo.upsert_global_benchmark(
		asset_type="STOCK",
		metric_key="pe_ratio",
		name="P/E Ratio",
		formula_type="sigmoid",
		unit="multiplier",
		is_decimal=False,
		display_key=None,
		params_json='{"best": 10, "worst": 20}',
		weight=1.5,
		version="2.0.0",
	)

	# 3. Retrieve and verify
	v1 = repo.get_global_benchmarks("STOCK", version="1.0.0")
	v2 = repo.get_global_benchmarks("STOCK", version="2.0.0")

	assert len(v1) == 1
	assert len(v2) == 1
	assert v1[0]["best"] == 15
	assert v2[0]["best"] == 10
	assert v1[0]["weight"] == 1.0
	assert v2[0]["weight"] == 1.5


def test_sector_benchmark_versioning(repo):
	"""Test versioning for sector-specific benchmarks."""
	repo.upsert_sector_benchmark(
		sector="Tech",
		metric_key="pe_ratio",
		benchmark_type="best_worst",
		value_a=20.0,
		value_b=40.0,
		version="1.0.0",
	)
	repo.upsert_sector_benchmark(
		sector="Tech",
		metric_key="pe_ratio",
		benchmark_type="best_worst",
		value_a=25.0,
		value_b=50.0,
		version="2.0.0",
	)

	v1 = repo.get_sector_benchmarks("Tech", version="1.0.0")
	v2 = repo.get_sector_benchmarks("Tech", version="2.0.0")

	assert v1[0]["value_a"] == 20.0
	assert v2[0]["value_a"] == 25.0


def test_analysis_snapshot_versioning(repo):
	"""Test that analysis snapshots record the benchmark version."""
	import time

	symbol = "AAPL"
	profile = "balanced"
	repo.create_analysis_snapshot(
		symbol, profile, 85.0, "{}", benchmark_version="1.0.0"
	)
	time.sleep(1.1)
	repo.create_analysis_snapshot(
		symbol, profile, 90.0, "{}", benchmark_version="2.0.0"
	)

	history = repo.get_historical_scores(symbol, profile)
	assert len(history) == 2
	assert history[0]["benchmark_version"] == "2.0.0"
	assert history[1]["benchmark_version"] == "1.0.0"


def test_load_benchmarks_with_version(repo):
	"""Test loading benchmarks with a specific version."""
	# Setup global v1 and v2
	repo.upsert_global_benchmark(
		"STOCK",
		"pe",
		"PE",
		"sigmoid",
		None,
		False,
		None,
		'{"best": 15, "worst": 30}',
		1.0,
		"1.0.0",
	)
	repo.upsert_global_benchmark(
		"STOCK",
		"pe",
		"PE",
		"sigmoid",
		None,
		False,
		None,
		'{"best": 10, "worst": 20}',
		1.0,
		"2.0.0",
	)
	repo.upsert_global_benchmark(
		"STOCK",
		"roe",
		"ROE",
		"bell_curve",
		None,
		False,
		None,
		'{"target": 0.1, "width": 0.02}',
		1.0,
		"2.0.0",
	)

	# Setup sector override for v2 only
	repo.upsert_sector_benchmark("Tech", "pe", "best_worst", 5.0, 15.0, "2.0.0")
	repo.upsert_sector_benchmark("Tech", "roe", "target_width", 0.15, 0.05, "2.0.0")

	# Load v1 for Tech (should have global v1 values)
	bench_v1 = load_benchmarks("STOCK", sector="Tech", repo=repo, version="1.0.0")
	# Load v2 for Tech (should have sector override)
	bench_v2 = load_benchmarks("STOCK", sector="Tech", repo=repo, version="2.0.0")

	pe_v1 = next(b for b in bench_v1 if b["metric"] == "pe")
	pe_v2 = next(b for b in bench_v2 if b["metric"] == "pe")
	roe_v2 = next((b for b in bench_v2 if b["metric"] == "roe"), None)

	assert pe_v1["best"] == 15
	assert pe_v2["best"] == 5.0
	if roe_v2:
		assert roe_v2["target"] == 0.15
		assert roe_v2["width"] == 0.05


def test_analyze_asset_saves_version(repo):
	"""Test that analyze_asset saves the correct benchmark version to the database."""
	from core.schema import AssetData, AssetType

	# Create a dummy asset
	dummy_asset = AssetData(
		symbol="TEST",
		asset_type=AssetType.STOCK,
		name="Test Asset",
		sector="Technology",
		metrics={"pe_ratio": 15.0},
	)

	# Setup a benchmark in the DB
	repo.upsert_global_benchmark(
		"STOCK",
		"pe_ratio",
		"PE",
		"sigmoid",
		None,
		False,
		None,
		'{"best": 10, "worst": 20}',
		1.0,
		"2.0.0",
	)

	# Seed a minimal profile so the scoring engine has a weight to work with.
	# This repo uses skip_auto_seed=True so profiles must be set up manually.
	repo.upsert_profile("balanced")
	repo.upsert_profile_setting("balanced", "pe_ratio", weight=1.0)

	res = analyze_asset(dummy_asset, "balanced", repo=repo, benchmark_version="2.0.0")
	repo.bulk_save_analyses([res], "balanced", benchmark_version="2.0.0")

	assert res is not None
	assert res["score"] > 0

	# Verify snapshot in DB
	history = repo.get_historical_scores("TEST", "balanced")
	assert len(history) == 1
	assert history[0]["benchmark_version"] == "2.0.0"
