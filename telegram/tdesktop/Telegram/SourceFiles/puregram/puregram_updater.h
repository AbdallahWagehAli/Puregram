/*
Puregram self-update for Telegram Desktop.

Telegram's built-in updater is DISABLED (it points at Telegram's official feed
and would overwrite this fork with stock Telegram, dropping every Puregram
restriction). Instead the app polls the Puregram server for a newer Puregram build,
downloads it next to the exe, and applies it on the next launch.

Server contract (Control API v3):
  GET /v1/desktop/version?app=telegram_desktop -> {version, url, sha256}
  (version = monotonic integer build number; 404 = no update advertised)
*/
#pragma once

namespace Puregram {

// If a verified update was staged on a previous run (Telegram.update.exe next to
// the running exe), spawn a tiny script that swaps the binary and relaunches.
// Returns true while an update is being applied — the caller MUST quit at once.
[[nodiscard]] bool ApplyStagedUpdateIfReady();

// Disable Telegram's native updater and start polling the Puregram server for a
// newer Puregram build (downloaded next to the exe; applied on the next launch).
void StartUpdater();

} // namespace Puregram
