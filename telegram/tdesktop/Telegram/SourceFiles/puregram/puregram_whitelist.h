/*
Puregram per-account chat rules for Telegram Desktop — the ONLY behavioural
difference from upstream tdesktop (ADR-002, see POLICY_SPEC.md at the repo root).

Every account governs its own client. People and secret chats always open;
channels, bots and groups are closed until the user allows them. `allow` is
reversible, `block` is PERMANENT — the one-way ratchet is enforced here, in the
UI, and again on the server, so no single layer can be talked out of it.

Rules are keyed by Telegram account id on the server, so they follow the account
to every device the user signs in on. A cache on disk keeps enforcement working
offline and at startup; changes made offline queue and are pushed when the
network returns.
*/
#pragma once

#include "data/data_peer_id.h"

#include <QtCore/QObject>
#include <QtCore/QByteArray>
#include <QtCore/QHash>
#include <QtCore/QString>
#include <QtCore/QVector>

#include <array>

class PeerData;
class QJsonObject;
class QNetworkAccessManager;
class QNetworkReply;
class QTimer;


namespace Puregram {

// The app's display name — "Puregram", matching the Android app. Display-only
// (window title, tray, notifications); the data folder keeps the stock AppName
// so existing logins survive the rename.
[[nodiscard]] QString AppDisplayName();

// Discovery surfaces removed from this client (POLICY_SPEC §9). Free-text search
// of the public GIF and sticker indexes is a search box for media, so it is
// closed; saved / installed / trending items are untouched.
inline constexpr auto kGifSearchEnabled = false;
inline constexpr auto kStickerSearchEnabled = false;
// Searching Telegram at large: messages, public posts and peers. Every entry
// point is closed, not just the obvious one — the Links tab reached it by a
// path with no gate at all. Opening a link you already have still works; that
// is contacts.resolveUsername, and what it resolves to is still checked.
inline constexpr auto kGlobalSearchEnabled = false;

// Peer classification used by the rules: `Group` covers basic groups AND
// megagroups; `Channel` is a broadcast channel only.
enum class PeerKind : uchar {
	User,
	Bot,
	Group,
	Channel,
};
constexpr auto kPeerKindCount = 4;

enum class Verdict : uchar {
	Open,          // nothing to ask: a person, or explicitly allowed
	NeedsChoice,   // gated and unruled — the user may allow or block
	Blocked,       // permanently blocked by the user
	Restricted,    // Telegram itself marks it restricted/sensitive
};

struct Rule {
	int64 chatId = 0;
	QString kind;
	QString rule;      // "allow" | "block"
	QString username;  // may be empty
	QString title;     // may be empty

	[[nodiscard]] bool blocked() const {
		return rule == u"block"_q;
	}
	[[nodiscard]] QString identity() const {
		return username.isEmpty() ? QString::number(chatId) : ('@' + username);
	}
	[[nodiscard]] QString display() const {
		return title.isEmpty() ? identity() : title;
	}
};

// Singleton. Lives for the whole app lifetime; started in Core::Application.
// Everything runs on the main thread (the QNetworkAccessManager lives there).
class Rules final : public QObject {
public:
	static Rules &Instance();

	// Applies the cached rules, then syncs and keeps polling every 60 s.
	void start();

	// The decision rule from POLICY_SPEC §2 — the same semantics as the
	// Android fork. Every "open chat" path funnels through this.
	[[nodiscard]] bool canOpen(not_null<PeerData*> peer) const;
	[[nodiscard]] Verdict verdict(not_null<PeerData*> peer) const;

	// Just the permanent block — one hash lookup, no restriction checks. The
	// chat list asks this for every row on every rebuild, so it must stay cheap;
	// verdict() computes an unavailable-reason string that would be wasted here.
	[[nodiscard]] bool blocked(not_null<PeerData*> peer) const;

	// Writes. `block` can never be undone; `withdraw` only removes an allow.
	void allow(not_null<PeerData*> peer);
	void block(not_null<PeerData*> peer);
	void withdraw(not_null<PeerData*> peer);
	// Same three, addressed by stored chat id — the lists box has no
	// PeerData in hand, only the rule it is showing.
	void withdrawById(int64 chatId);
	void blockById(int64 chatId);

	// The account's lists, for the settings box.
	[[nodiscard]] QVector<Rule> listOf(const QString &rule) const;
	// ISO time this account's data is due to be erased, or empty.
	[[nodiscard]] QString erasureEffectiveAt() const;
	// ISO time this device's claim on the account auto-approves, or empty when
	// the device is already trusted.
	[[nodiscard]] QString claimPendingUntil() const;

	void requestErasure();
	void cancelErasure();

	// PeerId -> the signed chat id shared with the server AND the Android fork:
	// user/bot = +id, basic group = -id, channel/supergroup = -id (plain
	// negation, NOT the Bot-API -100... form).
	[[nodiscard]] static int64 ChatId(PeerId peerId);
	[[nodiscard]] static PeerKind KindOf(not_null<PeerData*> peer);
	[[nodiscard]] static QString KindName(PeerKind kind);

	// Fires whenever the rules change, so open boxes can refresh.
	[[nodiscard]] rpl::producer<> changes() const {
		return _changes.events();
	}

private:
	Rules();

	void syncAccount();
	void checkDeviceClaims();
	void flushPending();
	void push(const Rule &rule);
	void applyLocal(const Rule &rule);
	[[nodiscard]] bool apply(const QJsonObject &document);
	void loadCache();
	void saveCache() const;
	// Blocked chats are hidden from the chat list, so whenever the set of blocks
	// changes the affected rows have to be re-asked. Takes the ids that entered
	// OR left the blocked set — a chat coming back after an erasure needs the
	// same nudge as one being hidden.
	void refreshChatList(const QVector<int64> &chatIds) const;
	[[nodiscard]] QVector<int64> blockedIds() const;
	[[nodiscard]] QString cachePath() const;
	[[nodiscard]] int64 selfId() const;
	void promptDeviceClaim(const QString &deviceId, const QString &model);
	[[nodiscard]] QNetworkReply *request(
		const QByteArray &method,
		const QString &path,
		const QByteArray &body = {});

	QNetworkAccessManager *_net = nullptr;
	QTimer *_timer = nullptr;
	QByteArray _token;
	QString _erasureEffectiveAt;
	QString _claimPendingUntil;
	bool _busy = false;

	int _version = 0;
	QHash<int64, Rule> _rules;
	QVector<QJsonObject> _pending;      // offline writes, replayed in order
	QVector<QString> _promptedClaims;   // ask about each new device once

	rpl::event_stream<> _changes;

};

// "Allowed and blocked" — the settings row and the box share this one string.
// It follows the app's language, not the system locale, exactly as every
// tr::lng_* phrase does.
[[nodiscard]] QString RulesTitle();

// The same, as a producer that re-emits when the app language changes, so the
// settings row relabels itself live like the rows around it.
[[nodiscard]] rpl::producer<QString> RulesTitleValue();

// Opens the "Allowed and blocked" box on the active window.
void ShowRulesBox();

// The refusal box shown at the gate: names the peer and offers the two
// choices that exist — allow it, or block it for good.
//
// `retry` is what the user was trying to do when the gate stopped them, run
// again after they allow. Without it, allowing only wrote the rule and left
// them staring at the same screen, which is indistinguishable from a dead
// button — so every call site passes one.
void ShowRefusal(not_null<PeerData*> peer, Fn<void()> retry = nullptr);

} // namespace Puregram
