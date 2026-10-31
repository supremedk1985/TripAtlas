package de.korte_daniel.tripatlas

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ServerTest {
    @Test fun withoutSchemeHttpsComesFirstThenHttp() {
        assertEquals(listOf("https://tripatlas.example.com", "http://tripatlas.example.com"), Server.candidates(" tripatlas.example.com/ "))
    }

    @Test fun explicitSchemePortAndPathAreKept() {
        assertEquals(listOf("http://192.168.1.10:8097"), Server.candidates("http://192.168.1.10:8097/"))
        assertEquals(listOf("https://home.example.org/tripatlas"), Server.candidates("HTTPS://Home.Example.org/tripatlas/"))
    }

    @Test fun nonsenseIsRejected() {
        assertNull(Server.candidates(""))
        assertNull(Server.candidates("trip atlas"))
        assertNull(Server.candidates("ftp://example.com"))
        assertNull(Server.candidates("https://"))
    }

    @Test fun originComparesSchemeHostAndPort() {
        assertTrue(Server.sameOrigin("https://a.example.com/trips/3", "https://A.example.com:443"))
        assertTrue(Server.sameOrigin("http://192.168.1.10:8097/login", "http://192.168.1.10:8097"))
        assertFalse(Server.sameOrigin("http://192.168.1.10:8098/", "http://192.168.1.10:8097"))
        assertFalse(Server.sameOrigin("https://de.wikipedia.org/wiki/Brest", "https://a.example.com"))
        assertFalse(Server.sameOrigin("http://a.example.com", "https://a.example.com"))
    }

    @Test fun healthOfTripAtlasGivesTheVersion() {
        assertEquals("0.2.0", Server.parseHealth("""{"ok":true,"version":"0.2.0"}"""))
        assertEquals("1.0", Server.parseHealth("""{ "version": "1.0", "ok" : true }"""))
    }

    @Test fun otherAnswersAreNotTripAtlas() {
        assertNull(Server.parseHealth("""{"ok":false,"version":"0.2.0"}"""))
        assertNull(Server.parseHealth("""{"status":"ok"}"""))
        assertNull(Server.parseHealth("<html><title>FRITZ!Box</title></html>"))
    }
}
