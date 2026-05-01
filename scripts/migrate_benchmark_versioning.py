import logging
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = "market_analysis.db"


def migrate():
	if not Path(DB_PATH).exists():
		logger.error(f"Database {DB_PATH} not found.")
		return

	conn = sqlite3.connect(DB_PATH)
	cursor = conn.cursor()

	try:
		# 1. Migrate sector_benchmarks
		logger.info("Migrating sector_benchmarks...")
		cursor.execute("ALTER TABLE sector_benchmarks RENAME TO sector_benchmarks_old")
		cursor.execute("""
			CREATE TABLE sector_benchmarks (
				sector TEXT,
				metric_key TEXT,
				benchmark_type TEXT,
				value_a REAL,
				value_b REAL,
				last_updated DATETIME,
				version TEXT DEFAULT '1.0.0',
				PRIMARY KEY (sector, metric_key, version)
			)
		""")
		cursor.execute("""
			INSERT INTO sector_benchmarks (sector, metric_key, benchmark_type, value_a, value_b, last_updated, version)
			SELECT sector, metric_key, benchmark_type, value_a, value_b, last_updated, '1.0.0'
			FROM sector_benchmarks_old
		""")
		cursor.execute("DROP TABLE sector_benchmarks_old")

		# 2. Migrate global_benchmarks
		logger.info("Migrating global_benchmarks...")
		cursor.execute("ALTER TABLE global_benchmarks RENAME TO global_benchmarks_old")
		cursor.execute("""
			CREATE TABLE global_benchmarks (
				asset_type TEXT,
				metric_key TEXT,
				name TEXT,
				formula_type TEXT,
				unit TEXT,
				is_decimal BOOLEAN,
				display_key TEXT,
				params_json TEXT,
				weight REAL,
				version TEXT DEFAULT '1.0.0',
				PRIMARY KEY (asset_type, metric_key, version)
			)
		""")
		cursor.execute("""
			INSERT INTO global_benchmarks (asset_type, metric_key, name, formula_type, unit, is_decimal, display_key, params_json, weight, version)
			SELECT asset_type, metric_key, name, formula_type, unit, is_decimal, display_key, params_json, weight, '1.0.0'
			FROM global_benchmarks_old
		""")
		cursor.execute("DROP TABLE global_benchmarks_old")

		# 3. Migrate analysis_snapshots
		logger.info("Migrating analysis_snapshots...")
		# Check if column already exists
		cursor.execute("PRAGMA table_info(analysis_snapshots)")
		columns = [info[1] for info in cursor.fetchall()]
		if "benchmark_version" not in columns:
			cursor.execute(
				"ALTER TABLE analysis_snapshots ADD COLUMN benchmark_version TEXT DEFAULT '1.0.0'"
			)
		else:
			logger.warning(
				"benchmark_version column already exists in analysis_snapshots"
			)

		conn.commit()
		logger.info("Migration successful.")

	except Exception as e:
		conn.rollback()
		logger.error(f"Migration failed: {e}")
	finally:
		conn.close()


if __name__ == "__main__":
	migrate()
