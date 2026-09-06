#!/usr/bin/env bash
# Puregram release for the per-account rules model (ADR-002).
#
# Order matters: server first (it also answers the OLD device protocol, so
# un-updated handsets keep working), then the clients, then the site.
#
# Usage (from the repo root, Git Bash):
#   bash deploy/release-policy.sh server
#   bash deploy/release-policy.sh apk <path/to/app.apk>
#   bash deploy/release-policy.sh desktop <Puregram.exe> <zip>
#   bash deploy/release-policy.sh site
#   bash deploy/release-policy.sh verify
#
# Transfers use `tar` over ssh — Git Bash has no rsync. The SSH identity comes
# from ~/.ssh/config (Host puregram.app).
set -euo pipefail

# The local resolver has been flaky; allow an explicit host/IP override.
HOST="${PUREGRAM_HOST:-root@puregram.app}"
SSH="ssh ${PUREGRAM_SSH_OPTS:-} $HOST"
WEB="/var/www/puregram.app"
SRV="/opt/puregram-server"
TS="$(date +%Y%m%d-%H%M%S)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

step() { printf '\n\033[1;32m== %s\033[0m\n' "$*"; }

deploy_server() {
  step "backup $SRV -> $SRV.bak-$TS"
  $SSH "cp -a $SRV $SRV.bak-$TS && ls -d $SRV.bak-$TS"

  step "upload server/ (keeping .env and venv)"
  # `app/` is wiped first so deleted modules really disappear; .env and venv are
  # never in the tarball and never removed.
  tar -C "$ROOT/server" -czf - \
      --exclude=.env --exclude=venv --exclude=__pycache__ --exclude='*.pyc' . \
    | $SSH "rm -rf $SRV/app && tar -C $SRV -xzf - && chown -R deploy:deploy $SRV"

  step "install deps + restart"
  $SSH "cd $SRV && venv/bin/pip install -q -r requirements.txt && systemctl restart puregram-server && sleep 3 && systemctl is-active puregram-server"

  step "health"
  $SSH "curl -s http://127.0.0.1:8020/health; echo; curl -s -o /dev/null -w 'GET /v1/rules (401 = wired) -> %{http_code}
' 'http://127.0.0.1:8020/v1/rules?tg_user_id=1'"
  $SSH "journalctl -u puregram-server -n 25 --no-pager | tail -10"
}

deploy_site() {
  # The pages AND what they load. Shipping only the HTML is why a new logo could
  # sit in the repo while the site kept serving the old one — assets/ was never
  # in the tarball. Still no --delete: the web root also holds download/ and the
  # dated backups.
  step "site -> $WEB (pages + assets/css/js/img; never --delete on the web root)"
  $SSH "mkdir -p $WEB/.bak-site-$TS && cp -pr $WEB/index.html $WEB/privacy.html $WEB/terms.html $WEB/assets $WEB/css $WEB/js $WEB/.bak-site-$TS/ 2>/dev/null || true"
  tar -C "$ROOT/site" -czf - index.html privacy.html terms.html assets css js img \
    | $SSH "tar -C $WEB -xzf - && chown -R www-data:www-data $WEB/index.html $WEB/privacy.html $WEB/terms.html $WEB/assets $WEB/css $WEB/js $WEB/img && ls -la $WEB/assets/icons/"
}

deploy_apk() {
  local apk="$1"
  [[ -f "$apk" ]] || { echo "no such apk: $apk"; exit 1; }
  local sha; sha="$(sha256sum "$apk" | cut -d' ' -f1)"
  step "apk $(basename "$apk") sha256=$sha -> $WEB/download/puregram.apk"
  cat "$apk" | $SSH "cat > $WEB/download/puregram.apk.new"
  $SSH "cd $WEB/download && echo '$sha  puregram.apk.new' | sha256sum -c - && cp -p puregram.apk puregram.apk.bak-$TS && mv -f puregram.apk.new puregram.apk && chown www-data:www-data puregram.apk && ls -la puregram.apk"
  echo "device_update.py must advertise _ANDROID_SHA256=$sha"
}

deploy_desktop() {
  local exe="$1" zip="$2"
  [[ -f "$exe" && -f "$zip" ]] || { echo "need <exe> <zip>"; exit 1; }
  local esha zsha
  esha="$(sha256sum "$exe" | cut -d' ' -f1)"
  zsha="$(sha256sum "$zip" | cut -d' ' -f1)"
  step "desktop exe sha256=$esha -> $WEB/download/"
  cat "$exe" | $SSH "cat > $WEB/download/puregram-desktop.exe.new"
  cat "$zip" | $SSH "cat > $WEB/download/puregram-desktop-win64.zip.new"
  $SSH "cd $WEB/download && echo '$esha  puregram-desktop.exe.new' | sha256sum -c - && echo '$zsha  puregram-desktop-win64.zip.new' | sha256sum -c -"
  $SSH "cd $WEB/download && (cp -p puregram-desktop.exe puregram-desktop.exe.bak-$TS || true) && (cp -p puregram-desktop-win64.zip puregram-desktop-win64.zip.bak-$TS || true) && mv -f puregram-desktop.exe.new puregram-desktop.exe && mv -f puregram-desktop-win64.zip.new puregram-desktop-win64.zip && chown www-data:www-data puregram-desktop.exe puregram-desktop-win64.zip && ls -la puregram-desktop.exe puregram-desktop-win64.zip"
  echo "device_update.py must advertise _DESKTOP_SHA256=$esha"
}

verify() {
  step "live verification"
  echo -n "health:    "; curl -s https://puregram.app/control/health; echo
  curl -s -o /dev/null -w 'rules (401 expected):  %{http_code}
' 'https://puregram.app/control/v1/rules?tg_user_id=1'
  curl -s -o /dev/null -w 'old policy (404 expected): %{http_code}
' https://puregram.app/control/v1/policy
  echo -n "android:   "; curl -s https://puregram.app/control/v1/android/version; echo
  echo -n "desktop:   "; curl -s "https://puregram.app/control/v1/desktop/version?app=telegram_desktop"; echo
  curl -s -o /dev/null -w 'apk:       %{http_code}  %{size_download} bytes
' https://puregram.app/download/puregram.apk
  curl -s -o /dev/null -w 'exe:       %{http_code}  %{size_download} bytes
' https://puregram.app/download/puregram-desktop.exe
  curl -s -o /dev/null -w 'zip:       %{http_code}  %{size_download} bytes
' https://puregram.app/download/puregram-desktop-win64.zip
  echo -n "site says 'your rules': "; curl -s https://puregram.app/ | grep -c 'your rules'
  echo -n "site supervision leftovers (want 0): "; curl -s https://puregram.app/ | grep -c 'puregram-control\|#control' || true
}

case "${1:-}" in
  server)  deploy_server ;;
  site)    deploy_site ;;
  apk)     deploy_apk "${2:?apk path}" ;;
  desktop) deploy_desktop "${2:?exe}" "${3:?zip}" ;;
  verify)  verify ;;
  *) sed -n '2,17p' "$0"; exit 1 ;;
esac
