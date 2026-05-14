import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from core.data import get_stock_data, load_benchmarks
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

	if repo:
		_save_analysis_to_db(
			repo, asset, profile, final_pct, results, benchmark_version
		)

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


def _save_analysis_to_db(
	repo: DatabaseRepository,
	asset: AssetData,
	profile: str,
	final_pct: float,
	results: List[Dict[str, Any]],
	benchmark_version: str,
) -> None:
	"""Save analysis results to the database in a thread-safe manner."""
	try:
		repo.upsert_asset(
			symbol=asset.symbol,
			name=asset.name,
			asset_type=asset.asset_type.value,
			sector=asset.sector,
			industry=asset.industry,
		)
		for res in results:
			metric_key = res.get("metric")
			val = res.get("raw_value")
			if metric_key and val is not None:
				try:
					repo.insert_metric_history(asset.symbol, metric_key, float(val))
				except (ValueError, TypeError):
					pass
		results_summary = [
			{
				"metric": r["metric"],
				"value": r["value"],
				"score": r["score"],
				"weight": r["weight"],
			}
			for r in results
		]
		repo.create_analysis_snapshot(
			symbol=asset.symbol,
			profile=profile,
			total_score=final_pct,
			results_json=json.dumps(results_summary),
			benchmark_version=benchmark_version,
		)
		stats.db_snapshots += 1
	except Exception as e:
		logger.error(f"Failed to save to DB for {asset.symbol}: {e}")


def _fetch_batch_with_backoff(
	batch_tickers: List[str], current_cooldown: float
) -> Tuple[bool, float]:
	"""Attempt to fetch a batch of tickers with retry and backoff using adaptive probing."""
	from core.openbb_client import fetch_openbb_data_bulk, probe_api

	base_cooldown = 5.0
	max_cooldown = 60.0

	for attempt in range(2):
		try:
			if fetch_openbb_data_bulk(batch_tickers):
				return True, base_cooldown

			logger.warning(f"Batch fetch failure. Attempt {attempt + 1}/2")

			# 1. Initial Cooldown
			logger.info(f"Entering {current_cooldown}s cooldown...")
			stats.record_cooldown(current_cooldown)
			time.sleep(current_cooldown)

			# 2. Probing mechanism: verify health before resuming bulk operations
			probe_ticker = batch_tickers[0]
			probe_attempts = 0
			max_probe_attempts = 10
			while not probe_api(probe_ticker):
				probe_attempts += 1
				if probe_attempts >= max_probe_attempts:
					logger.error(
						f"Max probe attempts ({max_probe_attempts}) reached for {probe_ticker}. Aborting batch."
					)
					return False, current_cooldown

				current_cooldown = min(current_cooldown * 2, max_cooldown)
				logger.warning(
					f"Rate-limit probe failed for {probe_ticker}. Extending cooldown to {current_cooldown}s..."
				)
				stats.record_cooldown(current_cooldown)
				time.sleep(current_cooldown)

			# Success: increment cooldown for next attempt's safety and log success
			current_cooldown = min(current_cooldown * 2, max_cooldown)
			logger.info(f"Probe successful for {probe_ticker}. Resuming bulk fetch.")

		except Exception as e:
			logger.warning(f"Fetch error for {batch_tickers}: {e}")
			time.sleep(current_cooldown)
			current_cooldown = min(current_cooldown * 2, max_cooldown)
			break
	return False, current_cooldown


def _tracked_analyze_asset(
	asset: AssetData,
	profile: str,
	repo: Optional[DatabaseRepository] = None,
	benchmark_version: str = "1.0.0",
	submitted_at: float = 0.0,
) -> Optional[Dict[str, Any]]:
	queued_latency = time.perf_counter() - submitted_at
	stats.record_task_start(queued_latency)
	start_time = time.perf_counter()
	try:
		return analyze_asset(asset, profile, repo, benchmark_version)
	finally:
		worker_time = time.perf_counter() - start_time
		stats.record_task_complete(worker_time)


def run_bulk_analysis(
	tickers: List[str],
	profile: str,
	progress_callback: Optional[Any] = None,
	repo: Optional[DatabaseRepository] = None,
	benchmark_version: str = "1.0.0",
	max_workers: int = 5,
) -> List[Dict[str, Any]]:
	"""
	Run analysis for multiple tickers using overlapped fetching and parallel analysis.
	"""
	logger.info(
		f"Starting bulk analysis for {len(tickers)} tickers with {max_workers} workers"
	)

	all_results = []
	batch_size = 20
	current_cooldown = 5.0

	with ThreadPoolExecutor(max_workers=max_workers) as executor:
		futures = []

		for i in range(0, len(tickers), batch_size):
			batch_tickers = [t.upper().strip() for t in tickers[i : i + batch_size]]
			logger.info(f"Fetching batch: {batch_tickers}")

			success, current_cooldown = _fetch_batch_with_backoff(
				batch_tickers, current_cooldown
			)

			for ticker in batch_tickers:
				asset = get_stock_data(ticker)
				if asset:
					stats.record_pool_submission()
					futures.append(
						executor.submit(
							_tracked_analyze_asset,
							asset,
							profile,
							repo=repo,
							benchmark_version=benchmark_version,
							submitted_at=time.perf_counter(),
						)
					)
				else:
					logger.warning(
						f"Skipping analysis for {ticker}: No data retrieved."
					)

			if success:
				# Coordinated burst mitigation via jitter; B311 safe.
				time.sleep(random.uniform(3.0, 5.0))  # nosec B311  # nosec B311

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

	logger.info(
		f"Bulk analysis complete. {len(all_results)}/{len(tickers)} successful."
	)
	return all_results
