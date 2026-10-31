package de.korte_daniel.tripatlas.ui

import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.view.View
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.activity.compose.LocalActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.fragment.app.FragmentActivity
import de.korte_daniel.tripatlas.AccountVault
import de.korte_daniel.tripatlas.R
import de.korte_daniel.tripatlas.Server
import org.json.JSONObject
import java.util.concurrent.atomic.AtomicBoolean

/**
 * The TripAtlas web interface of [server]. Pages of the server stay in the app, everything else (Wikipedia, OpenStreetMap,
 * Immich) opens in the browser. The bridge `window.TripAtlasApp` is only offered while a page of the server is loaded.
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun AtlasScreen(server: String, onChangeServer: () -> Unit) {
    val activity = LocalActivity.current as FragmentActivity
    var webView by remember { mutableStateOf<WebView?>(null) }
    var canGoBack by remember { mutableStateOf(false) }
    var fullscreen by remember { mutableStateOf(false) }
    // The page could not be loaded at all (no service-worker copy either): our own screen instead of Chromium's
    var loadError by remember { mutableStateOf<String?>(null) }
    var fileCallback by remember { mutableStateOf<ValueCallback<Array<Uri>>?>(null) }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
        fileCallback?.onReceiveValue(uris.toTypedArray())
        fileCallback = null
    }

    BackHandler(enabled = canGoBack && loadError == null) { webView?.goBack() }
    // In full screen Back first leaves full screen (declared later = takes precedence)
    BackHandler(enabled = fullscreen) { webView?.evaluateJavascript("document.exitFullscreen && document.exitFullscreen()", null) }

    val vault = remember(server) { AccountVault(activity, server) }
    var offer by remember { mutableStateOf<Triple<String, String, String>?>(null) }   // username, name, password
    val bridgeOpen = remember { AtomicBoolean(false) }
    fun toast(text: String) = Toast.makeText(activity, text, Toast.LENGTH_LONG).show()

    offer?.let { (username, name, password) ->
        AlertDialog(
            onDismissRequest = { offer = null },
            title = { Text(stringResource(R.string.vault_offer_title)) },
            text = { Text(stringResource(R.string.vault_offer_text, name)) },
            confirmButton = { TextButton({ offer = null; vault.save(activity, username, name, password, ::toast) }) { Text(stringResource(R.string.vault_offer_save)) } },
            dismissButton = { TextButton({ offer = null }) { Text(stringResource(R.string.vault_offer_later)) } },
        )
    }

    DisposableEffect(server) { onDispose { webView?.destroy(); webView = null } }

    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Box(Modifier.fillMaxSize()) {
            AndroidView(
                modifier = Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing),
                factory = { ctx ->
                    WebView(ctx).apply {
                        settings.javaScriptEnabled = true
                        settings.domStorageEnabled = true
                        settings.mediaPlaybackRequiresUserGesture = true
                        CookieManager.getInstance().setAcceptCookie(true)
                        val wv = this
                        addJavascriptInterface(object {
                            @JavascriptInterface fun accounts(): String = if (bridgeOpen.get()) vault.accountsJson() else "[]"
                            @JavascriptInterface fun offerSave(json: String) {
                                if (!bridgeOpen.get() || !vault.possible()) return
                                val o = runCatching { JSONObject(json) }.getOrNull() ?: return
                                wv.post { offer = Triple(o.optString("username"), o.optString("display_name"), o.optString("password")) }
                            }
                            @JavascriptInterface fun signIn(username: String) {
                                if (!bridgeOpen.get()) return
                                wv.post {
                                    vault.fetch(activity, username) { pw, msg ->
                                        if (pw != null && bridgeOpen.get())
                                            wv.evaluateJavascript("window.tripAtlasSignIn(${JSONObject.quote(username)}, ${JSONObject.quote(pw)})", null)
                                        msg?.let(::toast)
                                    }
                                }
                            }
                            @JavascriptInterface fun forget(username: String) { if (bridgeOpen.get()) vault.forget(username) }
                            @JavascriptInterface fun changeServer() { if (bridgeOpen.get()) wv.post(onChangeServer) }
                        }, "TripAtlasApp")
                        webViewClient = object : WebViewClient() {
                            override fun shouldOverrideUrlLoading(view: WebView, req: WebResourceRequest): Boolean {
                                if (Server.sameOrigin(req.url.toString(), server)) return false
                                runCatching { ctx.startActivity(Intent(Intent.ACTION_VIEW, req.url)) }
                                return true
                            }

                            override fun doUpdateVisitedHistory(view: WebView, url: String?, isReload: Boolean) {
                                canGoBack = view.canGoBack()
                            }

                            override fun onPageStarted(view: WebView, url: String?, favicon: android.graphics.Bitmap?) {
                                bridgeOpen.set(url != null && Server.sameOrigin(url, server))
                            }

                            override fun onReceivedError(view: WebView, req: WebResourceRequest, error: WebResourceError) {
                                if (req.isForMainFrame) loadError = error.description?.toString() ?: ""
                            }

                            override fun onReceivedHttpError(view: WebView, req: WebResourceRequest, res: WebResourceResponse) {
                                // A reverse proxy whose TripAtlas is down answers 502/503/504
                                if (req.isForMainFrame && res.statusCode in 500..599) loadError = "HTTP ${res.statusCode}"
                            }
                        }
                        webChromeClient = object : WebChromeClient() {
                            // Full screen (map, videos): the page hands over its own view; the app puts it on top and
                            // hides the system bars
                            private var custom: View? = null
                            private var customEnd: CustomViewCallback? = null
                            private val bars get() = WindowInsetsControllerCompat(activity.window, activity.window.decorView)

                            override fun onShowCustomView(view: View, callback: CustomViewCallback) {
                                if (custom != null) return callback.onCustomViewHidden()
                                custom = view; customEnd = callback; fullscreen = true
                                (activity.window.decorView as ViewGroup).addView(view,
                                    ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
                                bars.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
                                bars.hide(WindowInsetsCompat.Type.systemBars())
                            }

                            override fun onHideCustomView() {
                                custom?.let { (activity.window.decorView as ViewGroup).removeView(it) }
                                custom = null; fullscreen = false
                                customEnd?.onCustomViewHidden(); customEnd = null
                                bars.show(WindowInsetsCompat.Type.systemBars())
                            }

                            override fun onShowFileChooser(v: WebView, cb: ValueCallback<Array<Uri>>, p: FileChooserParams): Boolean {
                                fileCallback?.onReceiveValue(null)
                                fileCallback = cb
                                picker.launch("*/*")
                                return true
                            }
                        }
                        loadUrl(server)
                        webView = this
                    }
                },
            )
            loadError?.let { reason ->
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    Column(
                        Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing).padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically),
                    ) {
                        Text(stringResource(R.string.error_title), style = MaterialTheme.typography.titleLarge)
                        Text(stringResource(R.string.error_text, server), textAlign = TextAlign.Center,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (reason.isNotBlank()) Text(reason, style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
                        Button({ loadError = null; webView?.reload() }) { Text(stringResource(R.string.error_retry)) }
                        OutlinedButton(onChangeServer) { Text(stringResource(R.string.change_server)) }
                    }
                }
            }
        }
    }
}
