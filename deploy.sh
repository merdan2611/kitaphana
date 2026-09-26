#!/usr/bin/env bash
# Deploy the latest main to this server (ADR-0005). Run on the server as root:
#
#     /srv/kitaphana/deploy.sh
#
# Pulls, installs dependencies, applies migrations, installs the service and nginx files from
# deploy/, restarts the app and checks /health. Stops at the first error.
set -euo pipefail

APP=/srv/kitaphana
as_app() { sudo -u kitaphana -H "$@"; }

cd "$APP"
if [ -n "$(as_app git status --porcelain --untracked-files=no)" ]; then
    echo "The server's checkout has local changes; understand them before deploying:" >&2
    as_app git status --short >&2
    exit 1
fi

echo "==> Pulling"
as_app git pull --ff-only
echo "==> Installing dependencies"
as_app .venv/bin/pip install -q --disable-pip-version-check -r requirements.txt
echo "==> Migrating"
as_app .venv/bin/python -m scripts.migrate

echo "==> Installing service and nginx configuration"
install -m 644 deploy/kitaphana.service          /etc/systemd/system/kitaphana.service
install -m 644 deploy/nginx-kitaphana.conf       /etc/nginx/sites-available/kitaphana
install -m 644 deploy/nginx-kitaphana-proxy.conf /etc/nginx/snippets/kitaphana-proxy.conf
ln -sf /etc/nginx/sites-available/kitaphana /etc/nginx/sites-enabled/kitaphana
rm -f /etc/nginx/sites-enabled/default
systemctl daemon-reload
nginx -t -q
systemctl reload nginx

echo "==> Restarting"
systemctl enable -q kitaphana
systemctl restart kitaphana

for _ in $(seq 1 20); do
    if health=$(curl -fsS http://127.0.0.1:8000/health 2>/dev/null); then
        echo "==> Live: $(as_app git log -1 --format='%h %s')"
        echo "    /health: $health"
        exit 0
    fi
    sleep 0.5
done
echo "The app did not answer /health within 10 seconds. Look at: journalctl -u kitaphana -n 50" >&2
exit 1
