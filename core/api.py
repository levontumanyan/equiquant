import os
from contextlib import asynccontextmanager
from typing import Any, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository
from core.logger import get_logger
from core.orchestrator import fetch_data as orchestrator_fetch_data
from core.orchestrator import run_bulk_analysis
from core.scorers import SCORERS

logger = get_logger(__name__)

_openbb_ready = False


@asynccontextmanager
async def lifespan(_app: FastAPI):
	"""Warm up OpenBB synchronously on startup so it runs in the main thread."""
	global _openbb_ready
	try:
		logger.info("Warming up OpenBB...")
		from openbb import obb  # noqa: F401
		_openbb_ready = True
		logger.info("OpenBB ready.")
	except Exception as e:
		logger.error(f"OpenBB warmup failed: {e}")
	yield


app = FastAPI(
	title="EquiQuant API",
	description="Backend API for the EquiQuant Market Analysis Dashboard",
	version="0.1.0",
	lifespan=lifespan,
)


# Initialize Database
db_manager = DatabaseManager()
repo = DatabaseRepository(db_manager)

_cors_origins = os.getenv(
	"CORS_ORIGINS", "http://localhost:8888,http://localhost:5173"
).split(",")
app.add_middleware(
	CORSMiddleware,
	allow_origins=_cors_origins,
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
	unit: Optional[str] = None
	best: Optional[float] = None
	worst: Optional[float] = None
	target: Optional[float] = None
	target_min: Optional[float] = None
	target_max: Optional[float] = None
	width: Optional[float] = None
	threshold: Optional[float] = None


class FetchRequest(BaseModel):
	"""Request model for data fetching."""

	tickers: List[str]
	provider: str = "openbb"


class AnalysisRequest(BaseModel):
	"""Request model for analysis."""

	tickers: List[str]
	profile: str = "balanced"
	benchmark_version: str = "1.0.0"


class GroupRequest(BaseModel):
	"""Request model for creating or updating a stock group."""

	name: str
	tickers: List[str]
	description: Optional[str] = None


class ProfileRequest(BaseModel):
	"""Request model for creating or updating an investor profile."""

	name: str
	weights: dict
	ranges: dict
	formulas: dict


class MetricResult(BaseModel):
	"""Result model for individual metrics."""

	metric: str
	name: str
	value: Any
	raw_value: Optional[float] = None
	score: float
	weight: float
	status: str


class AssetAnalysis(BaseModel):
	"""Full analysis result for a single asset."""

	symbol: str
	name: str
	sector: Optional[str] = None
	industry: Optional[str] = None
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
	return {
		"backend": "connected",
		"database": "available",
		"version": "0.1.0",
		"openbb": "ready" if _openbb_ready else "warming_up",
	}


@app.get("/api/benchmarks", response_model=List[BenchmarkResponse])
async def get_benchmarks(
	asset_type: str = "equity", sector: Optional[str] = None, version: str = "1.0.0"
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
	metric_key: str, symbol: Optional[str] = None, limit: int = 100
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


@app.get("/api/formulas")
async def get_formulas():
	"""Fetch all available scoring formulas."""
	return list(SCORERS.keys())


@app.get("/api/groups")
async def list_groups():
	"""Fetch all available stock groups."""
	try:
		return repo.list_groups()
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/groups/{name}/tickers")
async def get_group_tickers(name: str):
	"""Fetch tickers for a specific group."""
	try:
		return repo.get_group_constituents(name)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/groups")
async def create_group(request: GroupRequest):
	"""Create or update a custom stock group."""
	try:
		repo.upsert_group(request.name, request.description)
		repo.update_group_constituents(request.name, request.tickers)
		return {"status": "ok", "name": request.name}
	except ValueError as e:
		raise HTTPException(status_code=409, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/groups/{name}")
async def delete_group(name: str):
	"""Delete a custom stock group."""
	try:
		result = repo.delete_group(name)
		if result == "not_found":
			raise HTTPException(status_code=404, detail=f"Group '{name}' not found")
		if result == "system":
			raise HTTPException(
				status_code=409,
				detail=f"'{name}' is a system group and cannot be deleted",
			)
		return {"status": "ok"}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/profiles/list")
async def list_profiles():
	"""Fetch all saved investor profile names."""
	try:
		return repo.list_profiles()
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/profiles/{name}")
async def get_profile(name: str):
	"""Fetch a single investor profile with all metric settings."""
	try:
		settings = repo.get_profile_settings(name)
		if not settings:
			raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")
		weights, ranges, formulas = {}, {}, {}
		for s in settings:
			key = s["metric_key"]
			weights[key] = s["weight"]
			ranges[key] = {"min": s["range_min"], "max": s["range_max"]}
			formulas[key] = s["formula"]
		return {"name": name, "weights": weights, "ranges": ranges, "formulas": formulas}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/profiles")
async def save_profile(profile: ProfileRequest):
	"""Create or update an investor profile with metric settings."""
	try:
		repo.create_profile(profile)
		return {"status": "ok", "name": profile.name}
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
	async for batch in orchestrator_fetch_data(tickers, repo=repo):
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
	missing_tickers = [t for t in tickers if not repo.should_use_db_cache(t)]

	if missing_tickers:
		async for _ in orchestrator_fetch_data(missing_tickers, repo=repo):
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
