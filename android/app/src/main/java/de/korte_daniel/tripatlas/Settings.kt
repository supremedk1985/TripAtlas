package de.korte_daniel.tripatlas

import android.content.Context

/** What the app remembers besides the accounts: the server address. */
class Settings(ctx: Context) {
    private val prefs = ctx.getSharedPreferences("settings", Context.MODE_PRIVATE)

    var server: String?
        get() = prefs.getString("server", null)
        set(v) = prefs.edit().putString("server", v).apply()
}
