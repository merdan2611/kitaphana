"""Application settings, read once from the environment at import time.

Every setting has a safe default so the app starts in a safe configuration with no `.env`
file present at all (see .env.example and ADR-0013 for dev_otp_mode specifically).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _bool_env(name: str, default: bool) -> bool:
    """Parse a boolean env var. Missing or unrecognised values fall back to `default`.

    ADR-0013 requires DEV_OTP_MODE to be off unless explicitly and recognisably turned on,
    so "unparseable" must mean "off", not "crash" or "guess true".
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _int_env(name: str, default: int) -> int:
    """Parse a positive integer env var. Missing, unparseable or non-positive -> `default`."""
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


def _limits_env(name: str, default: str) -> tuple[tuple[int, int], ...]:
    """Parse rate limits written as `count/seconds` pairs, e.g. "3/600,10/86400".

    An unparseable value falls back to the default as a whole rather than silently dropping
    one limit — a typo must never switch a rate limit off.
    """
    def parse(raw: str) -> tuple[tuple[int, int], ...]:
        limits = []
        for part in raw.split(","):
            count, seconds = (int(x) for x in part.strip().split("/"))
            if count <= 0 or seconds <= 0:
                raise ValueError(part)
            limits.append((count, seconds))
        return tuple(limits)

    try:
        return parse(os.environ.get(name, default))
    except ValueError:
        return parse(default)


@dataclass(frozen=True)
class Settings:
    database_path: Path
    media_dir: Path
    secret_key: str
    dev_otp_mode: bool
    debug: bool
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    # (count, window_seconds) pairs; a code request is refused once any one is reached.
    otp_limits_per_phone: tuple[tuple[int, int], ...] = ((3, 600), (10, 86400))
    otp_limits_per_ip: tuple[tuple[int, int], ...] = ((10, 600), (50, 86400))
    session_ttl_days: int = 180
    max_upload_mb: int = 200
    cookie_secure: bool = True
    app_version: str = "0.1.0"


def load_settings() -> Settings:
    return Settings(
        database_path=Path(os.environ.get("DATABASE_PATH", "kitaphana.db")),
        media_dir=Path(os.environ.get("MEDIA_DIR", "media")),
        secret_key=os.environ.get("SECRET_KEY", "dev-insecure-secret-key-change-in-production"),
        dev_otp_mode=_bool_env("DEV_OTP_MODE", default=False),
        debug=_bool_env("DEBUG", default=False),
        otp_ttl_seconds=_int_env("OTP_TTL_SECONDS", 300),
        otp_max_attempts=_int_env("OTP_MAX_ATTEMPTS", 5),
        otp_limits_per_phone=_limits_env("OTP_LIMITS_PER_PHONE", "3/600,10/86400"),
        otp_limits_per_ip=_limits_env("OTP_LIMITS_PER_IP", "10/600,50/86400"),
        session_ttl_days=_int_env("SESSION_TTL_DAYS", 180),
        max_upload_mb=_int_env("MAX_UPLOAD_MB", 200),
        cookie_secure=_bool_env("COOKIE_SECURE", default=True),
    )


settings = load_settings()
