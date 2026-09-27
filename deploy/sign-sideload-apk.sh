#!/usr/bin/env bash
# Sign the direct-download APK (puregram.app/download/puregram.apk) with the
# Puregram sideload key, carrying a proof of rotation from the old key.
#
# Why: until 13.1.6 the direct APK was signed with the keystore that ships in
# Telegram's public repository, passwords included. Anyone could sign a
# modified app with it and Android would accept it as an update over ours.
#
# How: APK Signature Scheme v3 key rotation. The lineage file
# (deploy/puregram-sideload.lineage) is the old key vouching for the new one,
# so Android 9+ installs this APK as an ordinary update: same app data, same
# login, same ANDROID_ID, no reinstall. Once a phone has it, Android refuses
# any later APK signed only with the old key (rollback is off in the lineage).
# Android 5 to 8 still verify the v1/v2 signature made with the old key; the
# server has seen no such device since July 2026.
#
# Gradle keeps signing with the old key; this script re-signs its output.
# The Play AAB never comes here: it has its own upload key (sign-play-aab.sh).
#
# Usage: deploy/sign-sideload-apk.sh <gradle-built.apk> <out.apk>
set -euo pipefail

readonly NEW_CERT_SHA256='e8e62c9ae8fd5ddf9712e3766c4e406a63ddddda329803031266933d82f9bf07'
readonly OLD_CERT_SHA256='a08d7dc323ddf71ef3201944397e0d3cce7d40847263e11f328b68bbe19229ab'
# Android 9 (API 28) is the first release that understands v3 rotation. Left
# unset, apksigner would target Android 13+ only (v3.1) and leave Android 9 to
# 12, a third of our devices, on the old key.
readonly ROTATION_MIN_SDK=28

readonly ROOT="$(cd "$(dirname "$0")/.." && pwd)"
readonly SECRETS="${PUREGRAM_SECRETS:-$HOME/Desktop/Puregram-secrets/keystore}"
readonly NEW_PROPS="$SECRETS/keystore-sideload.properties"
readonly NEW_KEYSTORE="$SECRETS/puregram-sideload.keystore"
readonly OLD_KEYSTORE="$ROOT/telegram/telegram-android/TMessagesProj/config/release.keystore"
readonly LINEAGE="$ROOT/deploy/puregram-sideload.lineage"
readonly BUILD_TOOLS="${ANDROID_BUILD_TOOLS:-$LOCALAPPDATA/Android/Sdk/build-tools/36.1.0}"
readonly APKSIGNER="$BUILD_TOOLS/apksigner.bat"

if [ $# -ne 2 ]; then
    echo "usage: $0 <gradle-built.apk> <out.apk>" >&2
    exit 2
fi
readonly IN_APK="$1"
readonly OUT_APK="$2"

for f in "$IN_APK" "$NEW_PROPS" "$NEW_KEYSTORE" "$OLD_KEYSTORE" "$LINEAGE" "$APKSIGNER"; do
    [ -f "$f" ] || { echo "missing: $f" >&2; exit 1; }
done

key_prop() { sed -n "s/^$1=//p" "$NEW_PROPS" | tr -d '\r'; }
NEW_ALIAS="$(key_prop keyAlias)"
[ -n "$NEW_ALIAS" ] || { echo "no keyAlias in $NEW_PROPS" >&2; exit 1; }
# Passwords go through the environment, never the command line (visible in
# the process list) and never the terminal.
export PUREGRAM_OLD_PASS='android'   # public: it is in Telegram's repository
PUREGRAM_NEW_PASS="$(key_prop storePassword)"
export PUREGRAM_NEW_PASS
[ -n "$PUREGRAM_NEW_PASS" ] || { echo "no storePassword in $NEW_PROPS" >&2; exit 1; }

readonly WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

"$APKSIGNER" sign \
    --in "$IN_APK" --out "$WORK/signed.apk" \
    --lineage "$LINEAGE" --rotation-min-sdk-version "$ROTATION_MIN_SDK" \
    --ks "$OLD_KEYSTORE" --ks-key-alias androidkey \
        --ks-pass env:PUREGRAM_OLD_PASS --key-pass env:PUREGRAM_OLD_PASS \
    --next-signer \
    --ks "$NEW_KEYSTORE" --ks-key-alias "$NEW_ALIAS" \
        --ks-pass env:PUREGRAM_NEW_PASS --key-pass env:PUREGRAM_NEW_PASS

# Refuse to hand over an APK unless both halves are exactly what we expect:
# Android 9+ must see our key, older Android the old one.
signer_for_sdk() {
    "$APKSIGNER" verify --print-certs --min-sdk-version "$1" --max-sdk-version "$1" "$WORK/signed.apk" \
        | sed -n 's/^Signer #1 certificate SHA-256 digest: //p' | head -1 | tr -d '[:space:]'
}
readonly MODERN="$(signer_for_sdk "$ROTATION_MIN_SDK")"
readonly LEGACY="$(signer_for_sdk 27)"
if [ "$MODERN" != "$NEW_CERT_SHA256" ]; then
    echo "WRONG SIGNER for Android 9+: $MODERN (expected $NEW_CERT_SHA256)" >&2
    exit 1
fi
# Android 5 to 8 know nothing of rotation, so they must still see the old key
# or installs there would stop updating.
if [ "$LEGACY" != "$OLD_CERT_SHA256" ]; then
    echo "WRONG SIGNER for Android 8.1 and older: $LEGACY (expected $OLD_CERT_SHA256)" >&2
    exit 1
fi
"$APKSIGNER" verify --verbose "$WORK/signed.apk" | grep -q '^Verified using v3 scheme (APK Signature Scheme v3): true' \
    || { echo "v3 signature missing" >&2; exit 1; }

mv -f "$WORK/signed.apk" "$OUT_APK"
echo "signed:  $OUT_APK"
echo "android 9+ signer: $MODERN (Puregram sideload key)"
echo "android 8.1 and older signer: $LEGACY (old key, as required)"
echo "sha256:  $(sha256sum "$OUT_APK" | cut -d' ' -f1)"
