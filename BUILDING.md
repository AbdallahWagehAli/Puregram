# Building Puregram

Puregram is built from two forks of Telegram's open-source clients plus a small
FastAPI server. Everything here is what you need to reproduce a build yourself.

## Before anything: get your own Telegram API credentials

Puregram does **not** ship an `api_id`/`api_hash` pair, and neither should any
fork you make of it. Telegram's API terms forbid publishing a pair, and a
published one gets banned — which would break the app for everyone using it.

Register your own at **<https://my.telegram.org>** → *API development tools*.
It takes a minute and is free.

### Android

Put the pair in `telegram/telegram-android/local.properties` (git ignores it):

```properties
sdk.dir=/path/to/Android/Sdk
PUREGRAM_API_ID=1234567
PUREGRAM_API_HASH=your_api_hash_here
```

`TMessagesProj/build.gradle` reads them into `BuildConfig`, and `BuildVars` reads
`BuildConfig`. A build with no pair compiles fine but cannot connect to Telegram.

### Desktop

Copy the example and fill it in (git ignores the real one):

```bash
cp telegram/api_credentials.example.bat telegram/api_credentials.bat
```

```bat
set TDESKTOP_API_ID=1234567
set TDESKTOP_API_HASH=your_api_hash_here
```

`configure_telegram.bat` sources it and refuses to run without it.

## Signing keys

No signing key is in this repository, by design. To build a release you supply
your own:

- **Android (sideload APK):** `TMessagesProj_AppStandalone/build.gradle` reads
  `RELEASE_STORE_PASSWORD` / `RELEASE_KEY_PASSWORD` from `gradle.properties` and
  a keystore path. Upstream Telegram ships a keystore with well-known passwords;
  for anything you actually distribute, generate your own with `keytool` and keep
  it outside the repository.
- **Google Play:** pass the upload key to Gradle at build time (see below) rather
  than committing it.

## Android

```bash
cd telegram/telegram-android

# Sideload APK (this is what puregram.app/download/puregram.apk is):
./gradlew :TMessagesProj_AppStandalone:assembleAfatStandalone --console=plain
# -> TMessagesProj_AppStandalone/build/outputs/apk/afat/standalone/app.apk

# Play bundle, signed with an upload key held outside the repo:
./gradlew :TMessagesProj_AppStandalone:bundleAfatStandalone \
  -Pandroid.injected.signing.store.file=/path/to/upload.keystore \
  -Pandroid.injected.signing.store.password=... \
  -Pandroid.injected.signing.key.alias=... \
  -Pandroid.injected.signing.key.password=... \
  --console=plain
```

The version lives in `gradle.properties`: `APP_VERSION_CODE`, `APP_VERSION_NAME`.
The final `versionCode` is `APP_VERSION_CODE * 10 + 9` for the `afat` flavour.
Bump it for every release and mirror it in `server/app/routes/device_update.py`.

Cold native build ~15–30 min; incremental ~10 min. arm64-v8a only.

## Desktop (Windows)

Prebuilt dependencies are expected in `telegram/Libraries/win64` (Qt 5.15, OpenSSL 3,
FFmpeg, tg_owt, tg_angle…). With those present:

```bat
telegram\configure_telegram.bat   :: only after CMake/source-list changes
telegram\build_telegram.bat       :: -> telegram/tdesktop/out/Release/Puregram.exe
```

The portable distributable is `Puregram.exe` plus
`modules/x64/d3d/d3dcompiler_47.dll` — nothing else.

**Known issue:** the Release link needs a lot of RAM because it generates a ~3 GB
PDB. On a 16 GB machine it fails with `LNK1102: out of memory`. Set
`<GenerateDebugInformation>false</GenerateDebugInformation>` in the `Release|x64`
block of `out/Telegram/Telegram.vcxproj`; the PDB is not part of the
distributable. Re-running `configure_telegram.bat` regenerates that file and undoes
the change. Do not run the Android and desktop builds at the same time — they will
fight over memory and the link will fail.

The desktop build number is `kPuregramBuild` in
`Telegram/SourceFiles/puregram/puregram_updater.cpp`; mirror it in
`device_update.py`.

## Server

```bash
cd server
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill in PUREGRAM_DATABASE_URL and PUREGRAM_JWT_SECRET
uvicorn app.main:app --host 127.0.0.1 --port 8020 --reload
```

The schema is applied on startup and every statement is idempotent. `server/.env`
is gitignored and must never be committed.

## What the fork actually changes

See **[POLICY_SPEC.md](POLICY_SPEC.md)** — it is the contract both clients
implement, and the shortest way to understand the diff against upstream. In
short: people always open, channels/bots/groups are closed until the user allows
them, a block the user makes is permanent, discovery surfaces are removed, and
sponsored messages are gone.
