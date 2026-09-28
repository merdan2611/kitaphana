"""The Russian interface beside Turkmen (ADR-0021): every reader text has its Russian, the
reader's choice sticks, and the admin area stays Turkmen."""
from __future__ import annotations

import ast
import re

import pytest

from app import i18n, ratelimit
from app.config import BASE_DIR
from app.templating import _ago, templates
from app.translations import ru
from tests.test_admin import admin  # noqa: F401  (fixture)
from tests.test_auth import login

# Admin pages and admin-only modules stay Turkmen (ADR-0021), so they carry no marked text.
READER_TEMPLATES = sorted((BASE_DIR / "templates").glob("*.html"))
ADMIN_ONLY_MODULES = {"admin.py", "storage.py", "dashboard.py", "i18n.py"}
READER_MODULES = sorted(p for p in (BASE_DIR / "app").glob("*.py") if p.name not in ADMIN_ONLY_MODULES)


def marked_texts() -> dict[str, bool]:
    """Every translatable Turkmen text -> whether it is used with a number (a plural)."""
    found: dict[str, bool] = {}
    for path in READER_TEMPLATES:
        for _lineno, function, message in templates.env.extract_translations(path.read_text()):
            text = message[0] if isinstance(message, tuple) else message
            if text:  # None: _() of a variable, whose values are marked where defined
                found[text] = found.get(text, False) or function == "ngettext"
    for path in READER_MODULES:
        for node in ast.walk(ast.parse(path.read_text())):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", None) in {"N_", "tr", "tr_n"}
                    and node.args and isinstance(node.args[0], ast.Constant)):
                text = node.args[0].value
                found[text] = found.get(text, False) or node.func.id == "tr_n"
    return found


@pytest.fixture()
def russian():
    """Russian for code called directly in a test, reset afterwards so it cannot leak."""
    token = i18n._current.set("ru")
    try:
        yield
    finally:
        i18n._current.reset(token)


# --- The catalogue keeps up ------------------------------------------------------------------


def test_every_reader_text_has_its_russian():
    missing = sorted(text for text in marked_texts() if text not in ru.TRANSLATIONS)
    assert missing == [], "add these to app/translations/ru.py"


def test_texts_used_with_a_number_have_all_three_russian_forms():
    wrong = sorted(
        text for text, plural in marked_texts().items()
        if plural and not (isinstance(ru.TRANSLATIONS.get(text), tuple) and len(ru.TRANSLATIONS[text]) == 3)
    )
    assert wrong == []


def test_the_catalogue_has_no_entries_the_site_no_longer_uses():
    stale = sorted(set(ru.TRANSLATIONS) - set(marked_texts()))
    assert stale == [], "a Turkmen text changed or went: update or remove its key"


PLACEHOLDER = re.compile(r"%\((\w+)\)[sd]")
# Links and emphasis carry meaning and must survive translation; a nowrap <span> only steers
# Turkmen line breaks, so a translation may drop it.
MEANINGFUL_TAG = re.compile(r"<(?:a\b[^>]*|/a|strong\b[^>]*|/strong)>")


@pytest.mark.parametrize("text", sorted(ru.TRANSLATIONS))
def test_a_translation_keeps_its_placeholders_links_and_emphasis(text):
    entry = ru.TRANSLATIONS[text]
    for russian_text in entry if isinstance(entry, tuple) else (entry,):
        assert sorted(PLACEHOLDER.findall(russian_text)) == sorted(PLACEHOLDER.findall(text))
        assert sorted(MEANINGFUL_TAG.findall(russian_text)) == sorted(MEANINGFUL_TAG.findall(text))


# --- Russian grammar -------------------------------------------------------------------------


@pytest.mark.parametrize("n, form", [
    (0, 2), (1, 0), (2, 1), (4, 1), (5, 2), (11, 2), (12, 2), (14, 2), (21, 0), (22, 1),
    (25, 2), (101, 0), (111, 2), (1004, 1),
])
def test_russian_plural_rule(n, form):
    assert i18n._russian_form(n) == form


def test_how_long_ago_in_russian(russian):
    assert _ago("2026-01-01 00:00:00").endswith("назад")
    assert i18n.tr_n("%(num)d gün öň", 3) == "3 дня назад"
    assert i18n.tr_n("%(num)d gün öň", 5) == "5 дней назад"
    assert i18n.tr_n("%(num)d gün öň", 21) == "21 день назад"
    assert i18n.tr("häzir") == "только что"


def test_how_long_ago_stays_turkmen_by_default():
    assert i18n.tr_n("%(num)d gün öň", 3) == "3 gün öň"


def test_rate_limit_message_in_russian(russian):
    assert ratelimit.RateLimited(5 * 60).message == "Код запрашивали слишком часто. Попробуйте снова через 5 минут."
    assert ratelimit.RateLimited(3 * 3600).message.endswith("через 3 часа.")


# --- Choosing the language -------------------------------------------------------------------


def test_the_site_is_turkmen_unless_the_reader_chooses_otherwise(client):
    html = client.get("/", headers={"Accept-Language": "ru-RU,ru;q=0.9"}).text
    assert '<html lang="tk">' in html
    assert "Türkmen dilindäki kitaplar bir ýerde" in html


def test_the_switch_remembers_russian_and_returns_to_the_page(client):
    response = client.get("/dil/ru?next=/books%3Fsort%3Dtitle", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/books?sort=title"
    cookie = response.headers["set-cookie"]
    assert "ui_lang=ru" in cookie and "HttpOnly" in cookie and "Max-Age=31536000" in cookie

    html = client.get("/").text
    assert '<html lang="ru">' in html
    assert "Книги на\u00a0туркменском языке в\u00a0одном месте" in html
    assert ">Каталог<" in html  # the tab bar and the header


def test_russian_pages_offer_the_way_back_to_turkmen(client):
    client.get("/dil/ru")
    html = client.get("/books").text
    assert 'href="/dil/tk?next=/books"' in html and ">Türkmençe<" in html


@pytest.mark.parametrize("target", ["//evil.example/x", "https://evil.example", "/dil/ru", "/logout"])
def test_the_switch_only_returns_to_a_page_on_this_site(client, target):
    response = client.get("/dil/ru", params={"next": target}, follow_redirects=False)
    assert response.headers["location"] == "/"


def test_the_switch_can_return_to_the_login_page(client):
    response = client.get("/dil/ru", params={"next": "/login?next=/books/3"}, follow_redirects=False)
    assert response.headers["location"] == "/login?next=/books/3"


def test_an_unknown_language_changes_nothing(client):
    response = client.get("/dil/xx", follow_redirects=False)
    assert response.status_code == 303 and "set-cookie" not in response.headers
    assert '<html lang="tk">' in client.get("/").text


def test_the_admin_area_stays_turkmen(admin):  # noqa: F811
    admin.get("/dil/ru")
    assert '<html lang="ru">' in admin.get("/").text
    page = admin.get("/admin").text
    assert '<html lang="tk">' in page and "Umumy" in page
    assert "Каталог" not in page


def test_the_book_language_filter_is_not_the_interface_language(client, db):
    from tests.test_catalogue import add_book, titles
    add_book(db, "Каштанка", language="ru")
    add_book(db, "Görogly", language="tk")
    client.get("/dil/ru")
    html = client.get("/books?lang=ru").text
    assert titles(html) == ["Каштанка"]
    assert 'href="/books?lang=ru" aria-current="true">Русский <span class="chip-count">1</span>' in html


def test_a_signed_in_reader_sees_russian_messages_and_can_switch_on_the_account_page(client):
    login(client)
    client.get("/dil/ru")
    page = client.get("/account").text
    assert "Язык сайта" in page and 'href="/dil/tk?next=/account"' in page
    refused = client.post("/login", data={"phone": "12"})
    assert "В номере должно быть 8 цифр" in refused.text


def test_a_missing_page_follows_the_choice(client):
    client.get("/dil/ru")
    response = client.get("/no-such-page")
    assert response.status_code == 404 and "Страница не найдена" in response.text
