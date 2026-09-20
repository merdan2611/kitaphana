# ADR-0014: Serve downloads with nginx via X-Accel-Redirect

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

Downloading a book has two parts that pull in opposite directions. Deciding whether a download
is allowed is application logic: is this reader signed in, can they afford the book, has the
spend been recorded. Sending twenty to a hundred megabytes over a slow mobile connection is not
logic at all — it is minutes of a process doing nothing but copying bytes.

The natural FastAPI implementation, returning a `FileResponse`, does both in the application
process. On this server that is a genuine problem rather than a theoretical one. There are 2
vCPU and 2 GB of RAM, so the application runs a small number of uvicorn workers. A reader on a
slow connection occupies a worker for the entire duration of their download. A handful of
simultaneous downloads is enough to occupy every worker, at which point the site stops
responding to everyone else — not slowly, but completely — while the server looks almost idle.

nginx is already in front of the application ([ADR-0004](0004-systemd-and-nginx-no-docker.md))
and is built precisely for this: thousands of slow connections held open at negligible cost.

## Decision

The download endpoint does the thinking and none of the carrying:

1. Check the session, the book, and the star balance.
2. Append the `spend` row to the ledger, in a transaction
   ([ADR-0007](0007-star-credits-append-only-ledger.md)).
3. Return an **empty response** carrying an `X-Accel-Redirect` header pointing at the file's
   path, plus a `Content-Disposition` header giving the reader a filename derived from the book's
   title rather than its content hash.

nginx sees that header, fetches the file itself, and streams it. The worker is free
immediately — typically in milliseconds.

The media directory is configured in nginx as `internal;`, which means nginx will only serve
from it in response to an `X-Accel-Redirect` from the application. A reader who guesses the path
gets a 404.

## Consequences

### Positive

- Workers are occupied for milliseconds instead of minutes, which is the difference between the
  site staying up under concurrent downloads and falling over.
- nginx handles range requests, resumed downloads and conditional requests correctly, for free.
  Resuming an interrupted download matters a great deal on an unreliable mobile connection.
- Memory stays flat regardless of file size, because file contents never enter the Python
  process.
- Authorisation stays entirely in the application, and the files stay entirely unreachable
  without it.

### Negative / accepted costs

- This couples the application to nginx. It does not work under a bare `uvicorn`, so local
  development needs a fallback path that streams the file directly — a branch on a setting, with
  the direct path used only in development.
- Two places must agree about where files live: the application's media path and the nginx
  `internal` location. A mismatch produces a 404 that looks like a missing book. Worth a comment
  in both files, and worth checking first when a download 404s after a deployment.
- The star is spent before the bytes are sent, so a download that fails mid-transfer has still
  been charged. With resumable downloads this is rarely a real loss, and the ledger makes a
  refund a single row when it is.
- `X-Accel-Redirect` is an nginx feature. Moving to another proxy would mean its equivalent
  (`X-Sendfile` on Apache, for instance) or reverting to streaming.

## Alternatives considered

- **`FileResponse` from FastAPI.** One line, and it converts a slow reader into a denial of
  service against everybody. This ADR exists to record why the one-line version was rejected.
- **A public static directory under nginx.** Fastest of all and removes authorisation entirely —
  the whole collection would be one path away, which defeats stars and the library's control of
  its own files.
- **Signed temporary URLs** to a public directory. Workable, and it needs signing, expiry and
  clock handling to be got right, where `internal` plus a header needs none of it.
