# ADR-0004: Run under systemd behind nginx, without Docker

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

The application needs to start on boot, restart if it crashes, terminate TLS, and serve static
files and large PDFs efficiently — on a server with 2 GB of RAM shared with everything else.

The developer knows Linux as a desktop user but has not run a production server before. That
cuts both ways: containers are often recommended precisely to spare people from learning
service management, but they also add a layer that has to be understood when something breaks
at two in the morning.

## Decision

The application runs as a `uvicorn` process managed by a **systemd** unit, as an unprivileged
user. **nginx** sits in front of it as a reverse proxy, terminating TLS, serving static assets,
and serving PDF downloads via internal redirect ([ADR-0014](0014-x-accel-redirect-for-downloads.md)).
No Docker, no container runtime, no orchestration.

## Consequences

### Positive

- Nothing is spent on a container runtime's memory or CPU, which on 2 GB is a real fraction.
- systemd is what the operating system already uses for every other service on the machine, so
  learning it is learning the system rather than learning a layer on top of it. `systemctl
  status`, `journalctl -u kitaphana` and `systemctl restart` cover nearly everything.
- Debugging is direct: one Python process, its logs in the journal, no indirection between the
  error and the machine.
- nginx handles the two things it is far better at than a Python process — TLS and sending large
  files — while uvicorn only ever handles small dynamic responses.

### Negative / accepted costs

- The server's environment is set up by hand, which means it can drift from the development
  machine and there is no image that captures it. Mitigated by writing the setup down in the
  Sprint 02 document as commands that can be replayed, and by keeping the unit file and nginx
  configuration in the repository rather than only on the server.
- Python version and system package differences between the developer's Fedora machine and the
  server's distribution are a real source of surprises, and there is no container isolating
  them. A virtual environment on the server covers the Python side; the system side needs
  noting when it bites.
- Rebuilding the server after a catastrophe is a manual procedure, not a command. It is
  documented rather than automated.

## Alternatives considered

- **Docker and Docker Compose.** Reproducible environments and a clean rebuild story, at the
  cost of daemon memory on a 2 GB machine, image builds on a slow connection, and a layer of
  indirection over every problem. Rejected, though it would be reasonable at twice the RAM.
- **A platform-as-a-service** (Railway, Fly, Render). Removes server administration entirely,
  and is unavailable: foreign payment, and hosting outside the country for an audience inside it.
- **supervisord.** A third-party process supervisor doing what systemd already does on this
  machine. No reason to add it.
