package com.chelseakr.queertvguide.core

import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.decodeFromStream
import java.io.ByteArrayInputStream
import java.io.InputStream
import java.time.Instant
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.format.DateTimeParseException

/** Why a snapshot was refused. Mirrors GuideCore's `SnapshotDecodingError`. */
sealed class SnapshotDecodingException(message: String) : Exception(message) {
    class UnsupportedSchemaVersion(val version: String) : SnapshotDecodingException(
        "Snapshot schema_version \"$version\" is not supported (this app reads \"${Snapshot.SUPPORTED_SCHEMA_VERSION}\").",
    )

    class Malformed(val detail: String) : SnapshotDecodingException("Snapshot is malformed: $detail")
}

/**
 * Decodes `schema/snapshot.v1.json` documents. Every snapshot the app reads,
 * bundled or downloaded, comes through [decode] (by way of `SnapshotStore`),
 * so a rule enforced here holds for both. The same rules as GuideCore's
 * `SnapshotDecoder`, each refusing the whole file:
 *
 * - `schema_version` must be "1";
 * - every field the schema requires must be present (nullable ones may be
 *   absent and read as null, never as a default);
 * - `died` must be true or null (LezWatch records deaths, not survival);
 * - show ids and character ids must each be unique;
 * - LezWatch.TV's and TVmaze's credits must each appear exactly once;
 * - `generated_at` and `source_modified_at` must be UTC datetimes to the
 *   second, never quietly "now" or the epoch.
 */
object SnapshotDecoder {
    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        coerceInputValues = false
        isLenient = false
    }

    fun decode(bytes: ByteArray): Snapshot = decode(ByteArrayInputStream(bytes))

    @OptIn(kotlinx.serialization.ExperimentalSerializationApi::class)
    fun decode(stream: InputStream): Snapshot {
        val wire = try {
            json.decodeFromStream(SnapshotWire.serializer(), stream)
        } catch (e: SerializationException) {
            throw SnapshotDecodingException.Malformed(e.message ?: e.toString())
        } catch (e: IllegalArgumentException) {
            throw SnapshotDecodingException.Malformed(e.message ?: e.toString())
        }
        if (wire.schemaVersion != Snapshot.SUPPORTED_SCHEMA_VERSION) {
            throw SnapshotDecodingException.UnsupportedSchemaVersion(wire.schemaVersion)
        }
        val generatedAt = Dates.parseTaggedDate(wire.generatedAt, "generated_at")
        wire.shows.forEachIndexed { i, show -> Dates.parseTaggedDate(show.sourceModifiedAt, "shows.$i.source_modified_at") }
        wire.characters.forEachIndexed { i, c ->
            Dates.parseTaggedDate(c.sourceModifiedAt, "characters.$i.source_modified_at")
            if (c.death.died == false) {
                throw SnapshotDecodingException.Malformed(
                    "died at characters.$i.death is false; the contract only allows true or null (LezWatch records deaths, not survival)",
                )
            }
        }
        firstRepeatedId(wire.shows.map { it.id })?.let { throw SnapshotDecodingException.Malformed("duplicate show id $it") }
        firstRepeatedId(wire.characters.map { it.id })?.let { throw SnapshotDecodingException.Malformed("duplicate character id $it") }
        val snapshot = Snapshot(
            schemaVersion = wire.schemaVersion,
            generatedAt = generatedAt,
            contentDigest = wire.contentDigest,
            license = wire.license,
            attribution = wire.attribution,
            coverage = wire.coverage,
            taxonomies = wire.taxonomies,
            shows = wire.shows,
            characters = wire.characters,
        )
        requireEachCredit(snapshot)
        return snapshot
    }

    /**
     * LezWatch.TV's and TVmaze's credits must each appear exactly once. A file
     * without TVmaze's would put TVmaze's dates on screen with no credit, so
     * it is refused whole and the last good file is kept.
     */
    fun requireEachCredit(snapshot: Snapshot) {
        for (source in listOf(Attribution.LEZWATCH_SOURCE, Attribution.TVMAZE_SOURCE)) {
            when (val count = snapshot.attribution.count { it.source == source }) {
                1 -> continue
                0 -> throw SnapshotDecodingException.Malformed("attribution has no entry for source $source")
                else -> throw SnapshotDecodingException.Malformed(
                    "attribution has $count entries for source $source, expected exactly one",
                )
            }
        }
    }

    /** Reads only `generated_at`, cheaply, to compare a bundled file's date before decoding all of it. */
    fun generatedAtOnly(bytes: ByteArray): Instant? {
        val head = String(bytes, 0, minOf(bytes.size, 4096), Charsets.UTF_8)
        val match = Regex("\"generated_at\"\\s*:\\s*\"([^\"]+)\"").find(head) ?: return null
        return Dates.parseInstant(match.groupValues[1])
    }

    private fun firstRepeatedId(ids: List<String>): String? {
        val seen = HashSet<String>()
        return ids.firstOrNull { !seen.add(it) }
    }
}

/** The contract's date shapes, parsed strictly. */
object Dates {
    private val datetime = Regex("""^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$""")
    private val day = Regex("""^\d{4}-\d{2}-\d{2}$""")

    /** `YYYY-MM-DDTHH:MM:SS` with `Z` or an offset, to the second; null otherwise. */
    fun parseInstant(text: String): Instant? {
        if (!datetime.matches(text)) return null
        return try {
            OffsetDateTime.parse(text).toInstant()
        } catch (_: DateTimeParseException) {
            null
        }
    }

    fun parseDay(text: String?): LocalDate? {
        if (text == null || !day.matches(text)) return null
        return try {
            LocalDate.parse(text)
        } catch (_: DateTimeParseException) {
            null
        }
    }

    internal fun parseTaggedDate(text: String, path: String): Instant =
        parseInstant(text) ?: throw SnapshotDecodingException.Malformed(
            "data corrupted at $path: '$text' is not a UTC datetime (YYYY-MM-DDTHH:MM:SSZ)",
        )

    /** Whole-second UTC, as the snapshot writes its own dates: `2026-09-18T09:44:42Z`. */
    fun formatInstant(instant: Instant): String = java.time.format.DateTimeFormatter.ISO_INSTANT
        .format(instant.truncatedTo(java.time.temporal.ChronoUnit.SECONDS))
}
