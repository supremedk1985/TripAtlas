package de.korte_daniel.tripatlas

import java.net.HttpURLConnection
import java.net.URI
import java.net.URL

/** The TripAtlas server the app talks to: turning what the user typed into an address, and checking it. */
object Server {
    /**
     * Addresses to try for what the user typed, best first. Without a scheme https comes first and plain http second
     * (a server at home is often reachable only as http://192.168.x.y:8097). A trailing slash is dropped; a path stays,
     * for servers behind a reverse proxy under a sub-path. Null when it cannot be an address.
     */
    fun candidates(input: String): List<String>? {
        val s = input.trim()
        if (s.isEmpty() || s.any { it.isWhitespace() }) return null
        val withScheme = if (s.contains("://")) listOf(s) else listOf("https://$s", "http://$s")
        val out = withScheme.mapNotNull(::clean)
        return out.ifEmpty { null }
    }

    private fun clean(s: String): String? {
        val u = runCatching { URI(s) }.getOrNull() ?: return null
        val scheme = u.scheme?.lowercase() ?: return null
        if (scheme != "http" && scheme != "https") return null
        val host = u.host?.takeIf { it.isNotEmpty() } ?: return null
        val port = if (u.port == -1) "" else ":${u.port}"
        val path = (u.rawPath ?: "").trimEnd('/')
        return "$scheme://${host.lowercase()}$port$path"
    }

    /** Scheme, host and port -- the part that decides whether a page belongs to the server. */
    fun origin(url: String): String? {
        val u = runCatching { URI(url) }.getOrNull() ?: return null
        val scheme = u.scheme?.lowercase() ?: return null
        val host = u.host?.lowercase() ?: return null
        val port = if (u.port != -1) u.port else if (scheme == "https") 443 else if (scheme == "http") 80 else -1
        return "$scheme://$host:$port"
    }

    fun sameOrigin(a: String, b: String) = origin(a) != null && origin(a) == origin(b)

    /** `GET /api/health` answers `{"ok":true,"version":"0.2.0"}`; anything else is not TripAtlas. Returns the version. */
    fun parseHealth(body: String): String? {
        if (!Regex("\"ok\"\\s*:\\s*true").containsMatchIn(body)) return null
        return Regex("\"version\"\\s*:\\s*\"([^\"]{1,40})\"").find(body)?.groupValues?.get(1)
    }

    sealed interface Check {
        data class Found(val url: String, val version: String) : Check
        /** Something answered, but it is not TripAtlas (a router page, another app, a login wall of a proxy) */
        data class NotTripAtlas(val url: String) : Check
        data class Unreachable(val reason: String) : Check
        data object Invalid : Check
    }

    /** Tries each candidate in turn; blocking, call it off the main thread. */
    fun check(input: String): Check {
        val list = candidates(input) ?: return Check.Invalid
        var last: Check = Check.Unreachable("")
        for (base in list) {
            val result = runCatching {
                val c = URL("$base/api/health").openConnection() as HttpURLConnection
                c.connectTimeout = 6000; c.readTimeout = 6000
                c.setRequestProperty("Accept", "application/json")
                try {
                    val code = c.responseCode
                    val body = (if (code in 200..299) c.inputStream else c.errorStream)?.bufferedReader()?.use { it.readText().take(4000) } ?: ""
                    val v = if (code == 200) parseHealth(body) else null
                    if (v != null) Check.Found(base, v) else Check.NotTripAtlas(base)
                } finally { c.disconnect() }
            }.getOrElse { Check.Unreachable(it.message ?: it.javaClass.simpleName) }
            if (result is Check.Found) return result
            // A real answer from the wrong thing says more than a timeout on the second guess
            if (result is Check.NotTripAtlas || last !is Check.NotTripAtlas) last = result
        }
        return last
    }
}
