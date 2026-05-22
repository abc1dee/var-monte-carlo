"""
main.py — FastAPI application entry point.

Responsibilities:
  - Create the FastAPI app instance with metadata
  - Register CORS middleware
  - Mount all routers
  - Expose the GET /api/health endpoint

Start the server with:
    cd backend && uvicorn main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import (
    API_DESCRIPTION,
    API_TITLE,
    API_VERSION,
    CORS_ALLOWED_ORIGINS,
)
from routers.simulation import router as simulation_router
from schemas.responses import HealthResponse


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    docs_url="/docs",      # Swagger UI  — share this URL with your FE teammate
    redoc_url="/redoc",    # ReDoc alternative
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(simulation_router)


# ---------------------------------------------------------------------------
# Health check  (GET /api/health)
# ---------------------------------------------------------------------------

@app.get(
    "/api/health",
    response_model=HealthResponse,
    tags=["meta"],
    summary="Health check",
    response_description="Service status and API version.",
)
async def health_check() -> HealthResponse:
    """Lightweight liveness probe.

    Used by:
    - Frontend: to confirm the backend is reachable before submitting a simulation.
    - Render/deployment platform: as the health-check URL.
    - Developers: to wake the server before a live demo (avoids cold-start lag).

    Returns:
        ``{"status": "healthy", "version": "<API_VERSION>"}``
    """
    return HealthResponse(status="healthy", version=API_VERSION)