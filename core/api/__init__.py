import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.api.routers import admin, analysis, assets, config
from core.logger import SERVER_LOG_FILE, get_logger, setup_logging

logger = get_logger(__name__)
_openbb_ready = False


@asynccontextmanager
async def lifespan(_app: FastAPI):
	"""Configure logging, then warm up OpenBB synchronously in the main thread."""
	global _openbb_ready
	setup_logging(force_console=True, log_file=SERVER_LOG_FILE)
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
