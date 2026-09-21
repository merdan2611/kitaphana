from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import apply_migrations, connect, get_db
from app.main import app


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture()
def client(db_path):
    """A TestClient wired to a fresh, migrated, temporary database."""
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
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
