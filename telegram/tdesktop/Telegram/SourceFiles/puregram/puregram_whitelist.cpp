/*
Puregram per-account chat rules for Telegram Desktop. See puregram_whitelist.h.
*/
#include "puregram/puregram_whitelist.h"

#include "settings.h" // cWorkingDir — our state lives next to tdata.
#include "base/debug_log.h"
#include "core/application.h"
#include "data/data_peer.h"
#include "main/main_account.h"
#include "main/main_session.h"
#include "data/data_session.h"
#include "history/history.h" // updateChatListExistence — blocked chats leave the list
#include "lang/lang_instance.h"
#include "ui/boxes/confirm_box.h"
#include "ui/layers/generic_box.h"
#include "ui/vertical_list.h"
#include "ui/widgets/buttons.h"
#include "window/window_controller.h"
#include "styles/style_settings.h"

#include <QtCore/QDir>
#include <QtCore/QFile>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QSettings>
#include <QtCore/QStandardPaths>
#include <QtCore/QTimer>
#include <QtCore/QUrl>
#include <QtCore/QUuid>
#include <QtNetwork/QNetworkAccessManager>
#include <QtNetwork/QNetworkReply>
#include <QtNetwork/QNetworkRequest>

namespace Puregram {
namespace {

constexpr auto kApiBase = "https://puregram.app/control/v1";
constexpr auto kRefreshMs = 60 * 1000;
constexpr auto kTransferTimeoutMs = 15 * 1000;
constexpr auto kStateName = "puregram_rules.json";
// The pre-ADR-002 caches; wiped on start so no stale global list survives.
constexpr auto kLegacyNames = {
	"puregram_policy.json",
	"puregram_whitelist.json",
};

[[nodiscard]] bool Arabic() {
	// The APP's language, never the operating system's. Reading QLocale::system()
	// meant an Arabic Windows kept showing Arabic here however the user set
	// Puregram, and switching the app to English changed everything except our
	// own strings. Android picks these through the resource system, which
	// follows the app language — this is the same rule.
	//
	// Match the language part, not the whole id: packs ship as "ar", but also
	// as regional and beta variants like "ar-beta".
	const auto language = [](const QString &id) {
		return id.split('-').front();
	};
	const auto &instance = Lang::GetInstance();
	if (instance.id().isEmpty()) {
		// No pack chosen yet — a cold start before the language downloads.
		// Fall back to the system language, which is the one the app is about
		// to ask for anyway, so the first screens do not flash the wrong one.
		return language(instance.systemLangCode()) == u"ar"_q;
	}
	return (language(instance.id()) == u"ar"_q)
		|| (language(instance.baseId()) == u"ar"_q);
}

[[nodiscard]] QString Tr(const char *arabic, const char *english) {
	return QString::fromUtf8(Arabic() ? arabic : english);
}

// "2026-11-04T…" -> "2026-11-04"; the time of day is noise for the user.
[[nodiscard]] QString ShortDate(const QString &iso) {
	const auto t = iso.indexOf('T');
	return (t > 0) ? iso.left(t) : iso;
}

// Any Telegram restriction reason. "sensitive" is never ignored.
[[nodiscard]] bool IsRestricted(not_null<PeerData*> peer) {
	return peer->hasSensitiveContent()
		|| !peer->computeUnavailableReason().isEmpty();
}

// `replace` swaps the box on screen instead of stacking a second layer on top
// of it. Layers default to KeepOther, so a box opened from another box's button
// left the first one sitting behind it — visible again the moment the new one
// closed, as if the choice had not been taken.
void ShowBox(object_ptr<Ui::BoxContent> box, bool replace = false) {
	if (const auto window = Core::App().activePrimaryWindow()) {
		window->show(std::move(box), replace
			? Ui::LayerOption::CloseOther
			: Ui::LayerOption::KeepOther);
	}
}

} // namespace

QString AppDisplayName() {
	// Display-only (window title, tray, notifications); the data folder keeps
	// the stock AppName so existing logins survive the rename.
	return u"Puregram"_q;
}

Rules &Rules::Instance() {
	static Rules instance;
	return instance;
}

Rules::Rules() = default;

int64 Rules::ChatId(PeerId peerId) {
	// MUST match the Android fork exactly — both clients are filtered by the
	// same stored rules: user/bot = +id, chat AND channel = -id (never the
	// Bot-API -100... offset).
	if (peerIsUser(peerId)) {
		return int64(peerToUser(peerId).bare);
	} else if (peerIsChat(peerId)) {
		return -int64(peerToChat(peerId).bare);
	} else if (peerIsChannel(peerId)) {
		return -int64(peerToChannel(peerId).bare);
	}
	return 0;
}

PeerKind Rules::KindOf(not_null<PeerData*> peer) {
	if (peer->isUser()) {
		return peer->isBot() ? PeerKind::Bot : PeerKind::User;
	} else if (peer->isChat() || peer->isMegagroup()) {
		return PeerKind::Group;
	}
	return PeerKind::Channel;
}

QString Rules::KindName(PeerKind kind) {
	switch (kind) {
	case PeerKind::User: return u"user"_q;
	case PeerKind::Bot: return u"bot"_q;
	case PeerKind::Group: return u"group"_q;
	case PeerKind::Channel: return u"channel"_q;
	}
	return u"channel"_q;
}

int64 Rules::selfId() const {
	// maybePrimarySession(), not activeAccount(): Domain::active() asserts that
	// an account exists, and on a first run there is none yet. The rules client
	// starts before the user has signed in, so reaching for the active account
	// directly took the whole app down at launch on a fresh profile.
	if (const auto session = Core::App().maybePrimarySession()) {
		return int64(session->userId().bare);
	}
	return 0;
}

void Rules::start() {
	if (_net) {
		return;
	}
	_net = new QNetworkAccessManager(this);
	for (const auto name : kLegacyNames) {
		QFile::remove(cWorkingDir() + QString::fromUtf8(name));
	}
	loadCache();
	LOG(("Puregram: rules client started, cached rules=%1 v=%2").arg(
		_rules.size()).arg(_version));
	syncAccount();
	_timer = new QTimer(this);
	_timer->setInterval(kRefreshMs);
	QObject::connect(_timer, &QTimer::timeout, this, [=] {
		flushPending();
		syncAccount();
		checkDeviceClaims();
	});
	_timer->start();
}

// ── Decision ────────────────────────────────────────────────────────────────

Verdict Rules::verdict(not_null<PeerData*> peer) const {
	if (peer->isSelf()) {
		return Verdict::Open;
	}
	const auto i = _rules.find(ChatId(peer->id));
	if (i != _rules.end() && i->blocked()) {
		return Verdict::Blocked; // permanent, checked before everything else
	}
	if (IsRestricted(peer)) {
		return Verdict::Restricted;
	}
	const auto kind = KindOf(peer);
	if (kind == PeerKind::User) {
		return Verdict::Open; // people are never gated
	}
	if (i != _rules.end() && i->rule == u"allow"_q) {
		return Verdict::Open;
	}
	return Verdict::NeedsChoice;
}

bool Rules::canOpen(not_null<PeerData*> peer) const {
	return verdict(peer) == Verdict::Open;
}

bool Rules::blocked(not_null<PeerData*> peer) const {
	const auto i = _rules.find(ChatId(peer->id));
	return (i != _rules.end()) && i->blocked();
}

QVector<int64> Rules::blockedIds() const {
	auto out = QVector<int64>();
	for (const auto &rule : _rules) {
		if (rule.blocked()) {
			out.push_back(rule.chatId);
		}
	}
	return out;
}

void Rules::refreshChatList(const QVector<int64> &chatIds) const {
	if (chatIds.isEmpty()) {
		return;
	}
	const auto session = Core::App().maybePrimarySession();
	if (!session) {
		return;
	}
	auto &owner = session->data();
	const auto refresh = [&](PeerId peerId) {
		if (const auto history = owner.historyLoaded(peerId)) {
			history->updateChatListExistence();
		}
	};
	for (const auto chatId : chatIds) {
		if (chatId > 0) {
			refresh(peerFromUser(UserId(chatId)));
			continue;
		}
		// A negative id is a basic group OR a channel — the shared wire format
		// does not distinguish them (see ChatId above), so nudge both and let
		// the one that is actually loaded answer. `::ChatId` on purpose: inside
		// this class the bare name is our own static method.
		refresh(peerFromChat(::ChatId(-chatId)));
		refresh(peerFromChannel(ChannelId(-chatId)));
	}
}

QVector<Rule> Rules::listOf(const QString &rule) const {
	auto out = QVector<Rule>();
	for (const auto &value : _rules) {
		if (value.rule == rule) {
			out.push_back(value);
		}
	}
	std::sort(out.begin(), out.end(), [](const Rule &a, const Rule &b) {
		return a.display().compare(b.display(), Qt::CaseInsensitive) < 0;
	});
	return out;
}

QString Rules::erasureEffectiveAt() const {
	return _erasureEffectiveAt;
}

QString Rules::claimPendingUntil() const {
	return _claimPendingUntil;
}

// ── Writes ──────────────────────────────────────────────────────────────────

void Rules::applyLocal(const Rule &rule) {
	_rules[rule.chatId] = rule;
	saveCache();
	if (rule.blocked()) {
		refreshChatList({ rule.chatId }); // drop it out of the chat list now
	}
	_changes.fire({});
}

void Rules::allow(not_null<PeerData*> peer) {
	const auto id = ChatId(peer->id);
	const auto i = _rules.find(id);
	if (i != _rules.end() && i->blocked()) {
		return; // the ratchet: a block is never reopened
	}
	auto rule = Rule{
		.chatId = id,
		.kind = KindName(KindOf(peer)),
		.rule = u"allow"_q,
		.username = peer->username(),
		.title = peer->name(),
	};
	applyLocal(rule);
	push(rule);
}

void Rules::block(not_null<PeerData*> peer) {
	auto rule = Rule{
		.chatId = ChatId(peer->id),
		.kind = KindName(KindOf(peer)),
		.rule = u"block"_q,
		.username = peer->username(),
		.title = peer->name(),
	};
	applyLocal(rule);
	push(rule);
}

void Rules::withdraw(not_null<PeerData*> peer) {
	const auto id = ChatId(peer->id);
	const auto i = _rules.find(id);
	if (i == _rules.end() || i->blocked()) {
		return;
	}
	_rules.erase(i);
	saveCache();
	_changes.fire({});

	auto op = QJsonObject();
	op.insert(u"op"_q, u"withdraw"_q);
	op.insert(u"chat_id"_q, double(id));
	_pending.push_back(op);
	flushPending();
}

void Rules::withdrawById(int64 chatId) {
	const auto i = _rules.find(chatId);
	if (i == _rules.end() || i->blocked()) {
		return; // never a way to lift a block
	}
	_rules.erase(i);
	saveCache();
	_changes.fire({});

	auto op = QJsonObject();
	op.insert(u"op"_q, u"withdraw"_q);
	op.insert(u"chat_id"_q, double(chatId));
	_pending.push_back(op);
	flushPending();
}

void Rules::blockById(int64 chatId) {
	auto rule = Rule{ .chatId = chatId, .rule = u"block"_q };
	const auto i = _rules.find(chatId);
	if (i != _rules.end()) {
		rule.kind = i->kind;
		rule.username = i->username;
		rule.title = i->title;
	}
	if (rule.kind.isEmpty()) {
		rule.kind = (chatId < 0) ? u"channel"_q : u"bot"_q;
	}
	applyLocal(rule);
	push(rule);
}

void Rules::push(const Rule &rule) {
	auto op = QJsonObject();
	op.insert(u"op"_q, u"rule"_q);
	op.insert(u"chat_id"_q, double(rule.chatId));
	op.insert(u"kind"_q, rule.kind);
	op.insert(u"rule"_q, rule.rule);
	if (!rule.username.isEmpty()) {
		op.insert(u"username"_q, rule.username);
	}
	if (!rule.title.isEmpty()) {
		op.insert(u"title"_q, rule.title);
	}
	_pending.push_back(op);
	flushPending();
}

// ── Networking ──────────────────────────────────────────────────────────────

QNetworkReply *Rules::request(
		const QByteArray &method,
		const QString &path,
		const QByteArray &body) {
	if (!_net) {
		return nullptr;
	}
	auto req = QNetworkRequest(QUrl(QString::fromUtf8(kApiBase) + path));
	req.setTransferTimeout(kTransferTimeoutMs);
	req.setRawHeader("Accept", "application/json");
	if (!_token.isEmpty()) {
		req.setRawHeader("Authorization", "Bearer " + _token);
	}
	if (!body.isEmpty()) {
		req.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
	}
	return _net->sendCustomRequest(req, method, body);
}

void Rules::flushPending() {
	if (_busy || _pending.isEmpty() || _token.isEmpty()) {
		return;
	}
	const auto self = selfId();
	if (!self) {
		return;
	}
	_busy = true;
	const auto op = _pending.front();
	const auto isWithdraw = (op.value(u"op"_q).toString() == u"withdraw"_q);
	const auto chatId = int64(op.value(u"chat_id"_q).toDouble());

	auto reply = (QNetworkReply*)nullptr;
	if (isWithdraw) {
		reply = request("DELETE", u"/rules/%1?tg_user_id=%2"_q
			.arg(chatId).arg(self));
	} else {
		auto payload = op;
		payload.remove(u"op"_q);
		payload.insert(u"tg_user_id"_q, double(self));
		reply = request("POST", u"/rules"_q,
			QJsonDocument(payload).toJson(QJsonDocument::Compact));
	}
	if (!reply) {
		_busy = false;
		return;
	}
	QObject::connect(reply, &QNetworkReply::finished, this, [=] {
		_busy = false;
		reply->deleteLater();
		const auto status = reply->attribute(
			QNetworkRequest::HttpStatusCodeAttribute).toInt();
		if (status >= 200 && status < 300) {
			apply(QJsonDocument::fromJson(reply->readAll()).object());
		} else if (status < 400 || status >= 500) {
			// Network or server trouble: keep the op and retry on the next tick.
			return;
		}
		// 2xx, or a 4xx the server will never accept — either way replaying it
		// for ever would wedge the queue behind it.
		if (!_pending.isEmpty()) {
			_pending.pop_front();
		}
		flushPending();
	});
}

void Rules::syncAccount() {
	const auto self = selfId();
	if (!self || !_net) {
		return;
	}
	if (_token.isEmpty()) {
		// Bootstrap a device token first; the sync runs on the next tick.
		auto body = QJsonObject();
		body.insert(u"device_id"_q, [&] {
			auto saved = QSettings(cachePath() + u".device"_q,
				QSettings::IniFormat).value(u"id"_q).toString();
			if (saved.isEmpty()) {
				saved = QUuid::createUuid().toString(QUuid::WithoutBraces);
				auto out = QSettings(cachePath() + u".device"_q,
					QSettings::IniFormat);
				out.setValue(u"id"_q, saved);
				out.sync();
			}
			return saved;
		}());
		body.insert(u"model"_q, u"Puregram Desktop"_q);
		const auto reply = request("POST", u"/device/checkin"_q,
			QJsonDocument(body).toJson(QJsonDocument::Compact));
		if (!reply) {
			return;
		}
		QObject::connect(reply, &QNetworkReply::finished, this, [=] {
			reply->deleteLater();
			const auto json = QJsonDocument::fromJson(reply->readAll()).object();
			_token = json.value(u"token"_q).toString().toUtf8();
			if (!_token.isEmpty()) {
				saveCache();
				syncAccount();
			}
		});
		return;
	}

	const auto reply = request("GET", u"/rules?tg_user_id=%1"_q.arg(self));
	if (!reply) {
		return;
	}
	QObject::connect(reply, &QNetworkReply::finished, this, [=] {
		reply->deleteLater();
		const auto status = reply->attribute(
			QNetworkRequest::HttpStatusCodeAttribute).toInt();
		if (status == 409) {
			// This device's claim on the account is waiting for approval from
			// an already-trusted one. Local rules keep working meanwhile.
			const auto detail = QJsonDocument::fromJson(reply->readAll())
				.object().value(u"detail"_q).toObject();
			_claimPendingUntil = detail.value(u"auto_approve_at"_q).toString();
			_changes.fire({});
			return;
		}
		if (status != 200) {
			return;
		}
		_claimPendingUntil = QString();
		apply(QJsonDocument::fromJson(reply->readAll()).object());
	});
}

bool Rules::apply(const QJsonObject &document) {
	const auto rules = document.value(u"rules"_q);
	if (!rules.isArray()) {
		return false;
	}
	auto next = QHash<int64, Rule>();
	for (const auto &value : rules.toArray()) {
		const auto entry = value.toObject();
		const auto id = int64(entry.value(u"chat_id"_q).toDouble());
		if (!id) {
			continue;
		}
		next.insert(id, Rule{
			.chatId = id,
			.kind = entry.value(u"kind"_q).toString(),
			.rule = entry.value(u"rule"_q).toString(),
			.username = entry.value(u"username"_q).toString(),
			.title = entry.value(u"title"_q).toString(),
		});
	}
	// The union of what was blocked and what is blocked now: a chat that just
	// became blocked has to leave the list, and one whose block disappeared
	// (an erasure ran) has to come back.
	auto touched = blockedIds();
	_version = document.value(u"version"_q).toInt();
	_rules = std::move(next);
	_erasureEffectiveAt = document.value(u"erasure_effective_at"_q).toString();
	for (const auto chatId : blockedIds()) {
		if (!touched.contains(chatId)) {
			touched.push_back(chatId);
		}
	}
	saveCache();
	refreshChatList(touched);
	_changes.fire({});
	return true;
}

void Rules::checkDeviceClaims() {
	const auto self = selfId();
	if (!self || _token.isEmpty()) {
		return;
	}
	const auto reply = request("GET", u"/rules/meta?tg_user_id=%1"_q.arg(self));
	if (!reply) {
		return;
	}
	QObject::connect(reply, &QNetworkReply::finished, this, [=] {
		reply->deleteLater();
		const auto json = QJsonDocument::fromJson(reply->readAll()).object();
		for (const auto &value : json.value(u"pending_devices"_q).toArray()) {
			const auto entry = value.toObject();
			const auto id = entry.value(u"device_id"_q).toString();
			if (id.isEmpty() || _promptedClaims.contains(id)) {
				continue;
			}
			_promptedClaims.push_back(id);
			promptDeviceClaim(id, entry.value(u"model"_q).toString());
		}
	});
}

void Rules::promptDeviceClaim(const QString &deviceId, const QString &model) {
	const auto self = selfId();
	const auto what = model.isEmpty() ? deviceId : model;
	const auto answer = [=](bool approve) {
		const auto path = u"/rules/devices/%1/%2?tg_user_id=%3"_q
			.arg(QString::fromUtf8(QUrl::toPercentEncoding(deviceId)))
			.arg(approve ? u"approve"_q : u"deny"_q)
			.arg(self);
		if (const auto reply = request("POST", path, "{}")) {
			QObject::connect(reply, &QNetworkReply::finished, this, [=] {
				reply->deleteLater();
				syncAccount();
			});
		}
	};
	ShowBox(Ui::MakeConfirmBox({
		.text = Tr(
			"جهاز جديد يريد مزامنة قوائم السماح والحجب لحسابك.\n\n"
			"إن لم يكن جهازك أنت، ارفضه.",
			"A new device wants to sync your allow and block lists.\n\n"
			"If this is not your device, deny it.") + u"\n\n"_q + what,
		// The `close` form throughout this file, never the plain Fn<void()>:
		// ConfirmBox only closes itself for a NULL callback, so a plain one
		// runs and leaves the box on screen — the button looks broken.
		.confirmed = [=](Fn<void()> close) { answer(true); close(); },
		.cancelled = [=](Fn<void()> close) { answer(false); close(); },
		.confirmText = Tr("موافقة", "Approve"),
		.cancelText = Tr("رفض", "Deny"),
		.title = Tr("جهاز جديد", "A new device"),
		.strictCancel = true,
	}));
}

void Rules::requestErasure() {
	const auto self = selfId();
	if (!self) {
		return;
	}
	if (const auto reply = request("DELETE",
			u"/rules?tg_user_id=%1&confirm=erase"_q.arg(self))) {
		QObject::connect(reply, &QNetworkReply::finished, this, [=] {
			reply->deleteLater();
			_erasureEffectiveAt = QJsonDocument::fromJson(reply->readAll())
				.object().value(u"effective_at"_q).toString();
			_changes.fire({});
		});
	}
}

void Rules::cancelErasure() {
	const auto self = selfId();
	if (!self) {
		return;
	}
	if (const auto reply = request("POST",
			u"/rules/erase/cancel?tg_user_id=%1"_q.arg(self), "{}")) {
		QObject::connect(reply, &QNetworkReply::finished, this, [=] {
			reply->deleteLater();
			apply(QJsonDocument::fromJson(reply->readAll()).object());
		});
	}
}

// ── Cache ───────────────────────────────────────────────────────────────────

QString Rules::cachePath() const {
	auto dir = cWorkingDir();
	if (dir.isEmpty()) {
		dir = QStandardPaths::writableLocation(
			QStandardPaths::AppDataLocation) + '/';
	}
	QDir().mkpath(dir);
	return dir + QString::fromUtf8(kStateName);
}

void Rules::loadCache() {
	auto file = QFile(cachePath());
	if (!file.open(QIODevice::ReadOnly)) {
		return;
	}
	const auto json = QJsonDocument::fromJson(file.readAll()).object();
	_token = json.value(u"token"_q).toString().toUtf8();
	for (const auto &value : json.value(u"pending"_q).toArray()) {
		_pending.push_back(value.toObject());
	}
	apply(json.value(u"document"_q).toObject());
}

void Rules::saveCache() const {
	auto rules = QJsonArray();
	for (const auto &rule : _rules) {
		auto entry = QJsonObject();
		entry.insert(u"chat_id"_q, double(rule.chatId));
		entry.insert(u"kind"_q, rule.kind);
		entry.insert(u"rule"_q, rule.rule);
		entry.insert(u"username"_q, rule.username);
		entry.insert(u"title"_q, rule.title);
		rules.push_back(entry);
	}
	auto document = QJsonObject();
	document.insert(u"version"_q, _version);
	document.insert(u"rules"_q, rules);
	document.insert(u"erasure_effective_at"_q, _erasureEffectiveAt);

	auto pending = QJsonArray();
	for (const auto &op : _pending) {
		pending.push_back(op);
	}

	auto json = QJsonObject();
	json.insert(u"token"_q, QString::fromUtf8(_token));
	json.insert(u"document"_q, document);
	json.insert(u"pending"_q, pending);

	auto file = QFile(cachePath());
	if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
		LOG(("Puregram: cannot write %1").arg(cachePath()));
		return;
	}
	file.write(QJsonDocument(json).toJson(QJsonDocument::Compact));
}

// ── The "Allowed and blocked" box ───────────────────────────────────────────

QString RulesTitle() {
	return Tr("المسموح والمحجوب", "Allowed and blocked");
}

rpl::producer<QString> RulesTitleValue() {
	return rpl::single(
		rpl::empty
	) | rpl::then(
		Lang::GetInstance().idChanges() | rpl::to_empty
	) | rpl::map([] { return RulesTitle(); });
}

void ShowRefusal(not_null<PeerData*> peer, Fn<void()> retry) {
	auto &rules = Rules::Instance();
	const auto verdict = rules.verdict(peer);
	const auto name = peer->name();
	const auto identity = peer->username().isEmpty()
		? QString::number(Rules::ChatId(peer->id))
		: ('@' + peer->username());
	const auto head = name + u"\n"_q + identity + u"\n\n"_q;

	if (verdict == Verdict::Blocked) {
		// Nothing to offer: the block is permanent, and pretending otherwise
		// would undo the only guarantee this app makes.
		ShowBox(Ui::MakeInformBox(head + Tr(
			"حجبتَ هذه المحادثة نهائياً. لا يمكن التراجع عن الحجب.",
			"You blocked this chat permanently. A block cannot be undone.")));
		return;
	} else if (verdict == Verdict::Restricted) {
		ShowBox(Ui::MakeInformBox(head + Tr(
			"صنّف تيليجرام هذه المحادثة كمقيّدة أو حساسة، فلا تُفتح في Puregram.",
			"Telegram marks this chat restricted or sensitive, so Puregram will not open it.")));
		return;
	}

	const auto peerId = peer->id;
	ShowBox(Ui::MakeConfirmBox({
		.text = head + Tr(
			"القنوات والبوتات والمجموعات مغلقة حتى تسمح بها. الحجب دائم ولا رجعة فيه.",
			"Channels, bots and groups stay closed until you allow them. Blocking is permanent."),
		.confirmed = [=](Fn<void()> close) {
			if (const auto session = Core::App().maybePrimarySession()) {
				Rules::Instance().allow(session->data().peer(peerId));
			}
			close();
			// Then finish what the user was doing. Writing the rule and going
			// no further left them on the same screen with the chat still
			// unopened, which is exactly what a broken button looks like.
			if (retry) {
				retry();
			}
		},
		.cancelled = [=](Fn<void()>) {
			// Second confirmation: blocking can never be walked back, so it is
			// never one tap away. It replaces this box rather than covering it,
			// which is why the close callback goes unused here.
			ShowBox(Ui::MakeConfirmBox({
				.text = Tr(
					"سيُحجب نهائياً. لا يمكن التراجع لاحقاً، لا من هذا الجهاز ولا من غيره.",
					"This will be blocked forever. It cannot be undone later, on this device or any other."),
				.confirmed = [=](Fn<void()> closeInner) {
					if (const auto s2 = Core::App().maybePrimarySession()) {
						Rules::Instance().block(s2->data().peer(peerId));
					}
					closeInner();
				},
				.confirmText = Tr("احجب نهائياً", "Block forever"),
				.cancelText = Tr("إلغاء", "Cancel"),
				.title = Tr("حجب دائم", "Block forever"),
			}), true);
		},
		.confirmText = Tr("السماح", "Allow"),
		.cancelText = Tr("حجب دائم", "Block forever"),
		.title = Tr("غير متاحة", "Not available"),
		.strictCancel = true,
	}));
}

namespace {

// Fills `layout` with the lists as they stand right now. Called again from
// scratch whenever they change: this box is the one screen where a withdrawal
// or a block has to show immediately, and rebuilding is easier to get right
// than patching rows in place.
void FillRules(not_null<Ui::VerticalLayout*> layout) {
	auto &rules = Rules::Instance();
	layout->clear();
	{
		const auto claim = rules.claimPendingUntil();
		Ui::AddSkip(layout);
		Ui::AddDividerText(layout, rpl::single(claim.isEmpty()
			? Tr("الأشخاص مفتوحون دائماً. القنوات والبوتات والمجموعات مغلقة حتى تسمح بها.",
				"People always open. Channels, bots and groups stay closed until you allow them.")
			: (Tr("هذا الجهاز ينتظر موافقة جهازك الآخر لمزامنة قوائمك حتى ",
				"This device is waiting for your other device to approve syncing until ")
				+ ShortDate(claim))));
	}

	const auto allowed = rules.listOf(u"allow"_q);
	Ui::AddSkip(layout);
	Ui::AddSubsectionTitle(layout, rpl::single(
		Tr("المسموح بها", "Allowed")));
	for (const auto &rule : allowed) {
		const auto chatId = rule.chatId;
		const auto name = rule.display();
		layout->add(object_ptr<Ui::SettingsButton>(
			layout,
			rpl::single(name),
			st::settingsButtonNoIcon
		))->setClickedCallback([=] {
			// Both choices tighten; there is no third, looser option.
			ShowBox(Ui::MakeConfirmBox({
				.text = name,
				.confirmed = [=](Fn<void()> close) {
					Rules::Instance().withdrawById(chatId);
					close();
				},
				.cancelled = [=](Fn<void()> close) {
					Rules::Instance().blockById(chatId);
					close();
				},
				.confirmText = Tr("سحب السماح", "Withdraw"),
				.cancelText = Tr("حجب دائم", "Block forever"),
				.strictCancel = true,
			}));
		});
	}
	Ui::AddDividerText(layout, rpl::single(allowed.isEmpty()
		? Tr("لم تسمح بشيء بعد. عندما تفتح محادثة مغلقة سيسألك التطبيق.",
			"Nothing allowed yet. When you open a closed chat the app will ask you.")
		: Tr("اضغط على أي عنصر لسحب السماح أو حجبه نهائياً.",
			"Tap an item to withdraw it or block it forever.")));

	const auto blocked = rules.listOf(u"block"_q);
	Ui::AddSkip(layout);
	Ui::AddSubsectionTitle(layout, rpl::single(
		Tr("المحجوبة نهائياً", "Blocked forever")));
	for (const auto &rule : blocked) {
		// Read-only on purpose: offering any control here would suggest the
		// block can be lifted, and it cannot.
		layout->add(object_ptr<Ui::SettingsButton>(
			layout,
			rpl::single(rule.display()),
			st::settingsButtonNoIcon
		))->setClickedCallback([] {
			ShowBox(Ui::MakeInformBox(Tr(
				"الحجب دائم ولا يمكن التراجع عنه.",
				"Blocking is permanent and cannot be undone.")));
		});
	}
	Ui::AddDividerText(layout, rpl::single(blocked.isEmpty()
		? Tr("لم تحجب شيئاً بعد. الحجب قرار دائم لا رجعة فيه.",
			"Nothing blocked yet. Blocking is a permanent decision.")
		: Tr("هذه المحادثات محجوبة نهائياً ولا يمكن فتحها مرة أخرى.",
			"These chats are blocked forever and cannot be opened again.")));

	// The data-deletion path. Scheduled, never instant: erasing the rules
	// also clears the permanent blocks, so an immediate button would be a
	// one-tap way around them. Worded as "delete my data", never "unblock".
	const auto pending = rules.erasureEffectiveAt();
	Ui::AddSkip(layout);
	layout->add(object_ptr<Ui::SettingsButton>(
		layout,
		rpl::single(pending.isEmpty()
			? Tr("حذف بياناتي", "Delete my data")
			: (Tr("حذف مجدول — ", "Deletion scheduled — ") + ShortDate(pending))),
		st::settingsButtonNoIcon
	))->setClickedCallback([=] {
		if (!pending.isEmpty()) {
			ShowBox(Ui::MakeConfirmBox({
				.text = Tr(
					"ستُحذف بياناتك في هذا التاريخ. قوائمك تعمل كالمعتاد حتى ذلك الحين.",
					"Your data will be deleted on this date. Your lists keep working until then.")
					+ u"\n\n"_q + ShortDate(pending),
				.confirmed = [](Fn<void()> close) {
					Rules::Instance().cancelErasure();
					close();
				},
				.confirmText = Tr("إلغاء الحذف", "Cancel deletion"),
				.cancelText = Tr("إغلاق", "Close"),
				.title = Tr("حذف مجدول", "Deletion scheduled"),
			}));
			return;
		}
		ShowBox(Ui::MakeConfirmBox({
			.text = Tr(
				"سيُحذف كل ما نحفظه لحسابك — قوائم السماح والحجب — بعد 60 يوماً. حتى ذلك اليوم تبقى قوائمك سارية، ويمكنك إلغاء الطلب في أي وقت.",
				"Everything we store for your account — your allow and block lists — will be "
				"deleted after 60 days. Until then your lists stay in force, and you can cancel any time."),
			.confirmed = [](Fn<void()> close) {
				Rules::Instance().requestErasure();
				close();
			},
			.confirmText = Tr("اطلب الحذف", "Request deletion"),
			.cancelText = Tr("إلغاء", "Cancel"),
			.title = Tr("حذف بياناتي", "Delete my data"),
		}));
	});
	Ui::AddDividerText(layout, rpl::single(Tr(
		"يحذف بياناتك المحفوظة بعد 60 يوماً. قوائمك سارية حتى ذلك الحين، ويمكنك الإلغاء.",
		"Deletes your stored data after 60 days. Your lists stay in force until then, and you can cancel.")));
}

} // namespace

void ShowRulesBox() {
	ShowBox(Box([](not_null<Ui::GenericBox*> box) {
		box->setTitle(RulesTitleValue());

		// The lists live in their own layout so they can be thrown away and
		// redrawn; the box's own layout also holds the buttons.
		const auto outer = box->verticalLayout();
		const auto layout = outer->add(
			object_ptr<Ui::VerticalLayout>(outer));
		FillRules(layout);

		// Two reasons to redraw: the lists changed, or the app language did —
		// every string in here is chosen when the row is built, so a language
		// switch has to rebuild them the way tr::lng_* phrases update themselves.
		rpl::merge(
			Rules::Instance().changes(),
			Lang::GetInstance().idChanges() | rpl::to_empty
		) | rpl::on_next([=] {
			// Deferred: a change usually arrives from inside a button's own
			// click handler, and clearing the layout there would destroy a
			// widget that is still running.
			crl::on_main(box, [=] { FillRules(layout); });
		}, box->lifetime());

		box->addButton(rpl::single(
			rpl::empty
		) | rpl::then(
			Lang::GetInstance().idChanges() | rpl::to_empty
		) | rpl::map([] {
			return Tr("إغلاق", "Close");
		}), [=] {
			box->closeBox();
		});
	}));
}

} // namespace Puregram
