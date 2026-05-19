from typing import List, Optional

from fastapi import APIRouter, HTTPException

from core.api.deps import db_manager, repo
from core.api.models import BenchmarkResponse, ProfileRequest
from core.scorers import SCORERS

router = APIRouter(prefix="/api")


@router.get("/benchmarks", response_model=List[BenchmarkResponse])
async def get_benchmarks(asset_type: str = "equity", version: str = "1.0.0"):
	"""Fetch all global benchmarks for a given asset type."""
	try:
		benchmarks = repo.get_global_benchmarks(asset_type, version)
		return benchmarks
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/sectors")
async def get_sectors():
	"""Fetch all unique sectors present in the asset registry."""
	try:
		conn = db_manager.get_connection()
		cursor = conn.cursor()
		cursor.execute(
			"SELECT DISTINCT sector FROM assets WHERE sector IS NOT NULL ORDER BY sector"
		)
		return [row[0] for row in cursor.fetchall()]
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/benchmark-versions")
async def get_benchmark_versions():
	"""Get all available benchmark versions."""
	try:
		versions = repo.get_benchmark_versions()
		return {"versions": versions}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/formulas")
async def get_formulas():
	"""Fetch all available scoring formulas."""
	return list(SCORERS.keys())


@router.get("/profiles/list")
async def list_profiles():
	"""Fetch all saved investor profile names."""
	try:
		return repo.list_profiles()
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/profiles/{name}")
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
		return {
			"name": name,
			"weights": weights,
			"ranges": ranges,
			"formulas": formulas,
		}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.post("/profiles")
async def save_profile(profile: ProfileRequest):
	"""Create or update an investor profile with metric settings."""
	try:
		repo.create_profile(profile)
		return {"status": "ok", "name": profile.name}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/{metric_key}/history")
async def get_metric_history(
	metric_key: str, symbol: Optional[str] = None, limit: int = 100
):
	"""Fetch historical data for a specific metric."""
	try:
		return repo.get_metric_history(metric_key, symbol, limit)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
