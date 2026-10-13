package com.chelseakr.queertvguide.core

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.io.File
import java.time.Duration
import java.time.Instant
import java.time.LocalDate

/**
 * What the home-screen widget shows: the next episode of each favorite show.
 * The app writes one small file and the widget reads only that file: no
 * network request, never the snapshot.
 *
 * Spoiler safety is structural: an item carries a show's title, its schedule
 * status, and an episode's season, number and air date. No field could hold
 * death data, and there is no episode name (a title can give an ending away).
 */
@Serializable
data class UpNext(
    @SerialName("formatVersion") val formatVersion: Int = CURRENT_FORMAT_VERSION,
    /** The snapshot's `generated_at`, as seconds since 1970 in UTC. */
    @SerialName("snapshotGeneratedAt") val snapshotGeneratedAtEpochSeconds: Long,
    /** Favorite shows, newest first. */
    val items: List<Item>,
    /** Favorite shows the snapshot no longer lists: counted, never dropped silently. */
    @SerialName("missingShowCount") val missingShowCount: Int,
) {
    val snapshotGeneratedAt: Instant get() = Instant.ofEpochSecond(snapshotGeneratedAtEpochSeconds)

    @Serializable
    data class Item(
        @SerialName("showID") val showId: String,
        val title: String,
        val status: Status,
        val season: Int? = null,
        val number: Int? = null,
        /** YYYY-MM-DD exactly as TVmaze records it. */
        val airdate: String? = null,
    ) {
        /** The same four facts the Favorites screen states: an unmatched show is never "nothing upcoming". */
        @Serializable
        enum class Status(val raw: String) {
            @SerialName("dated") DATED("dated"),
            @SerialName("undated") UNDATED("undated"),
            @SerialName("noneListed") NONE_LISTED("noneListed"),
            @SerialName("unknown") UNKNOWN("unknown"),
        }

        val airdateDay: LocalDate? get() = if (status == Status.DATED) Dates.parseDay(airdate) else null
    }

    /**
     * The order the widget lists items on [today]: soonest air date first,
     * then passed dates, then undated, then nothing listed, then unknown.
     * Ties keep the favorites order.
     */
    fun ordered(today: Instant): List<Item> {
        fun rank(item: Item): Int = when (item.status) {
            Item.Status.DATED -> {
                val day = item.airdateDay
                if (day == null) 2 else if (Presentation.isPast(day, today)) 1 else 0
            }
            Item.Status.UNDATED -> 2
            Item.Status.NONE_LISTED -> 3
            Item.Status.UNKNOWN -> 4
        }
        return items.withIndex().sortedWith { a, b ->
            val ra = rank(a.value)
            val rb = rank(b.value)
            if (ra != rb) return@sortedWith ra - rb
            val da = a.value.airdateDay
            val db = b.value.airdateDay
            if (ra <= 1 && da != null && db != null && da != db) return@sortedWith da.compareTo(db)
            a.index - b.index
        }.map { it.value }
    }

    companion object {
        const val CURRENT_FORMAT_VERSION = 1
        const val FILE_NAME = "up-next.v1.json"

        fun build(favoriteShowIds: List<String>, snapshot: Snapshot): UpNext {
            val items = ArrayList<Item>()
            var missing = 0
            val seen = HashSet<String>()
            for (id in favoriteShowIds) {
                if (!seen.add(id)) continue
                val show = snapshot.show(id)
                if (show == null) {
                    missing += 1
                    continue
                }
                items += item(show)
            }
            return UpNext(CURRENT_FORMAT_VERSION, snapshot.generatedAt.epochSecond, items, missing)
        }

        fun item(show: Show): Item {
            val schedule = show.schedule
            if (!schedule.scheduleKnown) return Item(show.id, show.title, Item.Status.UNKNOWN)
            val episode = schedule.nextEpisode ?: return Item(show.id, show.title, Item.Status.NONE_LISTED)
            val dated = episode.airdateDay != null
            return Item(
                showId = show.id,
                title = show.title,
                status = if (dated) Item.Status.DATED else Item.Status.UNDATED,
                season = episode.season,
                number = episode.number,
                airdate = if (dated) episode.airdate else null,
            )
        }
    }
}

/** Reads and writes [UpNext] in a directory (the app's files directory, or a test's). */
class UpNextStore(private val directory: File) {
    val file: File get() = File(directory, UpNext.FILE_NAME)

    /** Null when there is no file, it does not decode, or it is another format version. */
    fun read(): UpNext? = try {
        val upNext = json.decodeFromString(UpNext.serializer(), file.readText())
        if (upNext.formatVersion == UpNext.CURRENT_FORMAT_VERSION) upNext else null
    } catch (_: Exception) {
        null
    }

    /** Writes atomically when the contents differ; returns whether it wrote. */
    fun write(upNext: UpNext): Boolean {
        if (read() == upNext) return false
        directory.mkdirs()
        val temp = File.createTempFile("up-next", ".tmp", directory)
        try {
            temp.writeText(json.encodeToString(UpNext.serializer(), upNext))
            if (!temp.renameTo(file)) {
                file.delete()
                check(temp.renameTo(file)) { "could not move the widget file into place" }
            }
        } finally {
            temp.delete()
        }
        return true
    }

    private companion object {
        val json = Json { ignoreUnknownKeys = true; encodeDefaults = true; explicitNulls = false }
    }
}

/**
 * The widget's text for every state, held to the app's rules: stated, never
 * blank, and an unknown schedule never reads as "nothing upcoming".
 */
object UpNextPresentation {
    const val STALE_AFTER_SECONDS: Long = 48 * 60 * 60
    const val TITLE = "Up next"
    const val NO_FAVORITE_SHOWS = "Star a show to see its next episode here."
    const val NOT_LOADED = "Open the app once to show your favorite shows here."
    const val TVMAZE_CREDIT = "Schedules: TVmaze"

    fun line(item: UpNext.Item, today: Instant, text: DateText): String = when (item.status) {
        UpNext.Item.Status.UNKNOWN -> "Schedule unknown"
        UpNext.Item.Status.NONE_LISTED -> "No upcoming episode listed"
        UpNext.Item.Status.UNDATED -> undated(item)
        UpNext.Item.Status.DATED -> {
            val day = item.airdateDay
            if (day == null) {
                undated(item)
            } else {
                val date = text.skeletonUtcDay("MMMd", day)
                val head = episodeCode(item) ?: "Next episode"
                if (Presentation.isPast(day, today)) "$head · $date, passed" else "$head · $date"
            }
        }
    }

    private fun undated(item: UpNext.Item): String =
        episodeCode(item)?.let { "$it · air date not recorded" } ?: "Next episode · air date not recorded"

    /** What TalkBack reads for a row: whole words, no "S23E1". */
    fun spoken(item: UpNext.Item, today: Instant, text: DateText): String {
        val episode = if (item.season != null && item.number != null) "Season ${item.season}, episode ${item.number}" else "Next episode"
        return when (item.status) {
            UpNext.Item.Status.UNKNOWN -> "${item.title}. Schedule unknown."
            UpNext.Item.Status.NONE_LISTED -> "${item.title}. No upcoming episode listed."
            UpNext.Item.Status.UNDATED -> "${item.title}. $episode, air date not recorded."
            UpNext.Item.Status.DATED -> {
                val day = item.airdateDay ?: return "${item.title}. $episode, air date not recorded."
                val date = text.skeletonUtcDay("MMMMd", day)
                if (Presentation.isPast(day, today)) {
                    "${item.title}. $episode was listed for $date, which has passed. This data may be out of date."
                } else {
                    "${item.title}. $episode, $date."
                }
            }
        }
    }

    fun episodeCode(item: UpNext.Item): String? =
        if (item.season != null && item.number != null) "S${item.season}E${item.number}" else null

    enum class Freshness { CURRENT, STALE, UNKNOWN_AGE }

    fun freshness(generatedAt: Instant, now: Instant): Freshness {
        val ageMillis = Duration.between(generatedAt, now).toMillis()
        if (ageMillis < -3_600_000) return Freshness.UNKNOWN_AGE
        return if (ageMillis > STALE_AFTER_SECONDS * 1000) Freshness.STALE else Freshness.CURRENT
    }

    /** The footer: always the data's date (a UTC day), and a plain warning when it is old or of unknown age. */
    fun dataAge(generatedAt: Instant, now: Instant, text: DateText): String {
        val date = text.skeletonUtcDay("MMMd", generatedAt.atZone(java.time.ZoneOffset.UTC).toLocalDate())
        return when (freshness(generatedAt, now)) {
            Freshness.CURRENT -> "Data as of $date"
            Freshness.STALE -> "Out of date: data as of $date"
            Freshness.UNKNOWN_AGE -> "Data age unknown"
        }
    }

    /** "+2 more", "1 not in this data": neither vanishes without a word. */
    fun more(count: Int, missing: Int = 0): String? {
        val parts = mutableListOf<String>()
        if (count > 0) parts += "+$count more"
        if (missing > 0) parts += "$missing not in this data"
        return if (parts.isEmpty()) null else parts.joinToString(", ")
    }
}
