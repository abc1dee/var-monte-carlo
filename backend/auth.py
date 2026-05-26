"""
auth.py — JWT authentication and user context for Supabase-issued tokens.

Provides two FastAPI dependencies:

``get_current_user``
    Soft auth — returns a ``UserContext`` for both guests and authenticated
    users.  Never rejects a request; unauthenticated callers simply receive
    a guest context with lower tier limits.

``require_auth``
    Hard auth — wraps ``get_current_user`` and raises ``AuthenticationError``
    (HTTP 401) if the caller is not authenticated.  Use for endpoints that
    must never be accessed anonymously (e.g. simulation history).

The JWT is expected in the ``Authorization: Bearer <token>`` header,
issued by Supabase Auth (email/password flow).
"""

import logging
from dataclasses import dataclass, field
from typing import Literal, Optional

from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client

from exceptions import AuthenticationError
from settings import settings

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User context
# ---------------------------------------------------------------------------


@dataclass
class UserContext:
    """
    Represents the current caller's identity and tier.

    For guest (unauthenticated) users, ``user_id`` and ``email`` are None,
    ``is_authenticated`` is False, and ``tier`` is ``"guest"``.
    """

    user_id: Optional[str] = None
    email: Optional[str] = None
    is_authenticated: bool = False
    tier: Literal["guest", "authenticated"] = "guest"


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

_supabase: Client = create_client(settings.supabase_url, settings.supabase_service_role_key)

def decode_supabase_jwt(token: str) -> dict:
    """
    Validate a Supabase-issued JWT using the official Supabase SDK.

    Parameters
    ----------
    token : str
        The raw JWT string (without the "Bearer " prefix).

    Returns
    -------
    dict
        The decoded JWT payload containing ``sub`` and ``email``.

    Raises
    ------
    AuthenticationError
        If the token is expired, malformed, or fails validation.
    """
    try:
        res = _supabase.auth.get_user(token)
        return {
            "sub": res.user.id,
            "email": res.user.email
        }
    except Exception as exc:
        logger.warning("Supabase auth failed: %s", exc)
        raise AuthenticationError(
            "Invalid or expired authentication token."
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserContext:
    """
    Soft-auth dependency — extracts user identity from the Authorization
    header if present.  Returns a guest ``UserContext`` if the header is
    missing or the token is invalid.

    **Never raises an error** — callers always get a ``UserContext``.

    Usage::

        @router.post("/api/simulate")
        async def run_simulation(
            request: SimulationRequest,
            user: UserContext = Depends(get_current_user),
        ):
            ...
    """
    auth_header: Optional[str] = request.headers.get("Authorization")

    # ── No header → guest ─────────────────────────────────────────────────
    if not auth_header:
        logger.debug("No Authorization header — treating as guest.")
        return UserContext()

    # ── Malformed header → guest ──────────────────────────────────────────
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning("Malformed Authorization header — treating as guest.")
        return UserContext()

    # ── Decode JWT ────────────────────────────────────────────────────────
    token = parts[1]
    try:
        payload = decode_supabase_jwt(token)
    except AuthenticationError:
        # Token is present but invalid/expired → treat as guest, not 401.
        # The warning was already logged inside decode_supabase_jwt.
        return UserContext()

    user_id: str = payload.get("sub", "")
    email: Optional[str] = payload.get("email")

    logger.info(
        "Authenticated user: id=%s, email=%s", user_id, email,
    )

    return UserContext(
        user_id=user_id,
        email=email,
        is_authenticated=True,
        tier="authenticated",
    )


async def require_auth(
    user: UserContext = Depends(get_current_user),
) -> UserContext:
    """
    Hard-auth dependency — raises 401 if the caller is not authenticated.

    Use for endpoints that require a logged-in user, such as
    ``GET /api/user/history``.
    """
    if not user.is_authenticated:
        raise AuthenticationError(
            "Authentication required. Please log in to access this resource."
        )
    return user
