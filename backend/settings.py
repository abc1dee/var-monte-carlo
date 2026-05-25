"""
settings.py — Environment-driven configuration using pydantic-settings.

Loads secrets and configuration from a `.env` file (or real environment
variables in production).  Validates that all required values are present
at import time — the app crashes immediately if anything is missing,
which is the correct fail-fast behaviour for misconfigured deployments.

Usage::

    from settings import settings
    print(settings.supabase_url)
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings populated from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # If a real env var exists, it takes priority over .env file values.
        extra="ignore",
    )

    # ── Supabase (all required — no defaults) ─────────────────────────────
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    # ── App ───────────────────────────────────────────────────────────────
    environment: str = "development"
    cors_origins: str = "http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse the comma-separated string into a list of origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


# ---------------------------------------------------------------------------
# Module-level singleton — import `settings` everywhere
# ---------------------------------------------------------------------------

settings = Settings()  # type: ignore[call-arg]
