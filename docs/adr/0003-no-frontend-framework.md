# ADR-0003: Server-rendered HTML, no frontend framework

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

The interface is a catalogue, a search box, a book page with a download button, a request list,
and an admin panel. There is no real-time anything, no collaborative editing, and no complex
client state. Readers are on mobile connections in Turkmenistan, where megabytes of JavaScript
are a cost paid in seconds and sometimes in money.

The developer is a computer engineering student with limited hours, not a frontend specialist
maintaining a build pipeline in their spare time.

## Decision

Pages are rendered on the server with Jinja templates and served as HTML. Styling is one
hand-written stylesheet. JavaScript is used only where a page genuinely needs it — an upload
progress indicator, an upvote that should not reload the page — written as plain scripts in the
page. No React, no Vue, no bundler, no npm, no build step.

## Consequences

### Positive

- A page is useful the moment the HTML arrives. On a slow connection this is the difference
  between a site that works and one that appears broken.
- There is no build step, so there is nothing to break between writing a template and seeing it,
  and nothing to reconstruct after a month away.
- Search engines and link previews get real content with no extra work.
- The server does the rendering, and the server is the thing under the developer's control.

### Negative / accepted costs

- Interactions that would be trivial in a framework — filtering a list without a reload,
  optimistic UI — are either full page loads or hand-written JavaScript.
- No component model, so shared markup lives in template includes and requires discipline to
  avoid duplication.
- The admin panel, which is the most interaction-heavy part, is the place this will chafe
  first. Accepted: the admin is one person who can tolerate a page reload.
- If a genuinely interactive feature is ever needed — an in-browser reader, for instance — this
  decision would need revisiting with a new ADR.

## Alternatives considered

- **React or Vue as a single-page application.** Rejected: a build pipeline, a bundle to ship
  over a slow connection, and an entire second skill to maintain, in exchange for interactivity
  this product does not need.
- **htmx.** Genuinely close to the right answer, and would make partial updates pleasant without
  a build step. Rejected only for now, as one more dependency to learn during the sprints where
  learning budget is already spent on nginx and systemd. It can be added later without undoing
  anything here, since it works with exactly this kind of server-rendered application.
- **A CSS framework** (Bootstrap, Tailwind). Bootstrap is weight for styling that a small site
  does not need; Tailwind wants a build step. One stylesheet is enough.
