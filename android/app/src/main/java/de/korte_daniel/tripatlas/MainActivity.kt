package de.korte_daniel.tripatlas

import android.content.Intent
import android.os.Bundle
import android.webkit.CookieManager
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.fragment.app.FragmentActivity
import de.korte_daniel.tripatlas.ui.AtlasScreen
import de.korte_daniel.tripatlas.ui.SetupScreen

/**
 * TripAtlas for Android: the web interface of the user's own TripAtlas server in a WebView, plus what a web page
 * cannot do on its own -- remember the server, keep passwords behind the fingerprint, open the file picker for
 * imports, full screen. On first start (and from the launcher shortcut "Change server") it asks for the address.
 *
 * FragmentActivity rather than ComponentActivity: Android's fingerprint prompt (BiometricPrompt) needs it.
 */
class MainActivity : FragmentActivity() {
    private lateinit var settings: Settings
    private var server by mutableStateOf<String?>(null)
    private var changing by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        settings = Settings(this)
        server = settings.server
        handle(intent)
        setContent {
            val dark = isSystemInDarkTheme()
            // The colours of the web interface (web/src/app.css), so the edges around the page match it
            MaterialTheme(
                colorScheme = if (dark) darkColorScheme(
                    primary = Color(0xFF2DD4BF), onPrimary = Color(0xFF06201D),
                    background = Color(0xFF0E1116), surface = Color(0xFF0E1116),
                    onBackground = Color(0xFFE6E9EE), onSurface = Color(0xFFE6E9EE), onSurfaceVariant = Color(0xFF9AA4B2),
                ) else lightColorScheme(
                    primary = Color(0xFF0F766E), onPrimary = Color.White,
                    background = Color(0xFFF6F7F9), surface = Color(0xFFF6F7F9),
                    onBackground = Color(0xFF1C2330), onSurface = Color(0xFF1C2330), onSurfaceVariant = Color(0xFF5B6575),
                ),
            ) {
                val s = server
                if (s == null || changing) {
                    BackHandler(enabled = s != null) { changing = false }
                    SetupScreen(
                        current = s,
                        onFound = { url -> settings.server = url; server = url; changing = false },
                        onCancel = if (s != null) ({ changing = false }) else null,
                    )
                } else {
                    AtlasScreen(s, onChangeServer = { changing = true })
                }
            }
        }
    }

    override fun onStop() {
        super.onStop()
        // WebView writes cookies to disk only now and then; when Android ends the app before that, the session is gone
        // and the user has to sign in again
        CookieManager.getInstance().flush()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handle(intent)
    }

    /** The launcher shortcut "Change server" */
    private fun handle(i: Intent?) {
        if (i?.action == ACTION_CHANGE_SERVER) {
            changing = true
            i.action = Intent.ACTION_MAIN   // not again after a rotation
        }
    }

    companion object {
        const val ACTION_CHANGE_SERVER = "de.korte_daniel.tripatlas.CHANGE_SERVER"
    }
}
