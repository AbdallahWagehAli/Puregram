package org.telegram.messenger;

import android.content.Context;
import android.content.SharedPreferences;
import android.text.TextUtils;

import org.json.JSONArray;
import org.json.JSONObject;
import org.telegram.tgnet.ConnectionsManager;
import org.telegram.tgnet.TLObject;
import org.telegram.tgnet.TLRPC;
import org.telegram.ui.ActionBar.AlertDialog;
import org.telegram.ui.LaunchActivity;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Puregram per-account chat rules — the ONLY behavioural difference between this
 * fork and the official Telegram for Android (contract: POLICY_SPEC.md, ADR-002).
 *
 * <p>Every account governs its own client. People and secret chats always open.
 * Channels, bots and groups are closed until the user allows them. {@code allow}
 * is reversible; <b>{@code block} is permanent</b> — the one-way ratchet is the
 * point of the product, and it is enforced here, in the UI, and on the server.
 *
 * <p>Rules are keyed by Telegram account id on the server, so they follow the
 * account to every device the user signs in on. A local cache keeps enforcement
 * working offline and at startup, and pending local changes are pushed when the
 * network comes back.
 *
 * <p>Dialog-id encoding is Telegram-Android's own: user/bot {@code +id},
 * group/channel {@code -id}.
 */
public final class PuregramRules {

    // ── Discovery surfaces removed from this build (POLICY_SPEC §9) ─────────
    /** Telegram's "show sensitive content" switch: never on, never shown. */
    public static final boolean SENSITIVE_CONTENT_ALLOWED = false;
    /** Hide Telegram sponsored messages (ads) everywhere. */
    public static final boolean HIDE_SPONSORED_MESSAGES = true;
    /** "Similar channels" strip + channel/bot recommendations. */
    public static final boolean CHANNEL_RECOMMENDATIONS_ENABLED = false;
    /** {@code @bot query} inline results inside the composer. */
    public static final boolean INLINE_BOTS_ENABLED = false;
    /** Web image search in the photo picker (an inline bot in disguise). */
    public static final boolean WEB_IMAGE_SEARCH_ENABLED = false;
    /** Public-post / hashtag search across all of Telegram. */
    public static final boolean PUBLIC_POSTS_SEARCH_ENABLED = false;
    /** Free-text GIF search (the public GIF index behind the emoji panel). */
    public static final boolean GIF_SEARCH_ENABLED = false;
    /** Free-text sticker-set search (the public sticker-set index). */
    public static final boolean STICKER_SEARCH_ENABLED = false;
    /** The "Channels" / "Apps" / "Posts" discovery tabs in the search pager. */
    public static final boolean DISCOVERY_TABS_ENABLED = false;
    /**
     * Searching Telegram at large: messages ({@code messages.searchGlobal}), public
     * posts ({@code channels.searchPosts}) and peers ({@code contacts.search}).
     *
     * <p>Enforced in {@code ConnectionsManager.sendRequestInternal} rather than in
     * each screen: there are about ten call sites, and one of them (the Links tab)
     * reached global search by a path with no gate at all. Refusing the request
     * itself closes every route, including ones added by a later upstream merge.
     *
     * <p>Opening a link you already have still works — that is
     * {@code contacts.resolveUsername}, a different request, and what it resolves to
     * is still checked by the rules before it opens.
     */
    public static final boolean GLOBAL_SEARCH_ENABLED = false;

    /**
     * An empty, well-formed answer for a refused global search, or null if this is
     * not one. Returning an empty result rather than an error makes callers render
     * their ordinary "nothing found" state instead of hanging or showing a failure.
     */
    public static TLObject refuseGlobalSearch(TLObject request) {
        if (GLOBAL_SEARCH_ENABLED || request == null) {
            return null;
        }
        if (request instanceof TLRPC.TL_messages_searchGlobal
                || request instanceof TLRPC.TL_channels_searchPosts) {
            return new TLRPC.TL_messages_messages();
        }
        if (request instanceof TLRPC.TL_contacts_search) {
            return new TLRPC.TL_contacts_found();
        }
        return null;
    }

    /** The folder downloads and saved media go into. Upstream hard-codes
     *  "Telegram" in half a dozen places; one constant keeps them in step. */
    public static final String MEDIA_FOLDER = "Puregram";

    public static final String KIND_USER = "user";
    public static final String KIND_BOT = "bot";
    public static final String KIND_GROUP = "group";
    public static final String KIND_CHANNEL = "channel";

    /** Bot-API writes channel ids as -100<id>; the clients use plain -<id>. */
    private static final long BOT_API_CHANNEL_OFFSET = 1_000_000_000_000L;

    public static final String RULE_ALLOW = "allow";
    public static final String RULE_BLOCK = "block";

    private static final String BASE_URL = "https://puregram.app/control/v1";
    private static final String PREFS = "puregram_rules";
    private static final String KEY_TOKEN = "device_token";
    private static final String KEY_CACHE = "rules_cache_json";
    private static final String KEY_PENDING = "pending_ops_json";
    private static final long REFRESH_INTERVAL_MS = 60 * 1000L;
    private static final long RETRY_INTERVAL_MS = 20 * 1000L;
    private static final int HTTP_TIMEOUT_MS = 15000;

    private static volatile PuregramRules instance;

    /** One rule as the user sees it. */
    public static final class Rule {
        public final long chatId;
        public final String kind;
        public final String rule;
        public final String username;   // may be null
        public final String title;      // may be null

        Rule(long chatId, String kind, String rule, String username, String title) {
            this.chatId = chatId;
            this.kind = kind;
            this.rule = rule;
            this.username = username;
            this.title = title;
        }

        public boolean isBlock() {
            return RULE_BLOCK.equals(rule);
        }

        /** The panel-ready identity: "@username" when there is one, else the id. */
        public String identity() {
            return TextUtils.isEmpty(username) ? String.valueOf(chatId) : "@" + username;
        }
    }

    /** Immutable per-account snapshot. */
    private static final class Snapshot {
        final int version;
        final Map<Long, Rule> byChat;
        final String erasureEffectiveAt;   // null when no erasure is pending

        Snapshot(int version, Map<Long, Rule> byChat, String erasureEffectiveAt) {
            this.version = version;
            this.byChat = Collections.unmodifiableMap(byChat);
            this.erasureEffectiveAt = erasureEffectiveAt;
        }

        static Snapshot empty() {
            return new Snapshot(0, new HashMap<>(), null);
        }
    }

    private final Context appContext;
    private final AtomicBoolean networkBusy = new AtomicBoolean(false);
    /** tg_user_id -> that account's rules. */
    private volatile Map<Long, Snapshot> byAccount = new HashMap<>();
    /** Changes made offline, replayed in order when the network returns. */
    private final List<JSONObject> pending = new ArrayList<>();
    private volatile String token;

    private PuregramRules(Context context) {
        this.appContext = context.getApplicationContext();
    }

    public static PuregramRules getInstance() {
        PuregramRules local = instance;
        if (local == null) {
            synchronized (PuregramRules.class) {
                local = instance;
                if (local == null) {
                    local = new PuregramRules(ApplicationLoader.applicationContext);
                    instance = local;
                }
            }
        }
        return local;
    }

    public static String baseUrl() {
        return BASE_URL;
    }

    /** Called once from {@link ApplicationLoader#onCreate()}. */
    public static void init(Context context) {
        if (instance == null) {
            synchronized (PuregramRules.class) {
                if (instance == null) {
                    instance = new PuregramRules(context);
                }
            }
        }
        instance.start();
    }

    private void start() {
        SharedPreferences prefs = prefs();
        token = prefs.getString(KEY_TOKEN, null);
        loadCache(prefs.getString(KEY_CACHE, null));
        loadPending(prefs.getString(KEY_PENDING, null));
        Utilities.globalQueue.postRunnable(refreshTask);
    }

    private SharedPreferences prefs() {
        return appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private final Runnable refreshTask = new Runnable() {
        @Override
        public void run() {
            boolean ok = false;
            try {
                ok = syncOnce();
            } catch (Throwable ignored) {
                // The sync loop must never crash the app.
            }
            Utilities.globalQueue.postRunnable(this, ok ? REFRESH_INTERVAL_MS : RETRY_INTERVAL_MS);
        }
    };

    // ── Decision API ────────────────────────────────────────────────────────

    // ── Our own strings ─────────────────────────────────────────────────────

    private static volatile Context localizedContext;
    private static volatile String localizedLang;

    /**
     * A Puregram string in the language chosen INSIDE the app.
     *
     * Not LocaleController.getString(). That reads Telegram's downloaded language
     * pack first and falls back to Android resources for anything the pack does
     * not carry — and our keys are never in the pack, so every Puregram string
     * took the fallback. The fallback resolves against the resource configuration,
     * and although applyLanguage() calls updateConfiguration() to point that at
     * the in-app language, the override does not survive on modern Android: the
     * system reapplies the device configuration on the next configuration change
     * and never restores it.
     *
     * The visible result was an English Telegram UI with Arabic Puregram rows on
     * an Arabic phone. So resolve against a Context we configure ourselves, which
     * no one else can reset. The context is cached and rebuilt only when the
     * language actually changes.
     */
    public static String str(int resId) {
        final Context base = ApplicationLoader.applicationContext;
        if (base == null) {
            return "";
        }
        final String lang = appLanguageTag();
        Context ctx = localizedContext;
        if (ctx == null || !lang.equals(localizedLang)) {
            final android.content.res.Configuration cfg =
                    new android.content.res.Configuration(base.getResources().getConfiguration());
            cfg.setLocale(java.util.Locale.forLanguageTag(lang));
            ctx = base.createConfigurationContext(cfg);
            localizedContext = ctx;
            localizedLang = lang;
        }
        try {
            return ctx.getString(resId);
        } catch (Throwable ignored) {
            return base.getString(resId);
        }
    }

    /** BCP-47 tag of the app's language, e.g. "en", "ar". */
    private static String appLanguageTag() {
        try {
            final LocaleController.LocaleInfo info =
                    LocaleController.getInstance().getCurrentLocaleInfo();
            if (info != null && !TextUtils.isEmpty(info.getLangCode())) {
                return info.getLangCode();
            }
        } catch (Throwable ignored) {
        }
        return "en";
    }

    /**
     * Just the permanent block — one map lookup, no restriction checks.
     *
     * The chat list asks this for every dialog on every sort, so it has to stay
     * cheap; canOpen() reaches into MessagesController for the peer and would be
     * wasted work here. A blocked chat is hidden from the list entirely, not
     * merely refused on open: seeing the name, the unread badge and the newest
     * message of something you decided never to open again is most of what you
     * were trying to get away from.
     */
    public boolean isBlocked(int account, long dialogId) {
        if (dialogId == 0) {
            return false;
        }
        final Rule rule = ruleFor(UserConfig.getInstance(account).getClientUserId(), dialogId);
        return rule != null && rule.isBlock();
    }

    /** Universal "may this chat be opened?" check (POLICY_SPEC §2). */
    public boolean canOpen(int account, long dialogId) {
        if (dialogId == 0) {
            return false;
        }
        if (dialogId == UserConfig.getInstance(account).getClientUserId()) {
            return true; // Saved Messages
        }
        final long self = UserConfig.getInstance(account).getClientUserId();
        final Rule rule = ruleFor(self, dialogId);
        if (rule != null && rule.isBlock()) {
            return false; // permanent, checked before everything else
        }
        if (DialogObject.isEncryptedDialog(dialogId)) {
            return true; // a secret chat is a person
        }
        MessagesController mc = MessagesController.getInstance(account);
        TLRPC.User user = null;
        TLRPC.Chat chat = null;
        if (DialogObject.isUserDialog(dialogId)) {
            user = mc.getUser(dialogId);
        } else {
            chat = mc.getChat(-dialogId);
        }
        if (hasRestriction(user, chat)) {
            return false;
        }
        if (KIND_USER.equals(kindOf(dialogId, user, chat))) {
            return true; // people are never gated
        }
        return rule != null && RULE_ALLOW.equals(rule.rule);
    }

    public boolean canOpen(int account, long userId, long chatId) {
        long dialogId = userId != 0 ? userId : (chatId != 0 ? -chatId : 0);
        return canOpen(account, dialogId);
    }

    /** Same rule for a peer already in hand (search results, cells). */
    public boolean canOpenPeer(int account, TLRPC.User user) {
        if (user == null) {
            return false;
        }
        if (user.self || user.id == UserConfig.getInstance(account).getClientUserId()) {
            return true;
        }
        return canOpen(account, user.id);
    }

    public boolean canOpenPeer(int account, TLRPC.Chat chat) {
        return chat != null && canOpen(account, -chat.id);
    }

    private static String kindOf(long dialogId, TLRPC.User user, TLRPC.Chat chat) {
        if (user != null) {
            return user.bot ? KIND_BOT : KIND_USER;
        }
        if (chat != null) {
            return ChatObject.isChannelAndNotMegaGroup(chat) ? KIND_CHANNEL : KIND_GROUP;
        }
        // Not loaded: a positive id is a person we already talk to; an unknown
        // negative id is treated as a channel (fail closed).
        return dialogId > 0 ? KIND_USER : KIND_CHANNEL;
    }

    private static boolean hasRestriction(TLRPC.User user, TLRPC.Chat chat) {
        if (user != null) {
            return user.restriction_reason != null && !user.restriction_reason.isEmpty();
        }
        if (chat != null) {
            return chat.restriction_reason != null && !chat.restriction_reason.isEmpty();
        }
        return false;
    }

    /** The kind string for a dialog, resolved against the loaded peer. */
    public String kindOfDialog(int account, long dialogId) {
        MessagesController mc = MessagesController.getInstance(account);
        if (DialogObject.isUserDialog(dialogId)) {
            return kindOf(dialogId, mc.getUser(dialogId), null);
        }
        return kindOf(dialogId, null, mc.getChat(-dialogId));
    }

    // ── Reading the lists (Settings screens) ────────────────────────────────

    private Rule ruleFor(long tgUserId, long dialogId) {
        Snapshot snapshot = byAccount.get(tgUserId);
        return snapshot == null ? null : snapshot.byChat.get(dialogId);
    }

    public Rule ruleForAccount(int account, long dialogId) {
        return ruleFor(UserConfig.getInstance(account).getClientUserId(), dialogId);
    }

    /** Rules of one kind ({@link #RULE_ALLOW} / {@link #RULE_BLOCK}) for the UI. */
    public ArrayList<Rule> rulesOf(int account, String which) {
        ArrayList<Rule> out = new ArrayList<>();
        Snapshot snapshot = byAccount.get(UserConfig.getInstance(account).getClientUserId());
        if (snapshot != null) {
            for (Rule r : snapshot.byChat.values()) {
                if (which.equals(r.rule)) {
                    out.add(r);
                }
            }
        }
        Collections.sort(out, (a, b) -> {
            String at = a.title == null ? a.identity() : a.title;
            String bt = b.title == null ? b.identity() : b.title;
            return at.compareToIgnoreCase(bt);
        });
        return out;
    }

    /** ISO timestamp when this account's data will be erased, or null. */
    public String erasureEffectiveAt(int account) {
        Snapshot snapshot = byAccount.get(UserConfig.getInstance(account).getClientUserId());
        return snapshot == null ? null : snapshot.erasureEffectiveAt;
    }

    // ── Writing (allow / block / withdraw) ──────────────────────────────────

    /**
     * Allow a chat. Refused outright when a block already exists — the ratchet is
     * enforced here as well as on the server, so the UI never even appears to
     * offer an unblock.
     *
     * @return true when the change was accepted locally.
     */
    public boolean allow(int account, long dialogId) {
        Rule existing = ruleForAccount(account, dialogId);
        if (existing != null && existing.isBlock()) {
            return false;
        }
        return apply(account, dialogId, RULE_ALLOW);
    }

    /** Block a chat PERMANENTLY. Cannot be undone by any later call. */
    public boolean block(int account, long dialogId) {
        return apply(account, dialogId, RULE_BLOCK);
    }

    /** Withdraw an allow (a tightening). Never touches a block. */
    public boolean withdraw(int account, long dialogId) {
        long self = UserConfig.getInstance(account).getClientUserId();
        Rule existing = ruleFor(self, dialogId);
        if (existing == null || existing.isBlock()) {
            return false;
        }
        Map<Long, Snapshot> next = copyAccounts();
        Snapshot snapshot = next.get(self);
        if (snapshot != null) {
            Map<Long, Rule> rules = new HashMap<>(snapshot.byChat);
            rules.remove(dialogId);
            next.put(self, new Snapshot(snapshot.version, rules, snapshot.erasureEffectiveAt));
            byAccount = next;
            saveCache();
            // Withdrawing an allow puts the chat back behind the gate, so it
            // stops being allowed to notify — and whatever it already placed in
            // the shade should go with it, exactly as for a block.
            dismissNotifications(account, dialogId);
        }
        JSONObject op = new JSONObject();
        try {
            op.put("op", "withdraw");
            op.put("tg_user_id", self);
            op.put("chat_id", dialogId);
        } catch (Throwable ignored) {
            return false;
        }
        queue(op);
        return true;
    }

    private boolean apply(int account, long dialogId, String rule) {
        final long self = UserConfig.getInstance(account).getClientUserId();
        if (self == 0 || dialogId == 0) {
            return false;
        }
        MessagesController mc = MessagesController.getInstance(account);
        String username = null;
        String title = null;
        if (DialogObject.isUserDialog(dialogId)) {
            TLRPC.User user = mc.getUser(dialogId);
            if (user != null) {
                username = UserObject.getPublicUsername(user);
                title = UserObject.getUserName(user);
            }
        } else {
            TLRPC.Chat chat = mc.getChat(-dialogId);
            if (chat != null) {
                username = ChatObject.getPublicUsername(chat);
                title = chat.title;
            }
        }
        final String kind = kindOfDialog(account, dialogId);

        // Apply locally first so the UI and the gate react immediately, then push.
        Map<Long, Snapshot> next = copyAccounts();
        Snapshot snapshot = next.get(self);
        Map<Long, Rule> rules = snapshot == null ? new HashMap<>() : new HashMap<>(snapshot.byChat);
        rules.put(dialogId, new Rule(dialogId, kind, rule, username, title));
        next.put(self, new Snapshot(
                snapshot == null ? 0 : snapshot.version, rules,
                snapshot == null ? null : snapshot.erasureEffectiveAt));
        byAccount = next;
        saveCache();
        notifyDialogsChanged();
        if (!RULE_ALLOW.equals(rule)) {
            // Stopping future notifications is not enough: whatever this chat
            // already put in the shade is still sitting there, and tapping it
            // would try to open a chat we now refuse. Clear it in the same breath.
            dismissNotifications(account, dialogId);
        }

        JSONObject op = new JSONObject();
        try {
            op.put("op", "rule");
            op.put("tg_user_id", self);
            op.put("chat_id", dialogId);
            op.put("kind", kind);
            op.put("rule", rule);
            if (!TextUtils.isEmpty(username)) {
                op.put("username", username);
            }
            if (!TextUtils.isEmpty(title)) {
                op.put("title", title);
            }
        } catch (Throwable ignored) {
            return false;
        }
        queue(op);
        return true;
    }

    private Map<Long, Snapshot> copyAccounts() {
        return new HashMap<>(byAccount);
    }

    private void queue(JSONObject op) {
        synchronized (pending) {
            pending.add(op);
            savePending();
        }
        Utilities.globalQueue.postRunnable(() -> {
            try {
                syncOnce();
            } catch (Throwable ignored) {
            }
        });
    }

    // ── Erasure (the Play deletion path — scheduled, cancellable) ───────────

    /** Ask the server to erase this account's data after the waiting period. */
    public void requestErasure(int account, Utilities.Callback<String> whenDone) {
        final long self = UserConfig.getInstance(account).getClientUserId();
        Utilities.globalQueue.postRunnable(() -> {
            String effective = null;
            String resp = httpJson("DELETE",
                    "/rules?tg_user_id=" + self + "&confirm=erase", null, true);
            if (resp != null) {
                try {
                    effective = new JSONObject(resp).optString("effective_at", null);
                } catch (Throwable ignored) {
                }
            }
            final String result = effective;
            syncAccountBlocking(self);
            if (whenDone != null) {
                AndroidUtilities.runOnUIThread(() -> whenDone.run(result));
            }
        });
    }

    /** Call off a scheduled erasure. */
    public void cancelErasure(int account, Runnable whenDone) {
        final long self = UserConfig.getInstance(account).getClientUserId();
        Utilities.globalQueue.postRunnable(() -> {
            httpJson("POST", "/rules/erase/cancel?tg_user_id=" + self, "{}", true);
            syncAccountBlocking(self);
            if (whenDone != null) {
                AndroidUtilities.runOnUIThread(whenDone);
            }
        });
    }

    // ── Refusal dialog + device-claim prompt ────────────────────────────────

    /** ISO time this device's claim on the account auto-approves, or null. */
    private volatile String claimPendingUntil;
    /** Device ids we have already asked the user about, so we ask once. */
    private final java.util.Set<String> promptedClaims = new java.util.HashSet<>();

    public String claimPendingUntil() {
        return claimPendingUntil;
    }

    /**
     * Shown when the rules refuse a chat. This is also where a chat normally
     * joins either list: the user meets the refusal and answers it, so nothing
     * has to be typed anywhere.
     */
    public void notifyBlocked(int account, long dialogId) {
        AndroidUtilities.runOnUIThread(() -> showBlockedDialog(account, dialogId));
    }

    /** Fallback for call sites without a peer in hand. */
    public void notifyBlocked() {
        AndroidUtilities.runOnUIThread(
                () -> toast(str(R.string.PuregramUnavailableShort)));
    }

    private void showBlockedDialog(int account, long dialogId) {
        final LaunchActivity activity = LaunchActivity.instance;
        if (activity == null || activity.isFinishing() || activity.isDestroyed()) {
            toast(str(R.string.PuregramUnavailableShort));
            return;
        }
        final Rule existing = ruleForAccount(account, dialogId);
        final String title = titleOf(account, dialogId);
        final String identity = identityOf(account, dialogId);
        final StringBuilder body = new StringBuilder();
        if (!TextUtils.isEmpty(title)) {
            body.append(title).append('\n');
        }
        body.append(identity).append("\n\n");

        if (existing != null && existing.isBlock()) {
            // A permanent block: say plainly that there is no way back, and offer
            // no control that pretends otherwise.
            body.append(str(R.string.PuregramBlockedExplain));
            new AlertDialog.Builder(activity)
                    .setTitle(str(R.string.PuregramBlockedTitle))
                    .setMessage(body.toString())
                    .setNegativeButton(str(R.string.PuregramClose),
                            (d, w) -> d.dismiss())
                    .show();
            return;
        }

        body.append(str(R.string.PuregramGateExplain));
        new AlertDialog.Builder(activity)
                .setTitle(str(R.string.PuregramNotAvailable))
                .setMessage(body.toString())
                .setPositiveButton(str(R.string.PuregramAllow), (d, w) -> {
                    d.dismiss();
                    if (allow(account, dialogId)) {
                        toast(str(R.string.PuregramAllowed));
                    }
                })
                .setNeutralButton(str(R.string.PuregramBlockForever), (d, w) -> {
                    d.dismiss();
                    confirmBlock(account, dialogId, null);
                })
                .setNegativeButton(str(R.string.PuregramClose),
                        (d, w) -> d.dismiss())
                .show();
    }

    /**
     * Blocking is irreversible, so it is never a single tap: the confirmation
     * says so in the user's own language before anything is written.
     */
    public void confirmBlock(int account, long dialogId, Runnable after) {
        final LaunchActivity activity = LaunchActivity.instance;
        if (activity == null || activity.isFinishing() || activity.isDestroyed()) {
            return;
        }
        final String title = titleOf(account, dialogId);
        final String name = TextUtils.isEmpty(title) ? identityOf(account, dialogId) : title;
        AndroidUtilities.runOnUIThread(() -> new AlertDialog.Builder(activity)
                .setTitle(str(R.string.PuregramBlockConfirmTitle))
                .setMessage(LocaleController.formatString(R.string.PuregramBlockConfirmBody, name))
                .setPositiveButton(str(R.string.PuregramBlockForever), (d, w) -> {
                    d.dismiss();
                    block(account, dialogId);
                    toast(str(R.string.PuregramBlockedDone));
                    if (after != null) {
                        after.run();
                    }
                })
                .setNegativeButton(str(R.string.PuregramCancel),
                        (d, w) -> d.dismiss())
                .show());
    }

    /** "A new device wants to sync your lists" — answered on the trusted device. */
    private void promptDeviceClaim(int account, String claimDeviceId, String model) {
        final LaunchActivity activity = LaunchActivity.instance;
        if (activity == null || activity.isFinishing() || activity.isDestroyed()) {
            return;
        }
        final long self = UserConfig.getInstance(account).getClientUserId();
        final String what = TextUtils.isEmpty(model) ? claimDeviceId : model;
        new AlertDialog.Builder(activity)
                .setTitle(str(R.string.PuregramNewDevice))
                .setMessage(LocaleController.formatString(R.string.PuregramNewDeviceBody, what))
                .setPositiveButton(str(R.string.PuregramApprove), (d, w) -> {
                    d.dismiss();
                    answerClaim(self, claimDeviceId, true);
                })
                .setNegativeButton(str(R.string.PuregramDeny), (d, w) -> {
                    d.dismiss();
                    answerClaim(self, claimDeviceId, false);
                })
                .show();
    }

    private void answerClaim(long tgUserId, String claimDeviceId, boolean approve) {
        Utilities.globalQueue.postRunnable(() -> {
            String path = "/rules/devices/" + urlPart(claimDeviceId)
                    + (approve ? "/approve" : "/deny") + "?tg_user_id=" + tgUserId;
            httpJson("POST", path, "{}", true);
            syncAccountBlocking(tgUserId);
        });
    }

    private static String urlPart(String value) {
        try {
            return URLEncoder.encode(value, "UTF-8");
        } catch (Throwable ignored) {
            return value;
        }
    }

    // ── Adding a pasted list ────────────────────────────────────────────────

    /** How many usable targets a pasted blob holds — for the confirmation text. */
    public static int countTargets(String text) {
        return parseTargets(text).size();
    }

    /**
     * One line per target: a t.me link, an @username, a bare username, or a
     * numeric chat id. Blank lines and '#' comments are skipped, and duplicates
     * collapse so a sloppy paste does not do the same work twice.
     */
    private static ArrayList<String> parseTargets(String text) {
        ArrayList<String> out = new ArrayList<>();
        if (TextUtils.isEmpty(text)) {
            return out;
        }
        for (String raw : text.split("[\\r\\n,;\\s]+")) {
            String line = raw.trim();
            int hash = line.indexOf('#');
            if (hash >= 0) {
                line = line.substring(0, hash).trim();
            }
            if (line.isEmpty()) {
                continue;
            }
            String value = line;
            int scheme = value.indexOf("://");
            if (scheme >= 0) {
                value = value.substring(scheme + 3);
            }
            for (String host : new String[]{"t.me/", "telegram.me/", "telegram.dog/"}) {
                if (value.toLowerCase(Locale.ROOT).startsWith(host)) {
                    value = value.substring(host.length());
                    break;
                }
            }
            if (value.startsWith("+") || value.toLowerCase(Locale.ROOT).startsWith("joinchat/")) {
                continue; // an invite link names no chat we could match on
            }
            if (value.toLowerCase(Locale.ROOT).startsWith("s/")) {
                value = value.substring(2);
            }
            int slash = value.indexOf('/');
            if (slash >= 0) {
                value = value.substring(0, slash);
            }
            int q = value.indexOf('?');
            if (q >= 0) {
                value = value.substring(0, q);
            }
            value = value.replace("@", "").trim();
            if (value.isEmpty() || out.contains(value)) {
                continue;
            }
            out.add(value);
        }
        return out;
    }

    /**
     * Apply one rule to every target in a pasted blob.
     *
     * <p>Each name is resolved to a real chat first, because rules are matched by
     * chat id — the same id the gate checks. Resolution is one request per name,
     * run in order on the background queue; anything that will not resolve is
     * counted as failed rather than silently dropped.
     */
    public void addByText(int account, String text, String rule,
                          Utilities.Callback2<Integer, Integer> whenDone) {
        final ArrayList<String> targets = parseTargets(text);
        Utilities.globalQueue.postRunnable(() -> {
            int added = 0;
            int failed = 0;
            for (String target : targets) {
                long dialogId = 0;
                try {
                    dialogId = Long.parseLong(target);
                    // A pasted Bot-API channel id (-100…) means the same channel
                    // as the plain negated form the clients enforce.
                    if (dialogId < 0 && Math.abs(dialogId) >= BOT_API_CHANNEL_OFFSET) {
                        dialogId = -(Math.abs(dialogId) - BOT_API_CHANNEL_OFFSET);
                    }
                } catch (NumberFormatException notANumber) {
                    dialogId = resolveUsernameBlocking(account, target);
                }
                if (dialogId == 0) {
                    failed++;
                    continue;
                }
                if (applyOnUiThread(account, dialogId, rule)) {
                    added++;
                } else {
                    failed++; // already blocked; the ratchet refuses to reopen it
                }
            }
            final int a = added;
            final int f = failed;
            if (whenDone != null) {
                AndroidUtilities.runOnUIThread(() -> whenDone.run(a, f));
            }
        });
    }

    private boolean applyOnUiThread(int account, long dialogId, String rule) {
        return RULE_BLOCK.equals(rule) ? block(account, dialogId) : allow(account, dialogId);
    }

    /** Resolve @username -> dialog id, blocking the calling background thread. */
    private long resolveUsernameBlocking(int account, String username) {
        final long[] result = new long[]{0};
        final java.util.concurrent.CountDownLatch latch = new java.util.concurrent.CountDownLatch(1);
        TLRPC.TL_contacts_resolveUsername req = new TLRPC.TL_contacts_resolveUsername();
        req.username = username;
        ConnectionsManager.getInstance(account).sendRequest(req, (response, error) -> {
            if (response instanceof TLRPC.TL_contacts_resolvedPeer) {
                TLRPC.TL_contacts_resolvedPeer res = (TLRPC.TL_contacts_resolvedPeer) response;
                MessagesController.getInstance(account).putUsers(res.users, false);
                MessagesController.getInstance(account).putChats(res.chats, false);
                if (res.peer != null) {
                    if (res.peer.user_id != 0) {
                        result[0] = res.peer.user_id;
                    } else if (res.peer.channel_id != 0) {
                        result[0] = -res.peer.channel_id;
                    } else if (res.peer.chat_id != 0) {
                        result[0] = -res.peer.chat_id;
                    }
                }
            }
            latch.countDown();
        });
        try {
            latch.await(20, java.util.concurrent.TimeUnit.SECONDS);
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
        }
        return result[0];
    }

    private String identityOf(int account, long dialogId) {
        Rule known = ruleForAccount(account, dialogId);
        if (known != null && !TextUtils.isEmpty(known.username)) {
            return "@" + known.username;
        }
        try {
            MessagesController mc = MessagesController.getInstance(account);
            String username = null;
            if (DialogObject.isUserDialog(dialogId)) {
                TLRPC.User user = mc.getUser(dialogId);
                if (user != null) {
                    username = UserObject.getPublicUsername(user);
                }
            } else {
                TLRPC.Chat chat = mc.getChat(-dialogId);
                if (chat != null) {
                    username = ChatObject.getPublicUsername(chat);
                }
            }
            if (!TextUtils.isEmpty(username)) {
                return "@" + username;
            }
        } catch (Throwable ignored) {
        }
        return String.valueOf(dialogId);
    }

    private String titleOf(int account, long dialogId) {
        Rule known = ruleForAccount(account, dialogId);
        if (known != null && !TextUtils.isEmpty(known.title)) {
            return known.title;
        }
        try {
            MessagesController mc = MessagesController.getInstance(account);
            if (DialogObject.isUserDialog(dialogId)) {
                TLRPC.User user = mc.getUser(dialogId);
                return user == null ? null : UserObject.getUserName(user);
            }
            TLRPC.Chat chat = mc.getChat(-dialogId);
            return chat == null ? null : chat.title;
        } catch (Throwable ignored) {
            return null;
        }
    }

    private void toast(String message) {
        try {
            android.widget.Toast.makeText(
                    appContext, message, android.widget.Toast.LENGTH_SHORT).show();
        } catch (Throwable ignored) {
        }
    }

    // ── Sync ────────────────────────────────────────────────────────────────

    /** @return true when the server was reachable. */
    private boolean syncOnce() {
        if (networkBusy.getAndSet(true)) {
            return false;
        }
        try {
            if (TextUtils.isEmpty(token)) {
                checkinBlocking();
            }
            if (TextUtils.isEmpty(token)) {
                return false;
            }
            if (!flushPendingBlocking()) {
                return false;
            }
            boolean any = false;
            for (int account = 0; account < UserConfig.MAX_ACCOUNT_COUNT; account++) {
                if (!UserConfig.getInstance(account).isClientActivated()) {
                    continue;
                }
                long self = UserConfig.getInstance(account).getClientUserId();
                if (self != 0) {
                    any |= syncAccountBlocking(self);
                    checkDeviceClaimsBlocking(account, self);
                }
            }
            return any;
        } finally {
            networkBusy.set(false);
        }
    }

    /** Replay queued offline changes in order. Stops at the first failure. */
    private boolean flushPendingBlocking() {
        while (true) {
            JSONObject op;
            synchronized (pending) {
                if (pending.isEmpty()) {
                    return true;
                }
                op = pending.get(0);
            }
            final String kind = op.optString("op");
            final long tg = op.optLong("tg_user_id");
            String resp;
            if ("withdraw".equals(kind)) {
                resp = httpJson("DELETE",
                        "/rules/" + op.optLong("chat_id") + "?tg_user_id=" + tg, null, true);
                // 403/404 mean the server refused or it is already gone; either
                // way replaying it forever would wedge the queue, so drop it.
                if (resp == null && !lastCallWasClientError) {
                    return false;
                }
            } else {
                JSONObject body = new JSONObject();
                try {
                    body.put("tg_user_id", tg);
                    body.put("chat_id", op.optLong("chat_id"));
                    body.put("kind", op.optString("kind"));
                    body.put("rule", op.optString("rule"));
                    if (op.has("username")) {
                        body.put("username", op.optString("username"));
                    }
                    if (op.has("title")) {
                        body.put("title", op.optString("title"));
                    }
                } catch (Throwable ignored) {
                    // Malformed op: drop it rather than block the queue forever.
                }
                resp = httpJson("POST", "/rules", body.toString(), true);
                if (resp == null && !lastCallWasClientError) {
                    return false;
                }
            }
            synchronized (pending) {
                if (!pending.isEmpty()) {
                    pending.remove(0);
                }
                savePending();
            }
        }
    }

    /** Surface any device waiting to be approved for this account. */
    private void checkDeviceClaimsBlocking(int account, long tgUserId) {
        String resp = httpJson("GET", "/rules/meta?tg_user_id=" + tgUserId, null, true);
        if (resp == null) {
            return;
        }
        try {
            JSONArray waiting = new JSONObject(resp).optJSONArray("pending_devices");
            if (waiting == null) {
                return;
            }
            for (int i = 0; i < waiting.length(); i++) {
                JSONObject d = waiting.getJSONObject(i);
                final String claimId = d.optString("device_id", null);
                if (TextUtils.isEmpty(claimId)) {
                    continue;
                }
                synchronized (promptedClaims) {
                    if (!promptedClaims.add(claimId)) {
                        continue; // asked already this run
                    }
                }
                final String model = d.isNull("model") ? null : d.optString("model", null);
                AndroidUtilities.runOnUIThread(() -> promptDeviceClaim(account, claimId, model));
            }
        } catch (Throwable ignored) {
        }
    }

    private boolean syncAccountBlocking(long tgUserId) {
        String resp = httpJson("GET", "/rules?tg_user_id=" + tgUserId, null, true);
        if (resp == null) {
            return false;
        }
        try {
            JSONObject json = new JSONObject(resp);
            Map<Long, Rule> rules = new HashMap<>();
            JSONArray arr = json.optJSONArray("rules");
            if (arr != null) {
                for (int i = 0; i < arr.length(); i++) {
                    JSONObject r = arr.getJSONObject(i);
                    long chatId = r.optLong("chat_id", 0);
                    if (chatId == 0) {
                        continue;
                    }
                    rules.put(chatId, new Rule(
                            chatId,
                            r.optString("kind", KIND_CHANNEL),
                            r.optString("rule", RULE_ALLOW),
                            r.isNull("username") ? null : r.optString("username", null),
                            r.isNull("title") ? null : r.optString("title", null)));
                }
            }
            String erasure = json.isNull("erasure_effective_at")
                    ? null : json.optString("erasure_effective_at", null);
            Map<Long, Snapshot> next = copyAccounts();
            next.put(tgUserId, new Snapshot(json.optInt("version", 0), rules, erasure));
            byAccount = next;
            saveCache();
            notifyDialogsChanged();
            return true;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private void checkinBlocking() {
        try {
            String deviceId = android.provider.Settings.Secure.getString(
                    appContext.getContentResolver(), android.provider.Settings.Secure.ANDROID_ID);
            if (TextUtils.isEmpty(deviceId)) {
                return;
            }
            JSONObject body = new JSONObject();
            body.put("device_id", deviceId);
            body.put("brand", android.os.Build.BRAND);
            body.put("manufacturer", android.os.Build.MANUFACTURER);
            body.put("model", android.os.Build.MODEL);
            body.put("android_version", android.os.Build.VERSION.RELEASE);
            body.put("sdk_int", android.os.Build.VERSION.SDK_INT);
            String resp = httpJson("POST", "/device/checkin", body.toString(), false);
            if (resp == null) {
                return;
            }
            String newToken = new JSONObject(resp).optString("token", null);
            if (!TextUtils.isEmpty(newToken)) {
                token = newToken;
                prefs().edit().putString(KEY_TOKEN, newToken).apply();
            }
        } catch (Throwable ignored) {
        }
    }

    // ── Cache ───────────────────────────────────────────────────────────────

    private void loadCache(String cached) {
        if (TextUtils.isEmpty(cached)) {
            return;
        }
        try {
            Map<Long, Snapshot> next = new HashMap<>();
            JSONArray accounts = new JSONObject(cached).optJSONArray("accounts");
            if (accounts != null) {
                for (int i = 0; i < accounts.length(); i++) {
                    JSONObject acc = accounts.getJSONObject(i);
                    long tg = acc.optLong("tg", 0);
                    if (tg == 0) {
                        continue;
                    }
                    Map<Long, Rule> rules = new HashMap<>();
                    JSONArray arr = acc.optJSONArray("rules");
                    if (arr != null) {
                        for (int j = 0; j < arr.length(); j++) {
                            JSONObject r = arr.getJSONObject(j);
                            long chatId = r.optLong("chat_id", 0);
                            if (chatId == 0) {
                                continue;
                            }
                            rules.put(chatId, new Rule(chatId,
                                    r.optString("kind", KIND_CHANNEL),
                                    r.optString("rule", RULE_ALLOW),
                                    r.isNull("username") ? null : r.optString("username", null),
                                    r.isNull("title") ? null : r.optString("title", null)));
                        }
                    }
                    next.put(tg, new Snapshot(acc.optInt("version", 0), rules,
                            acc.isNull("erasure") ? null : acc.optString("erasure", null)));
                }
            }
            byAccount = next;
        } catch (Throwable ignored) {
            // A corrupt cache means "no rules yet" — people still open, gated
            // kinds stay closed. Fail closed.
        }
    }

    private void saveCache() {
        try {
            JSONArray accounts = new JSONArray();
            for (Map.Entry<Long, Snapshot> e : byAccount.entrySet()) {
                JSONObject acc = new JSONObject();
                acc.put("tg", e.getKey());
                acc.put("version", e.getValue().version);
                if (e.getValue().erasureEffectiveAt != null) {
                    acc.put("erasure", e.getValue().erasureEffectiveAt);
                }
                JSONArray arr = new JSONArray();
                for (Rule r : e.getValue().byChat.values()) {
                    JSONObject o = new JSONObject();
                    o.put("chat_id", r.chatId);
                    o.put("kind", r.kind);
                    o.put("rule", r.rule);
                    if (r.username != null) {
                        o.put("username", r.username);
                    }
                    if (r.title != null) {
                        o.put("title", r.title);
                    }
                    arr.put(o);
                }
                acc.put("rules", arr);
                accounts.put(acc);
            }
            prefs().edit().putString(KEY_CACHE,
                    new JSONObject().put("accounts", accounts).toString()).apply();
        } catch (Throwable ignored) {
        }
    }

    private void loadPending(String cached) {
        if (TextUtils.isEmpty(cached)) {
            return;
        }
        try {
            JSONArray arr = new JSONArray(cached);
            synchronized (pending) {
                pending.clear();
                for (int i = 0; i < arr.length(); i++) {
                    pending.add(arr.getJSONObject(i));
                }
            }
        } catch (Throwable ignored) {
        }
    }

    private void savePending() {
        try {
            JSONArray arr = new JSONArray();
            for (JSONObject op : pending) {
                arr.put(op);
            }
            prefs().edit().putString(KEY_PENDING, arr.toString()).apply();
        } catch (Throwable ignored) {
        }
    }

    /** Clear anything this chat already put in the notification shade. */
    private void dismissNotifications(int account, long dialogId) {
        if (dialogId == 0) {
            return;
        }
        AndroidUtilities.runOnUIThread(() -> {
            try {
                NotificationsController.getInstance(account)
                        .removeNotificationsForDialog(dialogId);
            } catch (Throwable ignored) {
                // Never let tidying the shade break the rule that was just set.
            }
        });
    }

    private void notifyDialogsChanged() {
        AndroidUtilities.runOnUIThread(() -> {
            for (int account = 0; account < UserConfig.MAX_ACCOUNT_COUNT; account++) {
                if (UserConfig.getInstance(account).isClientActivated()) {
                    // sortDialogs BEFORE the notification, not just the notification.
                    // dialogsNeedReload only makes the list redraw itself from
                    // dialogsByFolder, and that array is built by sortDialogs — which
                    // is where blocked chats are filtered out. Posting alone therefore
                    // redrew the *stale* list, and a chat blocked just now stayed
                    // visible until something else happened to re-sort, i.e. until the
                    // user left the app and came back. The desktop client hid it
                    // instantly and this one did not, for exactly this reason.
                    MessagesController.getInstance(account).sortDialogs(null);
                    NotificationCenter.getInstance(account)
                            .postNotificationName(NotificationCenter.dialogsNeedReload);
                }
            }
        });
    }

    // ── HTTP ────────────────────────────────────────────────────────────────

    /** True when the last httpJson call failed with a 4xx (a permanent refusal). */
    private volatile boolean lastCallWasClientError;

    private String httpJson(String method, String path, String body, boolean auth) {
        HttpURLConnection conn = null;
        lastCallWasClientError = false;
        try {
            conn = (HttpURLConnection) new URL(BASE_URL + path).openConnection();
            conn.setRequestMethod(method);
            conn.setConnectTimeout(HTTP_TIMEOUT_MS);
            conn.setReadTimeout(HTTP_TIMEOUT_MS);
            conn.setRequestProperty("Accept", "application/json");
            if (auth && !TextUtils.isEmpty(token)) {
                conn.setRequestProperty("Authorization", "Bearer " + token);
            }
            if (body != null) {
                conn.setDoOutput(true);
                conn.setRequestProperty("Content-Type", "application/json");
                try (OutputStream os = conn.getOutputStream()) {
                    os.write(body.getBytes(StandardCharsets.UTF_8));
                }
            }
            int code = conn.getResponseCode();
            if (code == 401) {
                token = null;
                prefs().edit().remove(KEY_TOKEN).apply();
                return null;
            }
            if (code == 409) {
                // Our own claim on this account is waiting for approval.
                lastCallWasClientError = true;
                String body409 = readStream(conn.getErrorStream());
                if (body409 != null && body409.contains("device_claim_pending")) {
                    try {
                        claimPendingUntil = new JSONObject(body409)
                                .getJSONObject("detail").optString("auto_approve_at", null);
                    } catch (Throwable ignored) {
                        claimPendingUntil = "";
                    }
                }
                return null;
            }
            if (code >= 400 && code < 500) {
                lastCallWasClientError = true;
                return null;
            }
            claimPendingUntil = null;
            if (code < 200 || code >= 300) {
                return null;
            }
            return readStream(conn.getInputStream());
        } catch (Throwable ignored) {
            return null;
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    private static String readStream(InputStream in) {
        if (in == null) {
            return null;
        }
        try (BufferedReader reader =
                     new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
            return sb.toString();
        } catch (Throwable ignored) {
            return null;
        }
    }
}
