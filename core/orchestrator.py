import asyncio
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

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


async def fetch_data(
	tickers: List[str],
	batch_size: int = 20,
) -> bool:
	"""
	Fetch data for multiple tickers in batches with backoff and retry.
	"""
	logger.info(f"Starting data fetch for {len(tickers)} tickers")
	current_cooldown = 5.0
	overall_success = True

	for i in range(0, len(tickers), batch_size):
		batch_tickers = [t.upper().strip() for t in tickers[i : i + batch_size]]
		logger.info(f"Fetching batch: {batch_tickers}")

		from core.openbb_client import fetch_batch_with_backoff

		success, current_cooldown = await asyncio.to_thread(
			fetch_batch_with_backoff, batch_tickers, current_cooldown
		)

		if not success:
			overall_success = False
			logger.warning(f"Batch {i // batch_size + 1} failed partially or fully.")

		if i + batch_size < len(tickers):
			# Jittered wait between batches; B311 safe.
			await asyncio.sleep(random.uniform(2.0, 4.0))  # nosec B311

	logger.info(f"Data fetch complete. Success: {overall_success}")
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
