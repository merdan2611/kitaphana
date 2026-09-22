"""Phone + one-time code login, sessions, rate limits and the admin guard (Sprint 03)."""
from __future__ import annotations

import re

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import auth, sessions
from app.main import app

PHONE = "+99361234567"
DEV_CODE = re.compile(r'class="dev-code-value">(\d{6})<')


def request_code(client, phone=PHONE):
    return client.post("/login", data={"phone": phone})


def shown_code(response) -> str:
    match = DEV_CODE.search(response.text)
    assert match, "dev-OTP mode should show the code on the page"
    return match.group(1)


def verify(client, code, phone=PHONE):
    return client.post(
        "/login/verify", data={"phone": phone, "code": code}, follow_redirects=False
    )


def login(client, phone=PHONE):
    response = verify(client, shown_code(request_code(client, phone)), phone)
    assert response.status_code == 303
    return response


def wrong(code: str) -> str:
    return f"{(int(code) + 1) % 10**6:06d}"


# --- Sign-up and sign-in ---------------------------------------------------------------------


def test_new_number_becomes_an_account_through_the_on_screen_code(client, db):
    response = login(client, "8 61 234567")

    assert response.headers["location"] == "/account"
    users = db.execute("SELECT phone FROM users").fetchall()
    assert [u["phone"] for u in users] == [PHONE]

    account = client.get("/account")
    assert account.status_code == 200
    assert "+993 61 234567" in account.text
    assert "Çykyş" in account.text


def test_same_person_typing_differently_reaches_the_same_account(client, db):
    login(client, "+993 61 234567")
    client.post("/logout")
    login(client, "61-23-45-67")

    assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_invalid_phone_gets_a_readable_error(client):
    response = request_code(client, "12345")

    assert response.status_code == 400
    assert "8 sanly" in response.text
    assert 'value="12345"' in response.text  # what they typed is kept for correcting


def test_code_verifies_once_and_fails_the_second_time(client):
    code = shown_code(request_code(client))

    assert verify(client, code).status_code == 303
    second = verify(client, code)
    assert second.status_code == 400
    assert auth.MSG_CODE_GONE in second.text


def test_expired_code_fails(client, db):
    code = shown_code(request_code(client))
    db.execute("UPDATE otp_codes SET expires_at = '2000-01-01 00:00:00'")
    db.commit()

    response = verify(client, code)
    assert response.status_code == 400
    assert auth.MSG_CODE_GONE in response.text


def test_code_expires_after_the_configured_lifetime(client, db):
    request_code(client)
    row = db.execute(
        "SELECT (julianday(expires_at) - julianday(created_at)) * 86400 AS ttl FROM otp_codes"
    ).fetchone()
    assert round(row["ttl"]) == 300


def test_wrong_attempts_burn_the_code_at_the_threshold(client):
    code = shown_code(request_code(client))

    for remaining in (4, 3, 2, 1):
        response = verify(client, wrong(code))
        assert f"Ýene {remaining} synanyşygyňyz galdy" in response.text
    fifth = verify(client, wrong(code))
    assert auth.MSG_CODE_BURNED in fifth.text

    # The right code is now useless too.
    after = verify(client, code)
    assert after.status_code == 400
    assert auth.MSG_CODE_GONE in after.text


def test_burn_threshold_is_configuration(client, test_settings):
    test_settings(otp_max_attempts=2)
    code = shown_code(request_code(client))

    verify(client, wrong(code))
    assert auth.MSG_CODE_BURNED in verify(client, wrong(code)).text


def test_malformed_code_does_not_spend_an_attempt(client, db):
    code = shown_code(request_code(client))

    response = verify(client, "12ab")
    assert auth.MSG_CODE_FORMAT in response.text
    assert db.execute("SELECT attempt_count FROM otp_codes").fetchone()[0] == 0
    assert verify(client, code).status_code == 303


def test_code_with_spaces_is_accepted(client):
    code = shown_code(request_code(client))
    assert verify(client, f"{code[:3]} {code[3:]}").status_code == 303


def test_requesting_a_new_code_invalidates_the_old_one(client):
    old = shown_code(request_code(client))
    new = shown_code(request_code(client))

    if old != new:  # one in a million they coincide; then there is nothing to distinguish
        assert verify(client, old).status_code == 400
    assert verify(client, new).status_code == 303


def test_old_code_is_rejected_once_replaced(client, db):
    request_code(client)
    request_code(client)

    rows = db.execute("SELECT used_at FROM otp_codes ORDER BY id").fetchall()
    assert rows[0]["used_at"] is not None
    assert rows[1]["used_at"] is None


def test_blocked_user_cannot_log_in(client, db):
    db.execute("INSERT INTO users (phone, is_blocked) VALUES (?, 1)", (PHONE,))
    db.commit()

    response = verify(client, shown_code(request_code(client)))
    assert response.status_code == 400
    assert auth.MSG_BLOCKED in response.text


# --- Enumeration -----------------------------------------------------------------------------


def test_registered_and_unregistered_numbers_get_identical_responses(client, db, test_settings):
    test_settings(dev_otp_mode=False)
    db.execute("INSERT INTO users (phone) VALUES ('+99361111111')")
    db.commit()

    known = request_code(client, "+99361111111")
    unknown = request_code(client, "+99362222222")

    assert known.status_code == unknown.status_code == 200
    assert known.text.replace("61 111111", "X").replace("61111111", "X") == unknown.text.replace(
        "62 222222", "X"
    ).replace("62222222", "X")


def test_with_dev_otp_off_the_code_is_absent_from_the_response(client, db, test_settings):
    test_settings(dev_otp_mode=False)
    response = request_code(client)

    assert response.status_code == 200
    assert "dev-code" not in response.text
    stored = db.execute("SELECT code_hash FROM otp_codes").fetchone()["code_hash"]
    for candidate in re.findall(r"\d{6}", response.text):
        assert auth._hash_code(PHONE, candidate) != stored


# --- Rate limiting ---------------------------------------------------------------------------


def test_rate_limit_per_number(client):
    for _ in range(3):
        assert request_code(client).status_code == 200

    refused = request_code(client)
    assert refused.status_code == 429
    assert "Kod gaty köp soraldy" in refused.text
    assert "minutdan soň" in refused.text
    # A different number from the same address is still fine.
    assert request_code(client, "+99362222222").status_code == 200


def test_rate_limit_per_address(client):
    for i in range(10):
        assert request_code(client, f"+9936100000{i}").status_code == 200

    refused = request_code(client, "+99362222222")
    assert refused.status_code == 429
    assert "Kod gaty köp soraldy" in refused.text


def test_long_window_limit_reports_hours(client, db, test_settings):
    test_settings(otp_limits_per_phone=((100, 600), (2, 86400)))
    request_code(client)
    request_code(client)

    refused = request_code(client)
    assert refused.status_code == 429
    assert "sagatdan soň" in refused.text


def test_limits_are_configuration(client, test_settings):
    test_settings(otp_limits_per_phone=((1, 600),))

    assert request_code(client).status_code == 200
    assert request_code(client).status_code == 429


def test_limit_frees_up_once_the_window_passes(client, db):
    for _ in range(3):
        request_code(client)
    db.execute("UPDATE otp_codes SET created_at = datetime('now', '-11 minutes')")
    db.commit()

    assert request_code(client).status_code == 200


# --- Sessions --------------------------------------------------------------------------------


def test_session_cookie_is_persistent_httponly_secure_and_lax(client):
    header = login(client).headers["set-cookie"].lower()

    assert header.startswith(f"{sessions.COOKIE_NAME}=")
    assert "httponly" in header
    assert "secure" in header
    assert "samesite=lax" in header
    # Max-Age makes it survive a browser restart; a session cookie would not.
    assert f"max-age={180 * 86400}" in header


def test_session_survives_a_browser_restart(client):
    login(client)
    cookie = client.cookies[sessions.COOKIE_NAME]

    # A "restarted browser": a fresh client holding only the persisted cookie.
    fresh = TestClient(app, base_url="https://testserver")
    fresh.cookies.set(sessions.COOKIE_NAME, cookie)
    assert fresh.get("/account").status_code == 200


def test_logout_invalidates_the_session_server_side(client, db):
    login(client)
    cookie = client.cookies[sessions.COOKIE_NAME]

    client.post("/logout")
    assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0

    # Even a client that kept the old cookie is signed out.
    client.cookies.set(sessions.COOKIE_NAME, cookie)
    assert client.get("/account", follow_redirects=False).status_code == 303


def test_tampered_cookie_is_treated_as_signed_out(client):
    login(client)
    token, signature = client.cookies[sessions.COOKIE_NAME].rsplit(".", 1)
    client.cookies.clear()
    client.cookies.set(sessions.COOKIE_NAME, f"{token}x.{signature}")

    response = client.get("/account", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert 'href="/login"' in client.get("/").text


def test_unknown_but_well_signed_cookie_is_treated_as_signed_out(client):
    client.cookies.set(sessions.COOKIE_NAME, f"nosuchtoken.{sessions._sign('nosuchtoken')}")
    assert client.get("/account", follow_redirects=False).status_code == 303


def test_garbage_cookie_is_treated_as_signed_out(client):
    client.cookies.set(sessions.COOKIE_NAME, "garbage")
    assert client.get("/", follow_redirects=False).status_code == 200


def test_expired_session_is_signed_out_and_removed(client, db):
    login(client)
    db.execute("UPDATE sessions SET expires_at = '2000-01-01 00:00:00'")
    db.commit()

    assert client.get("/account", follow_redirects=False).status_code == 303
    assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_account_page_requires_login(client):
    response = client.get("/account", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_page_redirects_a_signed_in_reader_to_their_account(client):
    login(client)
    response = client.get("/login", follow_redirects=False)
    assert response.headers["location"] == "/account"


# --- Secrets at rest -------------------------------------------------------------------------


def test_no_code_or_session_token_is_readable_in_the_database(client, db):
    code = shown_code(request_code(client))
    verify(client, code)
    token = client.cookies[sessions.COOKIE_NAME].rsplit(".", 1)[0]

    stored = [
        str(value)
        for table in ("otp_codes", "sessions")
        for row in db.execute(f"SELECT * FROM {table}")
        for value in tuple(row)
    ]
    assert stored, "expected rows to inspect"
    assert not any(code in value for value in stored)
    assert not any(token in value for value in stored)


# --- Dev-mode banner -------------------------------------------------------------------------


def test_banner_is_on_every_page_in_dev_mode(client):
    for path in ("/", "/login"):
        assert "ÖSÜŞ TERTIBI" in client.get(path).text
    login(client)
    assert "ÖSÜŞ TERTIBI" in client.get("/account").text


def test_banner_vanishes_entirely_when_dev_mode_is_off(client, test_settings):
    test_settings(dev_otp_mode=False)
    for path in ("/", "/login"):
        text = client.get(path).text
        assert "ÖSÜŞ TERTIBI" not in text
        assert "dev-banner" not in text


def test_header_shows_signed_in_state(client):
    assert 'href="/login"' in client.get("/").text
    login(client)
    home = client.get("/").text
    assert 'href="/account"' in home
    assert 'action="/logout"' in home


# --- Admin guard -----------------------------------------------------------------------------


def _admin_probe_client(client) -> TestClient:
    """Sprint 04 builds the admin pages; this stands one up behind the real guard."""
    probe = FastAPI()
    probe.dependency_overrides = app.dependency_overrides

    @probe.get("/admin/probe")
    def admin_probe(user=Depends(auth.require_admin)):
        return {"ok": True}

    probe_client = TestClient(probe, base_url="https://testserver")
    probe_client.cookies = client.cookies
    return probe_client


def test_admin_route_is_404_for_a_signed_out_visitor(client):
    assert _admin_probe_client(client).get("/admin/probe").status_code == 404


def test_admin_route_is_404_for_a_normal_user(client):
    login(client)
    assert _admin_probe_client(client).get("/admin/probe").status_code == 404


def test_admin_route_is_open_to_a_flagged_user(client, db):
    login(client)
    db.execute("UPDATE users SET is_admin = 1 WHERE phone = ?", (PHONE,))
    db.commit()
    assert _admin_probe_client(client).get("/admin/probe").status_code == 200
