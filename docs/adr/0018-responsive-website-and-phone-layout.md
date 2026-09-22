# ADR-0018: A website on wide screens, an app-style layout on phones

- **Status**: Accepted
- **Date**: 2026-09-23

## Context

Until now every public page was one narrow, mobile-first column. On a phone that was fine; on a
laptop it looked like a phone page floating in empty space. The product owner asked for Kitaphana
to be a real website on desktop, with its own design and dimensions, and to feel like an app on
phones, with a separate design there. They were explicit that this means responsive design in
the browser, not an installable app: no PWA, no web app manifest, no home-screen install. The
vision's anti-goal "Not a mobile app… installable as nothing" stands.

[ADR-0003](0003-no-frontend-framework.md) still applies: server-rendered Jinja templates, one
hand-written stylesheet, no framework, no build step.

## Decision

One set of templates, two designs, chosen by CSS at a single breakpoint of 48rem (768px):

- **Phones, below 48rem — app-style.** A compact top bar (the site name, plus a small
  "Ösüş tertibi" pill while dev-OTP mode is on), full-width content, and a tab bar fixed to the
  bottom of the screen with an icon and label per section. There is no footer. These are the
  base rules of `static/style.css`.
- **48rem and wider — a website.** A header with the navigation along the top, the carpet
  border strip, a 72rem container, and a footer. From 64rem, pages that benefit from it use two
  columns: the home page, and login with its steps beside the form card.

Every page's HTML contains both navigations, the header nav and the tab bar; CSS shows one. The
admin follows the same pattern with its own tab bar (overview, books, add book, back to the
site).

Colours are role tokens at the top of `static/style.css` — classic, neutral values for now —
and no colour may be written anywhere else in the CSS, which `tests/test_layout.py` enforces.
The only colour outside CSS is the `theme-color` meta tag, which a test keeps equal to
`--color-header`.

## Consequences

### Positive

- Desktop visitors get a page designed for their screen; phone users get something that feels
  like an app, without an app store, installation or a second codebase.
- One template per page: a change to a page is made once, not once per device.
- No JavaScript and no user-agent sniffing: the choice is plain CSS, and it is right even when a
  desktop browser window is narrowed.
- The admin can be used comfortably from a phone as well.
- Any single colour can be changed later by editing one line.

### Negative / accepted costs

- **Every new page needs both designs**, checked at both widths before it is called done.
- **Every new top-level section needs a tab.** A tab bar holds four or five items at most:
  the catalogue (Sprint 05) and requests (Sprint 07) will fill it. A sixth section would need a
  "more" tab or a rethink.
- Both navigations are in every page's HTML — a few hundred bytes of markup that one of the two
  designs never shows.
- The fixed tab bar takes about 60px of a phone screen on every page, and on iPhones it has to
  respect the home-indicator safe area (`env(safe-area-inset-bottom)`).
- Tablets between 48rem and 64rem get the website with single-column pages, which is a
  compromise rather than a design of their own.

## Alternatives considered

- **Separate mobile templates** (or an `m.` subdomain) chosen by user agent. Truly separate
  designs, at the cost of maintaining every page twice and guessing devices from a header.
  Rejected for a solo developer with 5-10 hours a week.
- **An installable web app (PWA) or a native app.** Explicitly not wanted, and against the
  vision's anti-goals.
- **A single responsive column that simply widens.** What existed before, and what prompted
  this decision.
- **A hamburger menu on phones** instead of a tab bar. Hides the few sections there are behind
  an extra tap, and feels like a shrunken website rather than an app.
