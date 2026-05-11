import json
import random
import time
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
	Analyze a single asset and return the results and score.
	"""
	logger.info(
		f"Analyzing asset: {symbol} with profile: {profile} (benchmarks: {benchmark_version})"
	)
	asset = get_stock_data(symbol)
	if not asset:
		logger.warning(f"Could not retrieve data for {symbol}")
		return None

	# Load benchmarks with sector context for stocks
	sector_context = asset.sector if asset.asset_type == AssetType.STOCK else None
	benchmark_defs = load_benchmarks(
		asset.asset_type.value,
		sector=sector_context,
		repo=repo,
		version=benchmark_version,
	)

	if not benchmark_defs:
		logger.error(
			f"No benchmarks (version {benchmark_version}) found for {symbol} in database"
		)
		return None

	profile_weights = get_profile_weights(repo, profile)

	scoring_start = time.perf_counter()
	results = [evaluate_metric(asset, b, profile_weights) for b in benchmark_defs]
	stats.scoring_time_total += time.perf_counter() - scoring_start
	# Data Quality Audit: Record which metrics were present
	for res in results:
		metric_key = res.get("metric")
		if metric_key:
			# If 'raw_value' is None or item has no data, it's missing
			is_present = res.get("raw_value") is not None
			stats.record_metric_coverage(metric_key, is_present)

	# Calculate total score
	total_score = 0.0
	max_score = 0.0
	for res in results:
		total_score += res["score"]
		max_score += res["weight"]

	final_pct = (total_score / max_score * 100) if max_score > 0 else 0.0

	# DB Recording
	if repo:
		try:
			# 1. Update Asset Metadata
			repo.upsert_asset(
				symbol=asset.symbol,
				name=asset.name,
				asset_type=asset.asset_type.value,
				sector=asset.sector,
				industry=asset.industry,
			)

			# 2. Record Metric History (the raw values used for benchmarks)
			for res in results:
				metric_key = res.get("metric")
				val = res.get("raw_value")
				if metric_key and val is not None:
					try:
						repo.insert_metric_history(asset.symbol, metric_key, float(val))
					except (ValueError, TypeError):
						pass

			# 3. Create Analysis Snapshot
			# Convert results to JSON for historical breakdown
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
			logger.info(f"Saved analysis snapshot for {symbol} to DB")
		except Exception as e:
			logger.error(f"Failed to save analysis to DB for {symbol}: {e}")

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


def run_bulk_analysis(
	tickers: List[str],
	profile: str,
	progress_callback: Optional[Any] = None,
	repo: Optional[DatabaseRepository] = None,
	benchmark_version: str = "1.0.0",
) -> List[Dict[str, Any]]:
	"""
	Run analysis for multiple tickers using efficient bulk fetching.
	"""
	from core.openbb_client import fetch_openbb_data_bulk

	logger.info(
		f"Starting bulk analysis for {len(tickers)} tickers (benchmarks: {benchmark_version})"
	)

	# 1. Pre-fetch data in batches of 20 to warm the cache
	batch_size = 20
	import time

	base_cooldown = 5.0
	max_cooldown = 45.0
	current_cooldown = base_cooldown

	for i in range(0, len(tickers), batch_size):
		batch = tickers[i : i + batch_size]
		max_batch_retries = 1
		batch_success = False
		for attempt in range(max_batch_retries + 1):
			try:
				if fetch_openbb_data_bulk(batch):
					batch_success = True
					break

				logger.warning(
					f"Batch fetch returned incomplete or zero results (attempt {attempt + 1}/{max_batch_retries + 1}) for symbols: {batch}"
				)
				# Apply progressive backoff on any non-clean fetch
				logger.info(
					f"Entering {current_cooldown}s cooldown due to partial/total failure..."
				)
				stats.record_cooldown(current_cooldown)
				time.sleep(current_cooldown)
				current_cooldown = min(current_cooldown * 2, max_cooldown)

				if attempt < max_batch_retries:
					logger.info(f"Retrying batch: {batch}")
					continue
			except Exception as e:
				logger.warning(f"Bulk fetch encountered error for batch {batch}: {e}")
				# Mandatory sleep even on exception
				time.sleep(current_cooldown)
				current_cooldown = min(current_cooldown * 2, max_cooldown)
				break

		if batch_success:
			# Reset cooldown on clean success
			current_cooldown = base_cooldown

			# Mandatory inter-batch breather
			breather = random.uniform(3.0, 5.0)
			time.sleep(breather)

	# 2. Proceed with individual analysis (now mostly cache hits)
	all_results = []
	total = len(tickers)
	for idx, ticker in enumerate(tickers, 1):
		ticker = ticker.upper().strip()
		try:
			logger.info(f"[{idx}/{total}] Processing {ticker}")
			res = analyze_asset(
				ticker, profile, repo=repo, benchmark_version=benchmark_version
			)
			if res:
				all_results.append(res)
				if progress_callback:
					progress_callback(res)
		except Exception as e:
			logger.error(f"Error analyzing {ticker}: {e}")

	logger.info(
		f"Bulk analysis complete. Successfully analyzed {len(all_results)}/{len(tickers)} tickers."
	)
	return all_results
