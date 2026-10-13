package com.chelseakr.queertvguide.core

import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URI
import java.util.UUID

/**
 * Where the snapshot lives on disk and how it is replaced (GuideCore's
 * `SnapshotStore`). Load order: the newer, by `generated_at`, of the last
 * good downloaded snapshot and the one bundled with the app. A replacement
 * is decoded first, written to a temporary file beside the real one, and
 * renamed over it, so a crash mid-write never leaves half a file where the
 * app looks.
 */
class SnapshotStore(
    val directory: File,
    /** Reads the snapshot shipped inside the app (its assets), or null if there is none. */
    private val bundled: () -> ByteArray?,
) {
    enum class Origin { BUNDLED, DOWNLOADED }

    data class Loaded(val snapshot: Snapshot, val origin: Origin, val etag: String?)

    class BundledSnapshotMissing : Exception("The data file bundled with the app is missing.")

    val snapshotFile: File get() = File(directory, "snapshot.v1.json")
    val etagFile: File get() = File(directory, "snapshot.v1.etag")

    /**
     * The freshest snapshot on hand. An equal date prefers the downloaded one
     * (it carries the ETag). A downloaded file that no longer decodes is
     * ignored, not deleted. When the bundled one loads, its ETag is null.
     */
    fun load(): Loaded {
        val downloaded = try {
            if (snapshotFile.exists()) SnapshotDecoder.decode(snapshotFile.readBytes()) else null
        } catch (_: Exception) {
            null
        }
        if (downloaded != null) {
            bundledNewerThan(downloaded)?.let { return Loaded(it, Origin.BUNDLED, null) }
            return Loaded(downloaded, Origin.DOWNLOADED, readEtag())
        }
        val bytes = bundled() ?: throw BundledSnapshotMissing()
        return Loaded(SnapshotDecoder.decode(bytes), Origin.BUNDLED, null)
    }

    private fun bundledNewerThan(downloaded: Snapshot): Snapshot? {
        val bytes = try {
            bundled()
        } catch (_: Exception) {
            null
        } ?: return null
        val date = SnapshotDecoder.generatedAtOnly(bytes) ?: return null
        if (date <= downloaded.generatedAt) return null
        return try {
            SnapshotDecoder.decode(bytes)
        } catch (_: Exception) {
            null
        }
    }

    /** Validates [data] and, only if it decodes, swaps it in and records [etag]. On failure nothing changes. */
    fun replace(data: ByteArray, etag: String?): Snapshot {
        val snapshot = SnapshotDecoder.decode(data)
        directory.mkdirs()
        val temp = File(directory, "snapshot.v1.json.${UUID.randomUUID()}.tmp")
        try {
            temp.writeBytes(data)
            if (!temp.renameTo(snapshotFile)) throw IOException("could not move the new data file into place")
        } finally {
            temp.delete()
        }
        writeEtag(etag)
        return snapshot
    }

    fun readEtag(): String? = try {
        etagFile.readText().trim().ifEmpty { null }
    } catch (_: IOException) {
        null
    }

    private fun writeEtag(etag: String?) {
        if (!etag.isNullOrEmpty()) etagFile.writeText(etag) else etagFile.delete()
    }
}

/**
 * The app's entire network surface: one HTTPS GET of a static file
 * ([Endpoints.SNAPSHOT_URL]), conditional on the stored ETag. No cookies, no
 * cache, no identifiers: the headers are `Accept`, `If-None-Match` and the
 * app's own `User-Agent`, "QueerFrame/<version> (Android)" ([userAgent]). It
 * replaces the platform's default, which names the Android build and the
 * phone's model; nothing about the device is sent. On any failure the store
 * is untouched.
 */
class SnapshotRefresher(
    private val store: SnapshotStore,
    /** The whole User-Agent: [userAgent] of the app's version name. */
    private val userAgent: String,
    private val endpoint: String = Endpoints.SNAPSHOT_URL,
    private val transport: Transport = HttpTransport(),
    /** Whether the device reports any network at all; decides offline versus unreachable. */
    private val isOnline: () -> Boolean = { true },
) {
    sealed class Outcome {
        data object Unchanged : Outcome()
        data class Updated(val snapshot: Snapshot) : Outcome()
    }

    sealed class RefreshException(message: String) : Exception(message) {
        class HttpStatus(val code: Int) : RefreshException("The data file server answered HTTP $code.")
        class Transport(message: String, val offline: Boolean) : RefreshException(message)
        class Rejected(message: String) : RefreshException(message)
    }

    data class Request(val url: String, val headers: Map<String, String>)

    companion object {
        /** "QueerFrame/1.0.0 (Android)": the app's name and version, and the word Android. Nothing else. */
        fun userAgent(versionName: String): String = "QueerFrame/$versionName (Android)"
    }
    data class Response(val status: Int, val headers: Map<String, String>, val body: ByteArray)

    fun interface Transport {
        fun get(request: Request): Response
    }

    /** The exact request that will be sent. Pure; tests inspect it. */
    fun makeRequest(etag: String?): Request {
        val headers = linkedMapOf("Accept" to "application/json", "User-Agent" to userAgent)
        if (!etag.isNullOrEmpty()) headers["If-None-Match"] = etag
        return Request(endpoint, headers)
    }

    fun refresh(): Outcome {
        val request = makeRequest(store.readEtag())
        val response = try {
            transport.get(request)
        } catch (e: IOException) {
            val offline = !isOnline()
            throw RefreshException.Transport(e.message ?: e.toString(), offline)
        }
        return when (response.status) {
            304 -> Outcome.Unchanged
            200 -> {
                val etag = response.headers.entries.firstOrNull { it.key.equals("ETag", ignoreCase = true) }?.value
                try {
                    Outcome.Updated(store.replace(response.body, etag))
                } catch (e: SnapshotDecodingException) {
                    throw RefreshException.Rejected(e.message ?: "rejected")
                } catch (e: IOException) {
                    throw RefreshException.Rejected(e.message ?: "rejected")
                }
            }
            else -> throw RefreshException.HttpStatus(response.status)
        }
    }

    /** `HttpURLConnection`, with caches off and no cookie handler: nothing persists from a request. */
    class HttpTransport(private val connectTimeoutMillis: Int = 20_000, private val readTimeoutMillis: Int = 60_000) : Transport {
        override fun get(request: Request): Response {
            val connection = URI(request.url).toURL().openConnection() as HttpURLConnection
            try {
                connection.requestMethod = "GET"
                connection.useCaches = false
                connection.instanceFollowRedirects = true
                connection.connectTimeout = connectTimeoutMillis
                connection.readTimeout = readTimeoutMillis
                request.headers.forEach { (k, v) -> connection.setRequestProperty(k, v) }
                val status = connection.responseCode
                val headers = connection.headerFields.filterKeys { it != null }.mapValues { it.value.firstOrNull().orEmpty() }
                val body = if (status == 200) connection.inputStream.use { it.readBytes() } else ByteArray(0)
                return Response(status, headers, body)
            } finally {
                connection.disconnect()
            }
        }
    }
}
