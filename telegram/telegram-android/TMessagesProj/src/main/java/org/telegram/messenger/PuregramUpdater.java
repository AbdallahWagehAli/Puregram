package org.telegram.messenger;

import android.app.DownloadManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.Settings;

import androidx.core.app.NotificationCompat;

import org.json.JSONObject;
import org.telegram.ui.ActionBar.AlertDialog;
import org.telegram.ui.LaunchActivity;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Puregram in-app updater. Polls the server for the latest published build and,
 * when it is newer than THIS build, both raises a NOTIFICATION and (if the app is
 * open) shows a dialog. Either one downloads the new APK through Android's
 * DownloadManager and hands it straight to the package installer — the user taps
 * Update, then Install, and is on the new build. No visit to the website.
 *
 * Puregram is sideloaded, so Android cannot install silently: the system installer
 * always asks. If "install unknown apps" is not granted for Puregram, the user is
 * taken to that settings page first.
 *
 * The network call runs off the UI thread (Utilities.globalQueue); UI work is
 * marshalled back with AndroidUtilities.runOnUIThread and prompts at most once per
 * process.
 */
public final class PuregramUpdater {

    private static final String VERSION_URL =
            PuregramRules.baseUrl() + "/android/version";
    private static final String DOWNLOAD_PAGE = "https://puregram.app/#download";
    private static final String APK_NAME = "puregram-update.apk";
    private static final String CHANNEL_ID = "puregram_updates";
    private static final int NOTIFICATION_ID = 0x50550100;
    private static final int TIMEOUT_MS = 15000;

    // Arabic UI strings. The Android build forces UTF-8 source encoding
    // (build.gradle: options.encoding = "UTF-8"), so raw literals are safe.
    private static final String TITLE = "تحديث Puregram";
    private static final String BODY =
            "إصدار جديد من Puregram متاح. حمّله وثبّته الآن للحصول على آخر التحسينات.";
    private static final String UPDATE_NOW = "تحديث الآن";
    private static final String LATER = "لاحقًا";
    private static final String DOWNLOADING = "جارٍ تحميل التحديث…";
    private static final String READY = "اضغط للتثبيت";
    private static final String FAILED = "تعذّر تحميل التحديث";

    private static volatile boolean checked = false;
    private static volatile long downloadId = -1;

    private PuregramUpdater() {
    }

    /** Kick a one-time background version check (safe to call on every resume). */
    public static void checkOnce() {
        if (!BuildConfig.PUREGRAM_SELF_UPDATE) {
            // Play build: Play delivers updates, and shipping a self-updater
            // would violate its Device and Network Abuse policy.
            return;
        }
        if (checked) {
            return;
        }
        checked = true;
        Utilities.globalQueue.postRunnable(PuregramUpdater::checkInBackground);
    }

    private static void checkInBackground() {
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(VERSION_URL).openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(TIMEOUT_MS);
            conn.setReadTimeout(TIMEOUT_MS);
            conn.setRequestProperty("Accept", "application/json");
            final int code = conn.getResponseCode();
            if (code != 200) {
                return; // 404 = no update advertised; anything else = transient
            }
            final String text = readStream(conn.getInputStream());
            if (text == null || text.trim().isEmpty()) {
                return;
            }
            final JSONObject json = new JSONObject(text.trim());
            final int latest = json.optInt("version", 0);
            final String url = json.optString("url", DOWNLOAD_PAGE);
            if (latest <= BuildConfig.PUREGRAM_BUILD) {
                return; // already on the latest build
            }
            AndroidUtilities.runOnUIThread(() -> announce(url));
        } catch (Throwable t) {
            FileLog.e(t);
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    /** Notify on every device, and prompt right away if the app is on screen. */
    private static void announce(String url) {
        final String target = (url == null || url.isEmpty()) ? DOWNLOAD_PAGE : url;
        notifyAvailable(target);

        final LaunchActivity activity = LaunchActivity.instance;
        if (activity == null || activity.isFinishing() || activity.isDestroyed()) {
            return; // the notification carries it; a later resume may also prompt
        }
        try {
            new AlertDialog.Builder(activity)
                    .setTitle(TITLE)
                    .setMessage(BODY)
                    .setPositiveButton(UPDATE_NOW, (dialog, which) -> {
                        startDownload(activity, target);
                        dialog.dismiss();
                    })
                    .setNegativeButton(LATER, (dialog, which) -> dialog.dismiss())
                    .show();
        } catch (Throwable t) {
            FileLog.e(t);
        }
    }

    // ── Notification ───────────────────────────────────────────────────────

    private static NotificationManager manager(Context context) {
        return (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
    }

    private static void ensureChannel(NotificationManager nm) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O || nm == null) {
            return;
        }
        try {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID, "تحديثات Puregram", NotificationManager.IMPORTANCE_DEFAULT);
            channel.setDescription("إشعار عند توفّر إصدار جديد من Puregram");
            nm.createNotificationChannel(channel);
        } catch (Throwable ignored) {
        }
    }

    /** "A new version is available" — tapping it starts the download. */
    private static void notifyAvailable(String url) {
        final Context context = ApplicationLoader.applicationContext;
        final NotificationManager nm = manager(context);
        if (context == null || nm == null) {
            return;
        }
        ensureChannel(nm);
        Intent intent = new Intent(context, PuregramUpdateReceiver.class)
                .setAction(PuregramUpdateReceiver.ACTION_START_DOWNLOAD)
                .putExtra(PuregramUpdateReceiver.EXTRA_URL, url);
        PendingIntent pending = PendingIntent.getBroadcast(
                context, NOTIFICATION_ID, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        post(nm, new NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(R.drawable.notification)
                .setContentTitle(TITLE)
                .setContentText(BODY)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(BODY))
                .setAutoCancel(true)
                .setOnlyAlertOnce(true)
                .setContentIntent(pending)
                .addAction(0, UPDATE_NOW, pending)
                .build());
    }

    private static void notifyText(String text, PendingIntent action) {
        final Context context = ApplicationLoader.applicationContext;
        final NotificationManager nm = manager(context);
        if (context == null || nm == null) {
            return;
        }
        ensureChannel(nm);
        NotificationCompat.Builder builder = new NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(R.drawable.notification)
                .setContentTitle(TITLE)
                .setContentText(text)
                .setAutoCancel(true)
                .setOnlyAlertOnce(true);
        if (action != null) {
            builder.setContentIntent(action).addAction(0, READY, action);
        }
        post(nm, builder.build());
    }

    private static void post(NotificationManager nm, Notification notification) {
        try {
            nm.notify(NOTIFICATION_ID, notification);
        } catch (Throwable ignored) {
            // POST_NOTIFICATIONS may be denied — the in-app dialog still works.
        }
    }

    // ── Download → install ─────────────────────────────────────────────────

    /**
     * Queue the APK download. A non-APK url (e.g. the website) is opened in the
     * browser instead, so an older server that advertises a page still works.
     */
    static void startDownload(Context context, String url) {
        if (context == null || url == null || url.isEmpty()) {
            return;
        }
        if (!url.endsWith(".apk")) {
            openExternally(context, url);
            return;
        }
        try {
            DownloadManager dm =
                    (DownloadManager) context.getSystemService(Context.DOWNLOAD_SERVICE);
            if (dm == null) {
                openExternally(context, url);
                return;
            }
            // A stale copy from a previous attempt would make the installer show
            // the old build, so always start from a clean file.
            context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
            DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url))
                    .setTitle(TITLE)
                    .setDescription(DOWNLOADING)
                    .setMimeType("application/vnd.android.package-archive")
                    .setNotificationVisibility(
                            DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                    .setDestinationInExternalFilesDir(
                            context, Environment.DIRECTORY_DOWNLOADS, APK_NAME);
            downloadId = dm.enqueue(request);
            registerCompletion(context.getApplicationContext());
            notifyText(DOWNLOADING, null);
        } catch (Throwable t) {
            FileLog.e(t);
            openExternally(context, url);
        }
    }

    /**
     * DownloadManager broadcasts completion; a runtime receiver is enough because
     * the download only runs while the app is alive (and the notification lets the
     * user restart it otherwise).
     */
    private static void registerCompletion(Context context) {
        try {
            BroadcastReceiver receiver = new BroadcastReceiver() {
                @Override
                public void onReceive(Context ctx, Intent intent) {
                    long id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1);
                    if (id != downloadId) {
                        return;
                    }
                    try {
                        ctx.unregisterReceiver(this);
                    } catch (Throwable ignored) {
                    }
                    onDownloadFinished(ctx, id);
                }
            };
            IntentFilter filter = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                context.registerReceiver(receiver, filter, Context.RECEIVER_EXPORTED);
            } else {
                context.registerReceiver(receiver, filter);
            }
        } catch (Throwable t) {
            FileLog.e(t);
        }
    }

    private static void onDownloadFinished(Context context, long id) {
        DownloadManager dm =
                (DownloadManager) context.getSystemService(Context.DOWNLOAD_SERVICE);
        if (dm == null) {
            return;
        }
        Uri apk = null;
        try {
            apk = dm.getUriForDownloadedFile(id);
        } catch (Throwable ignored) {
        }
        if (apk == null) {
            notifyText(FAILED, null);
            return;
        }
        // Offer it from the shade too, so a backgrounded download still installs.
        Intent intent = new Intent(context, PuregramUpdateReceiver.class)
                .setAction(PuregramUpdateReceiver.ACTION_INSTALL)
                .putExtra(PuregramUpdateReceiver.EXTRA_APK, apk.toString());
        notifyText(READY, PendingIntent.getBroadcast(
                context, NOTIFICATION_ID + 1, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE));
        install(context, apk);
    }

    /** Hand the APK to the system installer, asking for the permission if needed. */
    static void install(Context context, Uri apk) {
        if (context == null || apk == null) {
            return;
        }
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                    && !context.getPackageManager().canRequestPackageInstalls()) {
                context.startActivity(new Intent(
                        Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                        Uri.parse("package:" + context.getPackageName()))
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                return; // the notification stays; the user comes back and taps it
            }
            context.startActivity(new Intent(Intent.ACTION_VIEW)
                    .setDataAndType(apk, "application/vnd.android.package-archive")
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK
                            | Intent.FLAG_GRANT_READ_URI_PERMISSION));
        } catch (Throwable t) {
            FileLog.e(t);
        }
    }

    private static void openExternally(Context context, String url) {
        try {
            context.startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        } catch (Throwable ignored) {
        }
    }

    private static String readStream(InputStream in) {
        if (in == null) {
            return null;
        }
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(in, StandardCharsets.UTF_8))) {
            final StringBuilder sb = new StringBuilder();
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
