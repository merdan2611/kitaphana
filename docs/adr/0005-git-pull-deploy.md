# ADR-0005: Deploy by pulling git on the server

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

Code is written on the developer's laptop and has to reach the server. The options range from
copying files over `scp` to a full continuous-deployment pipeline. Deployments will be frequent
during Phase 1 — every sprint from Sprint 02 onwards ends with one — and infrequent later, which
means the procedure must survive being forgotten for weeks at a time.

## Decision

The repository is cloned once onto the server. Deploying is: `git pull`, install any new
dependencies, apply any new migrations, restart the service. Those steps live in a
`deploy.sh` script in the repository so that the procedure is the script rather than a memory.
Nothing is built on the server, because there is nothing to build ([ADR-0003](0003-no-frontend-framework.md)).

The server's clone tracks `main` and is never committed to. It is a read-only copy in practice;
if `git status` on the server is ever dirty, something has gone wrong and the local change
should be understood before it is discarded.

## Consequences

### Positive

- The deployed version is identifiable at any moment with `git log -1`, and the difference
  between the server and the laptop is a `git diff`. This is worth more than it sounds when
  debugging something that only happens in production.
- Rolling back is `git checkout` of the previous commit and a restart.
- GitHub doubles as the off-site copy of the code, which is the one thing not covered by
  [ADR-0011](0011-backup-policy.md)'s database backups.
- No credentials or pipeline to configure beyond a deploy key.

### Negative / accepted costs

- There is a gap of a few seconds between pulling code and restarting the service during which
  the code on disk and the code running differ. Irrelevant at this scale; worth remembering
  when reading a confusing log line from exactly that moment.
- Nothing prevents deploying a broken commit — there is no CI gate. The mitigation is running
  the application locally before pushing, which is in every sprint's definition of done.
- A restart drops in-flight requests. With downloads served by nginx rather than by the
  application ([ADR-0014](0014-x-accel-redirect-for-downloads.md)), an interrupted request is a
  small HTML page and not somebody's half-finished 80 MB book.
- Deployment requires the server to reach GitHub. If that becomes unreliable from inside the
  country, this decision needs revisiting.

## Alternatives considered

- **`scp` or `rsync` of files.** Simpler to start, and it loses the history, the version
  identity and the rollback. Rejected.
- **GitHub Actions deploying on push.** Pleasant, and it needs a reachable server from GitHub's
  runners plus stored credentials, for a project where a deploy is a deliberate act by the only
  person involved. The manual step is a feature here, not friction.
- **A bare repository on the server with a `post-receive` hook**, pushing straight to production.
  Elegant, and it makes the server a git remote with its own state to reason about. The pull
  model keeps the server strictly downstream.
