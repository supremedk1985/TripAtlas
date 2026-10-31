package de.korte_daniel.tripatlas.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import de.korte_daniel.tripatlas.R
import de.korte_daniel.tripatlas.Server
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * First start: which TripAtlas server? The app checks the address with `GET /api/health` before it keeps it, so a
 * typo shows up here and not as a blank page. Without a server there is nothing to show, hence the link to the
 * installation guide.
 */
@Composable
fun SetupScreen(current: String?, onFound: (String) -> Unit, onCancel: (() -> Unit)?) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var input by rememberSaveable { mutableStateOf(current ?: "") }
    var busy by rememberSaveable { mutableStateOf(false) }
    // What went wrong, as a string resource plus its argument (resolved while composing, so a language change follows)
    var messageRes by rememberSaveable { mutableStateOf(0) }
    var messageArg by rememberSaveable { mutableStateOf("") }
    val message = if (messageRes != 0) stringResource(messageRes, messageArg) else null
    val installUrl = stringResource(R.string.install_url)
    // Found over plain http: say once what that costs, then continue
    var httpFound by rememberSaveable { mutableStateOf<String?>(null) }

    fun connect() {
        if (busy) return
        busy = true; messageRes = 0
        scope.launch {
            val r = withContext(Dispatchers.IO) { Server.check(input) }
            busy = false
            when (r) {
                is Server.Check.Found -> if (r.url.startsWith("http://")) httpFound = r.url else onFound(r.url)
                is Server.Check.NotTripAtlas -> { messageRes = R.string.setup_not_tripatlas; messageArg = r.url }
                is Server.Check.Unreachable -> messageRes = R.string.setup_unreachable
                Server.Check.Invalid -> messageRes = R.string.setup_invalid
            }
        }
    }

    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing).imePadding()
                .verticalScroll(rememberScrollState()).padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
        ) {
            Image(painterResource(R.drawable.logo), null, Modifier.size(88.dp))
            Text(stringResource(R.string.setup_title), style = MaterialTheme.typography.headlineSmall)
            Text(stringResource(R.string.setup_text), color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.widthIn(max = 480.dp))
            val h = httpFound
            if (h == null) {
                OutlinedTextField(
                    value = input, onValueChange = { input = it; messageRes = 0 },
                    modifier = Modifier.fillMaxWidth().widthIn(max = 480.dp).testTag("server"),
                    label = { Text(stringResource(R.string.setup_address)) },
                    placeholder = { Text("tripatlas.example.com") },
                    singleLine = true, enabled = !busy,
                    isError = message != null,
                    supportingText = { Text(message ?: stringResource(R.string.setup_address_hint)) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Go, autoCorrectEnabled = false),
                    keyboardActions = KeyboardActions(onGo = { connect() }),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    if (onCancel != null) TextButton(onCancel, enabled = !busy) { Text(stringResource(R.string.cancel)) }
                    Button(::connect, enabled = !busy && input.isNotBlank(), modifier = Modifier.testTag("connect")) {
                        if (busy) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
                        else Text(stringResource(R.string.setup_connect))
                    }
                }
            } else {
                Text(stringResource(R.string.setup_http_warning, h), modifier = Modifier.widthIn(max = 480.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    TextButton({ httpFound = null }) { Text(stringResource(R.string.back)) }
                    Button({ httpFound = null; onFound(h) }) { Text(stringResource(R.string.setup_http_continue)) }
                }
            }
            Spacer(Modifier.size(8.dp))
            Text(stringResource(R.string.setup_no_server), style = MaterialTheme.typography.titleSmall)
            Text(stringResource(R.string.setup_no_server_text), color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.widthIn(max = 480.dp))
            TextButton({ runCatching { ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(installUrl))) } }) {
                Text(stringResource(R.string.setup_install_guide))
            }
        }
    }
}
