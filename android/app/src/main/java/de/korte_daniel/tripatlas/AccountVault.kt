package de.korte_daniel.tripatlas

import android.content.Context
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyPermanentlyInvalidatedException
import android.security.keystore.KeyProperties
import android.util.Base64
import android.widget.Toast
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_STRONG
import androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_WEAK
import androidx.biometric.BiometricManager.Authenticators.DEVICE_CREDENTIAL
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import org.json.JSONArray
import org.json.JSONObject
import java.security.KeyStore
import java.security.MessageDigest
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Saved TripAtlas accounts for switching users with the fingerprint (the page side is `web/src/lib/accounts.ts`,
 * the bridge is described in docs/architecture.md#app-bridge).
 *
 * Passwords are stored AES-GCM encrypted; the key lives in the Android Keystore and can only be used for a few seconds
 * after a fingerprint (or the screen lock). Without unlocking nobody gets at a password, not even the app. When a new
 * fingerprint is enrolled, Android invalidates the key -- then all saved passwords are gone and have to be typed once.
 * Accounts are kept per server, so two TripAtlas servers with a user of the same name do not mix.
 */
class AccountVault(ctx: Context, server: String) {
    data class Account(val username: String, val name: String)

    private val app = ctx.applicationContext
    private val prefs = app.getSharedPreferences("accounts_" + hash(Server.origin(server) ?: server), Context.MODE_PRIVATE)

    fun accounts(): List<Account> = runCatching {
        val a = JSONArray(prefs.getString("list", "[]"))
        (0 until a.length()).map { a.getJSONObject(it).let { o -> Account(o.getString("username"), o.getString("name")) } }
    }.getOrDefault(emptyList())

    /** For the page: names only, never passwords */
    fun accountsJson(): String =
        JSONArray(accounts().map { JSONObject().put("username", it.username).put("display_name", it.name) }).toString()

    private fun store(list: List<Account>) =
        prefs.edit().putString("list", JSONArray(list.map { JSONObject().put("username", it.username).put("name", it.name) }).toString())

    fun forget(username: String) {
        store(accounts().filterNot { it.username.equals(username, true) }).remove("pw_" + username.lowercase()).apply()
    }

    /** Is a fingerprint or a screen lock set up at all? */
    fun possible() = BiometricManager.from(app).canAuthenticate(allowed()) == BiometricManager.BIOMETRIC_SUCCESS

    fun save(a: FragmentActivity, username: String, name: String, password: String, done: (String) -> Unit) {
        val started = unlock(a, a.getString(R.string.vault_save_title, name)) {
            val c = Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.ENCRYPT_MODE, key()) }
            val data = Base64.encodeToString(c.iv + c.doFinal(password.toByteArray()), Base64.NO_WRAP)
            store(accounts().filterNot { it.username.equals(username, true) } + Account(username, name))
                .putString("pw_" + username.lowercase(), data).apply()
            done(a.getString(R.string.vault_saved, name))
        }
        if (!started) done(a.getString(R.string.vault_no_lock))
    }

    /** Unlocks and hands out the password -- or a message why not. */
    fun fetch(a: FragmentActivity, username: String, result: (password: String?, message: String?) -> Unit) {
        val account = accounts().firstOrNull { it.username.equals(username, true) }
        val data = prefs.getString("pw_" + username.lowercase(), null)
        if (account == null || data == null) return result(null, a.getString(R.string.vault_none, username))
        val started = unlock(a, a.getString(R.string.vault_sign_in_title, account.name)) {
            val raw = Base64.decode(data, Base64.NO_WRAP)
            val c = Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, raw, 0, 12)) }
            result(String(c.doFinal(raw, 12, raw.size - 12)), null)
        }
        if (!started) result(null, a.getString(R.string.vault_no_lock))
    }

    /** Shows Android's prompt; `then` only runs after success, while the key is open. */
    private fun unlock(a: FragmentActivity, title: String, then: () -> Unit): Boolean {
        if (!possible()) return false
        val prompt = BiometricPrompt(a, ContextCompat.getMainExecutor(a), object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(r: BiometricPrompt.AuthenticationResult) {
                try {
                    then()
                } catch (e: KeyPermanentlyInvalidatedException) {
                    // The key is shared by all servers, so every saved password is unusable now
                    wipeAll(a)
                    Toast.makeText(a, R.string.vault_invalidated, Toast.LENGTH_LONG).show()
                } catch (e: Exception) {
                    Toast.makeText(a, a.getString(R.string.vault_failed, e.message ?: ""), Toast.LENGTH_LONG).show()
                }
            }
        })
        prompt.authenticate(
            BiometricPrompt.PromptInfo.Builder()
                .setTitle(title)
                .setSubtitle(a.getString(R.string.app_name))
                .setAllowedAuthenticators(allowed())
                .build()
        )
        return true
    }

    private fun allowed() =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) BIOMETRIC_STRONG or DEVICE_CREDENTIAL else BIOMETRIC_WEAK or DEVICE_CREDENTIAL

    private fun key(): SecretKey {
        (keystore().getKey(ALIAS, null) as? SecretKey)?.let { return it }
        val spec = KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .setUserAuthenticationRequired(true)
            .apply {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R)
                    setUserAuthenticationParameters(SECONDS, KeyProperties.AUTH_BIOMETRIC_STRONG or KeyProperties.AUTH_DEVICE_CREDENTIAL)
                else @Suppress("DEPRECATION") setUserAuthenticationValidityDurationSeconds(SECONDS)
            }
            .build()
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply { init(spec) }.generateKey()
    }

    companion object {
        private const val ALIAS = "tripatlas_accounts"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
        private const val SECONDS = 15

        private fun keystore() = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }

        private fun hash(s: String) =
            MessageDigest.getInstance("SHA-256").digest(s.toByteArray()).take(8).joinToString("") { "%02x".format(it) }

        /** Removes the saved accounts of every server and the key */
        fun wipeAll(ctx: Context) {
            val dir = java.io.File(ctx.applicationInfo.dataDir, "shared_prefs")
            dir.listFiles { f -> f.name.startsWith("accounts_") }?.forEach { f ->
                ctx.getSharedPreferences(f.name.removeSuffix(".xml"), Context.MODE_PRIVATE).edit().clear().apply()
            }
            runCatching { keystore().deleteEntry(ALIAS) }
        }
    }
}
