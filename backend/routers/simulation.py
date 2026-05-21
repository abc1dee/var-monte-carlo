"""
routers/simulation.py — Route handlers for simulation-related endpoints.

Current endpoints (Phase 0 scaffold):
  GET  /api/tickers              → list predefined tickers

Endpoints added in later prompts:
  GET  /api/validate-ticker/{symbol}
  POST /api/simulate
"""

from fastapi import APIRouter

from config import ALLOWED_TICKERS


router = APIRouter(prefix="/api", tags=["simulation"])


# ---------------------------------------------------------------------------
# GET /api/tickers
# ---------------------------------------------------------------------------

@router.get(
    "/tickers",
    summary="List available tickers",
    response_description="Array of predefined stock tickers with name and sector.",
)
async def list_tickers() -> dict:
    """Return the predefined list of stock tickers available for simulation.

    Returns:
        A dict with a ``tickers`` key containing all configured ticker objects.

    Example response::

        {
            "tickers": [
                {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Technology"},
                ...
            ]
        }
    """
    return {"tickers": ALLOWED_TICKERS}