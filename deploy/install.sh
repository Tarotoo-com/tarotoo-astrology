#!/usr/bin/env bash
# Install or update the Tarotoo astrology service on the server.
#   sudo bash deploy/install.sh            (run from a checkout of this repo)
# Needs: python3 (3.10+) with venv, nginx already serving tarotoo.com, systemd.
# Safe to re-run: it updates the code and restarts the service.
set -euo pipefail

APP_DIR=/var/www/tarotoo-astrology
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE=tarotoo-astrology

echo "== code -> $APP_DIR"
mkdir -p "$APP_DIR"
rsync -a --delete --exclude .venv --exclude .git --exclude scratch --exclude __pycache__ "$REPO_DIR"/ "$APP_DIR"/

echo "== python environment"
if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
    python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "== self-check (reference chart)"
cd "$APP_DIR"
LIBEPHEMERIS_IERS_AUTO_DOWNLOAD=false LIBEPHEMERIS_LOG_LEVEL=ERROR "$APP_DIR/.venv/bin/python" - <<'PY'
from datetime import date
from app.chart import build_chart
from app.places import PlaceIndex
c = build_chart(name="", birth_date=date(1990, 6, 12), hour=14, minute=40, lat=52.52437, lng=13.41053,
                tz="Europe/Berlin", place_label="Berlin", country_code="DE")
sun = next(p for p in c["planets"] if p["name"] == "Sun")
assert (sun["sign"], sun["position_text"]) == ("Gemini", "21°17′"), sun
assert c["angles"]["ascendant"]["position_text"] == "9°44′", c["angles"]
places = PlaceIndex()
assert places.search("berlin")[0].name == "Berlin", "place index"
print(f"chart OK, {len(places.places)} places")
PY

echo "== permissions"
chown -R www-data:www-data "$APP_DIR"

echo "== systemd"
install -m 644 "$APP_DIR/deploy/$SERVICE.service" /etc/systemd/system/$SERVICE.service
systemctl daemon-reload
systemctl enable --quiet $SERVICE
systemctl restart $SERVICE
sleep 2
systemctl is-active --quiet $SERVICE || { journalctl -u $SERVICE -n 30 --no-pager; exit 1; }
curl -fsS http://127.0.0.1:8781/health && echo

cat <<EOF

Service running on 127.0.0.1:8781.
nginx: add the limit_req_zone line to the http {} context and the location block from
  $APP_DIR/deploy/nginx-location.conf
to the tarotoo.com server block, then: nginx -t && systemctl reload nginx
Check: curl -s https://tarotoo.com/astro/health
EOF
