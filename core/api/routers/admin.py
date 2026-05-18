import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core.api.deps import repo
from core.api.models import ExportRequest
from core.reporting.factory import generate_report

router = APIRouter(prefix="/api")


@router.post("/export")
async def export_results(request: ExportRequest):
	"""Generate and return a report file."""
	try:
		path = generate_report(
			results=request.results,
			fmt=request.format,
			tickers=request.tickers,
			index_name=request.index_name,
			profile=request.profile,
		)
		return FileResponse(
			path,
			filename=os.path.basename(path),
			media_type="application/octet-stream",
		)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/telemetry")
async def get_telemetry_admin(limit: int = 50):
	"""Detailed telemetry for admin view."""
	try:
		return repo.get_telemetry_history(limit)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/db/{table}")
async def get_db_table_admin(table: str, limit: int = 100):
	"""Raw database table inspection."""
	try:
		return repo.get_table_data(table, limit)
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
