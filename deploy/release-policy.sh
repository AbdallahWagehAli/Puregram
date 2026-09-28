#!/usr/bin/env bash
# Puregram release for the per-account rules model (ADR-002).
#
# Order matters: server first (it also answers the OLD device protocol, so
# un-updated handsets keep working), then the clients, then the site.
#
# Usage (from the repo root, Git Bash):
#   bash deploy/release-policy.sh server
#   bash deploy/release-policy.sh apk      (retired: Android ships through Google Play)
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
# Backups live OUTSIDE the web root: anything under $WEB can be fetched by
# anyone who guesses its name, and dated names are easy to guess.
BAK_DOWNLOADS="/var/backups/puregram-downloads"
BAK_SITE="/var/backups/puregram-site"
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
  # review relay page under r/.
  step "site -> $WEB (pages + assets/css/js/img; never --delete on the web root)"
  $SSH "install -d -m 700 $BAK_SITE && mkdir -p $BAK_SITE/site-$TS && cp -pr $WEB/index.html $WEB/privacy.html $WEB/terms.html $WEB/assets $WEB/css $WEB/js $WEB/img $BAK_SITE/site-$TS/ 2>/dev/null || true"
  tar -C "$ROOT/site" -czf - index.html privacy.html terms.html assets css js img \
    | $SSH "tar -C $WEB -xzf - && chown -R www-data:www-data $WEB/index.html $WEB/privacy.html $WEB/terms.html $WEB/assets $WEB/css $WEB/js $WEB/img && ls -la $WEB/assets/icons/"
}

deploy_apk() {
  # Retired 2026-09-28: Android ships through Google Play only. The direct APK
  # is no longer hosted, /download/puregram.apk redirects to the store listing
  # (nginx), and /v1/android/version answers 404 so old installs stay quiet.
  # The sideload signing kit (sign-sideload-apk.sh + lineage) is kept in case
  # direct distribution ever returns.
  echo "refusing: Android is distributed through Google Play only (see deploy_apk in $0)."
  exit 1
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
  $SSH "install -d -m 700 $BAK_DOWNLOADS && cd $WEB/download && (cp -p puregram-desktop.exe $BAK_DOWNLOADS/puregram-desktop.exe.bak-$TS || true) && (cp -p puregram-desktop-win64.zip $BAK_DOWNLOADS/puregram-desktop-win64.zip.bak-$TS || true) && mv -f puregram-desktop.exe.new puregram-desktop.exe && mv -f puregram-desktop-win64.zip.new puregram-desktop-win64.zip && chown www-data:www-data puregram-desktop.exe puregram-desktop-win64.zip && ls -la puregram-desktop.exe puregram-desktop-win64.zip"
  echo "device_update.py must advertise _DESKTOP_SHA256=$esha"
}

verify() {
  step "live verification"
  echo -n "health:    "; curl -s https://puregram.app/control/health; echo
  curl -s -o /dev/null -w 'rules (401 expected):  %{http_code}
' 'https://puregram.app/control/v1/rules?tg_user_id=1'
  curl -s -o /dev/null -w 'old policy (404 expected): %{http_code}
' https://puregram.app/control/v1/policy
  echo -n "android (404 expected): "; curl -s -o /dev/null -w '%{http_code}
' https://puregram.app/control/v1/android/version
  echo -n "desktop:   "; curl -s "https://puregram.app/control/v1/desktop/version?app=telegram_desktop"; echo
  # HEAD only: the exe alone is over 200 MB.
  echo -n "apk (302 to the store expected): "; curl -sI -o /dev/null -w '%{http_code} %{redirect_url}
' https://puregram.app/download/puregram.apk
  echo -n "exe:       "; curl -sI -o /dev/null -w '%{http_code}
' https://puregram.app/download/puregram-desktop.exe
  echo -n "zip:       "; curl -sI -o /dev/null -w '%{http_code}
' https://puregram.app/download/puregram-desktop-win64.zip
  echo -n "dot paths hidden (404 expected): "; curl -sI -o /dev/null -w '%{http_code}
' https://puregram.app/.anything
  echo -n "site links the store (want >0): "; curl -s https://puregram.app/ | grep -c 'play.google.com/store/apps/details?id=app.puregram' || true
  echo -n "site links an apk (want 0): "; curl -s https://puregram.app/ | grep -c 'puregram\.apk\|puregram-control' || true
}

case "${1:-}" in
  server)  deploy_server ;;
  site)    deploy_site ;;
  apk)     deploy_apk "${2:?apk path}" ;;
  desktop) deploy_desktop "${2:?exe}" "${3:?zip}" ;;
  verify)  verify ;;
  *) sed -n '2,17p' "$0"; exit 1 ;;
esac
