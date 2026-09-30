"""Sprint 08, task 2: an unhandled error shows a page in the site's layout with nothing of the
error in it, and leaves a log line that journald files as an error."""
from __future__ import annotations

import logging
import re

import pytest
import yaml
from fastapi.testclient import TestClient

from app import catalogue
from app.config import BASE_DIR
from app.logs import JournalFormatter
from app.main import app


class Boom(RuntimeError):
    pass


@pytest.fixture()
def broken(client, monkeypatch):
    """The home page raises; the client returns the 500 response instead of re-raising."""
    def explode(conn):
        raise Boom("secret internals /srv/kitaphana/app/catalogue.py")

    monkeypatch.setattr(catalogue, "newest_books", explode)
    return TestClient(app, base_url="https://testserver", raise_server_exceptions=False)


def test_debug_mode_is_off():
    assert app.debug is False


def test_an_error_gets_the_styled_page_and_no_internals(broken):
    response = broken.get("/")
    assert response.status_code == 500
    assert "Ýalňyşlyk ýüze çykdy" in response.text
    assert 'class="site-header"' in response.text and 'class="tab-bar"' in response.text
    for leak in ("Boom", "secret internals", "Traceback", "catalogue.py", "/srv/"):
        assert leak not in response.text


def test_the_error_page_is_in_the_readers_language(broken):
    broken.cookies.set("ui_lang", "ru")
    assert "Произошла ошибка" in broken.get("/").text


def test_the_log_line_carries_a_reference_the_reader_also_sees(broken, caplog):
    with caplog.at_level(logging.ERROR, logger="app.main"):
        response = broken.get("/?q=x")
    ref = re.search(r"<code>([0-9a-f]{8})</code>", response.text).group(1)
    [record] = [r for r in caplog.records if r.name == "app.main"]
    assert record.levelno == logging.ERROR
    line = record.getMessage()
    assert ref in line and "GET /" in line and "Boom" in line


def test_a_broken_error_page_falls_back_to_bare_html(broken, monkeypatch):
    from app import main

    def fail(*args, **kwargs):
        raise RuntimeError("template broke")

    monkeypatch.setattr(main.templates, "TemplateResponse", fail)
    response = broken.get("/")
    assert response.status_code == 500
    assert "Ýalňyşlyk ýüze çykdy" in response.text and "Произошла ошибка" in response.text
    assert "template broke" not in response.text


# --- journald priorities ---------------------------------------------------------------------


def _record(level, exc_info=None):
    return logging.LogRecord("app.main", level, __file__, 1, "went wrong", None, exc_info)


def test_under_systemd_every_line_of_an_error_is_marked_as_one(monkeypatch):
    monkeypatch.setenv("JOURNAL_STREAM", "8:12345")
    try:
        raise Boom("x")
    except Boom:
        import sys
        text = JournalFormatter("%(message)s").format(_record(logging.ERROR, sys.exc_info()))
    lines = text.splitlines()
    assert len(lines) > 2 and "Traceback" in text
    assert all(line.startswith("<3>") for line in lines)


def test_info_is_marked_as_info_and_a_terminal_gets_plain_lines(monkeypatch):
    monkeypatch.setenv("JOURNAL_STREAM", "8:12345")
    assert JournalFormatter("%(message)s").format(_record(logging.INFO)) == "<6>went wrong"
    monkeypatch.delenv("JOURNAL_STREAM")
    assert JournalFormatter("%(message)s").format(_record(logging.ERROR)) == "went wrong"


def test_the_service_logs_through_the_journal_formatter():
    service = (BASE_DIR / "deploy/kitaphana.service").read_text()
    assert "--log-config /srv/kitaphana/deploy/logging.yaml" in service
    config = yaml.safe_load((BASE_DIR / "deploy/logging.yaml").read_text())
    assert config["formatters"]["journal"]["()"] == "app.logs.JournalFormatter"
    assert config["root"]["handlers"] == ["stderr"]


def test_nginx_shows_its_own_page_when_the_app_is_down():
    conf = (BASE_DIR / "deploy/nginx-kitaphana.conf").read_text()
    assert "error_page 502 503 504 /_errors/50x.html;" in conf
    assert (BASE_DIR / "static/errors/50x.html").is_file()
