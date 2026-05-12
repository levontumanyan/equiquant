#!/usr/bin/env -S uv run python3
import argparse
import json
import os
import sys
from typing import List

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


def _collect_tickers(args, repo, db_manager) -> List[str]:
	"""Collect and deduplicate tickers from various sources."""
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
		tickers.extend([row[0] for row in cursor.fetchall()])
	return sorted(list(set(t.upper().strip() for t in tickers)))


def _handle_backgrounding(args, tickers):
	"""Daemonize the process if backgrounding is requested or threshold is met."""
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
		setup_logging(verbose=args.verbose, force_console=True)


def _handle_history_request(repo, tickers, profile):
	"""Fetch and display historical scores."""
	console.print(
		f"[bold green]Fetching history for {len(tickers)} asset(s) with [cyan]{profile.upper()}[/cyan] profile[/bold green]"
	)
	for ticker in tickers:
		snapshots = repo.get_historical_scores(ticker, profile)
		display_historical_scores(ticker, profile, snapshots)
	sys.exit(0)


def _parse_args():
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
		help="Investment profile",
	)
	parser.add_argument(
		"--benchmark-version", default="1.0.0", help="Version of benchmarks to use"
	)
	parser.add_argument("-e", "--export", choices=["csv", "txt"], help="Export format")
	parser.add_argument("--history", action="store_true", help="Show historical scores")
	parser.add_argument(
		"-v", "--verbose", action="store_true", help="Enable verbose output"
	)
	parser.add_argument(
		"-b",
		"--background",
		action="store_true",
		help="Run the analysis in the background",
	)
	parser.add_argument("--logs", action="store_true", help="Tail background run logs")
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
		help="Inspect database",
	)
	parser.add_argument(
		"-w", "--workers", type=int, default=5, help="Number of parallel workers"
	)
	parser.add_argument("--list-tickers", action="store_true", help=argparse.SUPPRESS)
	parser.add_argument("--list-indices", action="store_true", help=argparse.SUPPRESS)
	parser.add_argument("--list-profiles", action="store_true", help=argparse.SUPPRESS)
	return parser.parse_args(), parser


def _handle_special_flags(args):
	if args.logs:
		import glob

		out_files = sorted(glob.glob(str(LOG_DIR / "run_*.out")), reverse=True)
		if out_files:
			print(f"Tailing latest logs from {out_files[0]}...")
			os.system(f"tail -f {out_files[0]}")
		sys.exit(0)

	if args.db:
		dispatch_db_view(args.db)
		sys.exit(0)


def main():
	args, parser = _parse_args()
	setup_logging(verbose=args.verbose)
	_handle_special_flags(args)

	db_manager = DatabaseManager()
	repo = DatabaseRepository(db_manager)
	if (db_path := db_manager.db_path).exists():
		stats.initial_db_size = db_path.stat().st_size
	stats.record_artifact(LOG_FILE)

	stats.start_stage("Data Discovery")
	tickers = _collect_tickers(args, repo, db_manager)
	stats.end_stage("Data Discovery")
	stats.total_tickers = len(tickers)

	if not tickers:
		console.print("[bold red]Error: No tickers provided.[/bold red]")
		parser.print_help()
		sys.exit(1)

	_handle_backgrounding(args, tickers)
	if args.history:
		_handle_history_request(repo, tickers, args.profile)

	stats.start_stage("Analysis & Scoring")
	is_bulk = len(tickers) > 1
	console.print(
		f"[bold green]Analyzing {len(tickers)} asset(s) with [cyan]{args.profile.upper()}[/cyan] profile[/bold green]"
	)

	def progress_cb(res):
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
		progress_cb,
		repo=repo,
		benchmark_version=args.benchmark_version,
		max_workers=args.workers,
	)
	stats.analyzed_tickers = len(all_analysis_results)
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

	if db_path.exists():
		stats.final_db_size = db_path.stat().st_size
		try:
			repo.save_telemetry(stats.get_total_time(), stats.to_dict())
		except Exception as e:
			logger.error(f"Failed to save telemetry: {e}")

	# Log final telemetry summary
	logger.info("Final Session Telemetry:\n%s", json.dumps(stats.to_dict(), indent=4))
	display_run_summary(stats)
	logger.info("Application finished")


if __name__ == "__main__":
	main()
