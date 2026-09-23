# Jahed Telegram — Progress & Pitfalls Log

> Living document. Read this BEFORE touching the forks so we don't repeat mistakes.
> Last updated: 2026-06-25.

## 🎨 BRANDING — Puregram theme + logo rebrand — 2026-06-25

Brand = **Puregram**: red `#FF3333` + gold `#D4AF37` paper-plane on dark navy.
Canonical logo source: `JahedTelegram/telegram/Puregram .png` (2000×2000 RGBA, red disk +
gold ring + white line-art plane). Android day theme **VERIFIED red on emulator**
(`app.puregram`, AVD `Puregram_Test`); desktop NOT build-verified.

### ⚠️ HOW THE ANDROID THEME IS MADE RED (do NOT use Theme.java accents)
The right lever is **editing the bundled `.attheme` assets** (`TMessagesProj/src/main/assets/`),
appending `key=value` color overrides (last value wins; parser reads the whole file, stops only
at a `WPS` wallpaper line — none of ours have one). The default day theme is `bluebubbles.attheme`
("Blue"), which already carries a red override block (≈16 keys: `chats_actionBackground`,
`featuredStickers_addButton`, `switchTrackChecked`, `radioBackgroundChecked`,
`chat_messagePanelSend`, `windowBackgroundWhiteBlueText*`, `chats_actionUnreadBackground`,
`dialogTextBlue*` = `-52941` = `0xFFFF3133`). Mirror the same block into `darkblue.attheme`
(done) / `night.attheme` for dark modes.

**DO NOT** set red accents in `Theme.java` (`setAccentColorOptions` / `currentAccentId`): the
accent system hue-rotates colors `newHue = accentHue + (colorHue − baseHue)`, so a red home/accent
takes the asset's red and rotates it back to **blue/teal**. We tried that first and it broke the
theme on-device; reverted to stock accents so the asset reds pass through (Blue home shift ≈4°,
Dark Blue home == base = no shift).

Hardcoded brand-blue that bypasses the theme: `ThemeColors.TELEGRAM_COLOR` (intro page dots,
many `defaultColors`) and `TELEGRAM_COLOR_TEXT` → changed to red `0xFFFF3333` / `0xFFE01F1F`.

**Android (`telegram-android`):**
- Launcher icon `@mipmap/ic_launcher` rebranded — VERIFIED red on the launcher. Adaptive
  (API 26+): `icon_background.xml`/`_round` red gradient (`#FF4040→#E01F1F`); foreground
  `mipmap-*/icon_foreground.png`/`_round` = white Puregram plane (5 densities). Legacy PNG
  `mipmap-*/ic_launcher.png`/`_round` = full logo. Monochrome = `icon_plane`.
- Animated intro logo (native GL): `IntroActivity` sphere texture provider draws the red disk
  (`0xFFFF3333`) + a gold ring (`0xFFD4AF37`, stroke `dp(4)` at `r=size/2−dp(5)`); plane =
  `intro_tg_plane` (white). VERIFIED red+gold on device (day & night).
- Theme: see the box above (asset overrides + TELEGRAM_COLOR). VERIFIED red in BOTH day &
  night — FAB, dots, dark-mode toggle, button, focused input-field border + label all `#FF3333`.
  Red override block now in `bluebubbles` (day) + `darkblue` + `night` (dark) `.attheme`; the
  block also covers `windowBackgroundWhiteInputFieldActivated`, `chat_fieldOverlayText`,
  `chats_sentCheck`. NOTE: a dimmed-looking red is just the system permission-dialog scrim, not
  the theme.
- Splash (cold-start, Android 12+ `windowSplashScreenAnimatedIcon` in `values-v31/` &
  `values-night/styles.xml`) = `drawable/tg_splash_320.xml`: circle `#2aabee`→`#FF3333`. VERIFIED
  red circle + white plane on cold start (day white bg / night dark bg).
- NOT changed (intentional): notification status icon (generic white plane, illegible at 24px),
  alternate launcher icons `icon_2..6` (disabled Jahed "J" designs).
- Build VERIFIED: `app.puregram`, `assembleAfatDebug` → `.../afat/debug/app.apk` (~96 MB).

**Desktop (`tdesktop`):**
- All app icons regenerated from the canonical logo: `art/icon{16..512}.png` + `@2x`,
  `art/icon256.ico` (Windows, 6 sizes), `art/icon_round512@2x.png`, in-app logos
  `art/logo_256.png` + `art/logo_256_no_margin.png`.
- Default accent → red in `lib_ui/ui/colors.palette`: `windowBgActive #40a7e3→#ff3333`,
  `windowActiveTextFg #168acd→#e01f1f`, `activeButtonBgOver→#e01f1f`,
  `activeButtonBgRipple→#c81e1e`, `activeLineFg→#ff3333`. Classic embedded scheme accent
  `40a7e3→ff3333` in `window_themes_embedded.cpp`. First-run default uses the palette as-is
  (`systemAccentColorEnabled=false`, empty colorizer) → red.
- App display name → "Puregram": `core/version.h` `AppName "Telegram Desktop"→"Puregram"`
  (flows to window title / about / media controls) + `winrc/Telegram.rc` FileDescription &
  ProductName → "Puregram". LEFT unchanged on purpose: Qt `setApplicationName("TelegramDesktop")`
  in `launcher.cpp` (storage path stability), `AppFile`/`AppId` (exe/installer identity), and
  the `Telegram FZ-LLC` copyright/license headers. NOT build-verified.
- Keep LF line endings (see AGENTS.md). Edits were value-only; EOLs untouched.

**App display name = "Puregram" (done):** Android was already fully "Puregram" — `AppName`
string + manifest label (aapt `application-label:'Puregram'` for all locales) + the
`LocaleController.getPuregramAppName()` override (title bar, intro, stories cell). Cleaned the
last stale literal `Page1Title "Puregram Telegram"→"Puregram"` (values + values-ar; it was
already overridden in code so no visible change). Desktop name changed in source (see above).

**Open follow-ups:** Android intro GL animation is stock plane shape (only recolored, not
reshaped); optional alternate-icon `icon_2..6` cleanup; desktop build-verification of the
theme/icon/name changes.

## ⚠️ BEHAVIOUR MODEL CHANGED — 2026-06-21 (open-gate-only)

The fork no longer **hides** non-approved chats. The new model: **everything looks like
100% stock Telegram** — the full chat list, archive, unread counters and notifications
are all unfiltered — and the whitelist is enforced ONLY when the user *taps to open* a
chat. A non-approved chat refuses to open with a toast (`هذه المحادثة غير مسموح بها في
جاهد` on Arabic devices / `This chat is not allowed in Jahed` otherwise).

What changed vs. the old "hide everything" model:
- **Android:** `DialogsActivity.getDialogsArray` no longer filters (still reports seen
  chats); `DialogCell` archive preview + unread badge restored to stock;
  `NotificationsController` restored to stock (all 6 suppression guards removed);
  `JahedWhitelist.filterDialogs` deleted (dead). KEPT: the two `ChatActivity` open-gates
  (`onFragmentCreate` + `onResume`) — THIS is the only enforcement now.
- **Desktop (tdesktop):** `History::shouldBeInChatList()` restored to stock;
  `notifications_manager.cpp` + `dialogs_inner_widget.cpp` search filters reverted;
  `data_session.cpp` keeps ONLY the known-chats reporting. KEPT: the
  `SessionController::showPeerHistory` open-gate.
- **App name** is now device-language aware: `جاهد تليجرام` on Arabic devices,
  `Jahed Telegram` otherwise (Android: `values-ar` AppName + `LocaleController.getJahedAppName()`
  via `Resources.getSystem()` device locale; the intro slide-1 wordmark image span was
  removed so the brand text shows).

## What this is

Two **forks of the official open-source Telegram clients**, each patched with ONE
behavioural difference: a per-device **whitelist** managed from the Jahed panel
(`jahed.net/admin/telegram.html`). Everything else (UI, settings, media, encryption)
stays 100% stock Telegram. The user explicitly wants it to be *literally* Telegram,
only the allowed chats differ — and now even the chat list looks fully normal (see the
behaviour-model note above); only *opening* a non-approved chat is blocked.

| Fork | Source | Local path | Status |
|---|---|---|---|
| Android | `github.com/DrKLO/Telegram` | `JahedTelegram/telegram-android` | ✅ builds + runs + whitelist + link-block verified |
| Desktop | `github.com/telegramdesktop/tdesktop` | `JahedTelegram/tdesktop` | ⬜ cloned, injection points identified, NOT patched/built |

The old Flutter+TDLib client (`07- jahed-Telegram/app`, 20 work packages) still builds
and runs but is **superseded** by these forks. Kept as a fallback only.

## Server / control plane (unchanged, shared by everything)

- Base: `https://jahed.net/control/v1` (FastAPI + SQLite on VPS 46.202.173.157, `deploy` SSH key).
- Device API: `POST /device/checkin` (android_id → bearer token), `GET /device/telegram/whitelist`,
  `POST /device/telegram/chats` (report seen chats), `POST /device/telegram/events`.
- Admin API: `/control/v1/admin/telegram/*`; panel page `jahed.net/admin/telegram.html`.
- Tables: `telegram_whitelist`, `telegram_known_chats`, `telegram_whitelist_meta`.
- dialog-id encoding (Android & TDLib agree): user/bot = `+id`, chat/channel = `-id`.

---

## ANDROID FORK — what we changed

All changes funnel through one new class + a few minimal call-site patches:

1. **`TMessagesProj/src/main/java/org/telegram/messenger/JahedWhitelist.java`** (NEW)
   - Checkin (ANDROID_ID) → bearer token; fetch whitelist; report seen chats; poll loop.
   - `isAllowed(long dialogId)` — deny by default (false until loaded).
   - `filterDialogs(list)` — returns approved dialogs only; DROPS the Archive folder
     row (`TL_dialogFolder`) so archived non-approved names don't leak.
   - Cache in SharedPreferences (`jahed_whitelist`), refresh loop on `Utilities.globalQueue`.
2. **`ApplicationLoader.onCreate()`** — `JahedWhitelist.init(applicationContext)` (best-effort).
3. **`DialogsActivity.getDialogsArray(...)`** — renamed original to `getDialogsArrayJahedRaw`;
   the public method now filters the result through `JahedWhitelist.filterDialogs` (deny by
   default) and reports seen chats. THIS is the chat-list enforcement point.
4. **`ChatActivity.onFragmentCreate()`** — guard: if the opened chat/user id is not allowed,
   refuse to open (this is what blocks `t.me/<channel>` links & usernames — VERIFIED: durov
   blocked, log `JahedGate: open chat_id=... allowed=false`).
5. **`BuildVars.java`** — `APP_ID=2040`, `APP_HASH=b18441a1ff607e10a989891a5462e627`
   (Telegram Desktop's PUBLIC keys, TEMPORARY). ⚠️ see "Known issues".

### Build command (Android)
```bash
cd "C:/Users/lap_shop/Desktop/Jahed/JahedTelegram/telegram-android"
./gradlew :TMessagesProj_AppStandalone:assembleAfatDebug --console=plain
# APK: TMessagesProj_AppStandalone/build/outputs/apk/afat/debug/app.apk
```
Install/run on emulator:
```bash
adb install -r -d <apk>
adb shell monkey -p org.telegram.messenger.web -c android.intent.category.LAUNCHER 1
```

---

## ⛔ PITFALLS — do NOT repeat these (each cost us a 15–30 min build)

1. **PATH MUST HAVE NO SPACES.** The native CMake/ninja link step splits paths on spaces,
   so `07- jahed-Telegram` broke ffmpeg/boringssl `.a` linking
   (`clang++: error: no such file or directory: 'jahed-Telegram/.../libavcodec.a,...'`).
   → That's why everything now lives under `JahedTelegram/` (no spaces). Keep it that way.
2. **`local.properties` needs FORWARD slashes.** `sdk.dir=C:\Users\...` fails with
   "The filename, directory name, or volume label syntax is incorrect" — backslashes are
   escape chars in `.properties`. Use `sdk.dir=C:/Users/lap_shop/AppData/Local/Android/Sdk`.
3. **Kotlin daemon hangs on this machine.** Builds stall forever at `compileKotlin`
   (CountDownLatch / "Could not connect to Kotlin compile daemon"). FIX: in `gradle.properties`
   add `kotlin.compiler.execution.strategy=in-process`. (Already set.)
4. **NDK / CMake version pins.** Repo wanted NDK `27.2.12479018` (not installed) & CMake
   `3.10.2`. Retargeted to installed **NDK 27.1.12297006** and **CMake 3.22.1** across all
   `*/build.gradle`. Installed NDKs: 25.1, 26.1, 27.1, 28.2. CMake: 3.22.1.
5. **Restrict ABIs to cut build time.** Added `ndk { abiFilters "x86_64" }` to BOTH
   `TMessagesProj` (library) defaultConfig AND `TMessagesProj_AppStandalone` afat flavor.
   x86_64 = emulator. For real devices/release, also add `arm64-v8a` (prebuilt `.a` libs ship
   for all ABIs in `jni/`, so it just links — but each ABI adds build time).
6. **Flaky network → re-run the build.** Transient maven download fails (e.g.
   `checker-compat-qual`) abort the build; the native part is cached in `.cxx`, so just
   re-running finishes in minutes. Build commands wrap a 3× retry loop.
7. **Repo ships only Unix `gradlew`** (no `gradlew.bat`). Run `./gradlew` from Git Bash, not
   `./gradlew.bat`.
8. **Moving the project** invalidates absolute paths baked into `.cxx`. AGP makes a new
   hashed `.cxx` subdir per path, so it self-heals (full native rebuild on first build after move).

---

## DESKTOP FORK (tdesktop) — status 2026-06-14 ✅ BUILDS + RUNS + WHITELIST VERIFIED LIVE

> ▶ **DONE.** User logged in and confirmed the gate works: approved chats show, non-approved are
> hidden and can't be opened. The earlier "some approved chats missing" was a stale pre-sync state
> that cleared on a fresh login — the id encoding (including channel `-(1e12+bare)`, i.e. the `-100`
> marked form) was confirmed CORRECT via per-peer diagnostic logging (since removed). The final
> build also adds an Android-style block toast in `showPeerHistory`:
> `showToast(QString::fromUtf8("هذه المحادثة غير مسموح بها في جاهد"))`.
> Rebuild after any code change: `build_telegram.bat` → `out/Release/Telegram.exe` (libs+configure cached).
> Open items: dedicated my.telegram.org api_id/hash (2040 is temporary → occasional auto-logout),
> branding/icon, package/app name. The transient "-9" unread badge from the broken state did not
> recur once the list populated.

> ▶ (historical) **`Telegram.exe` is built. Only USER-login verification remains.**
> The full pipeline now works end-to-end:
> - Libs: `prepare_libs_silent.bat` → `PREPARE_DONE` (all 33 components built).
> - Configure: `configure_telegram.bat` (calls `configure.bat x64 -D TDESKTOP_API_ID=2040 -D TDESKTOP_API_HASH=b18441a1ff607e10a989891a5462e627` by full path) → `tdesktop/out/Telegram.sln`.
> - Build: `build_telegram.bat` (`cmake --build tdesktop/out --config Release --target Telegram --parallel 8`) → **`tdesktop/out/Release/Telegram.exe` (207 MB), BUILD_EXIT=0.** All Jahed sources compiled + linked clean.
> - Smoke test: the exe launches and runs (2 live processes, no crash dump).
> REMAINING (needs the user / a phone account): log in and verify (a) chat list shows ONLY
> approved chats, no gaps, (b) non-approved `t.me/<user>`/search hit is blocked, (c) no
> notifications from non-approved chats, (d) the panel's known-chats list populates.
> To rebuild after a code change: just re-run `build_telegram.bat` (libs + configure stay cached).
> api_id/hash 2040 are temporary (Telegram Desktop's public keys) — auto-logout caveat until a
> dedicated pair from my.telegram.org.

### How the build blockers were beaten (2026-06-14, all on a very slow/throttled link)
1. **msys2 installer download** timed out under PowerShell `iwr` (no resume) → replaced with
   `curl -L -C - --retry 30 ...` in `prepare.py` (resumes across attempts).
2. **pacman aborting at "<1 byte/s for 10s"** (built-in downloader, no config knob) → enabled an
   external-curl `XferCommand` in `msys64/etc/pacman.conf` via `JahedTelegram/fix_pacman.py`
   (called from the msys64 stage; done in Python to dodge cmd→bash→sed `%`/quote mangling).
3. **breakpad compile error C1083 `atlbase.h`** → VS BuildTools was missing the **C++ ATL**
   component. Installed `Microsoft.VisualStudio.Component.VC.ATL` via
   `setup.exe modify ... --quiet --norestart` run **elevated** (`Start-Process -Verb RunAs`,
   user approved UAC). Note: `--quiet` modify MUST start elevated; `--wait` is NOT a valid flag.
4. Two prepare loops once ran concurrently and fought over the log — kill ALL build loops with
   `JahedTelegram/kill_build.ps1` before relaunching, and run only ONE.

Path: `JahedTelegram/tdesktop`. Toolchain CONFIRMED present: VS 2022 **BuildTools** at
`C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools`, MSVC **14.44.35207** (v144.4 —
exactly what tdesktop wants), `vcvars64.bat` works, Python 3.11/3.14, CMake 3.22.1, git.

### Code — FEATURE-COMPLETE and ✅ COMPILED CLEAN into Telegram.exe (2026-06-14)
Architecture decision (differs from Android): the desktop list filtering is done at the
**data source** — `History::shouldBeInChatList()` returns false for non-approved peers — instead
of filtering the painted rows. This is cleaner than the Android `filterDialogs`: the chat list
stays live, gap-free, and automatically excludes non-approved chats from local search, folders
and unread badges too. The Android-style paint-time filter was tried first and reverted (it left
blank gaps where hidden rows used to be).

- `Telegram/SourceFiles/jahed/jahed_whitelist.{h,cpp}` (NEW) — Qt **Q_OBJECT** singleton:
  device check-in (Windows MachineGuid → `pc-<guid>`), fetch `/device/telegram/whitelist`, 15s
  QTimer refresh, JSON cache, `isAllowed(int64)`/`isAllowed(PeerId)`/`loaded()`, `ChatId(PeerId)`
  (user=+id, chat=-id, channel=-(1e12+id)), **`reportKnownChats(QVector<ChatInfo>)`** (POST
  `/device/telegram/chats`, throttled 60s), and a **`dialogsChanged()`** signal emitted from
  `applyAllowed`/`loadCache`. Everything runs on the main thread (Qt async network) → no locking.
- `history/history.cpp` — `shouldBeInChatList()` gated (deny-by-default). THE list-visibility point.
- `data/data_session.{cpp,h}` — `setupJahedWhitelistViewer()`: on `dialogsChanged` (bridged via
  `base::qt_signal_producer`) re-evaluates every history's chat-list membership (so newly-approved
  chats appear / revoked ones vanish without waiting for activity) and reports known chats; a
  `base::timer_each(60s)` re-reports periodically so the admin sees newly-arrived chats too.
- `dialogs/dialogs_inner_widget.cpp` — gates **server** search results that don't pass through
  the chat list: `searchReceived` (message search + injected pinned), `peerSearchReceived`
  (my/sponsored/global peers), `appendToFiltered`; + a `dialogsChanged`→`refresh()` repaint hook.
- `window/notifications_manager.cpp` — `System::schedule()` is the primary gate (covers new msgs,
  reactions, post-login unread sync); `showGrouped()` + the `showNext()` alert loop gated too.
- `window/window_session_controller.cpp` — `showPeerHistory` gate (access funnel, pre-existing).
- `core/application.cpp` — `Application::run()` calls `Jahed::Whitelist::Instance().start()`.
- `Telegram/CMakeLists.txt` — the two jahed/ sources (Qt::Network linked; Telegram target AUTOMOC=ON
  so the Q_OBJECT mocs fine).

### Build: ✅ DONE (was network-throttled; beaten with the curl fixes above)
The link is slow/throttled (msys2 mirrors 4–14 KB/s, github ~50 KB/s) but the curl resume +
`XferCommand` fixes made `pacman` and the source downloads tolerate it, so the full libs build
completed on a single clean run (attempt 1, 0 failures) once ATL was installed. Build helper bats
live at `JahedTelegram/{prepare_libs_silent,configure_telegram,build_telegram}.bat`; logs at
`C:/Users/lap_shop/tdesktop_{prepare_silent,configure,build}.log`.

## Tooling locations (this machine)
- Flutter SDK: `C:/dev/flutter` (3.44.0) — only needed by the old app.
- Android SDK: `C:/Users/lap_shop/AppData/Local/Android/Sdk` (no cmdline-tools/sdkmanager).
- Emulator AVD: `Medium_Phone_API_36.1` (x86_64, API 36).
- JDK: `C:/Program Files/Microsoft/jdk-17.0.18.8-hotspot`.

---

## ⚠️ Known issues (not bugs we introduced)

- **Auto-logout:** the account logs itself out sometimes because the public api_id/hash
  (2040) has a high shared load/limit. NOT our code. FIX = register a dedicated app at
  `my.telegram.org` and set `APP_ID`/`APP_HASH` in `BuildVars.java`. Until then, if a
  screenshot shows the login screen, assume the session dropped and re-login.

## Verified working (2026-06-12 / 13)
- ✅ App builds, installs, runs — literal official Telegram UI.
- ✅ Chat list shows ONLY whitelisted chats (deny by default).
- ✅ Opening a non-approved channel via `t.me/<user>` link is BLOCKED (durov test).
- ✅ Archive is ACCESSIBLE and shows only approved chats (contents + preview filtered);
  opening it shows only the approved archived chat ("Spam Info Bot").
- ✅ Notifications from non-approved chats suppressed (`NotificationsController.processNewMessages`
  filter). NOTE: notifications already posted BEFORE installing the fix stay in the tray until
  cleared — only NEW ones are gated.
- ✅ Whitelist refresh interval = 15s (`REFRESH_INTERVAL_MS` in `JahedWhitelist.java`).

### Notification + archive enforcement points (added 2026-06-13)
- `NotificationsController.processNewMessages(...)` — drops messages whose `getDialogId()`
  is not `JahedWhitelist.isAllowed(...)` before they can become a notification/popup.
- `DialogCell.formatArchivedDialogNames()` — archive preview filtered via `JahedWhitelist.filterDialogs`.
- `JahedWhitelist.filterDialogs` keeps the `TL_dialogFolder` (archive) row; archive contents
  are filtered by the existing `getDialogsArray(folderId)` wrapper.

### Notification entry points — ALL gated (2026-06-13, verified clean-install)
The first fix only gated `processNewMessages`; non-approved notifications still appeared after
LOGIN because the initial sync uses other paths. ALL four are now gated by `JahedWhitelist.isAllowed(dialogId)`:
- `processNewMessages` (new live messages)
- `processLoadedUnreadMessages` (post-login stored-unread sync — was the leak; gated in the
  messages loop, the dialogs-count loop, AND the push loop)
- `processDialogsUpdateRead` (source of the "X new messages from Y chats" summary → newCount=0)
- `processEditedMessages` (edited-message notifications)
NOTE: notifications posted BEFORE installing the fix persist in the tray → always test with a
CLEAN reinstall (`adb uninstall` then install).

### Archive unread badge — fixed
`DialogCell` (the `TL_dialogFolder` branch, ~line 3139) now sums `unread_count` over
`JahedWhitelist`-approved archived dialogs instead of `MessagesStorage.getArchiveUnreadCount()`.

### ✅ Android fork status: FEATURE-COMPLETE for the whitelist behaviour (2026-06-13)
Chat list, archive (accessible, approved-only contents+preview+badge), notifications, link/username
open-block, 15s refresh — all verified on clean install + login. Remaining = branding only.

## SESSION HANDOFF — 2026-06-13 (brand = "Jahed", logo deferred)

- Brand name CONFIRMED **"Jahed"** (user considered "Hisn" then reverted). The H-shield
  logo belonged to Hisn and is DROPPED. New logo monogram = letter **"J"**.
- Packages stay `com.jahed.launcher` / `com.jahed.browser` / `com.jahed.telegram` (the
  Telegram fork currently still installs as `org.telegram.messenger.web` — package rename
  to `com.jahed.telegram` is still an open TODO).
- App display name set to **"Jahed Telegram"** (English) everywhere, VERIFIED on emulator:
  launcher label (aapt `application-label:'Jahed Telegram'`) AND the chat-list top title.
  The Arabic "جاهد" was HARDCODED (not just in strings.xml) in three Java spots, all fixed:
  `DialogsActivity.java` `actionBar.setTitle("Jahed Telegram", ...)`, and two
  `LocaleController.java` getString overrides for `AppName`/`Page1Title`. Also updated
  `values/strings.xml` + `values-ar/strings.xml` AppName & Page1Title.
- LOGO: deferred by the user ("leave the logo for later"). Mark = gradient (cyan #2BD4FF →
  blue #1E78FF) angular shield + thin inner ring + negative-space **"J"**. Generator:
  `C:\Users\lap_shop\make_jahed_logo.py` (Pillow + Segoe UI Black) → outputs to
  `C:\Users\lap_shop\assets\jahed_{mark,icon,icon_512}.png`. NOT yet wired as the app icon.
  Canva MCP is connected (brand kit id `kAHA28uA3hQ`) for hosting the official mark there.
- Forks moved to `C:\Users\lap_shop\Desktop\Jahed\JahedTelegram\` (telegram-android/, tdesktop/).
- Desktop build still blocked on the user's network (MSYS2 pacman timeouts); user is fixing it.

## TODO / open items
1. ⬜ **Package name** → `com.jahed.telegram` (currently `org.telegram.messenger.web`).
   Plan: set `APP_PACKAGE` in `gradle.properties`; remove `apply plugin:
   'com.google.gms.google-services'` from `TMessagesProj/build.gradle` (~line 246) and
   `TMessagesProj_AppStandalone/build.gradle` (~line 154) — verified NO compile-time refs to
   google-services resources, so removal is safe (FCM push just won't work). Optionally drop
   the `.web` applicationIdSuffix for a clean id.
2. ⬜ **Custom logo** (app icon) — design a simple Jahed mark, replace `mipmap-*/ic_launcher*`.
3. ⬜ **Faster whitelist refresh** — currently 5 min; user wants ≤15–30 s. Lower
   `REFRESH_INTERVAL_MS` in `JahedWhitelist.java` (e.g. 15000).
4. ⬜ **Remove the "test back end" button** on the phone-registration screen (or replace the
   slot of the original "sync contacts" toggle). [user request]
5. ⬜ **Remove debug `Log.w("JahedGate", ...)`** from `ChatActivity.onFragmentCreate` after final verification.
6. ✅ **DESKTOP fork (tdesktop)** — whitelist code FEATURE-COMPLETE and COMPILED into
   `Telegram.exe` (207 MB), which launches/runs. Remaining = user-login verification of the
   gate. Details in the DESKTOP FORK section above.
7. ⬜ **dedicated api_id/api_hash** from my.telegram.org (fixes auto-logout).
8. ⬜ Real-device build: add `arm64-v8a` back to abiFilters.
