from fastapi import APIRouter, HTTPException

from core.analysis.indices import get_index_components
from core.api.deps import db_manager, repo
from core.api.models import FetchRequest, GroupRequest
from core.orchestrator import fetch_data as orchestrator_fetch_data

router = APIRouter(prefix="/api")


@router.get("/assets")
async def get_all_assets():
	"""Fetch all unique symbols currently in the assets table."""
	try:
		conn = db_manager.get_connection()
		cursor = conn.cursor()
		cursor.execute("SELECT symbol, name, sector FROM assets ORDER BY symbol")
		assets = [dict(row) for row in cursor.fetchall()]
		return assets
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/indices/{ticker}/constituents")
async def get_index_tickers(ticker: str):
	"""Fetch constituents for an index/ETF."""
	try:
		return get_index_components(ticker, repo=repo)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/groups")
async def list_groups():
	"""Fetch all available stock groups."""
	try:
		return repo.list_groups()
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/groups/{name}/tickers")
async def get_group_tickers(name: str):
	"""Fetch tickers for a specific group."""
	try:
		return repo.get_group_constituents(name)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.post("/groups")
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


@router.delete("/api/groups/{name}")
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


@router.post("/fetch")
async def fetch_data(request: FetchRequest):
	"""Trigger a data fetch for the given tickers. This is decoupled from analysis."""
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
