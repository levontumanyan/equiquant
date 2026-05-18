import logging
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.api.deps import repo
from core.api.models import ExportRequest
from core.logger import set_log_level
from core.reporting.factory import generate_report

router = APIRouter(prefix="/api")


class LogLevelRequest(BaseModel):
	"""Request model for changing the server log level."""

	level: str


@router.post("/export")
async def export_results(request: ExportRequest, background_tasks: BackgroundTasks):
	"""Generate and return a report file, removing it from disk after the response is sent."""
	try:
		path = generate_report(
			results=request.results,
			fmt=request.format,
			tickers=request.tickers,
			index_name=request.index_name,
			profile=request.profile,
		)
		background_tasks.add_task(os.unlink, path)
		return FileResponse(
			path,
			filename=os.path.basename(path),
			media_type="application/octet-stream",
		)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/stats")
async def get_admin_stats():
	"""Aggregate statistics across all sessions and the asset cache."""
	try:
		return repo.get_aggregate_stats()
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/telemetry")
async def get_telemetry_admin(limit: int = 50):
	"""Detailed telemetry for admin view."""
	try:
		return repo.get_telemetry_history(limit)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/log-level")
async def get_log_level():
	"""Return the current effective log level of the root logger."""
	return {"level": logging.getLevelName(logging.getLogger().level)}


@router.post("/admin/log-level")
async def update_log_level(request: LogLevelRequest):
	"""Dynamically change the server log level without a restart."""
	try:
		applied = set_log_level(request.level)
		return {"level": applied}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))


@router.get("/admin/db/{table}")
async def get_db_table_admin(table: str, limit: int = 100):
	"""Raw database table inspection."""
	try:
		return repo.get_table_data(table, limit)
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
