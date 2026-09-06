package org.telegram.messenger;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.text.TextUtils;

/**
 * Puregram — the actions on an update notification (see {@link PuregramUpdater}):
 * start the download, or install the APK that already finished downloading.
 *
 * Both are quick hand-offs (DownloadManager / the package installer), so they run
 * inline on the receiver thread.
 */
public class PuregramUpdateReceiver extends BroadcastReceiver {

    static final String ACTION_START_DOWNLOAD = "app.puregram.UPDATE_DOWNLOAD";
    static final String ACTION_INSTALL = "app.puregram.UPDATE_INSTALL";
    static final String EXTRA_URL = "url";
    static final String EXTRA_APK = "apk";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (context == null || intent == null || intent.getAction() == null) {
            return;
        }
        final Context appContext = context.getApplicationContext();
        switch (intent.getAction()) {
            case ACTION_START_DOWNLOAD: {
                String url = intent.getStringExtra(EXTRA_URL);
                if (!TextUtils.isEmpty(url)) {
                    PuregramUpdater.startDownload(appContext, url);
                }
                break;
            }
            case ACTION_INSTALL: {
                String apk = intent.getStringExtra(EXTRA_APK);
                if (!TextUtils.isEmpty(apk)) {
                    PuregramUpdater.install(appContext, Uri.parse(apk));
                }
                break;
            }
            default:
                break;
        }
    }
}
