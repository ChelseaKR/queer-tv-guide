package com.chelseakr.queertvguide.core

import com.chelseakr.queertvguide.core.JsonEdit.with
import kotlinx.serialization.json.JsonPrimitive
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.time.Instant

private val UA = SnapshotRefresher.userAgent("1.0.0")

class StoreAndRefresherTest {
    /** The app's name, its version and "Android": nothing about the build or the device. */
    @Test
    fun theUserAgentIsTheAppNameVersionAndAndroidOnly() {
        assertEquals("QueerFrame/1.0.0 (Android)", UA)
        assertTrue(Regex("""^QueerFrame/[0-9A-Za-z.\-]+ \(Android\)$""").matches(SnapshotRefresher.userAgent("1.2.3-rc1")))
    }

    /**
     * On the wire: the real transport (HttpURLConnection) sends the app's
     * User-Agent in place of the platform's default, and no other header the
     * app did not set beyond HTTP's own (Host, Connection, Accept-Encoding,
     * and the no-cache pair `useCaches = false` adds), none of which names
     * the device.
     */
    @Test
    fun theRealTransportSendsOnlyTheAppsUserAgent() {
        val server = java.net.ServerSocket(0, 1, java.net.InetAddress.getLoopbackAddress())
        val received = java.util.concurrent.CompletableFuture<List<String>>()
        val thread = Thread {
            server.accept().use { socket ->
                val reader = socket.getInputStream().bufferedReader()
                val lines = generateSequence { reader.readLine() }.takeWhile { it.isNotEmpty() }.toList()
                received.complete(lines)
                socket.getOutputStream().write("HTTP/1.1 304 Not Modified\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".toByteArray())
            }
        }
        thread.start()
        try {
            val refresher = SnapshotRefresher(store(), UA, endpoint = "http://127.0.0.1:${server.localPort}/snapshot.v1.json")
            assertEquals(SnapshotRefresher.Outcome.Unchanged, refresher.refresh())
            val headers = received.get(10, java.util.concurrent.TimeUnit.SECONDS).drop(1)
            val agents = headers.filter { it.startsWith("User-Agent:", ignoreCase = true) }
            assertEquals(listOf("User-Agent: QueerFrame/1.0.0 (Android)"), agents)
            val names = headers.map { it.substringBefore(':').lowercase() }.toSet()
            assertEquals(emptySet<String>(), names - setOf("accept", "user-agent", "host", "connection", "accept-encoding", "cache-control", "pragma"))
        } finally {
            server.close()
            thread.join(5000)
        }
    }

    private val dir: File = Files.createTempDirectory("qf-store").toFile()

    @After
    fun cleanUp() {
        dir.deleteRecursively()
    }

    private val fixture = Repo.fixtureBytes()
    private fun dated(date: String) = Repo.bytes(Repo.fixtureJson().with("generated_at", JsonPrimitive(date)))

    private fun store(bundled: ByteArray? = fixture) = SnapshotStore(dir) { bundled }

    @Test
    fun withNothingDownloadedTheBundledFileLoads() {
        val loaded = store().load()
        assertEquals(SnapshotStore.Origin.BUNDLED, loaded.origin)
        assertNull(loaded.etag)
    }

    @Test
    fun theNewerOfDownloadedAndBundledWins() {
        val s = store(bundled = dated("2026-09-13T20:00:00Z"))
        s.replace(dated("2026-09-20T09:17:00Z"), "\"abc\"")
        assertEquals(SnapshotStore.Origin.DOWNLOADED, s.load().origin)
        assertEquals("\"abc\"", s.load().etag)
        // An app update ships a newer bundled file: it wins, with no ETag.
        val updated = SnapshotStore(dir) { dated("2026-10-01T09:17:00Z") }
        assertEquals(SnapshotStore.Origin.BUNDLED, updated.load().origin)
        assertNull(updated.load().etag)
        // An equal date prefers the downloaded file.
        val same = SnapshotStore(dir) { dated("2026-09-20T09:17:00Z") }
        assertEquals(SnapshotStore.Origin.DOWNLOADED, same.load().origin)
    }

    @Test
    fun aDownloadedFileThatNoLongerDecodesIsIgnoredNotDeleted() {
        dir.mkdirs()
        File(dir, "snapshot.v1.json").writeText("{\"schema_version\":\"2\"}")
        assertEquals(SnapshotStore.Origin.BUNDLED, store().load().origin)
        assertTrue(File(dir, "snapshot.v1.json").exists())
    }

    @Test
    fun aBadReplacementLeavesTheLastGoodFileUntouched() {
        val s = store()
        s.replace(dated("2026-09-20T09:17:00Z"), "\"good\"")
        val before = s.snapshotFile.readBytes()
        try {
            s.replace("{\"schema_version\":\"1\"}".toByteArray(), "\"bad\"")
            fail("a broken file was accepted")
        } catch (_: SnapshotDecodingException) {
        }
        assertArrayEquals(before, s.snapshotFile.readBytes())
        assertEquals("\"good\"", s.readEtag())
        assertTrue("no temporary files left behind", dir.listFiles()!!.none { it.name.endsWith(".tmp") })
    }

    private class Script(var respond: (SnapshotRefresher.Request) -> SnapshotRefresher.Response) : SnapshotRefresher.Transport {
        val requests = mutableListOf<SnapshotRefresher.Request>()
        override fun get(request: SnapshotRefresher.Request): SnapshotRefresher.Response {
            requests += request
            return respond(request)
        }
    }

    /** The request carries `Accept` and, once there is one, `If-None-Match`; nothing else. */
    @Test
    fun theOneRequestCarriesNothingButAcceptAndTheEtag() {
        val s = store()
        val script = Script { SnapshotRefresher.Response(200, mapOf("ETag" to "\"v1\""), dated("2026-09-20T09:17:00Z")) }
        val refresher = SnapshotRefresher(s, UA, transport = script)
        assertTrue(refresher.refresh() is SnapshotRefresher.Outcome.Updated)
        script.respond = { SnapshotRefresher.Response(304, emptyMap(), ByteArray(0)) }
        assertEquals(SnapshotRefresher.Outcome.Unchanged, refresher.refresh())
        assertEquals(Endpoints.SNAPSHOT_URL, script.requests[0].url)
        assertEquals(mapOf("Accept" to "application/json", "User-Agent" to UA), script.requests[0].headers)
        assertEquals(mapOf("Accept" to "application/json", "User-Agent" to UA, "If-None-Match" to "\"v1\""), script.requests[1].headers)
        assertEquals("https://chelseakr.github.io/queer-tv-guide/snapshot.v1.json", Endpoints.SNAPSHOT_URL)
    }

    @Test
    fun everyFailureLeavesTheStoreAsItWasAndSaysWhichKind() {
        val s = store()
        s.replace(dated("2026-09-20T09:17:00Z"), "\"good\"")
        val before = s.snapshotFile.readBytes()
        fun problem(transport: SnapshotRefresher.Transport, online: Boolean = true): RefreshProblem {
            try {
                SnapshotRefresher(s, UA, transport = transport, isOnline = { online }).refresh()
            } catch (e: Exception) {
                return RefreshProblem.from(e)
            }
            fail("expected a failure")
            throw AssertionError()
        }
        assertEquals(RefreshProblem.OFFLINE, problem({ throw IOException("no route") }, online = false))
        assertEquals(RefreshProblem.UNREACHABLE, problem({ throw IOException("timeout") }, online = true))
        assertEquals(RefreshProblem.UNREACHABLE, problem({ SnapshotRefresher.Response(503, emptyMap(), ByteArray(0)) }))
        assertEquals(RefreshProblem.UNUSABLE, problem({ SnapshotRefresher.Response(200, emptyMap(), "{}".toByteArray()) }))
        assertArrayEquals(before, s.snapshotFile.readBytes())
        assertEquals("\"good\"", s.readEtag())
        for (p in RefreshProblem.entries) {
            assertTrue(p.message, p.message.endsWith("The data on screen stays as it is."))
            assertFalse(p.message, p.message.contains("HTTP"))
        }
    }
}

class FavoritesTest {
    private class MapStore : KeyValueStore {
        val map = HashMap<String, String>()
        override fun getString(key: String) = map[key]
        override fun putString(key: String, value: String?) {
            if (value == null) map.remove(key) else map[key] = value
        }
    }

    @Test
    fun favoritesPersistUnderTheirKeyAndSurviveARestart() {
        val storage = MapStore()
        var clock = Instant.parse("2026-09-18T09:44:42Z")
        val store = FavoritesStore(storage) { clock }
        assertTrue(store.toggle(FavoritesStore.Kind.SHOW, "lwtv:show:101"))
        clock = clock.plusSeconds(60)
        assertTrue(store.toggle(FavoritesStore.Kind.CHARACTER, "lwtv:character:203"))
        assertTrue(storage.map.containsKey("favourites.v1"))
        val again = FavoritesStore(storage)
        assertEquals(store.entries, again.entries)
        assertFalse(again.toggle(FavoritesStore.Kind.SHOW, "lwtv:show:101"))
        assertEquals(listOf("lwtv:character:203"), again.entries.map { it.id })
    }

    @Test
    fun mergeAddsOnlyWhatIsNew() {
        val store = FavoritesStore(MapStore()) { Instant.parse("2026-09-18T00:00:00Z") }
        store.toggle(FavoritesStore.Kind.SHOW, "lwtv:show:101")
        val (added, already) = store.merge(
            listOf(
                FavoritesStore.Entry(FavoritesStore.Kind.SHOW, "lwtv:show:101", Instant.EPOCH),
                FavoritesStore.Entry(FavoritesStore.Kind.SHOW, "lwtv:show:102", Instant.EPOCH),
            ),
        )
        assertEquals(1, added)
        assertEquals(1, already)
        assertEquals(Instant.parse("2026-09-18T00:00:00Z"), store.entries[0].addedAt)
    }

    @Test
    fun importTrustsNothingInTheFile() {
        val now = Instant.parse("2026-10-01T00:00:00Z")
        fun parse(text: String) = FavoritesBackup.parse(text.toByteArray(), now) { _, id -> id != "lwtv:show:999" }
        try {
            parse("[]")
            fail()
        } catch (_: FavoritesBackup.ImportException.NotABackup) {
        }
        try {
            parse("{\"format\":\"favourites-backup\",\"version\":2,\"favourites\":[]}")
            fail()
        } catch (e: FavoritesBackup.ImportException.UnsupportedVersion) {
            assertEquals(2, e.version)
        }
        try {
            FavoritesBackup.parse(ByteArray(FavoritesBackup.MAX_BYTES + 1), now) { _, _ -> true }
            fail()
        } catch (_: FavoritesBackup.ImportException.TooLarge) {
        }
        val parsed = parse(
            """{"format":"favourites-backup","version":1,"favourites":[
              {"kind":"show","id":"lwtv:show:101","added_at":"2030-01-01T00:00:00Z"},
              {"kind":"show","id":"lwtv:show:101"},
              {"kind":"show","id":"lwtv:show:999"},
              {"kind":"show","id":"lwtv:character:1"},
              {"kind":"episode","id":"lwtv:show:5"},
              42
            ]}""",
        )
        assertEquals(1, parsed.entries.size)
        assertEquals(now, parsed.entries[0].addedAt)
        assertEquals(1, parsed.notInSnapshot)
        assertEquals(3, parsed.unreadable)
    }
}
