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

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from supabase import create_client, Client
from settings import settings
_supabase: Client = create_client(settings.supabase_url, settings.supabase_service_role_key)

from config import (
    ALLOWED_TICKERS,
    HISTORICAL_DATA_PERIOD,
    GUEST_MAX_NUM_SIMULATIONS,
    GUEST_MAX_HORIZON_DAYS,
    AUTH_MAX_NUM_SIMULATIONS,
    AUTH_MAX_HORIZON_DAYS,
    GUEST_MAX_SIMULATIONS_PER_HOUR,
    AUTH_MAX_SIMULATIONS_PER_HOUR,
)
from exceptions import InvalidTickerError, DataFetchError, SimulationError, AuthorizationError
from schemas.requests import SimulationRequest
from schemas.responses import (
    SimulationResponse,
    TickersResponse,
    ValidateTickerResponse,
    ErrorResponse,
    SimulationHistoryResponse,
    UserTierResponse,
    TierLimits,
    TierUsage,
)
from services import data_service
from services import quant_engine
from auth import UserContext, get_current_user, require_auth
from middleware.rate_limit import limiter, get_dynamic_limit

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
        403: {
            "description": "Tier limit exceeded.",
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
@limiter.limit(get_dynamic_limit)
async def run_simulation(
    request: Request,
    sim_request: SimulationRequest,
    user: UserContext = Depends(get_current_user)
) -> SimulationResponse:
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
        # ── 0. Enforce tier limits ────────────────────────────────────────
        if not user.is_authenticated:
            if sim_request.num_simulations > GUEST_MAX_NUM_SIMULATIONS:
                raise AuthorizationError(
                    f"Guest users are limited to {GUEST_MAX_NUM_SIMULATIONS:,} simulations. "
                    f"Sign up for free to unlock up to {AUTH_MAX_NUM_SIMULATIONS:,}."
                )
            if sim_request.horizon_days > GUEST_MAX_HORIZON_DAYS:
                raise AuthorizationError(
                    f"Guest users are limited to {GUEST_MAX_HORIZON_DAYS}-day horizon. "
                    f"Sign up for free to unlock up to {AUTH_MAX_HORIZON_DAYS} days."
                )

        # ── 1. Fetch historical price data ────────────────────────────────
        logger.info(
            "Simulation request: ticker=%s, horizon=%d, confidence=%.1f%%, "
            "sims=%d, investment=$%,.0f, tier=%s",
            sim_request.ticker, sim_request.horizon_days, sim_request.confidence_level,
            sim_request.num_simulations, sim_request.initial_investment, user.tier,
        )

        prices = await data_service.fetch_historical_data(
            ticker=sim_request.ticker,
            period=HISTORICAL_DATA_PERIOD,
        )

        # ── 2. Preprocess: compute log returns + current price ────────────
        log_returns, current_price = data_service.preprocess_data(prices)

        # ── 3. Run Monte Carlo simulation ─────────────────────────────────
        engine_result: dict = quant_engine.run_simulation(
            log_returns=log_returns,
            num_simulations=sim_request.num_simulations,
            horizon_days=sim_request.horizon_days,
            confidence_level=sim_request.confidence_level,
            initial_investment=sim_request.initial_investment,
        )

        # ── 4. Build the response ─────────────────────────────────────────
        response = SimulationResponse(
            # Echo input parameters
            ticker=sim_request.ticker,
            period=HISTORICAL_DATA_PERIOD,
            horizon_days=sim_request.horizon_days,
            confidence_level=sim_request.confidence_level,
            num_simulations=sim_request.num_simulations,
            initial_investment=sim_request.initial_investment,
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
            sim_request.ticker,
            engine_result["simulated_var"]["var_pct"] * 100,
            current_price,
        )

        # ── 5. Persist history for authenticated users ────────────────────
        if user.is_authenticated:
            try:
                _supabase.table("simulation_runs").insert({
                    "user_id": user.user_id,
                    "ticker": sim_request.ticker,
                    "horizon_days": sim_request.horizon_days,
                    "confidence_level": sim_request.confidence_level,
                    "num_simulations": sim_request.num_simulations,
                    "initial_investment": sim_request.initial_investment,
                    "var_pct": response.simulated_var.var_pct,
                    "var_dollar": response.simulated_var.var_dollar,
                    "cvar_pct": response.simulated_var.cvar_pct,
                    "cvar_dollar": response.simulated_var.cvar_dollar,
                    "current_price": response.current_price,
                }).execute()
            except Exception as exc:
                # Non-fatal: log and continue — the simulation result is returned regardless
                logger.error("Failed to persist simulation history for user %s: %s", user.user_id, exc)

        return response

    except AuthorizationError as exc:
        logger.warning("Tier limit exceeded: %s", exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

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
        logger.exception("Unexpected error during simulation for %s", sim_request.ticker)
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"An unexpected error occurred: {exc}",
                "error_code": "INTERNAL_ERROR",
            },
        )


# ---------------------------------------------------------------------------
# GET /api/user/tier
# ---------------------------------------------------------------------------


@router.get(
    "/user/tier",
    response_model=UserTierResponse,
    summary="Get user tier and limits",
)
async def get_user_tier(
    request: Request,
    user: UserContext = Depends(get_current_user)
) -> UserTierResponse:
    """Return the current user's tier, limits, and usage."""
    
    # Defaults for guest
    max_sims_per_hour = GUEST_MAX_SIMULATIONS_PER_HOUR
    max_num_sims = GUEST_MAX_NUM_SIMULATIONS
    max_horizon = GUEST_MAX_HORIZON_DAYS

    if user.is_authenticated:
        max_sims_per_hour = AUTH_MAX_SIMULATIONS_PER_HOUR
        max_num_sims = AUTH_MAX_NUM_SIMULATIONS
        max_horizon = AUTH_MAX_HORIZON_DAYS

    # Count usage in the last hour
    sims_this_hour = 0
    try:
        if user.is_authenticated:
            # Query by user_id
            response = _supabase.table("usage_counts") \
                .select("id", count="exact") \
                .eq("user_id", user.user_id) \
                .gte("created_at", "now() - interval '1 hour'") \
                .execute()
            sims_this_hour = response.count if response.count is not None else 0
        else:
            # Query by IP
            ip = request.client.host if request.client else "unknown"
            response = _supabase.table("usage_counts") \
                .select("id", count="exact") \
                .eq("ip_address", ip) \
                .is_("user_id", "null") \
                .gte("created_at", "now() - interval '1 hour'") \
                .execute()
            sims_this_hour = response.count if response.count is not None else 0
    except Exception as exc:
        logger.warning("Failed to fetch usage count: %s", exc)

    return UserTierResponse(
        tier=user.tier,
        limits=TierLimits(
            max_simulations_per_hour=max_sims_per_hour,
            max_num_simulations=max_num_sims,
            max_horizon_days=max_horizon,
        ),
        usage=TierUsage(
            simulations_this_hour=sims_this_hour,
            max_per_hour=max_sims_per_hour,
        )
    )


# ---------------------------------------------------------------------------
# GET /api/user/history
# ---------------------------------------------------------------------------


@router.get(
    "/user/history",
    response_model=SimulationHistoryResponse,
    summary="Get user simulation history",
)
async def get_user_history(
    user: UserContext = Depends(require_auth)
) -> SimulationHistoryResponse:
    """Return the current authenticated user's simulation history."""
    try:
        response = _supabase.table("simulation_runs") \
            .select("*") \
            .eq("user_id", user.user_id) \
            .order("created_at", desc=True) \
            .limit(20) \
            .execute()
        
        return SimulationHistoryResponse(
            runs=response.data,
            total=len(response.data)
        )
    except Exception as exc:
        logger.error("Failed to fetch history for user %s: %s", user.user_id, exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Failed to fetch simulation history.",
                "error_code": "INTERNAL_ERROR",
            },
        )