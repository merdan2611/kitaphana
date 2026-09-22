"""Search folding (Sprint 05 task 2).

SQLite's LIKE folds case for ASCII only: `LIKE '%älem%'` never matches "Älem", and nothing at
all matches "alem" typed on a phone without Turkmen letters. So every book stores a folded copy
of its title and author in books.search_text, and a query is folded the same way before it is
matched against that column. `fold` is the one function both sides use; app/db.py also registers
it with SQLite so a migration can fill in rows that existed before the column did.

Folding decomposes letters, drops their diacritics and case-folds them, so all of these reduce
to plain lowercase letters: Turkmen ä ç ň ö ş ü ý ž (and their capitals), and Cyrillic й and ё.
Any run of characters that are not letters or digits becomes a single space.
"""
from __future__ import annotations

import re
import unicodedata

_WORD = re.compile(r"\w+")

# A query longer than this is cut, and only this many of its words are used: enough for any real
# title, and it keeps a pasted paragraph from becoming dozens of LIKE clauses.
MAX_QUERY_LENGTH = 100
MAX_TERMS = 8


def fold(text: str | None) -> str:
    """Lowercase, diacritic-free words separated by single spaces. "Baglar, HEÝ!" -> "baglar hey"."""
    if not text:
        return ""
    # Decompose, case-fold, decompose again (case-folding can produce composed letters), and
    # drop the combining marks that decomposition split off.
    decomposed = unicodedata.normalize("NFKD", unicodedata.normalize("NFKD", text).casefold())
    bare = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(_WORD.findall(bare))


def book_search_text(title: str, author: str) -> str:
    """What books.search_text holds: the folded title followed by the folded author.

    Kept identical to the SQL `kitaphana_fold(title || ' ' || author)` that migration 004 uses to
    fill in existing books.
    """
    return fold(f"{title} {author}")


def query_terms(query: str) -> list[str]:
    """The folded words of a search query. A book matches when its search_text contains all of them."""
    return fold(query[:MAX_QUERY_LENGTH]).split()[:MAX_TERMS]


def like_pattern(term: str) -> str:
    """A LIKE pattern matching `term` anywhere, for use with ESCAPE '\\'.

    Folded terms cannot contain %, but they can contain _, which LIKE would read as a wildcard.
    """
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
