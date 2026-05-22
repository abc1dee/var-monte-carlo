"""
routers/simulation.py — Route handlers for simulation-related endpoints.

Endpoints
---------
GET  /api/tickers                → List predefined tickers
GET  /api/validate-ticker/{sym}  → Check if a custom ticker exists in yfinance
POST /api/simulate               → Run Monte Carlo VaR simulation

Architecture note
-----------------
This module is a *thin controller* — it delegates all business logic to the
service layer:
  - ``services.data_service``  : fetching + preprocessing historical data
  - ``services.quant_engine``  : Monte Carlo simulation + VaR calculation

Errors raised by services are caught here and translated into structured
HTTP responses using the custom exceptions from ``exceptions.py``.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config import ALLOWED_TICKERS, HISTORICAL_DATA_PERIOD
from exceptions import InvalidTickerError, DataFetchError, SimulationError
from schemas.requests import SimulationRequest
from schemas.responses import (
    SimulationResponse,
    TickersResponse,
    ValidateTickerResponse,
    ErrorResponse,
)
from services import data_service
from services import quant_engine

# ---------------------------------------------------------------------------
# Router instance
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["simulation"])


# ---------------------------------------------------------------------------
# GET /api/tickers
# ---------------------------------------------------------------------------


@router.get(
    "/tickers",
    response_model=TickersResponse,
    summary="List available tickers",
    response_description="Array of predefined stock tickers with name and sector.",
)
async def list_tickers() -> TickersResponse:
    """Return the predefined list of stock tickers available for simulation.

    These tickers are guaranteed to exist in Yahoo Finance and are curated
    for the demo.  Users can also enter custom tickers, validated via
    ``GET /api/validate-ticker/{symbol}``.
    """
    return TickersResponse(tickers=ALLOWED_TICKERS)


# ---------------------------------------------------------------------------
# GET /api/validate-ticker/{symbol}
# ---------------------------------------------------------------------------


@router.get(
    "/validate-ticker/{symbol}",
    response_model=ValidateTickerResponse,
    summary="Validate a custom ticker symbol",
    response_description="Whether the symbol is recognised by Yahoo Finance.",
    responses={
        200: {
            "description": "Validation result (always 200, even for invalid tickers).",
            "model": ValidateTickerResponse,
        }
    },
)
async def validate_ticker(symbol: str) -> ValidateTickerResponse:
    """Check whether a user-typed ticker symbol exists in Yahoo Finance.

    This is a lightweight probe that downloads one day of data.  Returns
    ``{valid: true/false, symbol: "..."}`` — never raises an HTTP error,
    even for unknown symbols.
    """
    normalised: str = symbol.strip().upper()
    is_valid: bool = await data_service.validate_ticker(normalised)
    return ValidateTickerResponse(valid=is_valid, symbol=normalised)


# ---------------------------------------------------------------------------
# POST /api/simulate
# ---------------------------------------------------------------------------


@router.post(
    "/simulate",
    response_model=SimulationResponse,
    summary="Run Monte Carlo VaR simulation",
    response_description="Full simulation results including VaR, CVaR, paths, and histogram.",
    responses={
        400: {
            "description": "Invalid ticker symbol.",
            "model": ErrorResponse,
        },
        503: {
            "description": "Yahoo Finance is unreachable.",
            "model": ErrorResponse,
        },
        500: {
            "description": "Unexpected server error during simulation.",
            "model": ErrorResponse,
        },
    },
)
async def run_simulation(request: SimulationRequest) -> SimulationResponse:
    """Fetch historical data, run Monte Carlo simulation, and return results.

    **Pipeline:**

    1. Fetch historical prices from Yahoo Finance via ``data_service``
    2. Compute log returns and extract the current price
    3. Run bootstrap Monte Carlo simulation via ``quant_engine``
    4. Assemble and return the structured response

    All custom exceptions are caught and translated into the appropriate
    HTTP status code with a structured error body.
    """
    try:
        # ── 1. Fetch historical price data ────────────────────────────────
        logger.info(
            "Simulation request: ticker=%s, horizon=%d, confidence=%.1f%%, "
            "sims=%d, investment=$%,.0f",
            request.ticker, request.horizon_days, request.confidence_level,
            request.num_simulations, request.initial_investment,
        )

        prices = await data_service.fetch_historical_data(
            ticker=request.ticker,
            period=HISTORICAL_DATA_PERIOD,
        )

        # ── 2. Preprocess: compute log returns + current price ────────────
        log_returns, current_price = data_service.preprocess_data(prices)

        # ── 3. Run Monte Carlo simulation ─────────────────────────────────
        engine_result: dict = quant_engine.run_simulation(
            log_returns=log_returns,
            num_simulations=request.num_simulations,
            horizon_days=request.horizon_days,
            confidence_level=request.confidence_level,
            initial_investment=request.initial_investment,
        )

        # ── 4. Build the response ─────────────────────────────────────────
        response = SimulationResponse(
            # Echo input parameters
            ticker=request.ticker,
            period=HISTORICAL_DATA_PERIOD,
            horizon_days=request.horizon_days,
            confidence_level=request.confidence_level,
            num_simulations=request.num_simulations,
            initial_investment=request.initial_investment,
            current_price=current_price,
            # Engine results (already in the correct nested structure)
            statistics=engine_result["statistics"],
            historical_var=engine_result["historical_var"],
            simulated_var=engine_result["simulated_var"],
            simulation_paths=engine_result["simulation_paths"],
            final_values_histogram=engine_result["final_values_histogram"],
        )

        logger.info(
            "Simulation complete for %s: MC VaR=%.4f%%, current_price=$%.2f",
            request.ticker,
            engine_result["simulated_var"]["var_pct"] * 100,
            current_price,
        )

        return response

    except InvalidTickerError as exc:
        logger.warning("Invalid ticker: %s", exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    except DataFetchError as exc:
        logger.error("Data fetch failure: %s", exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    except SimulationError as exc:
        logger.error("Simulation error: %s", exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    except Exception as exc:
        logger.exception("Unexpected error during simulation for %s", request.ticker)
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"An unexpected error occurred: {exc}",
                "error_code": "INTERNAL_ERROR",
            },
        )