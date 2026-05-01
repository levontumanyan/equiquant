import json
import logging
from pathlib import Path

from core.database import DatabaseManager, DatabaseRepository

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def migrate_file(
	repo: DatabaseRepository, file_path: Path, asset_type: str, version: str = "1.0.0"
):
	if not file_path.exists():
		logger.warning(f"{file_path} not found, skipping.")
		return

	try:
		with open(file_path, "r") as f:
			data = json.load(f)

		for item in data:
			metric_key = item.get("metric")
			if not metric_key:
				continue

			# Identify scorer parameters
			params = {}
			for p_key in ["best", "worst", "target", "width", "threshold"]:
				if p_key in item:
					params[p_key] = item[p_key]

			repo.upsert_global_benchmark(
				asset_type=asset_type,
				metric_key=metric_key,
				name=item.get("name"),
				formula_type=item.get("type"),
				unit=item.get("unit"),
				is_decimal=item.get("is_decimal", False),
				display_key=item.get("display_key"),
				params_json=json.dumps(params),
				weight=float(item.get("weight", 1.0)),
				version=version,
			)
			logger.info(
				f"Migrated benchmark: {asset_type} -> {metric_key} (v{version})"
			)

	except Exception as e:
		logger.error(f"Failed to migrate {file_path}: {e}")


def main():
	import argparse

	parser = argparse.ArgumentParser()
	parser.add_argument("--version", default="1.0.0", help="Benchmark version")
	args = parser.parse_args()

	db_manager = DatabaseManager()
	repo = DatabaseRepository(db_manager)

	migrate_file(repo, Path("benchmarks/stock.json"), "STOCK", version=args.version)
	migrate_file(repo, Path("benchmarks/etf.json"), "ETF", version=args.version)

	logger.info("Global benchmarks migration complete.")


if __name__ == "__main__":
	main()
