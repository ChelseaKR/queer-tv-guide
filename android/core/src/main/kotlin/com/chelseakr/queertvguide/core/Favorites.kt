package com.chelseakr.queertvguide.core

import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import java.time.Instant

/** Where favorites are kept: the app's private preferences, or a map in tests. */
interface KeyValueStore {
    fun getString(key: String): String?
    fun putString(key: String, value: String?)
}

/**
 * Favorites live on this device and nowhere else: no account, no sync. The
 * only copy that can leave is a backup file the person exports and sends
 * somewhere themselves ([FavoritesBackup]), and the device's own backup.
 */
class FavoritesStore(private val storage: KeyValueStore, private val now: () -> Instant = Instant::now) {
    enum class Kind(val raw: String) {
        SHOW("show"),
        CHARACTER("character"),
        ;

        companion object {
            fun from(raw: String?): Kind? = entries.firstOrNull { it.raw == raw }
        }
    }

    data class Entry(val kind: Kind, val id: String, val addedAt: Instant) {
        val key: String get() = "${kind.raw}:$id"
    }

    @Serializable
    private data class Stored(val kind: String, val id: String, val addedAt: String)

    private val lock = Any()
    private var cache: List<Entry> = read()
    private val listeners = mutableListOf<() -> Unit>()

    val entries: List<Entry> get() = synchronized(lock) { cache }

    fun isFavorite(kind: Kind, id: String): Boolean = synchronized(lock) { cache.any { it.kind == kind && it.id == id } }

    /** Returns the new state. */
    fun toggle(kind: Kind, id: String): Boolean {
        val result = synchronized(lock) {
            val index = cache.indexOfFirst { it.kind == kind && it.id == id }
            if (index >= 0) {
                cache = cache.toMutableList().also { it.removeAt(index) }
                persist()
                false
            } else {
                cache = cache + Entry(kind, id, now())
                persist()
                true
            }
        }
        notifyChanged()
        return result
    }

    fun remove(kind: Kind, id: String) {
        synchronized(lock) {
            cache = cache.filterNot { it.kind == kind && it.id == id }
            persist()
        }
        notifyChanged()
    }

    /** Adds every entry not already saved, keeping saved ones as they are. One write for the batch. */
    fun merge(incoming: List<Entry>): Pair<Int, Int> {
        val added: Int
        synchronized(lock) {
            val keys = cache.map { it.key }.toMutableSet()
            val fresh = incoming.filter { keys.add(it.key) }
            added = fresh.size
            if (added > 0) {
                cache = cache + fresh
                persist()
            }
        }
        if (added > 0) notifyChanged()
        return added to (incoming.size - added)
    }

    fun removeAll() {
        synchronized(lock) {
            cache = emptyList()
            persist()
        }
        notifyChanged()
    }

    /** Called after any change, on the caller's thread. */
    fun addListener(listener: () -> Unit) {
        synchronized(listeners) { listeners += listener }
    }

    private fun notifyChanged() {
        val copy = synchronized(listeners) { listeners.toList() }
        copy.forEach { it() }
    }

    private fun persist() {
        val stored = cache.map { Stored(it.kind.raw, it.id, Dates.formatInstant(it.addedAt)) }
        storage.putString(STORED_UNDER, json.encodeToString(ListSerializer(Stored.serializer()), stored))
    }

    private fun read(): List<Entry> {
        val text = storage.getString(STORED_UNDER) ?: return emptyList()
        return try {
            json.decodeFromString(ListSerializer(Stored.serializer()), text).mapNotNull { s ->
                val kind = Kind.from(s.kind) ?: return@mapNotNull null
                Entry(kind, s.id, Dates.parseInstant(s.addedAt) ?: Instant.EPOCH)
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    companion object {
        // Persisted key: never rename it, or saved favorites vanish on update.
        const val STORED_UNDER = "favourites.v1"
        private val json = Json { ignoreUnknownKeys = true }
    }
}

/**
 * A favorites backup is a file the person holds (DG-10): the same format
 * iOS writes and reads, so a backup moves between an iPhone and an Android
 * phone. It holds only the kind, the snapshot id and when it was added; no
 * titles and no death answers. Import trusts nothing in the file.
 */
object FavoritesBackup {
    // Written into every backup file: spelling kept so existing files still import.
    const val FORMAT = "favourites-backup"
    const val VERSION = 1
    const val MAX_BYTES = 4 * 1024 * 1024
    const val MAX_ENTRIES = 50_000

    // Published file name (docs, support page, ADR 0014).
    const val SUGGESTED_FILE_NAME = "favourites-backup.json"

    sealed class ImportException(message: String) : Exception(message) {
        class TooLarge(val bytes: Int) : ImportException("This file is too large to be a favorites backup.")
        class NotABackup : ImportException("This file isn't a favorites backup from this app.")
        class UnsupportedVersion(val version: Int) :
            ImportException("This favorites backup was made by a newer version of the app. Update the app, then import it again.")
        class TooManyEntries(val count: Int) :
            ImportException("This file lists $count favorites, more than a backup from this app can hold.")
    }

    data class Parsed(val entries: List<FavoritesStore.Entry>, val notInSnapshot: Int, val unreadable: Int)

    /**
     * The backup file for [entries], byte for byte what iOS writes
     * (Foundation's pretty printing: two-space indent, " : ", sorted keys,
     * slashes unescaped), so the same favorites export to the same bytes on
     * either platform.
     */
    fun export(entries: List<FavoritesStore.Entry>): ByteArray {
        val sb = StringBuilder()
        sb.append("{\n  \"favourites\" : [\n")
        if (entries.isEmpty()) {
            sb.append("\n")
        } else {
            entries.forEachIndexed { i, e ->
                sb.append("    {\n")
                sb.append("      \"added_at\" : ").append(quote(Dates.formatInstant(e.addedAt))).append(",\n")
                sb.append("      \"id\" : ").append(quote(e.id)).append(",\n")
                sb.append("      \"kind\" : ").append(quote(e.kind.raw)).append("\n")
                sb.append("    }").append(if (i < entries.size - 1) ",\n" else "\n")
            }
        }
        sb.append("  ],\n  \"format\" : ").append(quote(FORMAT)).append(",\n  \"version\" : ").append(VERSION).append("\n}")
        return sb.toString().toByteArray(Charsets.UTF_8)
    }

    /** JSON string literal as Foundation writes it (slashes left alone). */
    private fun quote(s: String): String {
        val sb = StringBuilder("\"")
        for (c in s) {
            when (c) {
                '"' -> sb.append("\\\"")
                '\\' -> sb.append("\\\\")
                '\n' -> sb.append("\\n")
                '\r' -> sb.append("\\r")
                '\t' -> sb.append("\\t")
                '\b' -> sb.append("\\b")
                '\u000C' -> sb.append("\\f")
                else -> if (c < ' ') sb.append(String.format("\\u%04x", c.code)) else sb.append(c)
            }
        }
        return sb.append('"').toString()
    }

    /**
     * Validates [data] as a backup. [isKnown] says whether an id is in the
     * current snapshot; [now] stands in for an `added_at` that is missing,
     * unreadable or in the future.
     */
    fun parse(data: ByteArray, now: Instant, isKnown: (FavoritesStore.Kind, String) -> Boolean): Parsed {
        if (data.size > MAX_BYTES) throw ImportException.TooLarge(data.size)
        val root = try {
            Json.parseToJsonElement(String(data, Charsets.UTF_8)) as? JsonObject
        } catch (_: Exception) {
            null
        } ?: throw ImportException.NotABackup()
        val format = (root["format"] as? JsonPrimitive)?.takeIf { it.isString }?.content
        val items = root["favourites"] as? JsonArray
        if (format != FORMAT || items == null) throw ImportException.NotABackup()
        val versionPrimitive = root["version"] as? JsonPrimitive
        val version = versionPrimitive?.takeIf { !it.isString }?.intOrNull ?: throw ImportException.NotABackup()
        if (version != VERSION) throw ImportException.UnsupportedVersion(version)
        if (items.size > MAX_ENTRIES) throw ImportException.TooManyEntries(items.size)

        val entries = ArrayList<FavoritesStore.Entry>()
        val seen = HashSet<String>()
        var notInSnapshot = 0
        var unreadable = 0
        for (item in items) {
            val entry = entry(item, now)
            if (entry == null) {
                unreadable += 1
                continue
            }
            if (!isKnown(entry.kind, entry.id)) {
                notInSnapshot += 1
                continue
            }
            if (seen.add(entry.key)) entries += entry
        }
        return Parsed(entries, notInSnapshot, unreadable)
    }

    private fun entry(item: kotlinx.serialization.json.JsonElement, now: Instant): FavoritesStore.Entry? {
        val obj = item as? JsonObject ?: return null
        val kind = FavoritesStore.Kind.from((obj["kind"] as? JsonPrimitive)?.takeIf { it.isString }?.contentOrNull) ?: return null
        val id = (obj["id"] as? JsonPrimitive)?.takeIf { it.isString }?.contentOrNull ?: return null
        if (!isWellFormed(id, kind)) return null
        var added = (obj["added_at"] as? JsonPrimitive)?.takeIf { it.isString }?.contentOrNull?.let { Dates.parseInstant(it) } ?: now
        if (added > now) added = now
        return FavoritesStore.Entry(kind, id, added)
    }

    /** `lwtv:show:<digits>` or `lwtv:character:<digits>`, 1 to 12 ASCII digits, matching the kind. */
    fun isWellFormed(id: String, kind: FavoritesStore.Kind): Boolean {
        val prefix = "lwtv:${kind.raw}:"
        if (!id.startsWith(prefix)) return false
        val digits = id.substring(prefix.length)
        return digits.isNotEmpty() && digits.length <= 12 && digits.all { it in '0'..'9' }
    }
}
