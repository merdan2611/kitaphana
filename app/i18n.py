"""The reader-facing interface in Turkmen or Russian (ADR-0021).

Turkmen is the source language: every text is written in Turkmen, in the templates and in the
code, and that Turkmen text is also its key. Each other language has a catalogue mapping the
Turkmen text to its translation (app/translations/ru.py). A text the catalogue lacks falls back
to Turkmen, so no page is ever blank, and tests/test_i18n.py fails until it is translated.

The language is the reader's choice, kept in a cookie by the switch at /dil/<code>; Turkmen
unless they choose otherwise, whatever their browser prefers. The admin area is Turkmen only.

One language per request, held in a ContextVar. It is set by an async app-wide dependency
(app/main.py), so it lives in the request's own context and anyio copies it into the worker
thread that runs a sync handler and renders its template.
"""
from __future__ import annotations

from contextvars import ContextVar

from fastapi import Request

from app.translations import ru

# The interface languages, each named in itself. English would be one more line and catalogue.
LANGUAGES = {"tk": "Türkmençe", "ru": "Русский"}
DEFAULT = "tk"
# What the phone's app bar shows for each: the short codes readers there know.
SHORT_NAMES = {"tk": "TM", "ru": "RU"}

COOKIE_NAME = "ui_lang"  # not "lang": the catalogue's ?lang= filters books by their language
COOKIE_MAX_AGE = 365 * 24 * 3600

CATALOGUES: dict[str, dict[str, str | tuple[str, ...]]] = {"ru": ru.TRANSLATIONS}

_current: ContextVar[str] = ContextVar("ui_lang", default=DEFAULT)


def current() -> str:
    return _current.get()


def use(language: str) -> None:
    _current.set(language if language in LANGUAGES else DEFAULT)


def language_for(request: Request) -> str:
    """The reader's chosen language; always Turkmen in the admin area."""
    if request.url.path == "/admin" or request.url.path.startswith("/admin/"):
        return DEFAULT
    chosen = request.cookies.get(COOKIE_NAME, "")
    return chosen if chosen in LANGUAGES else DEFAULT


async def use_request_language(request: Request) -> None:
    """App-wide dependency. Async on purpose: see the module docstring."""
    use(language_for(request))


# --- Plurals ---------------------------------------------------------------------------------
# Turkmen does not inflect a noun after a number ("1 kitap", "5 kitap"); Russian has three forms
# ("1 книга", "2 книги", "5 книг"). A plural entry in a catalogue is a tuple of the language's
# forms, in the order its rule numbers them.


def _russian_form(n: int) -> int:
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return 0
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return 1
    return 2


PLURAL_RULES = {"ru": _russian_form}


# --- Translating -----------------------------------------------------------------------------


def gettext(text: str) -> str:
    """`text` (Turkmen) in the current language."""
    catalogue = CATALOGUES.get(current())
    if not catalogue:
        return text
    entry = catalogue.get(text)
    if entry is None:
        return text
    return entry[0] if isinstance(entry, tuple) else entry


def ngettext(singular: str, plural: str, n: int) -> str:
    """The right form for `n` in the current language. The Turkmen singular is the key."""
    language = current()
    catalogue = CATALOGUES.get(language)
    entry = catalogue.get(singular) if catalogue else None
    if entry is None:
        return singular if n == 1 else plural
    forms = entry if isinstance(entry, tuple) else (entry,)
    return forms[min(PLURAL_RULES.get(language, lambda _n: 0)(n), len(forms) - 1)]


# --- In Python code --------------------------------------------------------------------------
# Python code uses these names rather than the customary `_`, which is also Python's usual
# throwaway variable: a loop over `_` would silently hide the translator for the rest of the
# function. Templates use Jinja's `_()` and `ngettext()`, which fill placeholders themselves.


def N_(text: str) -> str:
    """Mark `text` as translatable where it is defined (a constant); translate it where used."""
    return text


def tr(text: str, **values: object) -> str:
    """`text` in the current language, with its %(name)s placeholders filled from `values`."""
    translated = gettext(text)
    return translated % values if values else translated


def tr_n(text: str, n: int, **values: object) -> str:
    """The form of `text` for the number `n` in the current language; `%(num)d` is `n`."""
    return ngettext(text, text, n) % {"num": n, **values}
