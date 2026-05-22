"""
Quant Engine — Bootstrap Monte Carlo Simulation Module

Adapted from the Quant Developer's Proof_of_Concept(3).ipynb notebook.

Methodology
-----------
Uses **bootstrap resampling** (random draws with replacement from historical
returns) instead of Geometric Brownian Motion (GBM).  This approach:
  - Preserves fat tails and skewness from the empirical distribution
  - Makes no distributional assumptions (no normality requirement)
  - Naturally captures volatility clustering present in real market data

Interface contract (see docs/api-contracts.md § 6):
    run_simulation(log_returns, num_simulations, horizon_days,
                   confidence_level, initial_investment) -> dict

Utility (preserved from notebook, not part of the API contract):
    backtest_var(returns, var_threshold, confidence_level) -> dict
"""

import logging

import numpy as np
from scipy import stats as scipy_stats

from exceptions import SimulationError

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Max number of simulation paths included in the API response payload.
# All num_simulations paths are used for VaR/CVaR math; only this many
# are serialised to JSON to keep the payload manageable (~200 KB).
_SAMPLE_PATH_COUNT: int = 100

# Number of bins for the final-values histogram.
_HISTOGRAM_BINS: int = 50

# Annualisation factor (trading days per year).
_TRADING_DAYS_PER_YEAR: int = 252


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------


def run_simulation(
    log_returns: np.ndarray,
    num_simulations: int,
    horizon_days: int,
    confidence_level: float,
    initial_investment: float,
) -> dict:
    """
    Run a bootstrap Monte Carlo VaR simulation.

    Parameters
    ----------
    log_returns : np.ndarray
        1-D array of historical daily log returns (preprocessed, no NaN).
        Produced by ``data_service.preprocess_data()``.
    num_simulations : int
        Number of Monte Carlo paths to generate (100–100,000).
    horizon_days : int
        Number of trading days to simulate forward (1–252).
    confidence_level : float
        VaR confidence level as a percentage (e.g. 95.0 means 95th
        percentile worst-case loss).
    initial_investment : float
        Starting portfolio value in USD.

    Returns
    -------
    dict
        Nested dictionary matching the API contract structure::

            {
                "statistics":             { ... },
                "historical_var":         { "var_pct", "var_dollar" },
                "simulated_var":          { "var_pct", "var_dollar",
                                            "cvar_pct", "cvar_dollar" },
                "simulation_paths":       { "sample_count", "days", "paths" },
                "final_values_histogram": { "bin_edges", "counts" },
            }

    Raises
    ------
    SimulationError
        If the simulation encounters a numerical error (e.g. all-NaN
        returns, empty input array, overflow).
    """
    try:
        return _run_simulation_inner(
            log_returns, num_simulations, horizon_days,
            confidence_level, initial_investment,
        )
    except SimulationError:
        # Re-raise domain errors as-is.
        raise
    except Exception as exc:
        logger.error(
            "Unexpected error during simulation: %s", exc, exc_info=True,
        )
        raise SimulationError(
            f"Monte Carlo simulation failed unexpectedly: {exc}"
        ) from exc


def _run_simulation_inner(
    log_returns: np.ndarray,
    num_simulations: int,
    horizon_days: int,
    confidence_level: float,
    initial_investment: float,
) -> dict:
    """Core simulation logic, separated for clean error handling."""

    # ── 0. Input validation ───────────────────────────────────────────────
    if log_returns is None or len(log_returns) == 0:
        raise SimulationError(
            "Cannot run simulation: the log-returns array is empty."
        )

    rng = np.random.default_rng()

    # Convert log returns → simple returns for bootstrap sampling.
    # Bootstrap draws from empirical simple returns to preserve the
    # exact distributional shape (fat tails, skew) of the observed data.
    simple_returns: np.ndarray = np.exp(log_returns) - 1.0

    # VaR tail probability: e.g. 95% confidence → alpha = 5 (percentile)
    alpha: float = 100.0 - confidence_level

    logger.info(
        "Running bootstrap MC: %d sims × %d days, confidence=%.1f%%, "
        "investment=$%,.0f, history=%d obs.",
        num_simulations, horizon_days, confidence_level,
        initial_investment, len(log_returns),
    )

    # ── 1. Descriptive statistics (from log returns) ──────────────────────
    mean_daily: float = float(np.mean(log_returns))
    std_daily: float = float(np.std(log_returns, ddof=1))
    ann_return: float = mean_daily * _TRADING_DAYS_PER_YEAR
    ann_vol: float = std_daily * np.sqrt(_TRADING_DAYS_PER_YEAR)
    skewness: float = float(scipy_stats.skew(log_returns))
    kurtosis: float = float(scipy_stats.kurtosis(log_returns))  # excess

    # ── 2. Historical VaR (daily, from simple returns) ────────────────────
    # Uses simple returns because var_dollar = var_pct × investment
    # must reflect actual portfolio loss, not log-space loss.
    hist_var_pct: float = float(np.percentile(simple_returns, alpha))
    hist_var_dollar: float = hist_var_pct * initial_investment

    # ── 3. Bootstrap Monte Carlo ──────────────────────────────────────────
    # Draw daily returns with replacement from the empirical distribution.
    # Shape: (num_simulations, horizon_days)
    simulated_daily: np.ndarray = rng.choice(
        simple_returns,
        size=(num_simulations, horizon_days),
        replace=True,
    )

    # Portfolio value paths: P_t = P_0 × ∏(1 + r_i)
    cumulative: np.ndarray = (1.0 + simulated_daily).cumprod(axis=1)
    portfolio_paths: np.ndarray = initial_investment * cumulative

    # Prepend day-0 column (all paths start at initial_investment)
    day_zero: np.ndarray = np.full((num_simulations, 1), initial_investment)
    full_paths: np.ndarray = np.hstack([day_zero, portfolio_paths])

    # ── 4. Simulated (horizon) VaR & CVaR ─────────────────────────────────
    final_values: np.ndarray = full_paths[:, -1]
    horizon_returns: np.ndarray = (
        (final_values - initial_investment) / initial_investment
    )

    sim_var_pct: float = float(np.percentile(horizon_returns, alpha))
    sim_var_dollar: float = sim_var_pct * initial_investment

    # CVaR (Expected Shortfall): average loss in the worst-alpha% of outcomes
    tail: np.ndarray = horizon_returns[horizon_returns <= sim_var_pct]
    sim_cvar_pct: float = float(tail.mean()) if len(tail) > 0 else sim_var_pct
    sim_cvar_dollar: float = sim_cvar_pct * initial_investment

    # ── 5. Sample paths for the frontend chart ────────────────────────────
    sample_count: int = min(_SAMPLE_PATH_COUNT, num_simulations)
    sample_indices: np.ndarray = rng.choice(
        num_simulations, size=sample_count, replace=False,
    )
    sampled_paths: np.ndarray = full_paths[sample_indices]

    # Day indices: [0, 1, 2, ..., horizon_days]
    days: list[int] = list(range(horizon_days + 1))

    # ── 6. Histogram of final portfolio values ────────────────────────────
    counts_arr, edges_arr = np.histogram(final_values, bins=_HISTOGRAM_BINS)

    # ── 7. Assemble response dict ─────────────────────────────────────────
    result: dict = {
        "statistics": {
            "mean_daily_return": round(mean_daily, 8),
            "std_daily_return": round(std_daily, 8),
            "annualized_return": round(ann_return, 6),
            "annualized_volatility": round(ann_vol, 6),
            "skewness": round(skewness, 4),
            "kurtosis": round(kurtosis, 4),
        },
        "historical_var": {
            "var_pct": round(hist_var_pct, 6),
            "var_dollar": round(hist_var_dollar, 2),
        },
        "simulated_var": {
            "var_pct": round(sim_var_pct, 6),
            "var_dollar": round(sim_var_dollar, 2),
            "cvar_pct": round(sim_cvar_pct, 6),
            "cvar_dollar": round(sim_cvar_dollar, 2),
        },
        "simulation_paths": {
            "sample_count": sample_count,
            "days": days,
            "paths": sampled_paths.round(2).tolist(),
        },
        "final_values_histogram": {
            "bin_edges": edges_arr.round(2).tolist(),
            "counts": counts_arr.tolist(),
        },
    }

    logger.info(
        "Simulation complete. Hist VaR=%.4f%%, MC VaR=%.4f%%, "
        "MC CVaR=%.4f%%, final-value mean=$%,.0f.",
        hist_var_pct * 100, sim_var_pct * 100,
        sim_cvar_pct * 100, float(final_values.mean()),
    )

    return result


# ---------------------------------------------------------------------------
# Utility — Backtest (not part of the API contract, preserved for future use)
# ---------------------------------------------------------------------------


def backtest_var(
    returns: np.ndarray,
    var_threshold: float,
    confidence_level: float = 95.0,
) -> dict:
    """
    Check how often historical returns actually breached the VaR threshold.

    Significant deviation between the actual breach rate and the expected
    rate (1 - confidence_level/100) suggests model mis-calibration.

    Preserved from the Quant Developer's notebook for internal validation
    and potential future ``/api/backtest`` endpoint.

    Parameters
    ----------
    returns : np.ndarray
        1-D array of historical simple returns.
    var_threshold : float
        The VaR value to test against (e.g. the hist_var_95 percentile).
    confidence_level : float
        Confidence level used to compute the VaR (default 95.0).

    Returns
    -------
    dict
        ``{"n", "breaches", "actual_rate", "expected_rate", "is_calibrated"}``
        where ``is_calibrated`` is True if actual_rate ≤ 2 × expected_rate.
    """
    n: int = len(returns)
    breaches: int = int((returns < var_threshold).sum())
    expected_rate: float = (100.0 - confidence_level) / 100.0
    actual_rate: float = breaches / n if n > 0 else 0.0

    return {
        "n": n,
        "breaches": breaches,
        "actual_rate": round(actual_rate, 6),
        "expected_rate": expected_rate,
        "is_calibrated": actual_rate <= expected_rate * 2.0,
    }
