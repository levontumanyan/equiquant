import asyncio
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from core.data import get_cached_stock_data, load_benchmarks
from core.database.repository import DatabaseRepository
from core.evaluation import evaluate_metric
from core.logger import get_logger
from core.profiles import get_profile_weights
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

	profile_weights = get_profile_weights(repo, profile)

	scoring_start = time.perf_counter()
	results = [evaluate_metric(asset, b, profile_weights) for b in benchmark_defs]
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
	}


def _tracked_analyze_asset(
	ticker: str,
	profile: str,
	repo: Optional[DatabaseRepository] = None,
	benchmark_version: str = "1.0.0",
	submitted_at: float = 0.0,
) -> Optional[Dict[str, Any]]:
	queued_latency = time.perf_counter() - submitted_at
	stats.record_task_start(queued_latency)
	start_time = time.perf_counter()
	try:
		asset = get_cached_stock_data(ticker)
		if not asset:
			logger.warning(f"Skipping analysis for {ticker}: No data cached.")
			return None
		return analyze_asset(asset, profile, repo, benchmark_version)
	finally:
		worker_time = time.perf_counter() - start_time
		stats.record_task_complete(worker_time)


def _fetch_batch_process_worker(
	batch_tickers: List[str], current_cooldown: float = 5.0
) -> Tuple[bool, float]:
	"""Worker function for ProcessPoolExecutor to fetch data."""
	# Re-import inside process to avoid issues
	from core.openbb_client import fetch_batch_with_backoff

	return fetch_batch_with_backoff(batch_tickers, current_cooldown)


async def fetch_data(
	tickers: List[str],
	batch_size: int = 100,
	use_processes: bool = True,
) -> bool:
	"""
	Fetch data for multiple tickers in parallel batches using processes.
	Super fast and async-friendly.
	"""
	# PR Feedback: Normalize symbols early and consistently
	tickers = [t.upper().strip() for t in tickers if t.strip()]
	logger.info(
		f"Starting data fetch for {len(tickers)} tickers (processes={use_processes})"
	)

	batches = [tickers[i : i + batch_size] for i in range(0, len(tickers), batch_size)]

	if not batches:
		return True

	if not use_processes:
		results = []
		current_cooldown = 5.0
		for batch in batches:
			# PR Feedback: Correctly propagate cooldown between batches in sequential mode
			success, current_cooldown = _fetch_batch_process_worker(
				batch, current_cooldown
			)
			results.append(success)
		return all(results)

	# PR Feedback: Use get_running_loop() (modern asyncio)
	loop = asyncio.get_running_loop()
	# Always use ProcessPoolExecutor to avoid signal issues in threads
	with ProcessPoolExecutor(max_workers=min(4, len(batches))) as pool:
		tasks = [
			loop.run_in_executor(pool, _fetch_batch_process_worker, batch, 5.0)
			for batch in batches
		]
		results = await asyncio.gather(*tasks)

	overall_success = all(results)
	logger.info(f"Parallel data fetch complete. Success: {overall_success}")
	return overall_success


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
