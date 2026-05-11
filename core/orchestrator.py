import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from core.data import get_stock_data, load_benchmarks
from core.database.repository import DatabaseRepository
from core.evaluation import evaluate_metric
from core.logger import get_logger
from core.profiles import get_profile_weights
from core.schema import AssetType
from core.stats import stats

logger = get_logger(__name__)


def analyze_asset(
	symbol: str,
	profile: str,
	repo: Optional[DatabaseRepository] = None,
	benchmark_version: str = "1.0.0",
) -> Optional[Dict[str, Any]]:
	"""
	Analyze a single asset by fetching data, evaluating benchmarks, and optionally saving results.
	"""
	logger.info(f"Analyzing asset: {symbol} with profile: {profile}")
	asset = get_stock_data(symbol)
	if not asset:
		return None

	sector_context = asset.sector if asset.asset_type == AssetType.STOCK else None
	benchmark_defs = load_benchmarks(
		asset.asset_type.value,
		sector=sector_context,
		repo=repo,
		version=benchmark_version,
	)

	if not benchmark_defs:
		return None

	profile_weights = get_profile_weights(repo, profile)

	scoring_start = time.perf_counter()
	results = [evaluate_metric(asset, b, profile_weights) for b in benchmark_defs]
	stats.scoring_time_total += time.perf_counter() - scoring_start

	for res in results:
		metric_key = res.get("metric")
		if metric_key:
			is_present = res.get("raw_value") is not None
			stats.record_metric_coverage(metric_key, is_present)

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
	asset: Any,
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
	from core.openbb_client import fetch_openbb_data_bulk

	all_results = []
	batch_size = 20

	base_cooldown = 5.0
	max_cooldown = 45.0
	current_cooldown = base_cooldown

	with ThreadPoolExecutor(max_workers=max_workers) as executor:
		futures = []

		for i in range(0, len(tickers), batch_size):
			batch = [t.upper().strip() for t in tickers[i : i + batch_size]]

			logger.info(f"Fetching batch: {batch}")
			batch_success = False
			for attempt in range(2):
				try:
					if fetch_openbb_data_bulk(batch):
						batch_success = True
						break

					logger.warning(f"Batch fetch failure. Attempt {attempt + 1}/2")
					logger.info(f"Entering {current_cooldown}s cooldown...")
					stats.record_cooldown(current_cooldown)
					time.sleep(current_cooldown)
					current_cooldown = min(current_cooldown * 2, max_cooldown)
				except Exception as e:
					logger.warning(f"Fetch error for {batch}: {e}")
					time.sleep(current_cooldown)
					current_cooldown = min(current_cooldown * 2, max_cooldown)
					break

			for ticker in batch:
				futures.append(
					executor.submit(
						analyze_asset,
						ticker,
						profile,
						repo=repo,
						benchmark_version=benchmark_version,
					)
				)

			if batch_success:
				current_cooldown = base_cooldown
				time.sleep(random.uniform(3.0, 5.0))

		total = len(tickers)
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
