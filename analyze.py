#!/usr/bin/env -S uv run python3
import argparse
import os
import sys

# Early exit for completion flags to avoid heavy imports
if len(sys.argv) > 1 and sys.argv[1] in [
	"--list-tickers",
	"--list-indices",
	"--list-profiles",
]:
	import sqlite3
	from pathlib import Path

	db_path = Path("market_analysis.db")
	if db_path.exists():
		conn = sqlite3.connect(str(db_path))
		cursor = conn.cursor()
		if sys.argv[1] == "--list-tickers":
			cursor.execute("SELECT symbol FROM assets ORDER BY symbol")
		elif sys.argv[1] == "--list-indices":
			cursor.execute("SELECT symbol FROM indices ORDER BY symbol")
		elif sys.argv[1] == "--list-profiles":
			cursor.execute("SELECT name FROM investor_profiles ORDER BY name")

		for row in cursor.fetchall():
			print(row[0])
		conn.close()
	sys.exit(0)

# Heavy imports only for actual execution
from rich.console import Console

from core.analysis.indices import get_index_components
from core.database import DatabaseManager, DatabaseRepository
from core.io.parsers import parse_ticker_file
from core.logger import LOG_DIR, LOG_FILE, get_logger, setup_logging
from core.orchestrator import run_bulk_analysis
from core.reporting.factory import generate_report
from core.stats import stats
from core.ui.database import dispatch_db_view
from core.ui.terminal import (
	display_historical_scores,
	display_individual_results,
	display_run_summary,
	display_summary_table,
)

console = Console()
logger = get_logger(__name__)

AUTO_BACKGROUND_THRESHOLD = 10
PID_FILE = LOG_DIR / "latest.pid"


def daemonize():
	"""Detaches the process from the terminal."""
	try:
		pid = os.fork()
		if pid > 0:
			sys.exit(0)
	except OSError as e:
		logger.error(f"fork #1 failed: {e.errno} ({e.strerror})")
		sys.exit(1)
	os.setsid()
	os.umask(0)
	try:
		pid = os.fork()
		if pid > 0:
			# Save the second child's PID
			with open(PID_FILE, "w") as f:
				f.write(str(pid))
			sys.exit(0)
	except OSError as e:
		logger.error(f"fork #2 failed: {e.errno} ({e.strerror})")
		sys.exit(1)

	out_file = str(LOG_FILE).replace(".log", ".out")

	sys.stdout.flush()
	sys.stderr.flush()
	si = open(os.devnull, "r")
	so = open(out_file, "a+")
	se = open(out_file, "a+")
	os.dup2(si.fileno(), sys.stdin.fileno())
	os.dup2(so.fileno(), sys.stdout.fileno())
	os.dup2(se.fileno(), sys.stderr.fileno())
	logger.info(
		f"Process daemonized. PID: {os.getpid()}. Output redirected to {out_file}"
	)


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
	parser.add_argument(
		"-b",
		"--background",
		action="store_true",
		help="Run the analysis in the background",
	)
	parser.add_argument(
		"--logs",
		action="store_true",
		help="Tail the latest background run logs",
	)
	parser.add_argument(
		"--db",
		choices=[
			"assets",
			"indices",
			"snapshots",
			"sectors",
			"profiles",
			"benchmarks",
			"inventory",
		],
		help="Inspect the database (replaces make db-*)",
	)
	parser.add_argument(
		"-w",
		"--workers",
		type=int,
		default=5,
		help="Number of parallel workers for fetching and analysis (default: 5)",
	)
	# Hidden flags for completion (handled early, but kept here for help/parsing)
	parser.add_argument("--list-tickers", action="store_true", help=argparse.SUPPRESS)
	parser.add_argument("--list-indices", action="store_true", help=argparse.SUPPRESS)
	parser.add_argument("--list-profiles", action="store_true", help=argparse.SUPPRESS)

	args = parser.parse_args()

	# Initialize Logging
	setup_logging(verbose=args.verbose)

	if args.logs:
		import glob

		out_files = sorted(glob.glob(str(LOG_DIR / "run_*.out")), reverse=True)
		if out_files:
			latest_log = out_files[0]
			print(f"Tailing latest logs from {latest_log}...")
			os.system(f"tail -f {latest_log}")
		else:
			print(f"No background log files found in {LOG_DIR}")
		sys.exit(0)

	if args.db:
		dispatch_db_view(args.db)
		sys.exit(0)

	logger.info("Application started")

	# Initialize Database
	db_manager = DatabaseManager()
	repo = DatabaseRepository(db_manager)

	# Resource Tracking: Initial DB Size
	db_path = db_manager.db_path
	if db_path.exists():
		stats.initial_db_size = db_path.stat().st_size

	# Artifact Tracking: Always record log file
	stats.record_artifact(LOG_FILE)

	# 1. Collect Tickers
	stats.start_stage("Data Discovery")
	tickers = list(args.tickers)
	if args.file:
		tickers.extend(parse_ticker_file(args.file))
	if args.index:
		tickers.extend(get_index_components(args.index, repo=repo))
	if args.all:
		cursor = db_manager.get_connection().cursor()
		cursor.execute(
			"SELECT symbol FROM assets WHERE symbol NOT IN (SELECT symbol FROM indices)"
		)
		all_symbols = [row[0] for row in cursor.fetchall()]
		tickers.extend(all_symbols)

	tickers = sorted(list(set(t.upper().strip() for t in tickers)))
	stats.end_stage("Data Discovery")

	if not tickers:
		console.print("[bold red]Error: No tickers provided.[/bold red]")
		parser.print_help()
		sys.exit(1)

	# 2. Check for Backgrounding
	should_background = args.background
	if (
		not should_background
		and len(tickers) >= AUTO_BACKGROUND_THRESHOLD
		and not args.verbose
	):
		console.print(
			f"[bold yellow]Large batch detected ({len(tickers)} assets). Moving to background...[/bold yellow]"
		)
		should_background = True

	if should_background:
		out_file = str(LOG_FILE).replace(".log", ".out")
		console.print(f"[cyan]Logs: tail -f {out_file}[/cyan]")
		if os.path.exists(PID_FILE):
			os.remove(PID_FILE)
		daemonize()
		# Re-setup logging to force output to the newly redirected stdout/stderr
		setup_logging(verbose=args.verbose, force_console=True)

	if args.history:
		console.print(
			f"[bold green]Fetching history for {len(tickers)} asset(s) with [cyan]{args.profile.upper()}[/cyan] profile[/bold green]"
		)
		for ticker in tickers:
			snapshots = repo.get_historical_scores(ticker, args.profile)
			display_historical_scores(ticker, args.profile, snapshots)
		sys.exit(0)

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
		max_workers=args.workers,
	)
	stats.end_stage("Analysis & Scoring")

	stats.start_stage("Reporting")
	if is_bulk and all_analysis_results:
		display_summary_table(all_analysis_results)

	if args.export and all_analysis_results:
		export_path = generate_report(
			all_analysis_results,
			args.export,
			tickers,
			index_name=args.index,
			profile=args.profile,
		)
		stats.record_artifact(export_path)
		console.print(f"\n[bold green]Report exported to: {export_path}[/bold green]")
	stats.end_stage("Reporting")

	# Final Resource Tracking
	if db_path.exists():
		stats.final_db_size = db_path.stat().st_size

	display_run_summary(stats)
	logger.info({"event": "run_summary", "stats": stats.to_dict()})
	logger.info("Application finished")


if __name__ == "__main__":
	main()
