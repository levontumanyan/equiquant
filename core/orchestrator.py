import asyncio
import os
import random
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from functools import partial
from typing import Any, AsyncGenerator, AsyncIterator, Dict, List, Optional, Tuple

from core.data import get_cached_stock_data, load_benchmarks
from core.database.repository import DatabaseRepository
from core.evaluation import evaluate_metric
from core.logger import get_logger
from core.profiles import get_profile_config
from core.schema import AssetData, AssetType
from core.stats import stats

logger = get_logger(__name__)


def analyze_asset(
	asset: AssetData,
	profile: str,
	repo: Optional[DatabaseRepository] = None,
	benchmark_version: str = "1.0.0",
) -> Optional[Dict[str, Any]]:
	"""
	Analyze a single pre-loaded asset by evaluating benchmarks and optionally saving results.

	Args:
		asset: Pre-loaded AssetData object.
		profile: The investor profile name to use for weighting.
		repo: Optional database repository for persistence.
		benchmark_version: The version of benchmarks to load.

	Returns:
		A dictionary containing analysis results and the final score, or None if analysis failed.
	"""
	symbol = asset.symbol
	logger.info(f"Analyzing asset: {symbol} with profile: {profile}")

	# Load benchmarks with sector context for stocks
	sector_context = asset.sector if asset.asset_type == AssetType.STOCK else None
	benchmark_defs = load_benchmarks(
		asset.asset_type.value,
		sector=sector_context,
		repo=repo,
		version=benchmark_version,
	)

	if not benchmark_defs:
		logger.error(f"No benchmarks found for {symbol}")
		return None

	profile_config = get_profile_config(repo, profile)

	scoring_start = time.perf_counter()
	results = [evaluate_metric(asset, b, profile_config) for b in benchmark_defs]
	stats.scoring_time_total += time.perf_counter() - scoring_start

	# Data Quality Audit: Record which metrics were present
	for res in results:
		metric_key = res.get("metric")
		if metric_key:
			is_present = res.get("raw_value") is not None
			stats.record_metric_coverage(metric_key, is_present)

	# Calculate total score
	total_score = sum(res["score"] for res in results)
	max_score = sum(res["weight"] for res in results)
	final_pct = (total_score / max_score * 100) if max_score > 0 else 0.0

	logger.info(f"Analysis complete for {symbol}: {final_pct:.2f}%")
	return {
		"symbol": asset.symbol,
		"name": asset.display_name,
		"sector": asset.sector,
		"industry": asset.industry,
		"results": results,
		"benchmark_defs": benchmark_defs,
		"score": final_pct,
		"asset_type": asset.asset_type,
		"raw_metrics": asset.raw_data,
	}


def _tracked_analyze_asset(
	ticker: str,
	profile: str,
	repo: Optional[DatabaseRepository] = None,
	benchmark_version: str = "1.0.0",
	submitted_at: float = 0.0,
	cancel_event: Optional[threading.Event] = None,
) -> Optional[Dict[str, Any]]:
	"""Wraps analyze_asset with telemetry and cooperative cancellation support."""
	if cancel_event and cancel_event.is_set():
		return None
	queued_latency = time.perf_counter() - submitted_at
	stats.record_task_start(queued_latency)
	start_time = time.perf_counter()
	try:
		asset = get_cached_stock_data(ticker, repo=repo)
		if not asset:
			logger.warning(f"Skipping analysis for {ticker}: No data cached.")
			return None
		return analyze_asset(asset, profile, repo, benchmark_version)
	finally:
		worker_time = time.perf_counter() - start_time
		stats.record_task_complete(worker_time)


def _fetch_batch_process_worker(
	batch_tickers: List[str], current_cooldown: float = 5.0
) -> Tuple[bool, float, Dict[str, Any]]:
	"""Worker function for ProcessPoolExecutor to fetch data."""
	from core.openbb_client import fetch_batch_with_backoff

	return fetch_batch_with_backoff(batch_tickers, current_cooldown)


async def fetch_data(  # noqa: C901 — batched async fetch, complexity is inherent to error-handling branches
	tickers: List[str],
	batch_size: int = 20,
	use_processes: bool = True,
	repo: Optional[DatabaseRepository] = None,
) -> AsyncIterator[List[str]]:
	"""
	Fetch data for multiple tickers in parallel batches and yield successful batches.
	Enables pipelining where analysis can start before all fetching is done.
	"""
	# PR Feedback: Normalize symbols early and consistently
	tickers = [t.upper().strip() for t in tickers if t.strip()]
	logger.info(
		f"Starting data fetch for {len(tickers)} tickers (processes={use_processes}, batch_size={batch_size})"
	)

	batches = [tickers[i : i + batch_size] for i in range(0, len(tickers), batch_size)]

	if not batches:
		return

	if use_processes:
		# Pre-initialize OpenBB in main process to avoid concurrent build locks in workers.
		# This ensures extensions are built and locked once before spawning parallel processes.
		try:
			from openbb import obb

			logger.info("Initializing OpenBB Platform...")
			# Accessing a core extension triggers the build process if needed
			_ = obb.equity
		except Exception as e:
			logger.debug(f"OpenBB pre-initialization skipped or failed: {e}")

	if not use_processes:
		current_cooldown = 5.0
		for batch in batches:
			# PR Feedback: Correctly propagate cooldown between batches in sequential mode
			success, current_cooldown, data = _fetch_batch_process_worker(
				batch, current_cooldown
			)
			if success:
				if repo:
					for symbol, payload in data.items():
						try:
							repo.upsert_raw_provider_data(symbol, "yfinance", payload)
						except Exception as e:
							logger.warning(
								f"Failed to persist raw data for {symbol}: {e}"
							)
				yield batch
		return

	loop = asyncio.get_running_loop()
	# Always use ProcessPoolExecutor to avoid signal issues in threads
	# Limited to 2 workers for fetching to avoid triggering IP blocks/crumbs
	with ProcessPoolExecutor(max_workers=min(2, len(batches))) as pool:
		task_to_batch: Dict[asyncio.Future, List[str]] = {}
		for batch in batches:
			task = loop.run_in_executor(pool, _fetch_batch_process_worker, batch, 5.0)
			task_to_batch[task] = batch
			# Stagger submission slightly for better responsiveness
			await asyncio.sleep(random.uniform(0.2, 0.5))  # nosec B311

		# Use asyncio.wait so done futures are the original objects (safe dict lookup)
		pending = set(task_to_batch.keys())
		while pending:
			done, pending = await asyncio.wait(
				pending, return_when=asyncio.FIRST_COMPLETED
			)
			for task in done:
				batch = task_to_batch[task]
				try:
					success, _, data = task.result()
					if success:
						if repo:
							for symbol, payload in data.items():
								try:
									repo.upsert_raw_provider_data(
										symbol, "yfinance", payload
									)
								except Exception as e:
									logger.warning(
										f"Failed to persist raw data for {symbol}: {e}"
									)
						yield batch
				except Exception as e:
					logger.error(f"Batch fetch task failed: {e}")

	logger.info("Data fetch complete.")


def run_bulk_analysis(
	tickers: List[str],
	profile: str,
	progress_callback: Optional[Any] = None,
	repo: Optional[DatabaseRepository] = None,
	benchmark_version: str = "1.0.0",
	max_workers: int = 5,
) -> List[Dict[str, Any]]:
	"""
	Run analysis for multiple tickers using parallel processing.
	Only processes data that is already cached locally.
	"""
	logger.info(
		f"Starting bulk analysis for {len(tickers)} tickers with {max_workers} workers"
	)

	all_results = []

	with ThreadPoolExecutor(max_workers=max_workers) as executor:
		futures = []

		for ticker in tickers:
			ticker = ticker.upper().strip()
			stats.record_pool_submission()
			futures.append(
				executor.submit(
					_tracked_analyze_asset,
					ticker,
					profile,
					repo=repo,
					benchmark_version=benchmark_version,
					submitted_at=time.perf_counter(),
				)
			)

		total = len(futures)
		for idx, future in enumerate(as_completed(futures), 1):
			try:
				res = future.result()
				if res:
					all_results.append(res)
					if progress_callback:
						progress_callback(res)
				logger.info(f"[{idx}/{total}] Completed analysis")
			except Exception as e:
				logger.error(f"Analysis error: {e}")

	if repo and all_results:
		try:
			logger.info(f"Saving {len(all_results)} analysis results to database...")
			repo.bulk_save_analyses(all_results, profile, benchmark_version)
			stats.db_snapshots += len(all_results)
		except Exception as e:
			logger.error(f"Failed bulk save to DB: {e}")

	logger.info(
		f"Bulk analysis complete. {len(all_results)}/{len(tickers)} successful."
	)
	return all_results


async def stream_bulk_analysis(  # noqa: C901 — inherent complexity of SSE streaming pipeline
	tickers: List[str],
	profile: str,
	repo: Optional[DatabaseRepository] = None,
	benchmark_version: str = "1.0.0",
	max_workers: int = min(32, (os.cpu_count() or 4) + 4),
	executor: Optional[ThreadPoolExecutor] = None,
	cancel_event: Optional[threading.Event] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
	"""
	Async generator that yields individual analysis results as each ticker completes.

	Runs analysis in a ThreadPoolExecutor and yields results via asyncio.wait so
	the caller receives each result as soon as it is ready. On cancellation the
	executor is shut down immediately without waiting for in-flight threads.

	When an external executor is provided the caller owns its lifecycle; otherwise
	this function creates and tears down its own executor.

	Args:
		tickers: Ticker symbols to analyse (normalised to uppercase internally).
		profile: Investor profile name used for metric weighting.
		repo: Optional database repository for persistence and result saving.
		benchmark_version: Benchmark definition version string.
		max_workers: Maximum parallel worker threads (used only when no external executor).
		executor: Optional external ThreadPoolExecutor to reuse across calls.
		cancel_event: Optional threading.Event for cooperative cancellation.

	Yields:
		Analysis result dict for each completed ticker (None results are skipped).
	"""
	loop = asyncio.get_running_loop()
	completed_results: List[Dict[str, Any]] = []
	cancelled = False
	owns_executor = executor is None

	if owns_executor:
		executor = ThreadPoolExecutor(max_workers=max_workers)

	futures: List[asyncio.Future] = []

	try:
		for ticker in tickers:
			ticker = ticker.upper().strip()
			stats.record_pool_submission()
			task = loop.run_in_executor(
				executor,
				partial(
					_tracked_analyze_asset,
					ticker,
					profile,
					repo,
					benchmark_version,
					time.perf_counter(),
					cancel_event,
				),
			)
			futures.append(task)

		pending = set(futures)
		total = len(futures)
		idx = 0
		while pending:
			done, pending = await asyncio.wait(
				pending, return_when=asyncio.FIRST_COMPLETED
			)
			for future in done:
				idx += 1
				try:
					res = future.result()
					if res:
						if repo:
							completed_results.append(res)
						yield res
					logger.info(f"[{idx}/{total}] Streaming analysis complete")
				except Exception as e:
					logger.error(f"Analysis error: {e}")

	except (asyncio.CancelledError, GeneratorExit):
		cancelled = True
		logger.info("Streaming analysis cancelled — stopping executor")
		for f in futures:
			f.cancel()
		if owns_executor:
			executor.shutdown(wait=False, cancel_futures=True)
		raise

	finally:
		if not cancelled:
			if owns_executor:
				executor.shutdown(wait=True)
			if repo and completed_results:
				try:
					logger.info(f"Saving {len(completed_results)} results to database…")
					repo.bulk_save_analyses(
						completed_results, profile, benchmark_version
					)
					stats.db_snapshots += len(completed_results)
				except Exception as e:
					logger.error(f"Failed bulk save to DB: {e}")
