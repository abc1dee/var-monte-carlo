"""
Data service — yfinance fetching, preprocessing, and in-memory caching.

Responsibilities
----------------
- fetch_historical_data : Download adjusted-close prices from Yahoo Finance.
- preprocess_data       : Compute log returns and extract the current price.
- validate_ticker       : Lightweight existence check for a custom ticker symbol.

Caching
-------
Responses from yfinance are stored in a module-level dict keyed by
``(ticker, period)``.  Each entry is timestamped; entries older than
CACHE_TTL_SECONDS (default: 15 minutes) are evicted on the next read.
This avoids hitting Yahoo Finance repeatedly during a single demo session
and makes the service more resilient to transient network hiccups.

The cache is process-local (no Redis / external store required for v1).
It is intentionally NOT thread-safe with locks — FastAPI runs on a single
event-loop thread for async handlers, and the CPU-bound simulation is
called synchronously, so a simple dict is sufficient.

Error hierarchy
---------------
InvalidTickerError  (400) — symbol not found in Yahoo Finance
DataFetchError      (503) — network failure or empty payload from yfinance
"""

import logging
import time
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

from exceptions import DataFetchError, InvalidTickerError

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache configuration
# ---------------------------------------------------------------------------

CACHE_TTL_SECONDS: int = 15 * 60  # 15 minutes

# Cache entry shape: { (ticker, period): {"data": pd.DataFrame, "ts": float} }
_price_cache: dict[tuple[str, str], dict] = {}


# ---------------------------------------------------------------------------
# Internal cache helpers
# ---------------------------------------------------------------------------


def _cache_get(ticker: str, period: str) -> Optional[pd.DataFrame]:
    """
    Return cached price DataFrame if it exists and is still fresh.
    Returns None on a cache miss or a stale entry (which is then evicted).
    """
    key = (ticker, period)
    entry = _price_cache.get(key)
    if entry is None:
        return None

    age = time.monotonic() - entry["ts"]
    if age > CACHE_TTL_SECONDS:
        logger.debug(
            "Cache STALE for %s/%s (age=%.0fs, TTL=%ds) — evicting.",
            ticker, period, age, CACHE_TTL_SECONDS,
        )
        del _price_cache[key]
        return None

    logger.debug(
        "Cache HIT for %s/%s (age=%.0fs remaining=%.0fs).",
        ticker, period, age, CACHE_TTL_SECONDS - age,
    )
    return entry["data"]


def _cache_set(ticker: str, period: str, data: pd.DataFrame) -> None:
    """Store a price DataFrame in the cache with the current timestamp."""
    _price_cache[(ticker, period)] = {"data": data, "ts": time.monotonic()}
    logger.debug("Cache SET for %s/%s (%d rows).", ticker, period, len(data))


def get_cache_stats() -> dict:
    """
    Return diagnostic information about the current cache state.
    Useful for a future /api/admin/cache-stats endpoint or health checks.
    """
    now = time.monotonic()
    entries = []
    for (ticker, period), entry in _price_cache.items():
        age = now - entry["ts"]
        entries.append(
            {
                "ticker": ticker,
                "period": period,
                "rows": len(entry["data"]),
                "age_seconds": round(age, 1),
                "expires_in_seconds": max(0.0, round(CACHE_TTL_SECONDS - age, 1)),
            }
        )
    return {"entry_count": len(entries), "entries": entries}


def clear_cache() -> int:
    """
    Evict all cached entries.  Returns the number of entries cleared.
    Intended for testing and future admin endpoints.
    """
    count = len(_price_cache)
    _price_cache.clear()
    logger.info("Cache manually cleared (%d entries removed).", count)
    return count


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def fetch_historical_data(ticker: str, period: str = "1y") -> pd.DataFrame:
    """
    Download adjusted close prices from Yahoo Finance for the given ticker.

    Parameters
    ----------
    ticker : str
        A valid, normalised (uppercased) ticker symbol, e.g. ``"AAPL"``.
    period : str
        yfinance period string.  Valid values: ``"1d"``, ``"5d"``, ``"1mo"``,
        ``"3mo"``, ``"6mo"``, ``"1y"``, ``"2y"``, ``"5y"``, ``"10y"``, ``"ytd"``, ``"max"``.
        Defaults to ``"1y"`` as per the API contract.

    Returns
    -------
    pd.DataFrame
        Single-column DataFrame with a DatetimeIndex and an ``"Adj Close"``
        (or ``"Close"`` fallback) column containing float64 prices.
        Guaranteed to have at least 30 rows (trading days) so that the
        simulation has meaningful input data.

    Raises
    ------
    InvalidTickerError
        If Yahoo Finance returns no data for the symbol.  This covers both
        completely unknown symbols and valid symbols with no data for the
        requested period.
    DataFetchError
        If the network call to Yahoo Finance fails (timeout, DNS error, etc.)
        or if the returned DataFrame is missing the expected price column.
    """
    # ── 1. Cache check ────────────────────────────────────────────────────
    cached = _cache_get(ticker, period)
    if cached is not None:
        return cached

    logger.info("Fetching %s data from yfinance (period=%s).", ticker, period)

    # ── 2. Network call ───────────────────────────────────────────────────
    try:
        raw: pd.DataFrame = yf.download(
            tickers=ticker,
            period=period,
            auto_adjust=True,   # Use split/dividend-adjusted prices
            progress=False,     # Suppress yfinance's tqdm progress bar
            threads=False,      # Single-threaded; we handle concurrency via FastAPI
        )
    except Exception as exc:
        logger.error(
            "yfinance network error for %s: %s", ticker, exc, exc_info=True
        )
        raise DataFetchError(
            f"Failed to reach Yahoo Finance while fetching '{ticker}'. "
            f"Please try again in a moment."
        ) from exc

    # ── 3. Empty-response check ───────────────────────────────────────────
    if raw is None or raw.empty:
        logger.warning("yfinance returned empty DataFrame for ticker '%s'.", ticker)
        raise InvalidTickerError(
            f"No historical data found for ticker '{ticker}'. "
            f"Verify the symbol is correct and has trading history."
        )

    # ── 4. Isolate the price column ───────────────────────────────────────
    # yfinance with auto_adjust=True returns "Close" (adjusted).
    # We also accept "Adj Close" for safety.
    if "Close" in raw.columns:
        prices: pd.DataFrame = raw[["Close"]].rename(columns={"Close": "Adj Close"})
    elif "Adj Close" in raw.columns:
        prices = raw[["Adj Close"]]
    else:
        logger.error(
            "yfinance response for '%s' has unexpected columns: %s",
            ticker, list(raw.columns),
        )
        raise DataFetchError(
            f"Yahoo Finance returned unexpected data format for '{ticker}'. "
            f"The expected price column was not found."
        )

    # ── 5. Handle MultiIndex columns (yfinance quirk for single tickers) ──
    # yfinance sometimes returns a MultiIndex like ("Adj Close", "AAPL").
    # Flatten to a plain Index so downstream code works uniformly.
    if isinstance(prices.columns, pd.MultiIndex):
        prices.columns = prices.columns.get_level_values(0)

    # ── 6. Drop rows with missing prices ─────────────────────────────────
    before_drop = len(prices)
    prices = prices.dropna()
    dropped = before_drop - len(prices)
    if dropped:
        logger.debug("Dropped %d NaN rows from %s price series.", dropped, ticker)

    # ── 7. Minimum data guard ─────────────────────────────────────────────
    MIN_ROWS = 30
    if len(prices) < MIN_ROWS:
        raise InvalidTickerError(
            f"Ticker '{ticker}' has only {len(prices)} trading days of history "
            f"for the '{period}' period (minimum required: {MIN_ROWS}). "
            f"Try a longer period or a different symbol."
        )

    logger.info(
        "Fetched %d rows for %s (period=%s, range=%s → %s).",
        len(prices), ticker, period,
        prices.index[0].date(), prices.index[-1].date(),
    )

    # ── 8. Cache and return ───────────────────────────────────────────────
    _cache_set(ticker, period, prices)
    return prices


def preprocess_data(prices: pd.DataFrame) -> tuple[np.ndarray, float]:
    """
    Compute daily log returns and extract the most recent closing price.

    Log returns are preferred over simple returns for Monte Carlo simulation
    because they are time-additive and better satisfy the normality assumption
    used by Geometric Brownian Motion.

    Formula: ``r_t = ln(P_t / P_{t-1})``

    Parameters
    ----------
    prices : pd.DataFrame
        Single-column DataFrame as returned by ``fetch_historical_data``.
        Must have an ``"Adj Close"`` column and at least 2 rows.

    Returns
    -------
    log_returns : np.ndarray
        1-D float64 array of daily log returns with NaN rows dropped.
        Length is ``len(prices) - 1``.
    current_price : float
        The most recent adjusted closing price in USD.

    Raises
    ------
    DataFetchError
        If the prices DataFrame is empty or missing the expected column,
        indicating a bug in the upstream data pipeline.
    """
    if prices is None or prices.empty:
        raise DataFetchError(
            "Cannot preprocess an empty price DataFrame. "
            "This is likely a data pipeline bug — please report it."
        )

    col = "Adj Close"
    if col not in prices.columns:
        raise DataFetchError(
            f"Expected column '{col}' not found in price DataFrame. "
            f"Available columns: {list(prices.columns)}"
        )

    price_series: pd.Series = prices[col]

    # Most recent price (used to echo current_price in the API response)
    current_price: float = float(price_series.iloc[-1])

    # Log returns: ln(P_t / P_{t-1})  — produces NaN at index 0
    log_returns: pd.Series = np.log(price_series / price_series.shift(1))
    log_returns = log_returns.dropna()

    returns_array: np.ndarray = log_returns.to_numpy(dtype=np.float64)

    logger.debug(
        "Preprocessed %d prices → %d log returns. "
        "Current price: $%.4f. Mean return: %.6f. Std: %.6f.",
        len(price_series), len(returns_array),
        current_price, returns_array.mean(), returns_array.std(),
    )

    return returns_array, current_price


async def validate_ticker(symbol: str) -> bool:
    """
    Check whether a ticker symbol is recognised by Yahoo Finance.

    Downloads one day of data as a lightweight existence probe.
    Used by ``GET /api/validate-ticker/{symbol}`` and optionally by the
    simulate endpoint to produce a friendlier error before attempting a
    full 1-year data pull.

    Parameters
    ----------
    symbol : str
        Normalised (uppercased, stripped) ticker symbol.

    Returns
    -------
    bool
        ``True`` if Yahoo Finance returns any data for the symbol.
        ``False`` if the symbol is unknown or has no trading history.

    Notes
    -----
    This does **not** raise exceptions — callers interpret the bool.
    Network errors are caught and logged; they return ``False`` so the
    UI shows "invalid ticker" rather than a 503 during validation.
    """
    logger.debug("Validating ticker symbol: %s", symbol)

    try:
        probe: pd.DataFrame = yf.download(
            tickers=symbol,
            period="5d",        # Minimal window — just need any data at all
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        is_valid = probe is not None and not probe.empty
        logger.info(
            "Ticker validation for '%s': %s", symbol, "VALID" if is_valid else "INVALID"
        )
        return is_valid

    except Exception as exc:
        # Network errors during validation are non-fatal — treat as invalid
        # rather than propagating a 503 from a lightweight check.
        logger.warning(
            "Exception during ticker validation for '%s': %s",
            symbol, exc, exc_info=False,
        )
        return False