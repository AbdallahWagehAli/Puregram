# Puregram — Google Play submission package

Everything needed to publish Puregram (`app.puregram`, 13.0.0 / 67729) to Google Play.

```
play-assets/
├── puregram-13.0.0-67729.aab        # the signed Android App Bundle to upload
├── POLICY-ASSESSMENT.md             # policy risk + verdict + Console checklist
├── keystore/
│   ├── puregram-upload.keystore     # UPLOAD KEY — back this up, never commit/share
│   └── keystore-upload.properties   # its passwords (secret)
├── listing/
│   ├── store-listing.md             # title, short/full desc (EN+AR), ASO, category
│   └── data-safety-and-content-rating.md
├── graphics/
│   ├── icon-512.png                 # 512×512 store icon (green Puregram mark)
│   └── feature-graphic-1024x500.png
└── screenshots/
    ├── real/                        # 7 REAL device captures (720×1600, populated) — use these
    └── mockups/                     # PIL mockups (optional fallback)
```

---

## 1) The app bundle

> **Upload note:** the AAB is 116 MB, over the 10 MB cap of any automated browser upload —
> the Play Console step must be done by hand with the native file picker.

- **File:** `puregram-13.0.0-67729.aab` (sha256 `4087248f47a639f9…`) (≈ 116 MB; includes full native debug symbols for
  Play crash symbolication — Google strips them for delivery, final download is far smaller).
- **Built with:**
  `./gradlew :TMessagesProj_AppStandalone:bundleAfatStandalone` with Gradle injected-signing
  pointing at the upload key (no source changes; the website-APK signing config is untouched).
- **Identity:** package `app.puregram`, versionName **13.0.0**, versionCode **67729**,
  arm64-v8a. per-account rules model (ADR-002: people open, channels/bots/groups closed until the user allows them, block is permanent), ad-removal (`HIDE_SPONSORED_MESSAGES`), green brand
  and clean green launcher icon — all preserved.
- **Signer (upload cert) SHA-256:**
  `E9:B3:A7:CA:C3:C4:A9:CA:64:A7:FA:3A:8B:C0:4F:08:CC:F0:60:3F:84:52:3D:32:6C:C1:90:32:3D:07:D4:80`
  (verified on the AAB).

To rebuild identically:
```bash
cd telegram/telegram-android
P=../../play-assets/keystore/keystore-upload.properties
./gradlew :TMessagesProj_AppStandalone:bundleAfatStandalone \
  -Pandroid.injected.signing.store.file="$(grep '^storeFile=' $P|cut -d= -f2-)" \
  -Pandroid.injected.signing.store.password="$(grep '^storePassword=' $P|cut -d= -f2-)" \
  -Pandroid.injected.signing.key.alias=puregram-upload \
  -Pandroid.injected.signing.key.password="$(grep '^keyPassword=' $P|cut -d= -f2-)" \
  --console=plain
# output: TMessagesProj_AppStandalone/build/outputs/bundle/afatStandalone/*.aab
```

---

## 2) Signing & Play App Signing — READ THIS

There are **two different keys** in play, and this matters for update continuity.

| Channel | Signing key | Notes |
|---|---|---|
| **Website APK** (`puregram.app/download/puregram.apk`) | the old **open-source** `release.keystore` (`SHA-256 a08d7dc3…`, public passwords) | unchanged — existing sideload users keep updating in place |
| **Google Play** (this AAB) | a **new private upload key** (`puregram-upload.keystore`, generated fresh, strong password) | Play re-signs for delivery with the **app signing key** |

### Recommended enrollment: Play App Signing with a Google-generated app signing key
When you create the production release, **let Google generate and hold the app signing key**.
You upload AABs signed with your **upload key**; Google re-signs the delivered APKs with the
app signing key it manages.

**Why this (and not reusing the old key):** the website's `release.keystore` uses *public*
open-source passwords — anyone could sign an APK with it. Using it as the Play app signing key
would import that weakness. A fresh upload key + Google-held app signing key is the secure path.

### Continuity implication (important, document for yourself)
Because Play will distribute with a **different** signature than the website APK:
- A user who sideloaded the website APK **cannot** update to the Play build in place (different
  signature) — switching channels needs an uninstall/reinstall (a one-time data reset).
- Going forward, **Play becomes the trusted, secure channel.** The website APK remains a
  separate, lower-trust channel (public key). Decide whether to eventually point new users to
  Play only.
- This does **not** break the website channel — that keeps working with `a08d7dc3…`.

### Keep the upload key safe
- **Back up `keystore/puregram-upload.keystore` + its password** (offline, in a password
  manager). If you lose the upload key you must ask Google to reset it (support flow); if you
  lose it *and* aren't on Play App Signing you can never update the app.
- Both `*.keystore` and the properties file are outside any git repo here and must never be
  committed or shared.

---

## 3) Listing, policy, graphics
- **Copy:** `listing/store-listing.md` — recommended title `Puregram: Focused Messenger` (27
  chars), short + full EN/AR descriptions, ASO, category **Communication**.
- **Data Safety + Content Rating:** `listing/data-safety-and-content-rating.md` — field-by-field.
- **Policy verdict + full Console checklist:** `POLICY-ASSESSMENT.md`.
- **Icon / feature graphic:** `graphics/` (green Puregram brand, no Telegram marks).
- **Screenshots:** `screenshots/real/` — 7 REAL device captures from build 12.8.7/67619
  (Puregram title, Settings ▸ Puregram + Puregram version footer, green QR, blocked toast,
  "Allowed to me" populated, "Users I supervise", per-chat approval toggles). See
  `screenshots/README.md`. The in-app UI and these screenshots are now fully Puregram-branded,
  which also satisfies the "no Telegram on identity surfaces" part of the policy Top-5.

---

## 4) Policy verdict (summary)

**NEEDS-CHANGES → GO after the Top 5.** Concept is allowed (unofficial OSS client + consent-based
parental control + ad-free). Before submitting:
1. Strip "Telegram" from all identity surfaces (title/icon/feature/screenshots) — keep nominative
   references only in the body.
2. Add a persistent "This device is supervised" indicator on supervised accounts.
3. Provide reviewer-testable access (demo/review mode) for the login-gated supervision flow.
4. Make Data Safety exactly match the privacy policy (all four items, linked-to-identity = Yes).
5. First-run + listing "unofficial / not affiliated" disclaimer + GPL-2.0 open-source attribution;
   remove any spy/covert wording; target audience 18+.

See `POLICY-ASSESSMENT.md` for the full reasoning and the numbered Console upload steps.
