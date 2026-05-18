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


def _finalize_stats(analyzed_count: int, db_path, tickers: List[str] | None = None):
	"""Finalize stats and save telemetry."""
	stats.analyzed_tickers = analyzed_count
	if tickers is not None:
		stats.analyzed_symbols = list(tickers)
	if db_path.exists():
		stats.final_db_size = db_path.stat().st_size
		repo.save_telemetry(stats.get_total_time(), stats.to_dict())


def _split_tickers(tickers: List[str]):
	"""Split tickers into cached and missing, updating stats accordingly."""
	missing_tickers = []
	cached_tickers = []
	for t in tickers:
		if repo.should_use_db_cache(t):
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
	):
		yield {
			"event": "result",
			"data": AssetAnalysis.model_validate(result).model_dump_json(),
		}


async def event_generator(tickers: List[str], request: AnalysisRequest, db_path):  # noqa: C901
	"""Generate analysis events for streaming."""
	cached_tickers, missing_tickers = _split_tickers(tickers)
	analyzed_count = 0
	cancel_event = threading.Event()
	executor = ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 4) + 4))

	try:
		if cached_tickers:
			stats.start_stage("Analysis & Scoring (Cached)")
			async for event in _stream_results(
				cached_tickers, request, executor, cancel_event
			):
				analyzed_count += 1
				yield event
			stats.end_stage("Analysis & Scoring (Cached)")

		if missing_tickers:
			yield {
				"event": "status",
				"data": json.dumps(
					{"message": f"Fetching data for {len(missing_tickers)} ticker(s)…"}
				),
			}
			stats.start_stage("Data Acquisition & Scoring")
			async for batch in orchestrator_fetch_data(missing_tickers, repo=repo):
				async for event in _stream_results(
					batch, request, executor, cancel_event
				):
					analyzed_count += 1
					yield event
			stats.end_stage("Data Acquisition & Scoring")

		executor.shutdown(wait=False)
		_finalize_stats(analyzed_count, db_path, tickers)

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
	_cached_tickers, missing_tickers = _split_tickers(tickers)

	if missing_tickers:
		stats.start_stage("Data Acquisition")
		async for _ in orchestrator_fetch_data(missing_tickers, repo=repo):
			pass
		stats.end_stage("Data Acquisition")

	try:
		stats.start_stage("Analysis & Scoring")
		results = run_bulk_analysis(
			tickers=tickers,
			profile=request.profile,
			repo=repo,
			benchmark_version=request.benchmark_version,
		)
		stats.end_stage("Analysis & Scoring")
		_finalize_stats(len(results), db_path, tickers)
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
