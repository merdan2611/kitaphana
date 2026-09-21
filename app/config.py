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


@dataclass(frozen=True)
class Settings:
    database_path: Path
    media_dir: Path
    secret_key: str
    dev_otp_mode: bool
    debug: bool
    app_version: str = "0.1.0"


def load_settings() -> Settings:
    return Settings(
        database_path=Path(os.environ.get("DATABASE_PATH", "kitaphana.db")),
        media_dir=Path(os.environ.get("MEDIA_DIR", "media")),
        secret_key=os.environ.get("SECRET_KEY", "dev-insecure-secret-key-change-in-production"),
        dev_otp_mode=_bool_env("DEV_OTP_MODE", default=False),
        debug=_bool_env("DEBUG", default=False),
    )


settings = load_settings()
