/*
Puregram self-update for Telegram Desktop. See puregram_updater.h.

Update model: when the server advertises a newer build we prompt (never silent).
Accepting downloads the new binary next to the running one as Telegram.update.exe
and offers to restart; the swap itself happens at startup, where the old binary
can be renamed out of the way safely. Arabic strings are hex-escaped UTF-8 so
this source stays ASCII.
*/
#include "puregram/puregram_updater.h"

#include "settings.h" // cSetAutoUpdate — kill the native Telegram updater
#include "base/debug_log.h"
#include "core/application.h" // Core::App().activePrimaryWindow(), Core::Quit()
#include "ui/boxes/confirm_box.h" // Ui::MakeConfirmBox
#include "window/window_controller.h" // Window::Controller::show

#include <QtCore/QCoreApplication>
#include <QtCore/QCryptographicHash>
#include <QtCore/QFile>
#include <QtCore/QFileInfo>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QProcess>
#include <QtCore/QTimer>
#include <QtCore/QUrl>
#include <QtGui/QDesktopServices>
#include <QtNetwork/QNetworkAccessManager>
#include <QtNetwork/QNetworkReply>
#include <QtNetwork/QNetworkRequest>

namespace Puregram {
namespace {

constexpr auto kBaseUrl = "https://puregram.app/control/v1";
// Where the prompt sends the user if the download itself cannot be used.
constexpr auto kDownloadPage = "https://puregram.app/#download";
// The staged binary, downloaded next to the running exe and swapped in at launch.
constexpr auto kStagedName = "/Puregram.update.exe";
// The displaced previous binary; removed on the next successful launch.
constexpr auto kBackupName = "/Puregram.previous.exe";

// Monotonic build number of THIS binary. Bump on every release; the server's
// /desktop/version "version" must be a HIGHER integer to prompt already-deployed
// clients.
// build 2 (2026-07-12): green-by-default theme (light + dark) + desktop
// supervision linking/QR fixes; first build served by /v1/desktop/version.
// build 3 (2026-07-26): supervision moved to the web panel — in-app supervision
// screens removed; a link request now arrives as an Allow/Decline prompt.
// build 4 (2026-07-27): the update prompt downloads and installs the new build
// itself instead of sending the user to the website.
// build 5 (2026-07-27): channel ids now match the Android fork (-id, no Bot-API
// -100... offset), so a channel approved from a phone also opens on desktop.
// build 6 (2026-07-27): the executable is Puregram.exe, so the running process is
// named after the product instead of "Telegram".
// build 7 (2026-09-03): ADR-001 global policy — per-account supervision, chat-list
// reporting and link requests removed; one public policy document gates
// channels/bots, restricted peers are refused and discovery surfaces are gone.
// build 13 (2026-09-06): the rules UI is reachable and its buttons work —
// "Allowed and blocked" is a top-level Settings row (it was buried in a box
// that only appears once the user has custom file extensions), and the boxes
// now close on their own and reopen the chat the user was refused, instead of
// sitting there looking like a dead button.
constexpr auto kPuregramBuild = 13;

constexpr auto kFirstCheckMs = 20 * 1000;          // 20s after launch
constexpr auto kRecheckMs = 6 * 60 * 60 * 1000;    // then every 6h

constexpr auto kTitle =
	"\xD8\xAA\xD8\xAD\xD8\xAF\xD9\x8A\xD8\xAB\x20\x50\x75\x72\x65"
	"\x67\x72\x61\x6D";
constexpr auto kAvailable =
	"\xD8\xA5\xD8\xB5\xD8\xAF\xD8\xA7\xD8\xB1\x20\xD8\xAC\xD8\xAF"
	"\xD9\x8A\xD8\xAF\x20\xD9\x85\xD9\x86\x20\x50\x75\x72\x65\x67"
	"\x72\x61\x6D\x20\xD9\x85\xD8\xAA\xD8\xA7\xD8\xAD\x2E\x20\xD8"
	"\xAD\xD9\x85\xD9\x91\xD9\x84\xD9\x87\x20\xD9\x88\xD8\xAB\xD8"
	"\xA8\xD9\x91\xD8\xAA\xD9\x87\x20\xD8\xA7\xD9\x84\xD8\xA2\xD9"
	"\x86\x20\xD9\x84\xD9\x84\xD8\xAD\xD8\xB5\xD9\x88\xD9\x84\x20"
	"\xD8\xB9\xD9\x84\xD9\x89\x20\xD8\xA2\xD8\xAE\xD8\xB1\x20\xD8"
	"\xA7\xD9\x84\xD8\xAA\xD8\xAD\xD8\xB3\xD9\x8A\xD9\x86\xD8\xA7"
	"\xD8\xAA\x2E";
constexpr auto kUpdateNow =
	"\xD8\xAA\xD8\xAD\xD8\xAF\xD9\x8A\xD8\xAB\x20\xD8\xA7\xD9\x84"
	"\xD8\xA2\xD9\x86";
constexpr auto kLater =
	"\xD9\x84\xD8\xA7\xD8\xAD\xD9\x82\xD9\x8B\xD8\xA7";
constexpr auto kDownloaded =
	"\xD8\xAA\xD9\x85\x20\xD8\xAA\xD9\x86\xD8\xB2\xD9\x8A\xD9\x84"
	"\x20\xD8\xA7\xD9\x84\xD8\xAA\xD8\xAD\xD8\xAF\xD9\x8A\xD8\xAB"
	"\x2E\x20\xD8\xA3\xD8\xB9\xD8\xAF\x20\xD8\xAA\xD8\xB4\xD8\xBA"
	"\xD9\x8A\xD9\x84\x20\x50\x75\x72\x65\x67\x72\x61\x6D\x20\xD8"
	"\xA7\xD9\x84\xD8\xA2\xD9\x86\x20\xD9\x84\xD8\xA5\xD9\x83\xD9"
	"\x85\xD8\xA7\xD9\x84\xD9\x87\x2E";
constexpr auto kRestartNow =
	"\xD8\xA5\xD8\xB9\xD8\xA7\xD8\xAF\xD8\xA9\x20\xD8\xA7\xD9\x84"
	"\xD8\xAA\xD8\xB4\xD8\xBA\xD9\x8A\xD9\x84\x20\xD8\xA7\xD9\x84"
	"\xD8\xA2\xD9\x86";
constexpr auto kFailed =
	"\xD8\xAA\xD8\xB9\xD8\xB0\xD9\x91\xD8\xB1\x20\xD8\xAA\xD8\xAD"
	"\xD9\x85\xD9\x8A\xD9\x84\x20\xD8\xA7\xD9\x84\xD8\xAA\xD8\xAD"
	"\xD8\xAF\xD9\x8A\xD8\xAB\x2E\x20\xD8\xAD\xD8\xA7\xD9\x88\xD9"
	"\x84\x20\xD9\x84\xD8\xA7\xD8\xAD\xD9\x82\xD9\x8B\xD8\xA7\x20"
	"\xD8\xA3\xD9\x88\x20\xD9\x86\xD8\xB2\xD9\x91\xD9\x84\xD9\x87"
	"\x20\xD9\x85\xD9\x86\x20\xD8\xA7\xD9\x84\xD9\x85\xD9\x88\xD9"
	"\x82\xD8\xB9\x2E";
constexpr auto kOk =
	"\xD8\xAD\xD8\xB3\xD9\x86\xD9\x8B\xD8\xA7";

bool _busy = false;
bool _notified = false;    // prompt at most once per run.
bool _downloading = false;

[[nodiscard]] QNetworkAccessManager *Net() {
	static const auto manager = new QNetworkAccessManager(
		QCoreApplication::instance());
	return manager;
}

[[nodiscard]] QString AppDir() {
	return QCoreApplication::applicationDirPath();
}

[[nodiscard]] QString StagedPath() {
	return AppDir() + QString::fromUtf8(kStagedName);
}

[[nodiscard]] QString BackupPath() {
	return AppDir() + QString::fromUtf8(kBackupName);
}

void ShowBox(Ui::ConfirmBoxArgs &&args) {
	if (const auto window = Core::App().activePrimaryWindow()) {
		window->show(Ui::MakeConfirmBox(std::move(args)));
	}
}

void ShowFailure() {
	ShowBox({
		.text = QString::fromUtf8(kFailed),
		.confirmed = [] {
			QDesktopServices::openUrl(QUrl(QString::fromUtf8(kDownloadPage)));
		},
		.confirmText = QString::fromUtf8(kOk),
		.title = QString::fromUtf8(kTitle),
	});
}

/*
Move the staged binary into place and start it. Windows allows renaming a
RUNNING executable, which is exactly what makes this safe: the live process keeps
its handle to the renamed file while the new binary takes the original path.
Returns false (leaving everything untouched) if any step fails.
*/
[[nodiscard]] bool SwapAndRelaunch() {
	const auto staged = StagedPath();
	const auto current = QCoreApplication::applicationFilePath();
	const auto backup = BackupPath();
	if (!QFile::exists(staged)) {
		return false;
	}
	QFile::remove(backup);
	if (!QFile::rename(current, backup)) {
		LOG(("Puregram updater: cannot move the running binary aside"));
		return false;
	}
	if (!QFile::rename(staged, current)) {
		LOG(("Puregram updater: staging failed, restoring the previous binary"));
		QFile::rename(backup, current);
		return false;
	}
	if (!QProcess::startDetached(current, QStringList())) {
		LOG(("Puregram updater: could not start the new binary"));
		return false;
	}
	LOG(("Puregram updater: swapped in build from %1").arg(staged));
	return true;
}

void OfferRestart() {
	ShowBox({
		.text = QString::fromUtf8(kDownloaded),
		.confirmed = [] {
			if (SwapAndRelaunch()) {
				Core::Quit();
			} else {
				ShowFailure();
			}
		},
		.confirmText = QString::fromUtf8(kRestartNow),
		.cancelText = QString::fromUtf8(kLater),
		.title = QString::fromUtf8(kTitle),
	});
}

void Download(const QString &url, const QString &sha256) {
	if (_downloading) {
		return;
	}
	_downloading = true;
	const auto reply = Net()->get(QNetworkRequest(QUrl(url)));
	QObject::connect(reply, &QNetworkReply::finished, [=] {
		_downloading = false;
		reply->deleteLater();
		if (reply->error() != QNetworkReply::NoError) {
			LOG(("Puregram updater: download failed (%1)").arg(reply->errorString()));
			ShowFailure();
			return;
		}
		const auto body = reply->readAll();
		if (body.isEmpty()) {
			ShowFailure();
			return;
		}
		if (!sha256.isEmpty()) {
			const auto actual = QString::fromLatin1(QCryptographicHash::hash(
				body, QCryptographicHash::Sha256).toHex());
			if (actual.compare(sha256, Qt::CaseInsensitive) != 0) {
				LOG(("Puregram updater: sha256 mismatch, refusing the download"));
				ShowFailure();
				return;
			}
		}
		auto file = QFile(StagedPath());
		if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)
			|| file.write(body) != body.size()) {
			LOG(("Puregram updater: cannot write next to the app"));
			ShowFailure();
			return;
		}
		file.close();
		OfferRestart();
	});
}

void NotifyUpdateAvailable(int build, const QString &url, const QString &sha256) {
	if (_notified) {
		return;
	}
	const auto window = Core::App().activePrimaryWindow();
	if (!window) {
		return; // no UI yet — the next scheduled check will prompt.
	}
	_notified = true;
	ShowBox({
		.text = QString::fromUtf8(kAvailable),
		.confirmed = [=] {
			if (url.endsWith(u".exe"_q, Qt::CaseInsensitive)) {
				Download(url, sha256);
			} else {
				QDesktopServices::openUrl(QUrl(url));
			}
		},
		.confirmText = QString::fromUtf8(kUpdateNow),
		.cancelText = QString::fromUtf8(kLater),
		.title = QString::fromUtf8(kTitle),
	});
	LOG(("Puregram updater: prompted for newer build %1").arg(build));
}

void CheckOnce() {
	if (_busy || _notified) {
		return;
	}
	_busy = true;
	const auto request = QNetworkRequest(QUrl(QString(kBaseUrl)
		+ "/desktop/version?app=telegram_desktop"));
	const auto reply = Net()->get(request);
	QObject::connect(reply, &QNetworkReply::finished, [=] {
		_busy = false;
		reply->deleteLater();
		const auto status = reply->attribute(
			QNetworkRequest::HttpStatusCodeAttribute).toInt();
		if (reply->error() != QNetworkReply::NoError || status != 200) {
			return; // 404 = no update advertised; anything else = transient
		}
		const auto json = QJsonDocument::fromJson(reply->readAll()).object();
		const auto build = json.value("version").toString().toInt();
		if (build <= kPuregramBuild) {
			return;
		}
		LOG(("Puregram updater: newer build %1 (have %2) — prompting").arg(
			build).arg(kPuregramBuild));
		NotifyUpdateAvailable(
			build,
			json.value("url").toString(QString::fromUtf8(kDownloadPage)),
			json.value("sha256").toString());
	});
}

} // namespace

bool ApplyStagedUpdateIfReady() {
	// A previous run downloaded a newer binary but the user chose "later"; put it
	// in place now, while nothing has been initialised yet, and hand over to it.
	QFile::remove(BackupPath());
	if (!QFile::exists(StagedPath())) {
		return false;
	}
	return SwapAndRelaunch();
}

void StartUpdater() {
	// Never let Telegram's native updater run: its feed serves official Telegram
	// and would overwrite this fork, dropping every Puregram restriction.
	cSetAutoUpdate(false);

	const auto timer = new QTimer(QCoreApplication::instance());
	QObject::connect(timer, &QTimer::timeout, [] { CheckOnce(); });
	timer->start(kRecheckMs);
	QTimer::singleShot(kFirstCheckMs, [] { CheckOnce(); });
}

} // namespace Puregram
