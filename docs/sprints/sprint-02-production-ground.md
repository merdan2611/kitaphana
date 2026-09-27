# Sprint 02 — Production ground

| | |
|---|---|
| **Status** | 🟡 In progress (started 2026-09-26) |
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
dependencies, write the production `.env` — with a real secret key and **dev-OTP on for Phase 1** (see the decisions under the server build notes) — and run
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

- [x] `https://<domain>` serves the home page with a valid certificate. *Let's Encrypt, valid to
      2026-12-26; behind the pre-launch password gate.*
- [x] The site survives `sudo reboot` with no manual steps. *Back in 25 s on 2026-09-27, with
      nginx, fail2ban (both jails), ufw and the certbot timer up and nothing failed.*
- [x] Deploying is one command and takes under a minute. *`./deploy.sh`, 4.8 s.*
- [x] Only SSH, 80 and 443 are open; SSH is key-only. *`ss -tlnp` shows nothing else public;
      password SSH answers `Permission denied (publickey)`.*
- [x] The uvicorn process is not reachable from outside except through nginx. *Bound to
      127.0.0.1:8000; port 8000 times out from outside.*
- [x] The server build is written down.
- [ ] Every sprint shipped locally before this one has been re-verified against the live server.
      *Waits on the developer's phone pass: the gate keeps scripted checks out, by design.*

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

## Server build notes

A record of what was actually run on the droplet (`159.65.8.186`, Ubuntu 24.04, SGP1), in
order. Replaying this list on a fresh droplet rebuilds the server. Everything runs as root.

### 2026-09-25 — baseline

```sh
apt-get update && apt-get -y upgrade
apt-get -y install nginx git python3-venv sqlite3 certbot python3-certbot-nginx ufw unattended-upgrades

# 2 GB swap, used only under memory pressure
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo "/swapfile none swap sw 0 0" >> /etc/fstab
echo "vm.swappiness=10" > /etc/sysctl.d/99-swap.conf && sysctl -p /etc/sysctl.d/99-swap.conf

# Firewall: ufw on the server, not a DigitalOcean Cloud Firewall (one of the two, not both)
ufw allow OpenSSH && ufw allow "Nginx Full" && ufw --force enable

timedatectl set-timezone Asia/Ashgabat
useradd --system --create-home --home-dir /srv/kitaphana --shell /usr/sbin/nologin kitaphana

# SSH: keys only; root by key only
printf "PermitRootLogin prohibit-password\nPasswordAuthentication no\nKbdInteractiveAuthentication no\n" \
    > /etc/ssh/sshd_config.d/10-hardening.conf
sshd -t && systemctl reload ssh

# Automatic security updates
printf 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n' \
    > /etc/apt/apt.conf.d/20auto-upgrades
reboot
```

DNS: `kitaphana.men` and `www` are A records to `159.65.8.186` on Cloudflare's nameservers,
**DNS only (grey cloud)**. The proxy stays off: Cloudflare's addresses are untested from inside
Turkmenistan, certbot's HTTP challenge is simpler without it, and the app's per-address limits
would see Cloudflare instead of readers.

### 2026-09-26 — layout

```sh
apt-get -y install poppler-utils fail2ban python3-systemd
usermod -d /var/lib/kitaphana -m kitaphana     # data home, outside the code
install -d -m 750 -o kitaphana -g kitaphana /var/lib/kitaphana/media
install -d -m 700 -o kitaphana -g kitaphana /var/lib/kitaphana/db
install -d -m 700 -o root -g root /var/backups/kitaphana
install -d -m 755 -o kitaphana -g kitaphana /srv/kitaphana
usermod -aG kitaphana www-data                 # nginx reads media through the group
```

| Path | What |
|---|---|
| `/srv/kitaphana` | the git checkout, `.venv`, `.env` (mode 600) |
| `/var/lib/kitaphana/db/kitaphana.db` | the database |
| `/var/lib/kitaphana/media` | PDFs, covers, upload spool |
| `/var/backups/kitaphana` | backups (Sprint 08) |

### 2026-09-27 — first deploy

Run on the developer's go-ahead. Three surprises, all fixed: `nginx -t` rejected `http2 on;`
(Ubuntu 24.04 ships nginx 1.24; `http2` goes on the `listen` lines instead) and the unquoted
`{2}` in the cover regex; and `systemctl enable --now fail2ban` did not load the new jail
because fail2ban was already running, so run `fail2ban-client reload` after installing it.
Certbot took about five minutes but succeeded. Live at `d59662c`, migration 6, behind the
password gate; the gate's password is not written down here.

```sh
# Code. The repository is public, so it clones over HTTPS with no deploy key; if it ever goes
# private, add a read-only deploy key for the kitaphana user instead.
sudo -u kitaphana git clone https://github.com/merdan2611/kitaphana.git /srv/kitaphana
cd /srv/kitaphana
sudo -u kitaphana python3 -m venv .venv
sudo -u kitaphana .venv/bin/pip install -r requirements.txt

# Production .env, mode 600. DEV_OTP_MODE=true for Phase 1: invite-only testing with login
# codes shown on screen (ADR-0013), decided 2026-09-26. Every page shows the dev-OTP banner.
# Turning it off is a Phase 2 exit criterion, once SMS delivery exists.
umask 077; cat > .env <<ENV
DATABASE_PATH=/var/lib/kitaphana/db/kitaphana.db
MEDIA_DIR=/var/lib/kitaphana/media
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
DEV_OTP_MODE=true
DEBUG=false
COOKIE_SECURE=true
DOWNLOADS_VIA_NGINX=true
MAX_UPLOAD_MB=200
ENV
chown kitaphana:kitaphana .env

# Certificate first: the nginx site refers to it. `certonly` leaves nginx's files alone.
certbot certonly --nginx -d kitaphana.men -d www.kitaphana.men --register-unsafely-without-email --agree-tos
certbot renew --dry-run

# Flood protection
install -m 644 deploy/fail2ban-kitaphana.local /etc/fail2ban/jail.d/kitaphana.local
install -m 644 deploy/sysctl-kitaphana.conf /etc/sysctl.d/90-kitaphana.conf && sysctl --system
ufw limit OpenSSH                              # at most 6 SSH connections per 30 s per address

# Pre-launch password gate, before deploy.sh: the nginx site refers to this file, and without it
# every page answers 500. Add a tester later with the same command minus -c.
apt-get -y install apache2-utils
htpasswd -c /etc/nginx/kitaphana.htpasswd merdan
chown root:www-data /etc/nginx/kitaphana.htpasswd && chmod 640 /etc/nginx/kitaphana.htpasswd

# Everything else — service, nginx site, migrations, restart — is deploy.sh
./deploy.sh
systemctl enable --now fail2ban && fail2ban-client reload && fail2ban-client status
```

### 2026-09-27 — checks against the live server

- `kill -9` on uvicorn: systemd had a new process answering `/health` within 4 s.
- App stopped: nginx answered `/health` with 502 in 0.8 s rather than hanging.
- `https://kitaphana.men/_protected/...` gives 404 from outside; the bare IP gets no TLS
  handshake.
- `otp_codes.request_ip` holds the phone's real address, not 127.0.0.1.
- Found only on the real nginx, and fixed: the admin home at `/admin` looped (nginx 301 to
  `/admin/`, the app 307 back); an exact `location = /admin` fixes it.
- Found only on the real nginx, and fixed: every download was a 403. nginx could not open the
  PDF because `stage()` writes it with `mkstemp`, which is owner-only whatever the umask, and
  `os.replace` kept that mode; `ingest` now makes it 0640, and the one PDF already uploaded was
  `chmod`ed by hand. Stars were not lost: the first attempt charged once, retries are free
  re-downloads.
- Downloads through nginx, after that fix: the full file arrives with the book's title as its
  name and the stored SHA-256; a `Range` request from 1 MB gives 206 and the two halves join
  into the same hash. The cover is served; `/media/…` and `/_protected/…` give 404; HTML and
  CSS go out gzipped.

Still open before this sprint ships: task 0 (download timings from a phone in Turkmenistan),
task 1's registrar lock, auto-renew and calendar reminder, and task 9's pass on a real phone —
upload, publish and download are done (above); still to do on a phone are a download
interrupted and resumed on mobile data, posting and upvoting a request, and a look at the
pages.

### Decisions that change the task list

- **Root keeps logging in, by key only** (2026-09-26). Task 2 asked for root SSH to be refused
  once another user could log in; the developer chose to keep administering as `root` with the
  laptop's key instead. Password logins stay refused, and `kitaphana` stays a no-login user that
  only runs the app. Read task 2's "root SSH is refused" as "SSH is key-only".
- **Login codes stay on screen** (2026-09-26). Task 3 asked for dev-OTP off, but with no SMS
  delivery until Phase 2 that would lock everyone out, the admin included. Phase 1 runs
  invite-only with codes on screen, as [ADR-0013](../adr/0013-dev-otp-mode.md) allows; anyone who
  knows a tester's phone number can sign in as them, so testers are told and nothing sensitive
  goes into accounts.
- **HTTPS clone, no deploy key**, because the repository is public.
- **The site sits behind a password until launch** (2026-09-27). The developer wants to test on
  the real domain before anyone else can reach it. nginx basic auth covers the whole
  `kitaphana.men` server block, with `X-Robots-Tag: noindex` sent too. `/health` and the ACME
  challenge (in the port-80 block) stay open, so the curl checks and certificate renewal still
  work. An IP allowlist was rejected because Turkmen mobile addresses are shared and keep
  changing. To launch, delete the gate lines and every `auth_basic off` block from
  `deploy/nginx-kitaphana.conf` and run `deploy.sh`.
