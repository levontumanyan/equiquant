from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
	title="EquiQuant API",
	description="Backend API for the EquiQuant Market Analysis Dashboard",
	version="0.1.0",
)

# Configure CORS for local development
# Allowing the default Vite dev server port (5173)
app.add_middleware(
	CORSMiddleware,
	allow_origins=["http://localhost:5173"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


@app.get("/health")
async def health_check():
	"""
	Returns the health status of the API.
	"""
	return {
		"status": "online",
		"version": "0.1.0",
		"message": "EquiQuant API is running",
	}


@app.get("/api/status")
async def get_status():
	"""
	Detailed status for the frontend dashboard.
	"""
	return {
		"backend": "connected",
		"database": "available",  # TODO: Add actual DB check
		"version": "0.1.0",
	}
