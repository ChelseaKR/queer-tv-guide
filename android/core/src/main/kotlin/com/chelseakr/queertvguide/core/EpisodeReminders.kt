package com.chelseakr.queertvguide.core

import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZonedDateTime

/**
 * Plans the optional local reminders for favorite shows' next episodes:
 * GuideCore's `EpisodeReminders`, ported, so Android sets the same reminders
 * at the same instants with the same words (`ParityGoldenTest`).
 *
 * A reminder carries a show's title, an episode's season and number, and the
 * data's date. Never an episode name (a title can give an ending away on a
 * lock screen) and never anything about a death: nothing here reads death
 * data at all.
 *
 * A reminder fires at the broadcast instant only when TVmaze records an air
 * time ([Episode.airInstant]). Otherwise it comes at [FALLBACK_HOUR] local
 * time on the air date, and its words give the date and say no air time is
 * listed: that hour is a delivery time, never a claim about the broadcast.
 */
object EpisodeReminders {
    /** Every reminder's id starts with this, so the app replaces its own and touches nothing else. */
    const val IDENTIFIER_PREFIX = "episode-reminder."

    /** The soonest 60, as on iOS (which keeps at most 64 pending). */
    const val LIMIT = 60

    const val FALLBACK_HOUR = 10

    data class Planned(
        val identifier: String,
        val showId: String,
        val fireAt: Instant,
        val title: String,
        val body: String,
    )

    /**
     * The reminders to set for [favoriteShowIds] (any order) as of [now], in
     * the device's zone and locale ([text]). Episodes already aired, undated,
     * or on shows with an unknown or empty schedule get none.
     */
    fun plan(favoriteShowIds: List<String>, snapshot: Snapshot, now: Instant, text: DateText, limit: Int = LIMIT): List<Planned> {
        val seen = HashSet<String>()
        val planned = ArrayList<Planned>()
        for (id in favoriteShowIds) {
            if (!seen.add(id)) continue
            val show = snapshot.show(id) ?: continue
            if (!show.schedule.scheduleKnown) continue
            val episode = show.schedule.nextEpisode ?: continue
            val fire = fireAt(episode, text) ?: continue
            if (fire <= now) continue
            planned += Planned(
                identifier = "$IDENTIFIER_PREFIX${show.id}.${episode.tvmazeId}",
                showId = show.id,
                fireAt = fire,
                title = show.title,
                body = body(episode, fire, text, snapshot.generatedAt),
            )
        }
        planned.sortWith { a, b -> if (a.fireAt != b.fireAt) a.fireAt.compareTo(b.fireAt) else SearchIndex.compareSwift(a.identifier, b.identifier) }
        return planned.take(limit)
    }

    /**
     * The broadcast instant when TVmaze records an air time; otherwise
     * [FALLBACK_HOUR] local on the air date; null with neither. The date's
     * parts are read the way iOS's calendar reads them, leniently (a day
     * past the month's end rolls into the next month).
     */
    fun fireAt(episode: Episode, text: DateText): Instant? {
        episode.airInstant?.let { return it }
        val airdate = episode.airdate ?: return null
        val parts = airdate.split('-').mapNotNull { it.toIntOrNull() }
        if (parts.size != 3) return null
        val day = LocalDate.of(parts[0], 1, 1).plusMonths(parts[1] - 1L).plusDays(parts[2] - 1L)
        return ZonedDateTime.of(day, LocalTime.of(FALLBACK_HOUR, 0), text.zone).toInstant()
    }

    /**
     * With a real air time: "S23E1 is listed to air now. Schedule from
     * TVmaze, data as of Sep 18; it may have changed." With a date only:
     * "S23E1 is listed for Sep 21, the network's date, with no air time. …"
     */
    fun body(episode: Episode, fireAt: Instant, text: DateText, generatedAt: Instant): String {
        val code = if (episode.season != null && episode.number != null) "S${episode.season}E${episode.number}" else "A new episode"
        val listed = if (episode.airInstant != null) {
            "is listed to air now"
        } else {
            "is listed for ${text.skeleton("MMMd", fireAt)}, the network's date, with no air time"
        }
        return "$code $listed. Schedule from TVmaze, data as of ${text.skeleton("MMMd", generatedAt)}; it may have changed."
    }
}
