"""
Pydantic v2 response models for the VaR Monte Carlo API.

Every model here maps 1-to-1 to a JSON shape defined in docs/api-contracts.md.
The frontend TypeScript interfaces are built against the same contract, so field
names, types, and nesting must never be changed unilaterally.

Change process: propose → both sides agree → update api-contracts.md → update
this file AND src/types/api.ts in the same commit.
"""

from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Shared / utility responses
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Response for GET /api/health."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "1.0.0",
            }
        }
    )

    status: str = Field(description="Always 'healthy' when the server is running.")
    version: str = Field(description="API version string.")


class ErrorResponse(BaseModel):
    """
    Structured error body returned for 400, 500, and 503 responses.

    Note: 422 validation errors use FastAPI's default format, not this model.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "Ticker 'XYZFAKE' is not a valid stock symbol.",
                "error_code": "INVALID_TICKER",
            }
        }
    )

    detail: str = Field(description="Human-readable description of the error.")
    error_code: str = Field(
        description=(
            "Machine-readable error code. "
            "One of: INVALID_TICKER, INVALID_PARAMS, "
            "DATA_SOURCE_UNAVAILABLE, INTERNAL_ERROR."
        )
    )


# ---------------------------------------------------------------------------
# Ticker-related responses
# ---------------------------------------------------------------------------


class TickerInfo(BaseModel):
    """A single ticker entry returned by GET /api/tickers."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "sector": "Technology",
            }
        }
    )

    symbol: str = Field(description="The ticker symbol (e.g. 'AAPL').")
    name: str = Field(description="Full company or fund name.")
    sector: str = Field(description="Market sector (e.g. 'Technology').")


class TickersResponse(BaseModel):
    """Response for GET /api/tickers."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tickers": [
                    {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Technology"},
                    {"symbol": "AMD", "name": "Advanced Micro Devices", "sector": "Technology"},
                    {"symbol": "SPY", "name": "S&P 500 ETF", "sector": "Index Fund"},
                    {"symbol": "TSLA", "name": "Tesla Inc.", "sector": "Automotive"},
                    {"symbol": "MSFT", "name": "Microsoft Corp.", "sector": "Technology"},
                    {"symbol": "GOOGL", "name": "Alphabet Inc.", "sector": "Technology"},
                ]
            }
        }
    )

    tickers: list[TickerInfo] = Field(
        description="List of predefined tickers available for simulation."
    )


class ValidateTickerResponse(BaseModel):
    """Response for GET /api/validate-ticker/{symbol}."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "valid": True,
                "symbol": "NVDA",
            }
        }
    )

    valid: bool = Field(
        description="True if the symbol is recognised by yfinance, False otherwise."
    )
    symbol: str = Field(
        description="The normalised (uppercased) symbol that was checked."
    )


# ---------------------------------------------------------------------------
# Simulation response — nested sub-models
# ---------------------------------------------------------------------------


class Statistics(BaseModel):
    """
    Descriptive statistics computed from the historical log-return series.
    All return figures are expressed as decimals (e.g. 0.00085, not 0.085%).
    Annualised figures assume 252 trading days per year.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mean_daily_return": 0.00085,
                "std_daily_return": 0.0167,
                "annualized_return": 0.2142,
                "annualized_volatility": 0.2651,
                "skewness": -0.34,
                "kurtosis": 4.21,
            }
        }
    )

    mean_daily_return: float = Field(
        description="Mean of the daily log-return series (decimal)."
    )
    std_daily_return: float = Field(
        description="Standard deviation of the daily log-return series (decimal)."
    )
    annualized_return: float = Field(
        description="Annualised return: mean_daily_return × 252 (decimal)."
    )
    annualized_volatility: float = Field(
        description="Annualised volatility: std_daily_return × √252 (decimal)."
    )
    skewness: float = Field(
        description="Skewness of the daily log-return distribution."
    )
    kurtosis: float = Field(
        description="Excess kurtosis of the daily log-return distribution."
    )


class HistoricalVarResult(BaseModel):
    """
    VaR calculated directly from the historical return series
    using np.percentile at the (1 - confidence_level) tail.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "var_pct": -0.0312,
                "var_dollar": -3120.0,
            }
        }
    )

    var_pct: float = Field(
        description=(
            "Historical VaR as a decimal return (negative = loss). "
            "E.g. -0.0312 means a 3.12% loss at the given confidence level."
        )
    )
    var_dollar: float = Field(
        description=(
            "Historical VaR in USD: var_pct × initial_investment. "
            "E.g. -3120.0 for a $100,000 portfolio."
        )
    )


class SimulatedVarResult(BaseModel):
    """
    VaR and CVaR (Expected Shortfall) derived from the Monte Carlo simulation.
    All N simulated paths are used for this calculation.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "var_pct": -0.0487,
                "var_dollar": -4870.0,
                "cvar_pct": -0.0723,
                "cvar_dollar": -7230.0,
            }
        }
    )

    var_pct: float = Field(
        description="Simulated VaR as a decimal return (negative = loss)."
    )
    var_dollar: float = Field(
        description="Simulated VaR in USD."
    )
    cvar_pct: float = Field(
        description=(
            "Conditional VaR (Expected Shortfall) as a decimal return. "
            "The average loss in the worst (1 - confidence_level)% of outcomes."
        )
    )
    cvar_dollar: float = Field(
        description="Conditional VaR in USD."
    )


class SimulationPaths(BaseModel):
    """
    A representative sample of simulated portfolio-value paths.

    Only 100 paths are returned (regardless of num_simulations) to keep the
    JSON payload manageable (~200 KB vs ~20 MB for 10,000 paths). The VaR/CVaR
    metrics are computed from the full simulation before sampling.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sample_count": 100,
                "days": [0, 1, 2, 3],
                "paths": [
                    [100000.0, 100234.0, 99870.0, 101200.0],
                    [100000.0, 99812.0, 100456.0, 100988.0],
                ],
            }
        }
    )

    sample_count: int = Field(
        description=(
            "Number of paths in this payload. Always 100 (or fewer if "
            "num_simulations < 100)."
        )
    )
    days: list[int] = Field(
        description=(
            "Day indices for each column in `paths`. "
            "Always starts at 0 and ends at horizon_days."
        )
    )
    paths: list[list[float]] = Field(
        description=(
            "2-D array of portfolio values. "
            "Outer list = paths (length = sample_count), "
            "inner list = portfolio value at each day (length = len(days))."
        )
    )


class Histogram(BaseModel):
    """
    Frequency distribution of simulated portfolio values at the end of the horizon.
    Suitable for rendering directly with Plotly's bar/histogram trace.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "bin_edges": [85000.0, 87000.0, 89000.0, 91000.0],
                "counts": [12, 34, 67],
            }
        }
    )

    bin_edges: list[float] = Field(
        description=(
            "Left edges of each histogram bin, in USD. "
            "Length is len(counts) + 1 (numpy convention)."
        )
    )
    counts: list[int] = Field(
        description=(
            "Number of simulated paths whose final value falls in each bin."
        )
    )


# ---------------------------------------------------------------------------
# Top-level simulation response
# ---------------------------------------------------------------------------


class SimulationResponse(BaseModel):
    """
    Full response for POST /api/simulate.

    Mirrors the TypeScript SimulationResponse interface in src/types/api.ts.
    Do not rename or reorder fields without updating the API contract.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ticker": "AAPL",
                "period": "1y",
                "horizon_days": 30,
                "confidence_level": 95.0,
                "num_simulations": 10000,
                "initial_investment": 100000.0,
                "current_price": 198.45,
                "statistics": {
                    "mean_daily_return": 0.00085,
                    "std_daily_return": 0.0167,
                    "annualized_return": 0.2142,
                    "annualized_volatility": 0.2651,
                    "skewness": -0.34,
                    "kurtosis": 4.21,
                },
                "historical_var": {
                    "var_pct": -0.0312,
                    "var_dollar": -3120.0,
                },
                "simulated_var": {
                    "var_pct": -0.0487,
                    "var_dollar": -4870.0,
                    "cvar_pct": -0.0723,
                    "cvar_dollar": -7230.0,
                },
                "simulation_paths": {
                    "sample_count": 2,
                    "days": [0, 1, 2, 3],
                    "paths": [
                        [100000.0, 100234.0, 99870.0, 101200.0],
                        [100000.0, 99812.0, 100456.0, 100988.0],
                    ],
                },
                "final_values_histogram": {
                    "bin_edges": [85000.0, 87000.0, 89000.0, 91000.0],
                    "counts": [12, 34, 67],
                },
            }
        }
    )

    # --- Echo of input parameters ---
    ticker: str = Field(
        description="The normalised ticker symbol used for the simulation."
    )
    period: str = Field(
        description="Historical data window fetched from yfinance. Always '1y' in v1."
    )
    horizon_days: int = Field(
        description="Number of trading days simulated forward."
    )
    confidence_level: float = Field(
        description="VaR confidence level (e.g. 95.0)."
    )
    num_simulations: int = Field(
        description="Total number of Monte Carlo paths generated."
    )
    initial_investment: float = Field(
        description="Starting portfolio value in USD."
    )
    current_price: float = Field(
        description="Most recent closing price of the ticker, in USD."
    )

    # --- Results ---
    statistics: Statistics = Field(
        description="Descriptive statistics from the historical return series."
    )
    historical_var: HistoricalVarResult = Field(
        description="VaR calculated directly from historical returns."
    )
    simulated_var: SimulatedVarResult = Field(
        description="VaR and CVaR derived from the Monte Carlo simulation."
    )
    simulation_paths: SimulationPaths = Field(
        description="Sampled simulation paths for chart rendering (max 100 paths)."
    )
    final_values_histogram: Histogram = Field(
        description="Distribution of final portfolio values across all simulated paths."
    )