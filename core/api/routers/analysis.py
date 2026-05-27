import asyncio
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from core.api.deps import db_manager, repo
from core.api.models import AnalysisRequest, AssetAnalysis
from core.logger import get_logger
from core.orchestrator import fetch_data as orchestrator_fetch_data
from core.orchestrator import run_bulk_analysis, stream_bulk_analysis
from core.stats import stats

logger = get_logger(__name__)
router = APIRouter(prefix="/api")


@router.get("/analysis/{symbol}")
async def get_analysis(symbol: str):
	"""Get the latest analysis for a specific symbol."""
	try:
		analysis = repo.get_latest_analysis(symbol.upper())
		if not analysis:
			raise HTTPException(status_code=404, detail="Analysis not found")
		return analysis
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{symbol}")
async def get_history(symbol: str, profile: str = "balanced"):
	"""Get historical scores for a specific symbol and profile."""
	try:
		history = repo.get_historical_scores(symbol.upper(), profile)
		return {"history": history}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


def _initialize_stats(tickers: List[str]):
	"""Initialize stats and return db_path."""
	stats.reset()
	stats.total_tickers = len(tickers)
	db_path = db_manager.db_path
	if db_path.exists():
		stats.initial_db_size = db_path.stat().st_size
	return db_path


async def _finalize_stats(
	analyzed_count: int, db_path, tickers: List[str] | None = None
):
	"""Finalize stats and save telemetry."""
	stats.analyzed_tickers = analyzed_count
	if tickers is not None:
		stats.analyzed_symbols = list(tickers)
	if db_path.exists():
		stats.final_db_size = db_path.stat().st_size
		await asyncio.to_thread(
			repo.save_telemetry, stats.get_total_time(), stats.to_dict()
		)


def _fetch_params(n: int) -> tuple[int, bool]:
	"""
	Compute optimal batch_size and use_processes for a given ticker count.

	Batch size scales linearly with n (capped at 50) so large runs use fewer,
	larger batches and reduce coordinator round-trip overhead. Subprocess workers
	are skipped entirely for tiny requests to avoid the ~300-500ms spawn cost.

	Args:
		n: Number of tickers to fetch.

	Returns:
		Tuple of (batch_size, use_processes).
	"""
	use_processes = n > 20
	batch_size = max(20, min(50, n // 10))
	return batch_size, use_processes


def _split_tickers(tickers: List[str], force_refresh: bool = False):
	"""Split tickers into cached and missing, updating stats accordingly.

	Args:
		tickers: List of ticker symbols to split.
		force_refresh: When True, all tickers are treated as missing regardless of cache state.

	Returns:
		Tuple of (cached_tickers, missing_tickers).
	"""
	missing_tickers = []
	cached_tickers = []
	for t in tickers:
		if not force_refresh and repo.should_use_db_cache(t):
			stats.cache_hits += 1
			cached_tickers.append(t)
		else:
			stats.api_attempts += 1
			missing_tickers.append(t)
	return cached_tickers, missing_tickers


async def _stream_results(
	batch: List[str],
	request: AnalysisRequest,
	executor: ThreadPoolExecutor,
	cancel_event: threading.Event,
):
	"""Stream analysis results for a batch of tickers."""
	async for result in stream_bulk_analysis(
		batch,
		profile=request.profile,
		repo=repo,
		benchmark_version=request.benchmark_version,
		executor=executor,
		cancel_event=cancel_event,
		context=request.context,
	):
		yield {
			"event": "result",
			"data": AssetAnalysis.model_validate(result).model_dump_json(),
		}


def _track_analyzed_symbol(event: dict, analyzed_symbols: set) -> None:
	"""Extract the symbol from a result event and record it as successfully analyzed.

	Args:
		event: SSE event dict with a 'data' key containing JSON.
		analyzed_symbols: Mutable set to add the symbol to.
	"""
	try:
		analyzed_symbols.add(json.loads(event["data"])["symbol"].upper())
	except Exception:  # nosec B110 - silently skip malformed SSE result events; symbol tracking is best-effort
		pass


async def event_generator(tickers: List[str], request: AnalysisRequest, db_path):  # noqa: C901
	"""Generate analysis events for streaming."""
	cached_tickers, missing_tickers = _split_tickers(
		tickers, force_refresh=request.force_refresh
	)
	analyzed_count = 0
	analyzed_symbols = set()
	cancel_event = threading.Event()
	executor = ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 4) + 4))

	try:
		if request.context == "batch" and missing_tickers:
			# Fetch all missing data first so batch benchmarks are computed from
			# the full ticker distribution, not sub-batches.
			yield {
				"event": "status",
				"data": json.dumps(
					{"message": f"Fetching data for {len(missing_tickers)} ticker(s)…"}
				),
			}
			batch_size, use_processes = _fetch_params(len(missing_tickers))
			stats.start_stage("Data Acquisition")
			async for batch in orchestrator_fetch_data(
				missing_tickers,
				batch_size=batch_size,
				use_processes=use_processes,
				repo=repo,
			):
				yield {
					"event": "status",
					"data": json.dumps(
						{
							"message": f"Fetched {len(batch)} ticker(s), preparing analysis…"
						}
					),
				}
			stats.end_stage("Data Acquisition")
			stats.start_stage("Analysis & Scoring")
			async for event in _stream_results(
				tickers, request, executor, cancel_event
			):
				analyzed_count += 1
				_track_analyzed_symbol(event, analyzed_symbols)
				yield event
			stats.end_stage("Analysis & Scoring")
		else:
			if cached_tickers:
				stats.start_stage("Analysis & Scoring (Cached)")
				async for event in _stream_results(
					cached_tickers, request, executor, cancel_event
				):
					analyzed_count += 1
					_track_analyzed_symbol(event, analyzed_symbols)
					yield event
				stats.end_stage("Analysis & Scoring (Cached)")

			if missing_tickers:
				yield {
					"event": "status",
					"data": json.dumps(
						{
							"message": f"Fetching data for {len(missing_tickers)} ticker(s)…"
						}
					),
				}
				batch_size, use_processes = _fetch_params(len(missing_tickers))
				stats.start_stage("Data Acquisition & Scoring")
				async for batch in orchestrator_fetch_data(
					missing_tickers,
					batch_size=batch_size,
					use_processes=use_processes,
					repo=repo,
				):
					async for event in _stream_results(
						batch, request, executor, cancel_event
					):
						analyzed_count += 1
						_track_analyzed_symbol(event, analyzed_symbols)
						yield event
				stats.end_stage("Data Acquisition & Scoring")

		# Yield errors for tickers that could not be analyzed
		failed_tickers = [
			t for t in tickers if t.upper().strip() not in analyzed_symbols
		]
		if failed_tickers:
			yield {
				"event": "error",
				"data": json.dumps(
					{
						"message": f"Could not analyze ticker(s): {', '.join(failed_tickers)}. Please verify that they are valid symbols containing fundamental data."
					}
				),
			}

		executor.shutdown(wait=False)
		await _finalize_stats(analyzed_count, db_path, tickers)

	except (asyncio.CancelledError, GeneratorExit):
		cancel_event.set()
		executor.shutdown(wait=False, cancel_futures=True)
		logger.info("SSE stream cancelled by client disconnect")
		return
	except Exception as e:
		import traceback

		cancel_event.set()
		executor.shutdown(wait=False)
		logger.error(f"Streaming analysis failed: {e}\n{traceback.format_exc()}")
		yield {"event": "error", "data": json.dumps({"message": str(e)})}
		return

	yield {
		"event": "done",
		"data": json.dumps({"analyzed": analyzed_count, "total": len(tickers)}),
	}


@router.post("/analyze", response_model=List[AssetAnalysis])
async def analyze_assets(request: AnalysisRequest):
	"""Trigger live analysis for a list of tickers."""
	tickers = [t.strip().upper() for t in request.tickers if t.strip()]
	if not tickers:
		raise HTTPException(status_code=400, detail="No tickers provided")

	db_path = _initialize_stats(tickers)
	# _split_tickers also records cache_hits / api_attempts on stats as a side effect
	_cached_tickers, missing_tickers = _split_tickers(
		tickers, force_refresh=request.force_refresh
	)

	if missing_tickers:
		batch_size, use_processes = _fetch_params(len(missing_tickers))
		stats.start_stage("Data Acquisition")
		async for _ in orchestrator_fetch_data(
			missing_tickers,
			batch_size=batch_size,
			use_processes=use_processes,
			repo=repo,
		):
			pass
		stats.end_stage("Data Acquisition")

	try:
		stats.start_stage("Analysis & Scoring")
		results = run_bulk_analysis(
			tickers=tickers,
			profile=request.profile,
			repo=repo,
			benchmark_version=request.benchmark_version,
			context=request.context,
		)
		stats.end_stage("Analysis & Scoring")
		await _finalize_stats(len(results), db_path, tickers)
		return results
	except Exception as e:
		import traceback

		logger.error(f"Analysis failed: {e}\n{traceback.format_exc()}")
		raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/stream")
async def analyze_assets_stream(request: AnalysisRequest):  # noqa: C901
	"""Stream analysis results for a list of tickers via Server-Sent Events."""
	tickers = [t.strip().upper() for t in request.tickers if t.strip()]
	if not tickers:
		raise HTTPException(status_code=400, detail="No tickers provided")

	db_path = _initialize_stats(tickers)
	return EventSourceResponse(event_generator(tickers, request, db_path))
