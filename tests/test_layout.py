"""The two designs (ADR-0018) and the colour tokens.

Phones get an app-style tab bar and wide screens a website header; both are in every page's
HTML and CSS picks one, so these tests check the markup both designs rely on.
"""
from __future__ import annotations

import re

import pytest

from app.config import BASE_DIR
from tests.test_auth import PHONE, login

STATIC = BASE_DIR / "static"
COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\(")
NAMED_COLOUR = re.compile(r":\s*[^;]*\b(?:white|black|red|blue|green|gray|grey|yellow|orange)\b")


def _without_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _token_blocks(css: str) -> list[str]:
    """The light tokens in `:root {`, the dark ones in `:root[data-theme="dark"] {`, and any
    other `:root` block (the wider gutter on the website)."""
    return re.findall(r":root[^{]*\{[^}]*\}", css)


def _dark_block(css: str) -> str:
    match = re.search(r':root\[data-theme="dark"\] \{[^}]*\}', css)
    assert match, "style.css should define a dark theme"
    return match.group(0)


def tab_bar(html: str) -> str:
    match = re.search(r'<nav class="tab-bar".*?</nav>', html, flags=re.S)
    assert match, "every page should carry the phone tab bar"
    return match.group(0)


def current_tab(html: str) -> str | None:
    match = re.search(r'<a href="([^"]+)" aria-current="page"', tab_bar(html))
    return match.group(1) if match else None


# --- Colours ---------------------------------------------------------------------------------


def test_colours_appear_only_in_the_token_block():
    """So any colour can be changed on its own by editing one line (static/style.css)."""
    css = _without_comments((STATIC / "style.css").read_text())
    outside = css
    for block in _token_blocks(css):
        outside = outside.replace(block, "")
    assert COLOUR.findall(outside) == []
    assert NAMED_COLOUR.findall(outside) == []


def test_admin_css_uses_only_the_tokens():
    css = _without_comments((STATIC / "admin.css").read_text())
    assert COLOUR.findall(css) == []
    assert NAMED_COLOUR.findall(css) == []


def test_theme_color_meta_matches_the_header_token():
    token = re.search(r"--color-header:\s*(#[0-9a-fA-F]+)", (STATIC / "style.css").read_text())
    meta = re.search(r'name="theme-color" content="([^"]+)"', (BASE_DIR / "templates/base.html").read_text())
    assert token and meta
    assert meta.group(1).lower() == token.group(1).lower()


def test_every_token_used_is_defined():
    style = (STATIC / "style.css").read_text()
    defined = set(re.findall(r"(--[\w-]+):", "".join(_token_blocks(style))))
    used = set()
    for name in ("style.css", "admin.css"):
        used |= set(re.findall(r"var\((--[\w-]+)", (STATIC / name).read_text()))
    assert used - defined == set()


def test_dark_theme_only_redefines_existing_colours():
    """The dark block may change a token, never invent one the light theme lacks."""
    css = _without_comments((STATIC / "style.css").read_text())
    light = set(re.findall(r"(--[\w-]+):", _token_blocks(css)[0]))
    dark = set(re.findall(r"(--[\w-]+):", _dark_block(css)))
    assert dark and dark <= light


def test_header_keeps_its_colour_in_the_dark_theme():
    """So <meta name="theme-color"> is right in both themes."""
    assert "--color-header:" not in _dark_block((STATIC / "style.css").read_text())


# --- Light and dark switch -------------------------------------------------------------------


def test_every_page_has_the_theme_switch_and_script(client):
    html = client.get("/").text
    assert 'class="theme-toggle"' in html
    assert 'localStorage.getItem("theme")' in html
    # The script sets the theme before the stylesheet is read, so the page never flashes.
    assert html.index("root.dataset.theme") < html.index("/static/style.css")


def test_admin_pages_have_the_theme_switch(client, db):
    login(client)
    db.execute("UPDATE users SET is_admin = 1 WHERE phone = ?", (PHONE,))
    db.commit()
    assert 'class="theme-toggle"' in client.get("/admin").text


# --- Phone tab bar ---------------------------------------------------------------------------


def test_signed_out_visitor_gets_home_catalogue_and_login_tabs(client):
    tabs = tab_bar(client.get("/").text)
    assert 'href="/"' in tabs and 'href="/books"' in tabs and 'href="/login"' in tabs
    assert 'href="/account"' not in tabs and 'href="/admin"' not in tabs


def test_reader_gets_an_account_tab_but_no_admin_tab(client):
    login(client)
    tabs = tab_bar(client.get("/").text)
    assert 'href="/account"' in tabs
    assert 'href="/login"' not in tabs and 'href="/admin"' not in tabs


def test_admin_also_gets_an_admin_tab(client, db):
    login(client)
    db.execute("UPDATE users SET is_admin = 1 WHERE phone = ?", (PHONE,))
    db.commit()
    assert 'href="/admin"' in tab_bar(client.get("/").text)


@pytest.mark.parametrize(
    "path, expected",
    [("/", "/"), ("/login", "/login"), ("/books", "/books"), ("/books?q=alem", "/books")],
)
def test_the_current_tab_is_marked(client, path, expected):
    assert current_tab(client.get(path).text) == expected


def test_catalogue_tab_stays_marked_on_a_book_page(client, db):
    import io

    from app import storage
    from tests.pdfs import make_pdf

    book_id = storage.ingest(
        db, storage.stage(io.BytesIO(make_pdf())), original_filename="a.pdf", is_published=True
    )
    assert current_tab(client.get(f"/books/{book_id}").text) == "/books"


def test_website_header_links_to_the_catalogue(client):
    header = client.get("/").text.split('<nav class="site-nav"', 1)[1].split("</nav>", 1)[0]
    assert 'href="/books"' in header


def test_account_tab_is_marked_on_the_account_page(client):
    login(client)
    assert current_tab(client.get("/account").text) == "/account"


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/admin", "/admin"),
        ("/admin/books", "/admin/books"),
        ("/admin/books/new", "/admin/books/new"),
        ("/admin/stars", "/admin/stars"),
    ],
)
def test_admin_pages_have_their_own_tab_bar(client, db, path, expected):
    login(client)
    db.execute("UPDATE users SET is_admin = 1 WHERE phone = ?", (PHONE,))
    db.commit()
    html = client.get(path).text
    assert current_tab(html) == expected
    assert 'href="/login"' not in tab_bar(html)


# --- Dev-mode reminder -----------------------------------------------------------------------


def test_top_bar_keeps_a_dev_mode_reminder(client):
    assert 'class="dev-pill"' in client.get("/").text


def test_reminder_is_gone_when_dev_mode_is_off(client, test_settings):
    test_settings(dev_otp_mode=False)
    assert "dev-pill" not in client.get("/").text
