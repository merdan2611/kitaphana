# ADR-0021: A Russian interface beside Turkmen, for readers

- **Status**: Accepted
- **Date**: 2026-09-28

## Context

Kitaphana was built for one interface language. The vision's anti-goal read "one server, one
country, one language", and every text was written in Turkmen, straight into the templates and
the code. R8 in [`../04-risks-and-research.md`](../04-risks-and-research.md) kept the question
open ("do readers expect a Russian interface?"). It warned that adding a second language after
the interface is written costs several times what building for two costs.

Russian is widely read in Turkmenistan, and many phones there are set to it. On 2026-09-28,
with the site on its real server and testers about to be invited, the developer decided to
offer Russian now, in Sprint 08, rather than wait for testers to ask. The scope was reader
pages only, with English later if it is wanted.

Measured at the time:
- the reader pages held about 229 pieces of text;
- the code held about 40 more reader messages (sign-in errors, rate limits, form checks,
  "3 gün öň");
- in all, about 1,000 words to translate.

## Decision

**Readers choose Turkmen or Russian; Turkmen is the default.**
- The choice is a cookie (`ui_lang`, a year), set by a plain link, `/dil/<code>?next=<page>`,
  that returns the reader to the page they were on.
- It is offered in the website's header, in a phone's app bar for visitors, and as a setting
  on the account page, which is the Profile tab on a phone.
- The site never guesses from the browser's language. Many phones in Turkmenistan are set to
  Russian, and this is a Turkmen library.
- The admin area is Turkmen whatever the cookie says.

**Turkmen stays the source.** Texts are written in Turkmen in the templates and the code, and
the Turkmen text is its own key:
- templates mark text with Jinja's standard `_()`, `ngettext()` and `{% trans %}`;
- Python marks it with `N_()` (a constant, translated where used), `tr()` and `tr_n()`.

The Russian lives in `app/translations/ru.py`, a plain dict from the Turkmen text to the
Russian, so there is no gettext toolchain on the server. A text used with a number has
Russian's three plural forms ("1 книга", "2 книги", "5 книг"), chosen by a five-line rule. A
missing entry falls back to Turkmen, so a page is never blank.

**One language per request**, in a `ContextVar`. It is set by an `async` app-wide dependency,
so anyio copies it into the worker thread that runs a sync handler and renders its template.

**`tests/test_i18n.py` keeps the two in step.** It extracts every marked text from the reader
templates and modules, and fails if Russian lacks one. It also fails if an entry is unused, or
if a translation loses a link, a `<strong>` or a `%(placeholder)s`.

**English**, when wanted, is one more catalogue and one more entry in `i18n.LANGUAGES`.

## Consequences

### Positive

- Russian-reading testers can use the whole reader side from the first day.
- Adding English later is translation work, not engineering.
- The switch is a link and a cookie: no script, no URL prefixes, and every shared link still
  works in both languages.

### Negative / accepted costs

- **Every new reader text is written twice from now on**, and the test refuses to let the
  Russian fall behind. Reader-facing UI work gets roughly 15–25 % slower. This is the cost R8
  warned about, accepted knowingly.
- **The Russian needs a fluent reviewer.** Claude drafted the first catalogue; the developer
  reviews it before it ships, and reviews each later addition.
- **Books, requests, notes and the admin's messages stay in the language they were written
  in.** A Russian page will show Turkmen book titles and request titles. That is content, not
  interface.
- **The language is not in the URL**, so search engines see only Turkmen. Acceptable while the
  site is invite-only and `noindex`. Revisit with URL prefixes (`/ru/…`) if public search
  traffic starts to matter.
- **The vision changes**: its anti-goal now reads "one country", not "one language".

## Alternatives considered

- **Keep Turkmen only until testers ask (R8's original plan).** It was cheaper today, but
  each sprint of Turkmen-only text would have made the change more expensive. The developer
  chose to pay now.
- **gettext `.po`/`.mo` files with Babel.** The industry standard, but it needs extraction
  and compiling tools on the server or in the deploy. Plain dicts are readable, and so is a
  test that checks them.
- **Guess the language from the browser.** Many Turkmen readers' phones are set to Russian, so
  the site would open in Russian for people who read Turkmen by choice.
- **Translate the admin area too.** Half as much again, for one Turkmen-speaking user.
