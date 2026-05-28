"""
routers/simulation.py — Route handlers for simulation-related endpoints.

Endpoints
---------
GET  /api/tickers                → List predefined tickers
GET  /api/validate-ticker/{sym}  → Check if a custom ticker exists in yfinance
POST /api/simulate               → Run Monte Carlo VaR simulation
GET  /api/user/tier              → Current user's tier, limits, and usage
GET  /api/user/history           → Authenticated user's simulation history

Architecture note
-----------------
This module is a *thin controller* — it delegates all business logic to the
service layer:

  - ``services.data_service``  : fetching + preprocessing historical data
  - ``services.quant_engine``  : Monte Carlo simulation + VaR calculation
  - ``services.db_service``    : all Supabase reads and writes

Custom domain exceptions (InvalidTickerError, DataFetchError, etc.) are
**not caught here** — they propagate to the global ``AppBaseError`` handler
registered in ``main.py``, keeping each handler focused on the happy path.
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

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
from exceptions import AuthorizationError
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
from services import data_service, db_service, quant_engine
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

    This is a lightweight probe that downloads five days of data.  Returns
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
        400: {"description": "Invalid ticker symbol.", "model": ErrorResponse},
        403: {"description": "Tier limit exceeded.", "model": ErrorResponse},
        503: {"description": "Yahoo Finance is unreachable.", "model": ErrorResponse},
        500: {"description": "Unexpected server error.", "model": ErrorResponse},
    },
)
@limiter.limit(get_dynamic_limit)
async def run_simulation(
    request: Request,
    sim_request: SimulationRequest,
    user: UserContext = Depends(get_current_user),
) -> SimulationResponse:
    """Fetch historical data, run Monte Carlo simulation, and return results.

    **Pipeline:**

    0. Enforce tier limits (guest parameter caps)
    1. Fetch historical prices from Yahoo Finance via ``data_service``
    2. Compute log returns and extract the current price
    3. Run bootstrap Monte Carlo simulation via ``quant_engine``
    4. Assemble and return the structured response
    5. Persist run + usage (non-fatal, handled by ``db_service``)

    Domain exceptions raised by the service layer propagate to the global
    ``AppBaseError`` handler in ``main.py`` — no per-route try/except needed.
    """
    # ── 0. Enforce tier limits ────────────────────────────────────────────
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

    # ── 1. Fetch historical price data ────────────────────────────────────
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

    # ── 2. Preprocess: compute log returns + current price ────────────────
    log_returns, current_price = data_service.preprocess_data(prices)

    # ── 3. Run Monte Carlo simulation ─────────────────────────────────────
    engine_result: dict = quant_engine.run_simulation(
        log_returns=log_returns,
        num_simulations=sim_request.num_simulations,
        horizon_days=sim_request.horizon_days,
        confidence_level=sim_request.confidence_level,
        initial_investment=sim_request.initial_investment,
    )

    # ── 4. Build the response ─────────────────────────────────────────────
    response = SimulationResponse(
        ticker=sim_request.ticker,
        period=HISTORICAL_DATA_PERIOD,
        horizon_days=sim_request.horizon_days,
        confidence_level=sim_request.confidence_level,
        num_simulations=sim_request.num_simulations,
        initial_investment=sim_request.initial_investment,
        current_price=current_price,
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

    # ── 5. Persist — db_service handles all errors internally (non-fatal) ─
    ip = request.client.host if request.client else None
    if user.is_authenticated:
        db_service.save_simulation_run(
            user_id=user.user_id,
            ticker=sim_request.ticker,
            horizon_days=sim_request.horizon_days,
            confidence_level=sim_request.confidence_level,
            num_simulations=sim_request.num_simulations,
            initial_investment=sim_request.initial_investment,
            var_pct=response.simulated_var.var_pct,
            var_dollar=response.simulated_var.var_dollar,
            cvar_pct=response.simulated_var.cvar_pct,
            cvar_dollar=response.simulated_var.cvar_dollar,
            current_price=response.current_price,
        )
        db_service.save_usage_count(user_id=user.user_id, ip=ip)
    else:
        db_service.save_usage_count(user_id=None, ip=ip)

    return response


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
    user: UserContext = Depends(get_current_user),
) -> UserTierResponse:
    """Return the current user's tier, limits, and usage."""
    if user.is_authenticated:
        max_sims_per_hour = AUTH_MAX_SIMULATIONS_PER_HOUR
        max_num_sims = AUTH_MAX_NUM_SIMULATIONS
        max_horizon = AUTH_MAX_HORIZON_DAYS
    else:
        max_sims_per_hour = GUEST_MAX_SIMULATIONS_PER_HOUR
        max_num_sims = GUEST_MAX_NUM_SIMULATIONS
        max_horizon = GUEST_MAX_HORIZON_DAYS

    sims_this_hour = 0
    try:
        ip = request.client.host if request.client else None
        sims_this_hour = db_service.count_usage_last_hour(
            user_id=user.user_id if user.is_authenticated else None,
            ip=ip if not user.is_authenticated else None,
        )
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
        ),
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
    user: UserContext = Depends(require_auth),
) -> SimulationHistoryResponse:
    """Return the current authenticated user's simulation history."""
    try:
        rows = db_service.get_simulation_history(user.user_id)
        logger.info("Fetched %d history rows for user %s.", len(rows), user.user_id)
        return SimulationHistoryResponse(runs=rows, total=len(rows))
    except Exception as exc:
        logger.exception(
            "Failed to fetch history for user %s — %s: %s",
            user.user_id, type(exc).__name__, exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Failed to fetch simulation history.",
                "error_code": "INTERNAL_ERROR",
            },
        )