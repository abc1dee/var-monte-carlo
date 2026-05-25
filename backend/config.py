"""
config.py — Application-wide constants, defaults, and configuration.

All magic numbers and environment-specific values live here.
Both the router and schemas import from this module — never hardcode
limits or defaults in multiple places.
"""

from typing import TypedDict

from settings import settings


# ---------------------------------------------------------------------------
# Ticker Registry
# ---------------------------------------------------------------------------

class TickerInfo(TypedDict):
    symbol: str
    name: str
    sector: str


ALLOWED_TICKERS: list[TickerInfo] = [
    {"symbol": "AAPL",  "name": "Apple Inc.",              "sector": "Technology"},
    {"symbol": "AMD",   "name": "Advanced Micro Devices",  "sector": "Technology"},
    {"symbol": "SPY",   "name": "S&P 500 ETF",             "sector": "Index Fund"},
    {"symbol": "TSLA",  "name": "Tesla Inc.",               "sector": "Automotive"},
    {"symbol": "MSFT",  "name": "Microsoft Corp.",          "sector": "Technology"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.",            "sector": "Technology"},
]

# Quick lookup set for O(1) validation checks
ALLOWED_TICKER_SYMBOLS: frozenset[str] = frozenset(
    t["symbol"] for t in ALLOWED_TICKERS
)


# ---------------------------------------------------------------------------
# Simulation Parameter Defaults
# ---------------------------------------------------------------------------

DEFAULT_CONFIDENCE_LEVEL: float = 95.0
DEFAULT_NUM_SIMULATIONS: int = 10_000
DEFAULT_INITIAL_INVESTMENT: float = 100_000.0

# How many years of historical data to pull from yfinance
HISTORICAL_DATA_PERIOD: str = "1y"

# Number of simulation paths returned in the API response
# (full num_simulations are used for VaR math; only this many are sent to FE)
SIMULATION_PATH_SAMPLE_COUNT: int = 100


# ---------------------------------------------------------------------------
# Validation Limits  (mirrors api-contracts.md § 4 Request Body table)
# ---------------------------------------------------------------------------

HORIZON_DAYS_MIN: int = 1
HORIZON_DAYS_MAX: int = 252          # ~1 trading year

CONFIDENCE_LEVEL_MIN: float = 80.0
CONFIDENCE_LEVEL_MAX: float = 99.9

NUM_SIMULATIONS_MIN: int = 100
NUM_SIMULATIONS_MAX: int = 100_000

INITIAL_INVESTMENT_MIN: float = 0.0  # exclusive — validated as > 0


# ---------------------------------------------------------------------------
# API Metadata
# ---------------------------------------------------------------------------

API_TITLE: str = "VaR Monte Carlo API"
API_DESCRIPTION: str = (
    "Estimates potential investment losses via Value-at-Risk (VaR) "
    "computed with Monte Carlo simulations over historical stock data."
)
API_VERSION: str = "1.0.0"


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

# Loaded from CORS_ORIGINS env var (comma-separated) via pydantic-settings.
# In production, set CORS_ORIGINS to the deployed frontend URL.
CORS_ALLOWED_ORIGINS: list[str] = settings.cors_origins_list


# ---------------------------------------------------------------------------
# User Tier Limits  (provisional — subject to team's final decision)
# ---------------------------------------------------------------------------
#
# All tier-specific caps are defined here as named constants so they can be
# changed in one place without touching business logic in the router.

# Simulation runs allowed per rolling 1-hour window
GUEST_MAX_SIMULATIONS_PER_HOUR: int = 3
AUTH_MAX_SIMULATIONS_PER_HOUR: int = 20

# Maximum num_simulations parameter value
GUEST_MAX_NUM_SIMULATIONS: int = 1_000
AUTH_MAX_NUM_SIMULATIONS: int = 100_000

# Maximum horizon_days parameter value
GUEST_MAX_HORIZON_DAYS: int = 30
AUTH_MAX_HORIZON_DAYS: int = 252