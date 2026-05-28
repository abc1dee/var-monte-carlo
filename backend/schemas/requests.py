"""
Pydantic v2 request models for the VaR Monte Carlo API.

These models define the shape and validation rules for all incoming request bodies.
They must stay in sync with the API contract in docs/api-contracts.md.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Annotated


class SimulationRequest(BaseModel):
    """
    Request body for POST /api/simulate.

    Accepts both predefined tickers (from config.ALLOWED_TICKERS) and any
    custom ticker symbol that is valid in yfinance. Ticker validation against
    yfinance happens in the service layer, not here — this model only enforces
    types, ranges, and basic string hygiene.
    """

    ticker: Annotated[
        str,
        Field(
            pattern=r"^[A-Z0-9.\-]{1,20}$",
            description="Stock ticker symbol. Can be a predefined ticker (AAPL, SPY, etc.) "
                        "or any valid yfinance symbol (e.g. NVDA, BRK-B).",
            examples=["AAPL", "NVDA", "SPY"],
        ),
    ]

    horizon_days: Annotated[
        int,
        Field(
            ge=1,
            le=252,
            description="Number of trading days to simulate forward. "
                        "Must be between 1 and 252 (one trading year).",
            examples=[30, 60, 252],
        ),
    ]

    confidence_level: Annotated[
        float,
        Field(
            default=95.0,
            ge=80.0,
            le=99.9,
            description="VaR confidence level as a percentage. "
                        "E.g. 95.0 means the 95th-percentile worst-case loss. "
                        "Must be between 80.0 and 99.9.",
            examples=[90.0, 95.0, 99.0],
        ),
    ] = 95.0

    num_simulations: Annotated[
        int,
        Field(
            default=10_000,
            ge=100,
            le=100_000,
            description="Number of Monte Carlo paths to generate. "
                        "Higher values increase accuracy but also computation time. "
                        "Must be between 100 and 100,000.",
            examples=[1_000, 10_000, 100_000],
        ),
    ] = 10_000

    initial_investment: Annotated[
        float,
        Field(
            default=100_000.0,
            gt=0,
            description="Starting portfolio value in USD. Must be greater than 0.",
            examples=[10_000.0, 100_000.0, 1_000_000.0],
        ),
    ] = 100_000.0

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, v: str) -> str:
        """Strip whitespace and uppercase the ticker symbol."""
        if not isinstance(v, str):
            raise ValueError("ticker must be a string")
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("ticker cannot be empty")
        if len(cleaned) > 20:
            raise ValueError("ticker symbol is too long (max 20 characters)")
        return cleaned

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ticker": "AAPL",
                    "horizon_days": 30,
                    "confidence_level": 95.0,
                    "num_simulations": 10000,
                    "initial_investment": 100000.0,
                }
            ]
        }
    }