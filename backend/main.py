"""
main.py — FastAPI application entry point.

Responsibilities:
  - Create the FastAPI app instance with metadata
  - Register CORS middleware
  - Register auth-injection middleware (attaches UserContext to request.state)
  - Register rate-limiter middleware (slowapi)
  - Mount all routers
  - Expose the GET /api/health endpoint

Start the server with:
    cd backend && uvicorn main:app --reload
"""

import logging
from typing import Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from auth import UserContext, decode_supabase_jwt
from exceptions import AppBaseError
from config import (
    API_DESCRIPTION,
    API_TITLE,
    API_VERSION,
    CORS_ALLOWED_ORIGINS,
)
from middleware.rate_limit import limiter
from routers.simulation import router as simulation_router
from schemas.responses import HealthResponse

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


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
# Rate limiter — attach to app state (required by slowapi)
# ---------------------------------------------------------------------------

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------

# One handler for ALL custom domain exceptions (InvalidTickerError,
# DataFetchError, SimulationError, AuthorizationError, AuthenticationError).
# This removes the need for repetitive except-blocks in every route handler.
@app.exception_handler(AppBaseError)
async def app_error_handler(request: Request, exc: AppBaseError) -> Response:
    logger.warning(
        "Domain error [%s %s]: %s — %s",
        request.method, request.url.path, exc.error_code, exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "error_code": exc.error_code},
    )


# Catch-all for truly unexpected errors so clients always get structured JSON.
@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> Response:
    logger.exception(
        "Unhandled exception [%s %s]: %s",
        request.method, request.url.path, exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred.", "error_code": "INTERNAL_ERROR"},
    )


# ---------------------------------------------------------------------------
# Middleware — execution order is LIFO (last added runs first)
# ---------------------------------------------------------------------------

# 1. CORS (outermost — runs first on every request)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. Auth injection — lightweight middleware that decodes the JWT (if present)
#    and attaches a UserContext to request.state so that the rate limiter's
#    key function and the router's Depends() can both read it without
#    decoding the token twice.
@app.middleware("http")
async def inject_user_context(request: Request, call_next) -> Response:
    """Attach UserContext to request.state before downstream processing."""
    user = UserContext()  # default: guest

    auth_header: Optional[str] = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            try:
                payload = decode_supabase_jwt(parts[1])
                user = UserContext(
                    user_id=payload.get("sub", ""),
                    email=payload.get("email"),
                    is_authenticated=True,
                    tier="authenticated",
                )
            except Exception:
                # Invalid/expired token → keep guest context.
                pass

    request.state.user = user
    response = await call_next(request)
    return response


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