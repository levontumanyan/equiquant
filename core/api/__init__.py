import asyncio
import os
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.api.routers import admin, analysis, assets, config
from core.logger import SERVER_LOG_FILE, get_logger, set_log_level, setup_logging
from core.openbb_client import ensure_openbb_ready, is_openbb_ready

logger = get_logger(__name__)
_sec_ready = False


def _warmup_sec_sync():
	"""Perform synchronous warmup of SEC EDGAR mapping."""
	global _sec_ready
	try:
		logger.info("Warming up SEC EDGAR mapping...")
		from core.api.deps import repo
		from core.utils.sec import get_cik

		# Trigger a lookup to ensure mapping is cached in DB
		_ = get_cik("AAPL", repo)
		_sec_ready = True
		logger.info("SEC EDGAR ready.")
	except Exception:
		logger.exception("SEC EDGAR warmup failed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
	"""Configure logging and perform background warmup of providers."""
	setup_logging(force_console=True, log_file=SERVER_LOG_FILE)

	# Restore persisted log level from DB
	try:
		from core.api.deps import repo

		saved = repo.get_setting("log_level")
		if saved:
			set_log_level(saved)
			logger.info("Restored log level from DB: %s", saved)
	except Exception as e:
		logger.warning("Could not restore log level from DB: %s", e)

	# Start warmup in background to avoid blocking server availability.
	# We use anyio.to_thread so health checks and requests work immediately.
	os.environ["OPENBB_AUTO_BUILD"] = "false"

	async def full_warmup():
		await anyio.to_thread.run_sync(ensure_openbb_ready)
		await anyio.to_thread.run_sync(_warmup_sec_sync)

	warmup_task = asyncio.create_task(full_warmup())

	try:
		yield
	finally:
		warmup_task.cancel()
		try:
			await warmup_task
		except asyncio.CancelledError:
			logger.debug("Warmup task successfully cancelled.")


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
	# We check the global flags from the providers
	return {
		"backend": "connected",
		"database": "available",
		"version": "0.1.0",
		"openbb": "ready" if is_openbb_ready() else "warming_up",
		"sec": "ready" if _sec_ready else "warming_up",
	}
