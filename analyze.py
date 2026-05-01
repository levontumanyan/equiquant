import argparse
import sys

from rich.console import Console

from core.analysis.indices import get_index_components
from core.database import DatabaseManager, DatabaseRepository
from core.io.parsers import parse_ticker_file
from core.logger import get_logger, setup_logging
from core.orchestrator import run_bulk_analysis
from core.reporting.factory import generate_report
from core.stats import stats
from core.ui.terminal import (
	display_historical_scores,
	display_individual_results,
	display_run_summary,
	display_summary_table,
)

console = Console()
logger = get_logger(__name__)


def main():
	parser = argparse.ArgumentParser(description="Stock & ETF Fundamental Analyzer")
	parser.add_argument("tickers", nargs="*", help="One or more ticker symbols")
	parser.add_argument("-f", "--file", help="Path to a file containing tickers")
	parser.add_argument(
		"-i", "--index", help="Ticker of an index/ETF to analyze its components"
	)
	parser.add_argument(
		"-a",
		"--all",
		action="store_true",
		help="Analyze all assets currently in the database",
	)
	parser.add_argument(
		"-p",
		"--profile",
		default="balanced",
		choices=["balanced", "growth", "dividend"],
		help="Investment profile to use",
	)
	parser.add_argument(
		"--benchmark-version",
		default="1.0.0",
		help="Version of benchmarks to use for analysis (default: 1.0.0)",
	)
	parser.add_argument(
		"-e",
		"--export",
		choices=["csv", "txt"],
		help="Export format (csv or txt). Filename is auto-generated.",
	)
	parser.add_argument(
		"--history",
		action="store_true",
		help="Show historical scores for the provided ticker(s)",
	)
	parser.add_argument(
		"-v",
		"--verbose",
		action="store_true",
		help="Enable verbose output (print logs to console)",
	)
	args = parser.parse_args()

	# Initialize Logging
	setup_logging(verbose=args.verbose)
	logger.info("Application started")

	# Initialize Database
	db_manager = DatabaseManager()
	repo = DatabaseRepository(db_manager)

	# 1. Collect Tickers
	stats.start_stage("Data Discovery")
	tickers = list(args.tickers)
	if args.file:
		tickers.extend(parse_ticker_file(args.file))
	if args.index:
		tickers.extend(get_index_components(args.index, repo=repo))
	if args.all:
		# Fetch all symbols that aren't indices themselves
		# This includes STOCK and assets not yet tagged (lazy metadata)
		cursor = db_manager.get_connection().cursor()
		cursor.execute(
			"SELECT symbol FROM assets WHERE symbol NOT IN (SELECT symbol FROM indices)"
		)
		all_symbols = [row[0] for row in cursor.fetchall()]
		tickers.extend(all_symbols)

	# Deduplicate and normalize
	tickers = sorted(list(set(t.upper().strip() for t in tickers)))
	stats.end_stage("Data Discovery")

	if not tickers:
		console.print("[bold red]Error: No tickers provided.[/bold red]")
		parser.print_help()
		sys.exit(1)

	# 1.5 Handle History Request
	if args.history:
		console.print(
			f"[bold green]Fetching history for {len(tickers)} asset(s) with [cyan]{args.profile.upper()}[/cyan] profile[/bold green]"
		)
		for ticker in tickers:
			snapshots = repo.get_historical_scores(ticker, args.profile)
			display_historical_scores(ticker, args.profile, snapshots)
		sys.exit(0)

	# 2. Process Tickers
	stats.start_stage("Analysis & Scoring")
	is_bulk = len(tickers) > 1
	console.print(
		f"[bold green]Analyzing {len(tickers)} asset(s) with [cyan]{args.profile.upper()}[/cyan] profile[/bold green]"
	)

	def progress_callback(res):
		if not is_bulk:
			display_individual_results(
				res["symbol"],
				res["name"],
				res["results"],
				res["benchmark_defs"],
				res.get("sector"),
				res.get("industry"),
			)

	all_analysis_results = run_bulk_analysis(
		tickers,
		args.profile,
		progress_callback,
		repo=repo,
		benchmark_version=args.benchmark_version,
	)
	stats.end_stage("Analysis & Scoring")

	# 3. Bulk Summary & Export
	stats.start_stage("Reporting")
	if is_bulk and all_analysis_results:
		display_summary_table(all_analysis_results)

	if args.export and all_analysis_results:
		export_path = generate_report(
			all_analysis_results, args.export, tickers, index_name=args.index
		)
		console.print(f"\n[bold green]Report exported to: {export_path}[/bold green]")
	stats.end_stage("Reporting")

	display_run_summary(stats)
	logger.info({"event": "run_summary", "stats": stats.to_dict()})
	logger.info("Application finished")


if __name__ == "__main__":
	main()
