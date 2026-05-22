import asyncio
import os
import random
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from functools import partial
from typing import (
	Any,
	AsyncGenerator,
	AsyncIterator,
	Dict,
	List,
	Literal,
	Optional,
	Tuple,
)

import anyio

from core.data import get_cached_stock_data, load_benchmarks
from core.database.repository import DatabaseRepository
from core.evaluation import evaluate_metric
from core.logger import get_logger
from core.profiles import get_profile_config
from core.schema import AssetData
from core.stats import stats

logger = get_logger(__name__)

ScoringContext = Literal["global", "sector", "batch"]


def analyze_asset(
	asset: AssetData,
	profile: str,
	repo: Optional[DatabaseRepository] = None,
	benchmark_version: str = "1.0.0",
	benchmark_overrides: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
	"""
	Analyze a single pre-loaded asset by evaluating benchmarks and optionally saving results.

	If benchmark_overrides is provided (computed externally for sector or batch context),
	those definitions are used directly instead of loading from the DB.

	Args:
		asset: Pre-loaded AssetData object.
		profile: The investor profile name to use for weighting.
		repo: Optional database repository for persistence.
		benchmark_version: The version of benchmarks to load (used when no overrides).
		benchmark_overrides: Pre-computed benchmark defs for relative scoring contexts.
			When None, global benchmarks are loaded from the DB.

	Returns:
		A dictionary containing analysis results and the final score, or None if analysis failed.
	"""
	symbol = asset.symbol
	logger.info(f"Analyzing asset: {symbol} with profile: {profile}")

	if benchmark_overrides is not None:
		benchmark_defs = benchmark_overrides
	else:
		benchmark_defs = load_benchmarks(
			asset.asset_type.value,
			repo=repo,
			version=benchmark_version,
		)

	if not benchmark_defs:
		logger.error(f"No benchmarks found for {symbol}")
		return None

	profile_config = get_profile_config(repo, profile)

	scoring_start = time.perf_counter()
	results = []
	for b in benchmark_defs:
		res = evaluate_metric(asset, b, profile_config)
		# Add source attribution
		m_key = b.get("metric_key") or b.get("metric")
		res["source"] = asset.sources.get(m_key, "unknown") if m_key else "unknown"
		results.append(res)

	stats.scoring_time_total += time.perf_counter() - scoring_start

	# Data Quality Audit: Record which metrics were present
	for res in results:
		metric_key = res.get("metric")
		if metric_key:
			is_present = res.get("raw_value") is not None
			stats.record_metric_coverage(metric_key, is_present)

	# Calculate total score
	total_score = sum(res["score"] for res in results)
	# Penalty metrics do not contribute to the 'potential' max score;
	# they only drag the total score down from its positive potential.
	max_score = sum(res["weight"] for res in results if not res.get("is_penalty"))
	final_pct = (total_score / max_score * 100) if max_score > 0 else 0.0

	# Clamp the final percentage to [0, 100] unless we want to allow negative totals
	# The issue suggests: "surface extreme cases" — let's allow it to go negative
	# but maybe clamp the UI? For now, we follow the math.
	# final_pct = max(0.0, min(100.0, final_pct))

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
		"sources": asset.sources,
		"market_cap": asset.raw_data.get("market_cap")
		if asset.raw_data.get("market_cap") is not None
		else asset.raw_data.get("marketCap"),
	}


def _tracked_analyze_asset(
	ticker: str,
	profile: str,
	repo: Optional[DatabaseRepository] = None,
	benchmark_version: str = "1.0.0",
	submitted_at: float = 0.0,
	cancel_event: Optional[threading.Event] = None,
	benchmark_overrides: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
	"""
	Wraps analyze_asset with telemetry and cooperative cancellation support.

	Args:
		ticker: Ticker symbol to analyse.
		profile: Investor profile name.
		repo: Database repository for cache and persistence.
		benchmark_version: Benchmark version string.
		submitted_at: perf_counter timestamp when the task was submitted (for latency tracking).
		cancel_event: Optional threading.Event; returns None immediately when set.
		benchmark_overrides: Pre-computed benchmark defs for relative scoring contexts.

	Returns:
		Analysis result dict, or None if cancelled or data unavailable.
	"""
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
		return analyze_asset(
			asset, profile, repo, benchmark_version, benchmark_overrides
		)
	finally:
		worker_time = time.perf_counter() - start_time
		stats.record_task_complete(worker_time)


def _fetch_batch_process_worker(
	batch_tickers: List[str],
	current_cooldown: float = 5.0,
	db_path: Optional[str] = None,
) -> Tuple[bool, float, Dict[str, Any]]:
	"""Worker function for ProcessPoolExecutor to fetch data."""
	from core.openbb_client import fetch_batch_with_backoff

	return fetch_batch_with_backoff(batch_tickers, current_cooldown, db_path=db_path)


async def fetch_data(  # noqa: C901
	tickers: List[str],
	batch_size: int = 20,
	use_processes: bool = True,
	repo: Optional[DatabaseRepository] = None,
) -> AsyncIterator[List[str]]:
	"""
	Fetch data for multiple tickers in parallel batches and yield successful batches.
	Enables pipelining where analysis can start before all fetching is done.
	Now supports multi-source fetching (OpenBB + SEC + FRED).
	"""

	tickers = [t.upper().strip() for t in tickers if t.strip()]
	logger.info(f"Starting hybrid data fetch for {len(tickers)} tickers")

	# 1. First, fetch from SEC and FRED (fast, I/O bound)
	from core.providers.fred_provider import FREDProvider
	from core.providers.sec_provider import SECProvider

	sec_provider = SECProvider(repo=repo)
	fred_provider = FREDProvider(repo=repo)

	def _perform_enrichment_fetch_sync():
		# Fetch Macro snapshot if needed (log warning once if not configured)
		if not fred_provider.is_configured:
			logger.info("FRED Provider skipped (API Key not configured)")
		elif repo and not repo.should_use_db_cache("MACRO", "fred"):
			macro_data = fred_provider.get_data("MACRO")
			if macro_data:
				repo.upsert_raw_provider_data("MACRO", "fred", macro_data.raw_data)

		# SEC Data Fetch (log warning once if not configured)
		if not sec_provider.is_configured:
			logger.info("SEC Provider skipped (User-Agent not configured)")
		else:
			# We can use a small ThreadPool for SEC lookups
			with ThreadPoolExecutor(max_workers=10) as executor:
				sec_futures = {
					executor.submit(sec_provider.get_data, t): t for t in tickers
				}
				for future in as_completed(sec_futures):
					symbol = sec_futures[future]
					try:
						asset = future.result()
						if asset and repo:
							repo.upsert_raw_provider_data(symbol, "sec", asset.raw_data)
					except Exception as e:
						logger.warning(f"Failed to fetch SEC data for {symbol}: {e}")

	await anyio.to_thread.run_sync(_perform_enrichment_fetch_sync)

	# 2. Then, proceed with OpenBB bulk fetch as before
	batches = [tickers[i : i + batch_size] for i in range(0, len(tickers), batch_size)]

	if not batches:
		return

	db_path_str = str(repo.db.db_path) if repo else None

	if not use_processes:
		current_cooldown = 5.0
		for batch in batches:
			# PR Feedback: Correctly propagate cooldown between batches in sequential mode
			success, current_cooldown, data = _fetch_batch_process_worker(
				batch, current_cooldown, db_path=db_path_str
			)
			if success:
				stats.api_successes += len(data)
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
			task = loop.run_in_executor(
				pool, _fetch_batch_process_worker, batch, 5.0, db_path_str
			)
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
						stats.api_successes += len(data)
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


def _build_batch_benchmarks(
	tickers: List[str],
	asset_type_value: str,
	repo: Optional[DatabaseRepository],
	benchmark_version: str,
) -> Optional[List[Dict[str, Any]]]:
	"""
	Pre-compute batch-relative benchmarks by loading all cached assets and
	deriving distributional thresholds from their metric values.

	Returns None if fewer than 3 assets have cached data (falls back to global).

	Args:
		tickers: All ticker symbols in the batch.
		asset_type_value: Asset type string for global benchmark lookup.
		repo: Database repository.
		benchmark_version: Benchmark version string.

	Returns:
		Relative benchmark list, or None to signal fallback to global.
	"""
	from core.analysis.relative import compute_batch_relative_benchmarks

	assets = [get_cached_stock_data(t, repo=repo) for t in tickers]
	assets = [a for a in assets if a is not None]

	if len(assets) < 3:
		logger.warning(
			"Batch-relative mode: fewer than 3 cached assets, falling back to global."
		)
		return None

	global_benchmarks = load_benchmarks(
		asset_type_value, repo=repo, version=benchmark_version
	)
	return compute_batch_relative_benchmarks(assets, global_benchmarks)


def _resolve_asset_benchmarks(
	ticker: str,
	context: ScoringContext,
	global_benchmarks: List[Dict[str, Any]],
	batch_benchmarks: Optional[List[Dict[str, Any]]],
	repo: Optional[DatabaseRepository],
	sector_cache: Dict[str, List[Dict[str, Any]]],
) -> Optional[List[Dict[str, Any]]]:
	"""
	Resolve the benchmark list for a single ticker given the active context.

	Called from the main thread so sector_cache writes are serialised.

	Args:
		ticker: Normalised ticker symbol.
		context: Active scoring context.
		global_benchmarks: Pre-loaded global benchmark definitions.
		batch_benchmarks: Pre-computed batch-relative benchmarks (context='batch').
		repo: Database repository for sector peer queries.
		sector_cache: Per-sector benchmark cache, mutated in-place as sectors are seen.

	Returns:
		Benchmark list to pass as overrides, or None to fall back to global.
	"""
	if context == "batch":
		return batch_benchmarks
	if context == "sector" and repo:
		# Use a cheap sector-only lookup so the full asset load happens only
		# once inside the analysis worker, not twice (here + in _tracked_analyze_asset).
		sector = repo.get_asset_sector(ticker)
		if sector:
			if sector not in sector_cache:
				from core.analysis.relative import compute_sector_relative_benchmarks

				sector_cache[sector] = compute_sector_relative_benchmarks(
					sector, repo, global_benchmarks
				)
			return sector_cache[sector]
	return None


def run_bulk_analysis(
	tickers: List[str],
	profile: str,
	progress_callback: Optional[Any] = None,
	repo: Optional[DatabaseRepository] = None,
	benchmark_version: str = "1.0.0",
	max_workers: int = 5,
	context: ScoringContext = "global",
) -> List[Dict[str, Any]]:
	"""
	Run analysis for multiple tickers using parallel processing.
	Only processes data that is already cached locally.

	Args:
		tickers: Ticker symbols to analyse.
		profile: Investor profile name.
		progress_callback: Optional callable called with each result as it completes.
		repo: Optional database repository for persistence.
		benchmark_version: Benchmark version string.
		max_workers: Thread pool size.
		context: Scoring context — 'global', 'sector', or 'batch'.

	Returns:
		List of analysis result dicts.
	"""
	logger.info(
		f"Starting bulk analysis for {len(tickers)} tickers with {max_workers} workers (context={context})"
	)

	global_benchmarks = load_benchmarks("STOCK", repo=repo, version=benchmark_version)
	batch_benchmarks: Optional[List[Dict[str, Any]]] = None
	sector_cache: Dict[str, List[Dict[str, Any]]] = {}

	if context == "batch":
		batch_benchmarks = _build_batch_benchmarks(
			tickers, "STOCK", repo, benchmark_version
		)

	all_results = []

	with ThreadPoolExecutor(max_workers=max_workers) as executor:
		futures = []

		for ticker in tickers:
			ticker = ticker.upper().strip()
			stats.record_pool_submission()
			asset_benchmarks = _resolve_asset_benchmarks(
				ticker, context, global_benchmarks, batch_benchmarks, repo, sector_cache
			)
			futures.append(
				executor.submit(
					_tracked_analyze_asset,
					ticker,
					profile,
					repo=repo,
					benchmark_version=benchmark_version,
					submitted_at=time.perf_counter(),
					benchmark_overrides=asset_benchmarks,
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
	context: ScoringContext = "global",
) -> AsyncGenerator[Dict[str, Any], None]:
	"""
	Async generator that yields individual analysis results as each ticker completes.

	Runs analysis in a ThreadPoolExecutor and yields results via asyncio.wait so
	the caller receives each result as soon as it is ready. On cancellation the
	executor is shut down immediately without waiting for in-flight threads.

	When an external executor is provided the caller owns its lifecycle; otherwise
	this function creates and tears down its own executor.

	For 'batch' context the function performs a two-pass approach: all asset data
	must be available before batch benchmarks can be computed, so there is no
	fetch-time pipelining in that mode. Data is loaded from cache only.

	Args:
		tickers: Ticker symbols to analyse (normalised to uppercase internally).
		profile: Investor profile name used for metric weighting.
		repo: Optional database repository for persistence and result saving.
		benchmark_version: Benchmark definition version string.
		max_workers: Maximum parallel worker threads (used only when no external executor).
		executor: Optional external ThreadPoolExecutor to reuse across calls.
		cancel_event: Optional threading.Event for cooperative cancellation.
		context: Scoring context — 'global', 'sector', or 'batch'.

	Yields:
		Analysis result dict for each completed ticker (None results are skipped).
	"""
	loop = asyncio.get_running_loop()
	completed_results: List[Dict[str, Any]] = []
	cancelled = False
	owns_executor = executor is None

	if owns_executor:
		executor = ThreadPoolExecutor(max_workers=max_workers)

	# Resolve per-asset benchmark overrides in the main thread before submitting to pool.
	# sector_cache is populated here (single-threaded) so workers only read from it.
	global_benchmarks = load_benchmarks("STOCK", repo=repo, version=benchmark_version)
	batch_benchmarks: Optional[List[Dict[str, Any]]] = None
	sector_cache: Dict[str, List[Dict[str, Any]]] = {}

	if context == "batch":
		batch_benchmarks = _build_batch_benchmarks(
			tickers, "STOCK", repo, benchmark_version
		)

	futures: List[asyncio.Future] = []

	try:
		for ticker in tickers:
			ticker = ticker.upper().strip()
			stats.record_pool_submission()

			asset_benchmarks = _resolve_asset_benchmarks(
				ticker, context, global_benchmarks, batch_benchmarks, repo, sector_cache
			)

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
					asset_benchmarks,
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
