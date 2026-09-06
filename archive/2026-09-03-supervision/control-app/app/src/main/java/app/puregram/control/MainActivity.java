package app.puregram.control;

import android.annotation.SuppressLint;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.activity.OnBackPressedCallback;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

/**
 * Puregram Control — the Android host for the Puregram Control panel.
 *
 * <p>The panel itself is the web app at {@link BuildConfig#CONTROL_URL} (debug
 * points at the local dev stack, release at production). Because the panel, its
 * API and the SSE stream share one origin, the session cookie and EventSource
 * work with no cross-origin handling.
 *
 * <p>What this shell adds over a bare WebView, so it feels like an app and not a
 * browser tab: pull-to-refresh, a native retry screen when the network is down,
 * hardware-back navigation through the SPA's history, external links handed to
 * the browser, and window insets so content never sits under the system bars.
 */
public class MainActivity extends AppCompatActivity {

    /** Everything under the panel's own origin stays in the WebView. */
    private static final String INTERNAL_HOST = "puregram.app";
    /** Brand green — the refresh spinner; matches the panel's accent. */
    private static final int BRAND = 0xFF2E9E4F;
    /** Panel background, so no white flash before the first paint. */
    private static final int CANVAS = 0xFF070C18;

    private WebView web;
    private SwipeRefreshLayout refresh;
    private View errorView;
    /** Set by onReceivedError so onPageFinished doesn't hide a failure screen. */
    private boolean loadFailed;

    @SuppressLint("SetJavaScriptEnabled") // First-party content only.
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        web = findViewById(R.id.web);
        refresh = findViewById(R.id.refresh);
        errorView = findViewById(R.id.error);

        applyWindowInsets();
        configureWebView();

        refresh.setColorSchemeColors(BRAND);
        refresh.setOnRefreshListener(this::reload);
        findViewById(R.id.retry).setOnClickListener(v -> reload());

        registerBackHandler();

        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else {
            load(BuildConfig.CONTROL_URL);
        }
    }

    /**
     * Pad the content by the system-bar insets. targetSdk 35 draws edge-to-edge
     * on Android 15, so without this the panel's header would sit under the
     * status bar.
     */
    private void applyWindowInsets() {
        final View root = findViewById(R.id.root);
        ViewCompat.setOnApplyWindowInsetsListener(root, (view, windowInsets) -> {
            Insets bars = windowInsets.getInsets(
                    WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return WindowInsetsCompat.CONSUMED;
        });
    }

    private void configureWebView() {
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setMediaPlaybackRequiresUserGesture(false);
        // The panel is responsive and ships its own viewport meta; pinch-zoom
        // would only let the user break its layout.
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);

        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(web, true);

        web.setWebViewClient(new PanelWebViewClient());
        web.setWebChromeClient(new WebChromeClient());
        web.setBackgroundColor(CANVAS);
    }

    /** Hardware/gesture back walks the SPA's history before leaving the app. */
    private void registerBackHandler() {
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (web.canGoBack()) {
                    web.goBack();
                    return;
                }
                setEnabled(false);
                getOnBackPressedDispatcher().onBackPressed();
            }
        });
    }

    private void load(String url) {
        loadFailed = false;
        errorView.setVisibility(View.GONE);
        web.setVisibility(View.VISIBLE);
        web.loadUrl(url);
    }

    private void reload() {
        if (web.getUrl() == null) {
            load(BuildConfig.CONTROL_URL);
            return;
        }
        loadFailed = false;
        errorView.setVisibility(View.GONE);
        web.setVisibility(View.VISIBLE);
        web.reload();
    }

    private boolean isOnline() {
        ConnectivityManager manager = getSystemService(ConnectivityManager.class);
        if (manager == null) {
            return true; // Can't tell — let the WebView try.
        }
        NetworkCapabilities capabilities =
                manager.getNetworkCapabilities(manager.getActiveNetwork());
        return capabilities != null
                && capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
    }

    /** Show the native retry screen instead of the WebView's error page. */
    private void showError() {
        loadFailed = true;
        refresh.setRefreshing(false);
        web.setVisibility(View.GONE);
        errorView.setVisibility(View.VISIBLE);
    }

    /** Hand a link outside the panel's origin to the system browser. */
    private boolean openExternally(Uri uri) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            return true;
        } catch (ActivityNotFoundException e) {
            return false; // No browser installed — let the WebView handle it.
        }
    }

    private class PanelWebViewClient extends WebViewClient {

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri uri = request.getUrl();
            String host = uri.getHost();
            if (host == null
                    || host.equalsIgnoreCase(INTERNAL_HOST)
                    || host.toLowerCase().endsWith("." + INTERNAL_HOST)
                    || "10.0.2.2".equals(host)
                    || "localhost".equals(host)) {
                return false; // Stay in the panel.
            }
            return openExternally(uri);
        }

        @Override
        public void onPageFinished(WebView view, String url) {
            refresh.setRefreshing(false);
            if (!loadFailed) {
                errorView.setVisibility(View.GONE);
                web.setVisibility(View.VISIBLE);
            }
        }

        @Override
        public void onReceivedError(
                WebView view, WebResourceRequest request, WebResourceError error) {
            // Sub-resource failures (an icon, a poll) must not blank the panel.
            if (request.isForMainFrame()) {
                showError();
            }
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Back online after the error screen: retry without making the user tap.
        if (loadFailed && isOnline()) {
            reload();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
        }
        super.onDestroy();
    }
}
