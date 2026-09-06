#!/usr/bin/env bash
# Sign a Play AAB with the Puregram upload key.
#
# Gradle signs every build with the sideload key (CN=Android Developer, the upstream
# Telegram cert) because that is what existing sideloaded users update against. Google
# Play expects a different, Puregram-only upload key, so the bundle is re-signed here
# after the build. Getting this wrong is silent — the build succeeds and Play rejects
# the upload with a signature mismatch — so the script verifies the result.
#
# Usage: deploy/sign-play-aab.sh <in.aab> <out.aab>
set -euo pipefail

readonly EXPECTED_SHA256='E9:B3:A7:CA:C3:C4:A9:CA:64:A7:FA:3A:8B:C0:4F:08:CC:F0:60:3F:84:52:3D:32:6C:C1:90:32:3D:07:D4:80'
readonly KEY_PROPS="${PUREGRAM_UPLOAD_PROPS:-$HOME/Desktop/Puregram-secrets/keystore/keystore-upload.properties}"
readonly KEYSTORE="${PUREGRAM_UPLOAD_KEYSTORE:-$HOME/Desktop/Puregram-secrets/keystore/puregram-upload.keystore}"

if [ $# -ne 2 ]; then
    echo "usage: $0 <in.aab> <out.aab>" >&2
    exit 2
fi
readonly IN_AAB="$1"
readonly OUT_AAB="$2"

for f in "$IN_AAB" "$KEY_PROPS" "$KEYSTORE"; do
    [ -f "$f" ] || { echo "missing: $f" >&2; exit 1; }
done

# The properties file is the single source of truth for the alias and passwords.
key_prop() { sed -n "s/^$1=//p" "$KEY_PROPS" | tr -d '\r'; }
readonly ALIAS="$(key_prop keyAlias)"
readonly STORE_PASS="$(key_prop storePassword)"
readonly KEY_PASS="$(key_prop keyPassword)"
[ -n "$ALIAS" ] && [ -n "$STORE_PASS" ] || { echo "could not read alias/password from $KEY_PROPS" >&2; exit 1; }

# jarsigner adds a signature, it does not replace one, so the gradle signature goes first.
# base/root/META-INF/* are ordinary app resources and must survive.
readonly WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
python - "$IN_AAB" "$WORK/unsigned.aab" <<'PY'
import sys, zipfile
src, dst = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        head, _, tail = item.filename.rpartition("/")
        if head == "META-INF" and tail.upper().endswith((".SF", ".RSA", ".DSA", ".EC")):
            continue
        if item.filename == "META-INF/MANIFEST.MF":
            continue
        zout.writestr(item, zin.read(item.filename))
PY

jarsigner -keystore "$KEYSTORE" \
    -storepass "$STORE_PASS" -keypass "$KEY_PASS" \
    -sigalg SHA256withRSA -digestalg SHA-256 \
    -signedjar "$OUT_AAB" "$WORK/unsigned.aab" "$ALIAS" > /dev/null

readonly ACTUAL="$(keytool -printcert -jarfile "$OUT_AAB" | sed -n 's/.*SHA256: //p' | head -1 | tr -d '[:space:]')"
if [ "$ACTUAL" != "$(echo "$EXPECTED_SHA256" | tr -d '[:space:]')" ]; then
    echo "SIGNATURE MISMATCH" >&2
    echo "  expected $EXPECTED_SHA256" >&2
    echo "  got      $ACTUAL" >&2
    rm -f "$OUT_AAB"
    exit 1
fi

echo "signed with the Puregram upload key: $OUT_AAB"
