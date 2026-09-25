# Sprint 02 — Production ground

| | |
|---|---|
| **Status** | ⚪ Pending |
| **Phase** | 1 (usable library, codes on screen) |
| **Milestone** | M2 — It is on the internet |
| **Estimated time** | ~1-2 weeks (the least familiar work in the project) |
| **Depends on** | Sprint 01 |
| **Blocked by** | Nothing. The droplet loads from inside Turkmenistan (checked 2026-09-25) |
| **Runs when** | Now: the DigitalOcean droplet was set up on 2026-09-25 ([ADR-0019](../adr/0019-digitalocean-droplet-hosting.md)), independent of which other sprint is in progress |

## Goal

Get the nearly empty application from Sprint 01 running on the real server, on the real domain,
over HTTPS, restarting by itself after a reboot, and deployable with one command.

This sprint is second rather than last on purpose. Server administration is the part of this
project the developer has not done before, and the worst time to learn it is the week before
launch with six sprints of code on top obscuring every error message. Right now the application
is a home page and a health endpoint, so anything that breaks is the server, not the code.

Budget more time than a normal sprint. It is a week of work only if nothing surprises you, and
something will.

This sprint waited for a Turkmentelecom VDS that never got a purchase date; hosting has moved to
a DigitalOcean droplet in Singapore instead ([ADR-0019](../adr/0019-digitalocean-droplet-hosting.md)).
Sprints 03-06 were built and tested on localhost in the meantime and are already shipped there.
Task 9 exists for exactly that case.

## You can now…

…send someone a link and have them see the site.

## Tasks

### 0. Finish answering R4

The Singapore droplet already loads from inside Turkmenistan (2026-09-25). What is left: from a
phone there, on mobile data and on a home connection, time the download of a large test file
served from the droplet, and once the domain exists (task 1), check it resolves from there too.
Port 80 is open on a droplet by default, so Let's Encrypt's HTTP challenge will work (task 6).

**Done when:** the download times and the domain check are written into
[`../04-risks-and-research.md`](../04-risks-and-research.md) with a date.

### 1. Domain

Register the domain ([ADR-0012](../adr/0012-foreign-domain-registrar.md)), point an A record at
the droplet's IPv4 address, enable auto-renew and registrar lock, and put the renewal date in a calendar with a
reminder. A library that disappears because a renewal email was missed is an avoidable
embarrassment.

**Done when:** `dig +short <domain>` returns the droplet's address from a machine in Turkmenistan.

### 2. Server baseline

The droplet is created with Ubuntu LTS and your laptop's SSH public key, so the first login is
`ssh root@<droplet-ip>` with no password. Create an unprivileged `kitaphana` user. Install Python, nginx, git, sqlite3, certbot and
`poppler-utils` (Sprint 04 renders book covers with its `pdftoppm`). Set up
the directory layout: application at `/srv/kitaphana`, media outside it, backups outside it.
Enable a firewall allowing only SSH, 80 and 443 — `ufw` on the server, or a DigitalOcean Cloud
Firewall attached to the droplet; one of the two, written down, not both half-configured. Disable
SSH password authentication and root login once the `kitaphana` user can log in with the key.

**Done when:** you can log in as the new user with a key, password SSH and root SSH are
refused, and the firewall is active with only those three ports open.

### 3. Application on the server

Clone the repository with a read-only deploy key, create a virtual environment, install
dependencies, write the production `.env` — with a real secret key and **dev-OTP off** — and run
the migrations.

**Done when:** `uvicorn` started by hand on the server serves `/health` over localhost with the
right migration number.

### 4. systemd service

A `kitaphana.service` unit running uvicorn as the `kitaphana` user, with `Restart=always`, bound
to localhost only, enabled at boot. Keep the unit file in the repository and symlink or copy it
into place, so it is version-controlled rather than existing only on the server
([ADR-0004](../adr/0004-systemd-and-nginx-no-docker.md)).

**Done when:** `systemctl status kitaphana` shows active, `journalctl -u kitaphana` shows the
logs, killing the process brings it straight back, and **rebooting the server brings the site
back with no intervention**. Actually reboot it — this is the step most often assumed rather
than tested.

### 5. nginx

A site configuration that proxies to uvicorn, serves `/static/` directly from disk, sets a
sensible upload size limit (large enough for the biggest PDF you expect), and defines the
`internal` location for media that [ADR-0014](../adr/0014-x-accel-redirect-for-downloads.md)
needs.

> **Carried in from Sprint 06 (2026-09-23):** the app sends `X-Accel-Redirect:
> /_protected/books/ab/cd/<hash>.pdf`, so the location must be exactly
>
> ```nginx
> location /_protected/ {
>     internal;
>     alias /path/to/MEDIA_DIR/;   # trailing slashes on both, or paths join wrongly
> }
> ```
>
> and `.env` on the server must have `DOWNLOADS_VIA_NGINX=true` (the default; `.env.example`
> sets it to false for development). The prefix lives in `app/downloads.py` as `ACCEL_PREFIX`;
> if downloads 404 after a deployment, compare the two first. In the catch-up pass, check that
> `curl https://<domain>/_protected/...` gives 404, that a download arrives complete with the
> book's title as its file name, and that one interrupted and resumed on a phone completes.

Turn on `gzip` for HTML and CSS: a catalogue page is 18 KB of HTML but 3.4 KB gzipped, and the
stylesheet 30 KB but 6.6 KB, which matters on metered connections (measured in Sprint 05).

Set `client_max_body_size` a little above `MAX_UPLOAD_MB` (default 200 MB), or nginx refuses
large admin uploads before the app sees them. `/covers/` can be aliased to `MEDIA_DIR/covers/`
so nginx serves cover images directly; the app's own `/covers/` route is the local fallback.

Set `proxy_set_header X-Forwarded-For $remote_addr;` and `X-Forwarded-Proto $scheme` on the
proxied location. Sprint 03's per-address rate limit on login codes reads the client address,
which uvicorn only takes from that header when the request comes from 127.0.0.1 (its default
`--forwarded-allow-ips`). Without it every reader appears to come from 127.0.0.1 and one busy
hour locks everyone out of logging in at once.

**Done when:** the site answers on port 80 through nginx, static files are served by nginx
rather than the application, `nginx -t` passes, and a code request logs the real client
address in `otp_codes.request_ip`, not 127.0.0.1.

### 6. TLS

Obtain a certificate with certbot, redirect HTTP to HTTPS, and confirm the renewal timer is
active.

**Done when:** `https://<domain>` has a valid certificate, HTTP redirects to it, and
`certbot renew --dry-run` succeeds.

### 7. Deploy script

`deploy.sh` in the repository: pull, install dependencies, run migrations, restart the service,
check `/health`. It should stop on the first error rather than carrying on
([ADR-0005](../adr/0005-git-pull-deploy.md)).

**Done when:** a trivial change committed locally and pushed is live after running one command
on the server, and the script reports the new version from `/health`.

### 8. Write down how the server was built

Append to this document the actual commands used, as they were run. Not a tutorial — a record,
so that rebuilding the server after a disaster is replaying a list instead of remembering a
week.

**Done when:** someone following only these notes could rebuild the server from a fresh image.

### 9. Catch-up verification

Deploy whatever has been built locally in the meantime, then re-run the "Done when" checklist of
every sprint from 03 onward that reports itself shipped, against the real server this time —
not as a formality, but because things that only exist in production (real TLS, real network
latency to Turkmenistan, nginx actually serving downloads via
[ADR-0014](../adr/0014-x-accel-redirect-for-downloads.md), a real reboot) have not been checked
against any of that code yet ([ADR-0017](../adr/0017-local-dev-with-placeholder-fixtures.md)).

**Done when:** every already-shipped sprint's acceptance checklist has been re-verified against
`https://<domain>`, and any gap found is written down and fixed before this sprint is marked
done — not deferred again.

## Done when (sprint acceptance)

- [ ] `https://<domain>` serves the home page with a valid certificate.
- [ ] The site survives `sudo reboot` with no manual steps.
- [ ] Deploying is one command and takes under a minute.
- [ ] Only SSH, 80 and 443 are open; SSH is key-only.
- [ ] The uvicorn process is not reachable from outside except through nginx.
- [ ] The server build is written down.
- [ ] Every sprint shipped locally before this one has been re-verified against the live server.

## Tests

Mostly manual, because what is being tested is a machine rather than a function.

- From a phone in Turkmenistan, the site loads and a book downloads (R4).
- Reboot and confirm recovery without intervention.
- `curl -I http://<domain>` returns a redirect to HTTPS.
- `curl https://<domain>/health` returns the deployed migration number.
- Stop the application and confirm nginx returns an error page rather than hanging.
- Confirm `https://<domain>/media/anything` is not served — the `internal` location must not be
  publicly reachable even before it is used.

## Files this sprint creates

`deploy.sh` · `deploy/kitaphana.service` · `deploy/nginx-kitaphana.conf` · notes appended to
this document

## No-gos

- No CI, no automated deployment on push. Deploying stays a deliberate act.
- No Docker.
- No monitoring or alerting stack — log inspection is enough until Sprint 08.
- No performance tuning. Worker counts get revisited in Sprint 08 with something real to measure.
- No features. If this sprint ships a feature, it was not focused enough.

## References

[ADR-0004](../adr/0004-systemd-and-nginx-no-docker.md) ·
[ADR-0005](../adr/0005-git-pull-deploy.md) ·
[ADR-0012](../adr/0012-foreign-domain-registrar.md) ·
[ADR-0014](../adr/0014-x-accel-redirect-for-downloads.md) ·
[ADR-0017](../adr/0017-local-dev-with-placeholder-fixtures.md) ·
[ADR-0019](../adr/0019-digitalocean-droplet-hosting.md)
