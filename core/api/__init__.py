import asyncio
import os
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.api.routers import admin, analysis, assets, config
from core.logger import SERVER_LOG_FILE, get_logger, set_log_level, setup_logging

logger = get_logger(__name__)
_openbb_ready = False


def _warmup_openbb_sync():
	"""Perform the synchronous OpenBB import and update the ready flag."""
	global _openbb_ready
	try:
		logger.info("Warming up OpenBB in background thread...")
		from openbb import obb  # noqa: F401

		_openbb_ready = True
		logger.info("OpenBB ready.")
	except Exception as e:
		logger.error(f"OpenBB warmup failed: {e}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
	"""Configure logging, then offload OpenBB warmup to a worker thread."""
	setup_logging(force_console=True, log_file=SERVER_LOG_FILE)

	# Restore persisted log level from DB so restarts/reloads honour the saved setting
	try:
		from core.api.deps import repo

		saved = repo.get_setting("log_level")
		if saved:
			set_log_level(saved)
			logger.info("Restored log level from DB: %s", saved)
	except Exception as e:
		logger.warning("Could not restore log level from DB: %s", e)

	# Start warmup in background to avoid blocking initial health checks
	asyncio.create_task(anyio.to_thread.run_sync(_warmup_openbb_sync))

	yield


app = FastAPI(
	title="EquiQuant API",
	description="Backend API for the EquiQuant Market Analysis Dashboard",
	version="0.1.0",
	lifespan=lifespan,
)

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

# Register Routers
app.include_router(analysis.router)
app.include_router(admin.router)
app.include_router(assets.router)
app.include_router(config.router)


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
