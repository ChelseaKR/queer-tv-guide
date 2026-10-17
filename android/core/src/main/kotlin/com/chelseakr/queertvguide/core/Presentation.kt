package com.chelseakr.queertvguide.core

import java.math.BigDecimal
import java.math.RoundingMode
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

/**
 * Pure text for every state the UI can be in, including every absence: the
 * Kotlin port of GuideCore's `Presentation`, word for word (the parity file,
 * `ParityGoldenTest`, holds the two together). An absent value is stated,
 * never blank and never a number, and never a manufactured "no" where the
 * source only records "not recorded".
 */
object Presentation {
    // Worth it / ratings

    fun worthIt(value: String?): String = value ?: "Not rated"

    fun rating(value: Int?, label: String): String = if (value == null) "$label: not rated" else "$label: $value of 5"

    fun ratingValue(value: Int?): String = if (value == null) "Not rated" else "$value of 5"

    /** "%.0f" as C's printf rounds it (half to even), as on iOS. */
    fun score(value: Double?): String {
        if (value == null) return "No score recorded"
        val rounded = BigDecimal(value).setScale(0, RoundingMode.HALF_EVEN).toPlainString()
        return "Score $rounded (an ordinal LezWatch ranking, not a percentage)"
    }

    // Death. Every unknown answer opens with "Not recorded." A sentence that
    // opens with "No" is heard as "No" by a TalkBack user who moves on after
    // the first word, and "No" answers "does she die?" with a fact the source
    // never asserts.

    fun death(death: Death, name: String): String {
        if (!death.isRecorded) return "Not recorded. This snapshot does not record a death for $name."
        if (death.years.isEmpty()) return "Yes. $name dies. The year is not recorded."
        val list = death.years.sorted().joinToString(", ")
        return if (death.years.size > 1) {
            "Yes. $name dies more than once, recorded in $list."
        } else {
            "Yes. $name dies ($list)."
        }
    }

    fun deathShort(death: Death): String = if (death.isRecorded) "Dies" else "Death not recorded"

    fun deathsSummary(cast: List<Character>): String {
        if (cast.isEmpty()) return NO_LISTED_CAST
        val dead = cast.filter { it.death.isRecorded }
        val noun = if (cast.size == 1) "character" else "characters"
        if (dead.isEmpty()) return "Not recorded for any of the ${cast.size} listed $noun."
        val verb = if (dead.size == 1) "dies" else "die"
        return "${dead.size} of ${cast.size} listed $noun $verb: ${dead.joinToString(", ") { it.name }}."
    }

    /** The show-level answer to "do any queer characters die?". */
    data class ShowDeaths(val headline: String, val lines: List<String>, val notes: List<String>) {
        /** Everything, in reading order, for a single TalkBack element. */
        val spoken: String get() = (listOf(headline) + lines + notes).joinToString(" ")
    }

    /**
     * LezWatch terms whose mere presence answers "does she die": kept out of
     * the always-visible trope lists so the reveal is not defeated by the line
     * above it.
     */
    val deathSpoilerClicheSlugs: Set<String> = setOf("dead")
    val deathSpoilerTropeSlugs: Set<String> = setOf("dead-queers")

    fun withoutSpoilers(terms: List<Term>, spoilers: Set<String>): List<Term> = terms.filter { it.slug !in spoilers }

    const val NO_LISTED_CAST = "Not recorded. This snapshot does not list any queer characters for this show."

    fun showDeaths(cast: List<Character>, show: Show): ShowDeaths {
        val notes = mutableListOf<String>()
        val spoilerTags = show.tropes.filter { it.slug in deathSpoilerTropeSlugs }
        if (cast.isEmpty()) {
            notes += spoilerTags.map { "LezWatch.TV tags this show “${it.name}”." }
            return ShowDeaths(NO_LISTED_CAST, emptyList(), notes)
        }
        val dead = cast.filter { it.death.isRecorded }
        val listed = "${cast.size} listed ${if (cast.size == 1) "character" else "characters"}"
        val reported = show.counts.deathsSourceReported
        if (reported != null && reported != dead.size) {
            notes += "LezWatch.TV's own tally for this show is $reported ${if (reported == 1) "death" else "deaths"}; its character records list ${dead.size}."
        }
        notes += spoilerTags.map { "LezWatch.TV tags this show “${it.name}”." }
        if (dead.isEmpty()) {
            val headline = if (cast.size == 1) {
                "Not recorded. This snapshot does not record a death for the one listed character."
            } else {
                "Not recorded. This snapshot does not record a death for any of the $listed."
            }
            return ShowDeaths(headline, emptyList(), notes)
        }
        val lines = dead.map { character ->
            val years = character.death.years.sorted().joinToString(", ")
            val whenText = if (years.isEmpty()) "" else " ($years)"
            val showCount = character.shows.map { it.showId }.toSet().size
            if (showCount > 1) {
                "${character.name}: a death is recorded$whenText. ${character.name} appears in $showCount shows, and the record does not say which one."
            } else {
                "${character.name} dies$whenText."
            }
        }
        return ShowDeaths(
            headline = "${dead.size} of $listed ${if (dead.size == 1) "has" else "have"} a recorded death.",
            lines = lines,
            notes = notes,
        )
    }

    // Where to watch / schedule

    const val NO_WATCH_LINKS = "No where-to-watch link in this snapshot."
    const val NO_TROPES = "No tropes listed."
    const val NO_TRIGGERS = "No trigger warnings listed."
    const val NO_SUMMARY = "No summary in this snapshot."
    const val NO_CHARACTERS = "No characters listed for this show."
    const val NO_PLOT = "No plot notes in this snapshot."

    /** "www.amazon.com" reads "amazon.com"; only a leading "www." is dropped. */
    fun displayHost(host: String): String = if (host.lowercase().startsWith("www.")) host.drop(4) else host

    fun watchLinkLabel(link: WatchLink, networks: List<Term>): String = "Watch on ${watchLinkService(link, networks)}"

    /**
     * The service name: one of the show's own networks only when it matches
     * the host's site name exactly (letters and digits, case ignored).
     * Nothing is guessed.
     */
    fun watchLinkService(link: WatchLink, networks: List<Term>): String {
        val host = displayHost(link.host)
        val parts = host.split('.')
        if (parts.size >= 2) {
            val site = comparable(parts[parts.size - 2])
            if (site.isNotEmpty()) {
                networks.firstOrNull { comparable(it.name) == site }?.let { return it.name }
            }
        }
        return host
    }

    /**
     * An Apple TV or iTunes link carrying the developer's Apple affiliate
     * token (`at=`), added by the pipeline after every other party's tag is
     * stripped (DECISIONS 0019). Read from the link itself, so the snapshot
     * contract does not change; the same rule as GuideCore's `WatchLink.isPaidLink`.
     */
    fun isPaidLink(link: WatchLink): Boolean {
        val uri = try {
            java.net.URI(link.url)
        } catch (_: java.net.URISyntaxException) {
            return false
        }
        if (uri.host?.lowercase() !in setOf("tv.apple.com", "itunes.apple.com")) return false
        return (uri.rawQuery ?: "").split('&').any { it.startsWith("at=") && it.length > "at=".length }
    }

    /** Shown next to a where-to-watch link that earns the developer a commission, so nobody taps it unaware. */
    const val PAID_LINK_NOTE = "Paid link"

    /** What TalkBack reads for a where-to-watch link: the label, and "paid link" when it is one. */
    fun watchLinkSpoken(link: WatchLink, networks: List<Term>): String {
        val label = watchLinkLabel(link, networks)
        return if (isPaidLink(link)) "$label, paid link" else label
    }

    private fun comparable(text: String): String = text.lowercase().filter { it.isLetterOrDigit() }

    /**
     * The next-episode sentence. "Schedule unknown" (never matched) and "no
     * upcoming episode" (matched, nothing listed) read differently; a listed
     * episode whose date has passed is said to be past; an air time is
     * written in the viewer's zone ([text]), a date-only episode as TVmaze's
     * day in the network's zone.
     */
    fun nextEpisode(schedule: Schedule, today: Instant, text: DateText): String {
        if (!schedule.scheduleKnown) return "Schedule unknown for this show."
        val e = schedule.nextEpisode ?: return "No upcoming episode is known."
        val parts = mutableListOf<String>()
        if (e.season != null && e.number != null) parts += "S${e.season}E${e.number}"
        if (!e.name.isNullOrEmpty()) parts += "“${e.name}”"
        val head = if (parts.isEmpty()) "Next episode" else parts.joinToString(" ")

        val instant = e.airInstant
        if (instant != null) {
            val dayStart = instant.atZone(text.zone).toLocalDate().atStartOfDay(text.zone).toInstant()
            val todayStart = today.atZone(text.zone).toLocalDate().atStartOfDay(text.zone).toInstant()
            if (dayStart < todayStart.minusSeconds(86_400)) {
                return "$head — ${text.mediumDateTime(instant)}, which has passed. This data may be out of date."
            }
            return "$head — ${text.mediumDateTime(instant)}"
        }
        val day = e.airdateDay ?: return "$head — air date not recorded"
        if (isPast(day, today)) {
            return "$head — listed for ${text.mediumDay(day)}, which has passed. This data may be out of date."
        }
        return "$head — ${text.mediumDay(day)} (date as TVmaze lists it, in the network’s time zone)"
    }

    /** True when [day] (a UTC calendar day) is more than one day before [today]'s UTC calendar day. */
    fun isPast(day: LocalDate, today: Instant): Boolean {
        val startOfToday = today.atZone(ZoneOffset.UTC).toLocalDate()
        return day < startOfToday.minusDays(1)
    }

    fun years(y: Years): String {
        val (s, e) = y.start to y.end
        return when {
            s == null && y.onAir == OnAir.UNKNOWN -> "Air dates not recorded"
            s != null && e == null && y.onAir == OnAir.YES -> "$s – present"
            s != null && e == null -> "$s – ongoing status not recorded"
            s != null && e != null -> "$s – $e"
            e != null -> "Ended $e"
            else -> "Air dates not recorded"
        }
    }

    /** 0 is LezWatch's "never filled in", so it reads as not recorded, never "0 seasons". */
    fun seasons(n: Int?): String {
        if (n == null || n <= 0) return "Seasons not recorded"
        return if (n == 1) "1 season" else "$n seasons"
    }

    fun terms(items: List<Term>, empty: String): String = if (items.isEmpty()) empty else items.joinToString(", ") { it.name }

    // Data status

    fun generatedAt(date: Instant, text: DateText): String = "Data as of ${text.mediumDateTime(date)}"

    fun dataAsOf(date: Instant, freshness: DataFreshness, text: DateText): String = when (freshness) {
        is DataFreshness.Current -> "${generatedAt(date, text)} (${age(freshness.ageSeconds)})"
        is DataFreshness.Stale -> "${generatedAt(date, text)} (${age(freshness.ageSeconds)})"
        DataFreshness.Unknown -> "${generatedAt(date, text)} (age unknown: that is later than this device's clock)"
    }

    /** Rounded down: never overstated into the next threshold. */
    fun age(seconds: Long): String {
        val hours = maxOf(0, seconds) / 3600
        if (hours < 1) return "less than an hour ago"
        if (hours < 48) return if (hours == 1L) "1 hour ago" else "$hours hours ago"
        return "${hours / 24} days ago"
    }

    /** "3 days", "6 hours", "1 hour". */
    fun span(seconds: Long): String {
        val hours = maxOf(1L, Math.round(seconds / 3600.0))
        if (hours >= 24 && hours % 24 == 0L) {
            val days = hours / 24
            return if (days == 1L) "1 day" else "$days days"
        }
        return if (hours == 1L) "1 hour" else "$hours hours"
    }

    /** Built from the gate's own numbers, so the words and the behavior cannot drift. */
    val returnRefreshRule: String
        get() = "while its data is more than ${span(ForegroundRefreshGate.STALE_AFTER_SECONDS)} old " +
            "(at most once every ${span(ForegroundRefreshGate.MINIMUM_INTERVAL_SECONDS)})"

    data class FreshnessWarning(val title: String, val detail: String) {
        /** Opens with "Warning" so a listener who moves on after the first word still hears it. */
        val spoken: String get() = "Warning. $title. $detail"
    }

    fun freshnessWarning(generatedAt: Instant, freshness: DataFreshness, text: DateText): FreshnessWarning? = when (freshness) {
        is DataFreshness.Current -> null
        is DataFreshness.Stale -> FreshnessWarning(
            title = "This data is out of date",
            detail = "It was last updated ${age(freshness.ageSeconds)}, on ${text.mediumDateTime(generatedAt)}. " +
                "Next episodes and where-to-watch links may have changed since then. The app looks for new data each " +
                "time it opens, and when you return to it $returnRefreshRule. Pull down on Search to look now.",
        )
        DataFreshness.Unknown -> FreshnessWarning(
            title = "This data's age is unknown",
            detail = "It is dated ${text.mediumDateTime(generatedAt)}, which is later than this device's clock, so the " +
                "app can't tell how old it is. Treat it as possibly out of date, and check the date and time in Settings.",
        )
    }

    // Favorites backup

    fun importSummary(added: Int, alreadySaved: Int, notInSnapshot: Int, unreadable: Int): String {
        fun count(n: Int, one: String, many: String) = "$n ${if (n == 1) one else many}"
        if (added + alreadySaved + notInSnapshot + unreadable == 0) return "The file lists no favorites. Nothing was added."
        val sentences = mutableListOf(
            if (added == 0) "No new favorites were added." else "Added ${count(added, "favorite", "favorites")}.",
        )
        if (alreadySaved > 0) sentences += "${count(alreadySaved, "was", "were")} already saved."
        if (notInSnapshot > 0) {
            sentences += "${count(notInSnapshot, "is", "are")} not in this snapshot and ${if (notInSnapshot == 1) "was" else "were"} skipped."
        }
        if (unreadable > 0) {
            sentences += "${count(unreadable, "entry", "entries")} could not be read and ${if (unreadable == 1) "was" else "were"} skipped."
        }
        return sentences.joinToString(" ")
    }
}
