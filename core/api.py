from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.database.manager import DatabaseManager
from core.database.repository import DatabaseRepository

app = FastAPI(
	title="EquiQuant API",
	description="Backend API for the EquiQuant Market Analysis Dashboard",
	version="0.1.0",
)

# Initialize Database
db_manager = DatabaseManager()
repo = DatabaseRepository(db_manager)

# Configure CORS for local development
app.add_middleware(
	CORSMiddleware,
	allow_origins=["http://localhost:5173"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


class BenchmarkResponse(BaseModel):
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
