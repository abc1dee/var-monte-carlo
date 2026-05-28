"""
services/db_service.py — Supabase database operations.

Centralises all reads/writes to the Supabase ``public`` schema so that
the router stays a thin controller and database logic can be tested and
extended in isolation.

All write helpers (``save_*``) are **non-fatal** — they catch their own
exceptions and log them, so a DB hiccup never fails the HTTP response.
Read helpers (``get_*``, ``count_*``) propagate exceptions so the caller
can decide whether to surface a 500.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from supabase import create_client, Client

from settings import settings

logger = logging.getLogger(__name__)

# One module-level client shared across all helpers.
_supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key,
)


# ---------------------------------------------------------------------------
# Writes (non-fatal)
# ---------------------------------------------------------------------------


def save_simulation_run(
    *,
    user_id: str,
    ticker: str,
    horizon_days: int,
    confidence_level: float,
    num_simulations: int,
    initial_investment: float,
    var_pct: float,
    var_dollar: float,
    cvar_pct: float,
    cvar_dollar: float,
    current_price: float,
) -> None:
    """Insert one row into ``simulation_runs``. Silently logs on failure."""
    try:
        _supabase.table("simulation_runs").insert({
            "user_id": user_id,
            "ticker": ticker,
            "horizon_days": horizon_days,
            "confidence_level": confidence_level,
            "num_simulations": num_simulations,
            "initial_investment": initial_investment,
            "var_pct": var_pct,
            "var_dollar": var_dollar,
            "cvar_pct": cvar_pct,
            "cvar_dollar": cvar_dollar,
            "current_price": current_price,
        }).execute()
        logger.info("Saved simulation_runs row for user %s.", user_id)
    except Exception as exc:
        logger.error(
            "Failed to persist simulation run for user %s: %s", user_id, exc
        )


def save_usage_count(
    *,
    user_id: Optional[str],
    ip: Optional[str],
) -> None:
    """Insert one row into ``usage_counts``. Silently logs on failure.

    Notes
    -----
    ``ip_address`` is a PostgreSQL ``inet`` column.  Only valid IP strings
    or ``None`` are accepted — never pass the string ``"unknown"``.
    """
    try:
        _supabase.table("usage_counts").insert({
            "user_id": user_id,
            "ip_address": ip,
        }).execute()
        label = f"user {user_id}" if user_id else f"guest IP {ip}"
        logger.info("Saved usage_counts row for %s.", label)
    except Exception as exc:
        logger.error(
            "Failed to persist usage_count (user=%s ip=%s): %s",
            user_id, ip, exc,
        )


# ---------------------------------------------------------------------------
# Reads (propagate exceptions)
# ---------------------------------------------------------------------------


def get_simulation_history(user_id: str, limit: int = 20) -> list[dict]:
    """Return the most-recent simulation runs for *user_id*.

    Raises
    ------
    Exception
        Re-raised from the Supabase client so the route handler can
        return a structured 500 response.
    """
    response = (
        _supabase.table("simulation_runs")
        .select(
            "ticker, horizon_days, confidence_level, num_simulations, "
            "initial_investment, var_pct, var_dollar, cvar_pct, cvar_dollar, "
            "current_price, created_at"
        )
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data


def count_usage_last_hour(
    *,
    user_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> int:
    """Count usage_counts rows in the past rolling hour.

    Keyed by *user_id* for authenticated users or *ip* for guests.
    Returns 0 if neither argument is provided.

    Notes
    -----
    PostgREST treats ``.gte()`` values as literal strings, **not** SQL
    expressions.  The cutoff timestamp must be computed in Python and
    passed as an ISO-8601 string.
    """
    one_hour_ago: str = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).isoformat()

    if user_id:
        result = (
            _supabase.table("usage_counts")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .gte("created_at", one_hour_ago)
            .execute()
        )
    elif ip:
        result = (
            _supabase.table("usage_counts")
            .select("id", count="exact")
            .eq("ip_address", ip)
            .is_("user_id", "null")
            .gte("created_at", one_hour_ago)
            .execute()
        )
    else:
        return 0

    return result.count if result.count is not None else 0
