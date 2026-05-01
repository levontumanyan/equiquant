import logging

from core.database import DatabaseManager, DatabaseRepository

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
	import argparse

	parser = argparse.ArgumentParser()
	parser.add_argument("--version", default="1.0.0", help="Benchmark version")
	args = parser.parse_args()

	db_manager = DatabaseManager()
	repo = DatabaseRepository(db_manager)

	# --- TECHNOLOGY ---
	# Price to Book: Semiconductor average ~13x, NVIDIA ~33x-40x.
	logger.info(
		f"Updating Technology sector Price to Book benchmark (v{args.version})..."
	)
	repo.upsert_sector_benchmark(
		sector="Technology",
		metric_key="price_to_book",
		benchmark_type="best_worst",
		value_a=10.0,
		value_b=60.0,
		version=args.version,
	)

	# EV/EBITDA: Industry average ~27.5x, NVIDIA ~39x.
	# Setting Best=15.0 (Great value for Tech) and Worst=50.0 (High premium)
	logger.info(f"Updating Technology sector EV/EBITDA benchmark (v{args.version})...")
	repo.upsert_sector_benchmark(
		sector="Technology",
		metric_key="enterprise_to_ebitda",
		benchmark_type="best_worst",
		value_a=15.0,
		value_b=50.0,
		version=args.version,
	)

	# --- FINANCIAL SERVICES ---
	# Price to Book: Best=1.0, Worst=3.5
	logger.info(
		f"Updating Financial Services sector Price to Book benchmark (v{args.version})..."
	)
	repo.upsert_sector_benchmark(
		sector="Financial Services",
		metric_key="price_to_book",
		benchmark_type="best_worst",
		value_a=1.0,
		value_b=3.5,
		version=args.version,
	)

	logger.info("Database update complete.")


if __name__ == "__main__":
	main()
