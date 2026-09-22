from __future__ import annotations

import dataclasses

import pytest
from fastapi.testclient import TestClient

from app import config
from app.db import apply_migrations, connect, get_db
from app.main import app


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    """Pin the settings tests rely on, so a developer's local .env cannot change results.

    Returns a function that overrides further fields for one test.
    """
    def override(**changes):
        monkeypatch.setattr(config, "settings", dataclasses.replace(config.settings, **changes))

    override(
        dev_otp_mode=True,
        secret_key="test-secret-key",
        cookie_secure=True,
        otp_ttl_seconds=300,
        otp_max_attempts=5,
        otp_limits_per_phone=((3, 600), (10, 86400)),
        otp_limits_per_ip=((10, 600), (50, 86400)),
        session_ttl_days=180,
    )
    return override


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture()
def client(db_path):
    """A TestClient wired to a fresh, migrated, temporary database.

    The base URL is https so the client, like a browser, sends the Secure session cookie back.
    """
    setup_conn = connect(db_path)
    apply_migrations(setup_conn)
    setup_conn.close()

    def override_get_db():
        conn = connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app, base_url="https://testserver")
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def db(db_path, client):
    """A direct connection to the same database the client uses, for setup and inspection."""
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()
