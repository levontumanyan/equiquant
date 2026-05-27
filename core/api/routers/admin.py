import logging
import os
import sqlite3
import subprocess  # nosec B404 - subprocess used only for osascript (macOS native dialog), not user input
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import ROOT_DIR
from core.api.deps import repo
from core.api.models import AppSetting, ExportRequest, SettingUpdate
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
		repo.upsert_app_setting("log_level", applied, category="logging")
		return {"level": applied}
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))


@router.get("/admin/settings", response_model=List[AppSetting])
async def get_all_settings_admin():
	"""Get all application settings."""
	try:
		return repo.get_all_settings()
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/settings/{key}")
async def update_setting_admin(key: str, update: SettingUpdate):
	"""Upsert a specific application setting."""
	try:
		existing = next((s for s in repo.get_all_settings() if s["key"] == key), None)
		repo.upsert_app_setting(
			key=key,
			value=update.value,
			category=existing["category"] if existing else "general",
			description=existing.get("description") if existing else None,
			is_secret=bool(existing.get("is_secret")) if existing else False,
		)

		if key == "log_level":
			try:
				set_log_level(update.value)
			except ValueError as e:
				raise HTTPException(status_code=400, detail=str(e))

		return {"status": "success", "message": f"Setting '{key}' updated."}
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/browse-directory")
async def browse_directory():
	"""Open a native macOS folder picker and return the selected path."""
	result = subprocess.run(  # nosec B603 B607 - hardcoded osascript invocation, no user input in args
		[
			"osascript",
			"-e",
			'POSIX path of (choose folder with prompt "Select backup directory:")',
		],
		capture_output=True,
		text=True,
	)
	if result.returncode != 0:
		return {"cancelled": True, "path": None}
	return {"cancelled": False, "path": result.stdout.strip()}


@router.post("/admin/backup")
async def create_backup():
	"""Perform a hot backup of equiquant.db to the configured backup directory."""
	backup_dir_setting = repo.get_setting("backup_dir", "")
	backup_dir = (
		Path(backup_dir_setting) if backup_dir_setting else ROOT_DIR / "backups"
	)
	backup_dir.mkdir(parents=True, exist_ok=True)

	db_path = ROOT_DIR / "equiquant.db"
	if not db_path.exists():
		raise HTTPException(status_code=404, detail="equiquant.db not found")

	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	dest_path = backup_dir / f"equiquant_{timestamp}.db"

	try:
		src = sqlite3.connect(str(db_path))
		dst = sqlite3.connect(str(dest_path))
		src.backup(dst)
		dst.close()
		src.close()
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Backup failed: {e}")

	return {"path": str(dest_path), "size_bytes": dest_path.stat().st_size}


@router.get("/admin/db/tables", response_model=List[str])
async def get_db_tables_admin():
	"""List all database tables."""
	try:
		return repo.get_db_tables()
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
