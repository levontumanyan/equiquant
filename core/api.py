from typing import Any, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository
from core.logger import get_logger
from core.openbb_client import should_use_cache
from core.orchestrator import fetch_data as orchestrator_fetch_data
from core.orchestrator import run_bulk_analysis

logger = get_logger(__name__)

app = FastAPI(
	title="EquiQuant API",
	description="Backend API for the EquiQuant Market Analysis Dashboard",
	version="0.1.0",
)

# Initialize Database
db_manager = DatabaseManager()
repo = DatabaseRepository(db_manager)

# CORS configuration
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


class BenchmarkResponse(BaseModel):
	"""Response model for benchmark data."""

	metric: str
	name: str
	type: str
	weight: float
	asset_type: str
	unit: str | None = None
	best: float | None = None
	worst: float | None = None
	target: float | None = None
	target_min: float | None = None
	target_max: float | None = None
	width: float | None = None
	threshold: float | None = None


class FetchRequest(BaseModel):
	"""Request model for data fetching."""

	tickers: List[str]
	provider: str = "openbb"


class AnalysisRequest(BaseModel):
	"""Request model for analysis."""

	tickers: List[str]
	profile: str = "balanced"
	benchmark_version: str = "1.0.0"


class MetricResult(BaseModel):
	"""Result model for individual metrics."""

	metric: str
	name: str
	value: Any
	raw_value: float | None = None
	score: float
	weight: float
	status: str


class AssetAnalysis(BaseModel):
	"""Full analysis result for a single asset."""

	symbol: str
	name: str
	sector: str | None = None
	industry: str | None = None
	score: float
	results: List[MetricResult]


@app.get("/health")
async def health_check():
	"""Returns the health status of the API."""
	return {
		"status": "online",
		"version": "0.1.0",
		"message": "EquiQuant API is running",
	}


@app.get("/api/status")
async def get_status():
	"""Detailed status for the frontend dashboard."""
	return {"backend": "connected", "database": "available", "version": "0.1.0"}


@app.get("/api/benchmarks", response_model=List[BenchmarkResponse])
async def get_benchmarks(
	asset_type: str = "equity", sector: str | None = None, version: str = "1.0.0"
):
	"""
	Fetch all global benchmarks for a given asset type, with optional sector overrides.
	"""
	try:
		benchmarks = repo.get_effective_benchmarks(asset_type, sector, version)
		return benchmarks
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sectors")
async def get_sectors():
	"""
	Fetch all unique sectors from the database.
	"""
	try:
		conn = db_manager.get_connection()
		cursor = conn.cursor()
		cursor.execute(
			"SELECT DISTINCT sector FROM assets WHERE sector IS NOT NULL ORDER BY sector"
		)
		sectors = [row[0] for row in cursor.fetchall()]

		# Also check sector_benchmarks just in case
		cursor.execute("SELECT DISTINCT sector FROM sector_benchmarks ORDER BY sector")
		for row in cursor.fetchall():
			if row[0] not in sectors:
				sectors.append(row[0])

		return sorted(sectors)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/benchmarks/sector/{sector}")
async def get_sector_benchmarks(sector: str, version: str = "1.0.0"):
	"""
	Fetch benchmarks for a specific sector.
	"""
	try:
		return repo.get_sector_benchmarks(sector, version)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metrics/{metric_key}/history")
async def get_metric_history(
	metric_key: str, symbol: str | None = None, limit: int = 100
):
	"""
	Fetch historical data for a specific metric.
	"""
	try:
		return repo.get_metric_history(metric_key, symbol, limit)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/assets")
async def get_all_assets():
	"""
	Fetch all unique symbols currently in the assets table.
	"""
	try:
		conn = db_manager.get_connection()
		cursor = conn.cursor()
		cursor.execute("SELECT symbol, name, sector FROM assets ORDER BY symbol")
		assets = [dict(row) for row in cursor.fetchall()]
		return assets
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analysis/{symbol}")
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


@app.get("/api/history/{symbol}")
async def get_history(symbol: str, profile: str = "balanced"):
	"""Get historical scores for a specific symbol and profile."""
	try:
		history = repo.get_historical_scores(symbol.upper(), profile)
		return {"history": history}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/benchmark-versions")
async def get_benchmark_versions():
	"""Get all available benchmark versions."""
	try:
		versions = repo.get_benchmark_versions()
		return {"versions": versions}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
	"""Get general database statistics."""
	try:
		counts = repo.get_asset_counts_by_type()
		total_analysis = repo.get_total_analysis_count()
		return {"asset_counts": counts, "total_analysis": total_analysis}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/fetch")
async def fetch_data(request: FetchRequest, background_tasks: BackgroundTasks):
	"""
	Trigger a data fetch for the given tickers.
	This is decoupled from analysis.
	"""
	tickers = [t.strip().upper() for t in request.tickers if t.strip()]

	if not tickers:
		return {"status": "error", "message": "No tickers provided"}

	fetched_count = 0
	async for batch in orchestrator_fetch_data(tickers):
		fetched_count += len(batch)

	return {
		"status": "success" if fetched_count == len(tickers) else "partial_success",
		"message": f"Fetched data for {fetched_count}/{len(tickers)} tickers",
		"tickers": tickers,
	}


@app.post("/api/analyze", response_model=List[AssetAnalysis])
async def analyze_assets(request: AnalysisRequest):
	"""
	Trigger live analysis for a list of tickers.
	"""
	tickers = [t.strip().upper() for t in request.tickers if t.strip()]
	if not tickers:
		raise HTTPException(status_code=400, detail="No tickers provided")

	# Identify tickers that need fetching
	missing_tickers = [t for t in tickers if not should_use_cache(t)]

	if missing_tickers:
		async for _ in orchestrator_fetch_data(missing_tickers):
			pass

	try:
		results = run_bulk_analysis(
			tickers=tickers,
			profile=request.profile,
			repo=repo,
			benchmark_version=request.benchmark_version,
		)
		return results
	except Exception as e:
		import traceback

		logger.error(f"Analysis failed: {e}\n{traceback.format_exc()}")
		raise HTTPException(status_code=500, detail=str(e))
