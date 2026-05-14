from typing import List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository
from core.orchestrator import fetch_data as orchestrator_fetch_data

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


class FetchRequest(BaseModel):
	tickers: List[str]


@app.get("/health")
async def health_check():
	return {
		"status": "online",
		"version": "0.1.0",
		"message": "EquiQuant API is running",
	}


@app.get("/api/status")
async def get_app_status():
	return {
		"backend": "connected",
		"database": "available",
		"version": "0.1.0",
	}


@app.get("/api/sectors")
async def get_sectors():
	"""Get all unique sectors from the assets table."""
	try:
		sectors = repo.get_all_sectors()
		return {"sectors": sectors}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/assets")
async def get_assets(sector: Optional[str] = None):
	"""Get all assets, optionally filtered by sector."""
	try:
		assets = repo.get_assets_by_sector(sector) if sector else repo.get_all_assets()
		return {"assets": assets}
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


@app.get("/api/benchmarks")
async def get_benchmarks(
	asset_type: str, sector: Optional[str] = None, version: str = "1.0.0"
):
	"""Get benchmarks for a specific asset type and optional sector/version."""
	try:
		benchmarks = repo.get_global_benchmarks(asset_type.upper(), version=version)
		if sector:
			overrides = repo.get_sector_benchmarks(sector, version=version)
			return {"global": benchmarks, "overrides": overrides}
		return {"benchmarks": benchmarks}
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
	# For now, we just trigger the bulk fetch.
	# In a real app, we might want to track progress.
	tickers = [t.strip().upper() for t in request.tickers if t.strip()]

	if not tickers:
		return {"status": "error", "message": "No tickers provided"}

	# We run it in the background if it's a large request,
	# but for simplicity let's just run it and return results for now
	# or just confirm it started.

	success = await orchestrator_fetch_data(tickers)

	return {
		"status": "success" if success else "partial_success",
		"message": f"Fetched data for {len(tickers)} tickers",
		"tickers": tickers,
	}
