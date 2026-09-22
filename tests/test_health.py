from __future__ import annotations

from app.db import MIGRATIONS_DIR

LATEST_MIGRATION = max(int(p.name.split("-", 1)[0]) for p in MIGRATIONS_DIR.glob("*.sql"))


def test_health_reports_ok_status_migration_and_version(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["migration"] == LATEST_MIGRATION
    assert body["version"]


def test_home_page_renders_through_the_base_layout(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Kitaphana" in response.text
    assert "/static/style.css" in response.text
