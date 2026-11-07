package com.chelseakr.queertvguide.core

import java.time.format.DateTimeFormatter
import java.util.Locale

/**
 * "Has anyone died so far?" (DECISIONS 0043, 0044): the recorded deaths up to
 * where the viewer is in a show, from the placements the pipeline matched by
 * air date (DECISIONS 0041). Pure: the same show, cast and position always
 * give the same words. The Kotlin twin of GuideCore's `SoFar.swift`, word for
 * word; `SoFarTest` mirrors `SoFarTests`.
 *
 * The rules, from growth/qf-progress-and-stats-2026-11-06.md:
 * - Only deaths at or before the viewer's episode are in `soFar`. Deaths after
 *   it are in `later`, which the app keeps behind a second reveal.
 * - Each precision says only what it knows: one episode, "episode 7 or 8"
 *   (never one of the two), a special by its air date, a season only, or "we
 *   can't place it", said plainly. A death that might be on either side of the
 *   viewer is never counted as either: it is in `uncertain`, without a name.
 * - Never "0" or "none" for a death that cannot be placed.
 * - A recorded death means the character died at some point. LezWatch.TV
 *   records no date for a return, so nothing here says "still dead".
 * - `Show.episodeCounts` exists only for shows with a recorded death, so it is
 *   read here, behind the reveal, and never to shape the picker
 *   ([seasonRange], [EPISODE_RANGE]).
 */
object SoFar {
    /** Where the viewer is: they have watched up to and including this episode. */
    data class Position(val season: Int, val episode: Int) : Comparable<Position> {
        /** "season 3, episode 4" */
        val spoken: String get() = "season $season, episode $episode"

        override fun compareTo(other: Position): Int = compareValuesBy(this, other, { it.season }, { it.episode })

        companion object {
            val START = Position(1, 1)
        }
    }

    /** One recorded death date in one show: who, the year LezWatch.TV records, and where it falls. */
    data class Event(val name: String, val year: Int?, val placement: DeathPlacement)

    data class Answer(
        /** The so-far reveal: a verdict for the deaths up to the viewer. */
        val headline: String,
        /** One named line per death at or before the viewer's episode. */
        val soFar: List<String>,
        /** Deaths we cannot put on either side of the viewer, unnamed. */
        val uncertain: List<String>,
        /** Anything else the reader should know (a position past the list). */
        val notes: List<String>,
        /** The second reveal's verdict and its named lines. */
        val laterHeadline: String,
        val later: List<String>,
        val footer: String,
    ) {
        /** What TalkBack reads for the so-far reveal, as one stop. */
        val spoken: String get() = (listOf(headline) + soFar + uncertain + notes).joinToString(" ")

        /** What TalkBack reads for the later reveal, as one stop. */
        val laterSpoken: String get() = (listOf(laterHeadline) + later).joinToString(" ")
    }

    const val FOOTER = "Deaths as recorded by LezWatch.TV; episodes matched by air date using TVmaze. LezWatch.TV may not list every character. A recorded death means a character died at some point, not that they stay dead."

    /** The snapshot places deaths in episodes at all. Files built before DECISIONS 0041 do not, and the app does not offer the question for them. */
    fun isAvailable(snapshot: Snapshot): Boolean = snapshot.coverage.placements != null

    /**
     * Seasons the picker offers: LezWatch.TV's season count, which the show
     * screen already shows, plus one for a show still on air (LezWatch.TV can
     * lag a new season). With no count, 1 to 99. Never the episode list's
     * count: that list exists only for shows with a death.
     */
    fun seasonRange(show: Show): IntRange {
        val seasons = show.seasons
        if (seasons == null || seasons <= 0) return 1..99
        return 1..(if (show.years.onAir == OnAir.YES) seasons + 1 else seasons)
    }

    /** Episodes the picker offers, the same for every show and season (see [seasonRange] for why). */
    val EPISODE_RANGE: IntRange = 1..999

    /** A stored position brought inside the picker's ranges. */
    fun clamped(position: Position, show: Show): Position {
        val seasons = seasonRange(show)
        return Position(position.season.coerceIn(seasons), position.episode.coerceIn(EPISODE_RANGE))
    }

    /**
     * Every recorded death date that counts for [show] (DECISIONS 0030, as the
     * pipeline placed it), one event per date, so a character who died twice
     * has two. A crossover date placed in another show is left out. A date
     * without placements (not computed for it) is unplaced when the
     * character's years in the show include its year, as under 0030.
     */
    fun events(cast: List<Character>, show: Show): List<Event> {
        val out = mutableListOf<Event>()
        for (character in cast) {
            for (date in character.death.dates) {
                val placements = date.placements
                if (placements != null) {
                    for (placement in placements) {
                        if (placement.showId == show.id && placement.precision != DeathPlacement.Precision.OTHER_SHOW) {
                            out += Event(character.name, date.year, placement)
                        }
                    }
                } else {
                    val year = date.year ?: continue
                    if (character.shows.any { it.showId == show.id && it.years.contains(year.toString()) }) {
                        val unplaced = DeathPlacement.of(show.id, DeathPlacement.Precision.UNPLACED, "not_computed")
                        out += Event(character.name, year, unplaced)
                    }
                }
            }
        }
        return out
    }

    fun answer(show: Show, cast: List<Character>, position: Position): Answer =
        answer(events(cast, show), castIsEmpty = cast.isEmpty(), episodeCounts = show.episodeCounts, position = position)

    private sealed interface Side {
        data class SoFarLine(val line: String) : Side
        data class LaterLine(val line: String) : Side

        /** Unnamed line for the so-far reveal, grouped by [key]; named line for the later reveal. */
        class Uncertain(val key: String, val line: (Int) -> String, val named: String) : Side
    }

    /** The core rule, on events alone, so every tier is testable without a snapshot. */
    fun answer(events: List<Event>, castIsEmpty: Boolean = false, episodeCounts: List<SeasonEpisodeCount>?, position: Position): Answer {
        val through = position.spoken
        val counts = LinkedHashMap<Int, Int>()
        for (c in episodeCounts.orEmpty()) counts.putIfAbsent(c.season, c.episodes)

        val soFar = mutableListOf<String>()
        val later = mutableListOf<String>()
        val maybeNamed = mutableListOf<String>()
        val uncertainOrder = mutableListOf<String>()
        val uncertainCount = HashMap<String, Int>()
        val uncertainLine = HashMap<String, (Int) -> String>()

        for (event in events) {
            when (val side = side(event, position, counts)) {
                is Side.SoFarLine -> soFar += side.line
                is Side.LaterLine -> later += side.line
                is Side.Uncertain -> {
                    if (side.key !in uncertainCount) {
                        uncertainOrder += side.key
                        uncertainLine[side.key] = side.line
                    }
                    uncertainCount[side.key] = (uncertainCount[side.key] ?: 0) + 1
                    maybeNamed += side.named
                }
            }
        }
        val uncertain = uncertainOrder.map { uncertainLine.getValue(it)(uncertainCount.getValue(it)) }

        val notes = mutableListOf<String>()
        if (!episodeCounts.isNullOrEmpty()) {
            val inSeason = counts[position.season]
            val last = episodeCounts.maxOf { it.season }
            if (inSeason != null && position.episode > inSeason) {
                notes += "TVmaze lists $inSeason ${if (inSeason == 1) "episode" else "episodes"} in season ${position.season}, so this counts all of it."
            } else if (inSeason == null && position.season > last) {
                notes += "TVmaze lists episodes up to season $last, so this counts every listed episode."
            }
        }

        val headline = when {
            castIsEmpty -> "Not recorded. LezWatch.TV lists no characters for this show, so there is nothing to check."
            soFar.isNotEmpty() -> "Yes. ${deaths(soFar.size)} through $through."
            uncertain.isEmpty() -> "Not recorded through $through. LezWatch.TV records no death of a listed character up to here."
            else -> "Can't say for sure through $through. A recorded death can't be placed before or after where you are."
        }

        val laterHeadline = when {
            later.isNotEmpty() -> "After $through: ${deaths(later.size)} placed later."
            maybeNamed.isEmpty() -> "Not recorded after $through. LezWatch.TV records no later death of a listed character."
            else -> "Not recorded as placed after $through."
        }
        val laterLines = if (maybeNamed.isEmpty()) later.toList() else later + listOf("May be before or after where you are:") + maybeNamed

        return Answer(headline, soFar, uncertain, notes, laterHeadline, laterLines, FOOTER)
    }

    private fun deaths(n: Int): String = if (n == 1) "1 recorded death" else "$n recorded deaths"

    /** Which side of the viewer a death is on, with the words for it. */
    private fun side(event: Event, position: Position, counts: Map<Int, Int>): Side {
        val p = event.placement
        val name = event.name

        // The viewer has watched every listed episode of `season`.
        fun finished(season: Int): Boolean =
            season < position.season || (season == position.season && counts[season]?.let { position.episode >= it } == true)

        return when (p.precision) {
            DeathPlacement.Precision.EPISODE -> {
                val season = p.season
                val number = p.episodes?.firstOrNull()
                if (season == null || number == null) return unplaced(event)
                val dayOff = if (p.reason == "one_day_off") " (matched to an episode a day from the recorded date)" else ""
                val line = "$name: season $season, episode $number$dayOff."
                if (Position(season, number) <= position) Side.SoFarLine(line) else Side.LaterLine(line)
            }

            DeathPlacement.Precision.EPISODE_PAIR -> {
                val season = p.season
                val first = p.episodes?.minOrNull()
                val second = p.episodes?.maxOrNull()
                if (season == null || first == null || second == null || first == second) return unplaced(event)
                val line = "$name: season $season, episode $first or $second (both aired the same day)."
                when {
                    Position(season, second) <= position -> Side.SoFarLine(line)
                    Position(season, first) > position -> Side.LaterLine(line)
                    // The viewer is on the first of the two: never pick one.
                    else -> Side.Uncertain(
                        key = "pair:$season:$first",
                        line = { n ->
                            if (n == 1) {
                                "A recorded death in this episode or the next (episodes $first and $second aired the same day)."
                            } else {
                                "$n recorded deaths in this episode or the next (episodes $first and $second aired the same day)."
                            }
                        },
                        named = line,
                    )
                }
            }

            DeathPlacement.Precision.SPECIAL -> {
                val aired = p.airdate?.let(::spokenDate) ?: "on a date we don't have"
                val line = "$name: a special that aired $aired."
                val season = p.season
                    ?: return Side.Uncertain(
                        key = "special:${p.airdate ?: ""}",
                        line = { n -> "${if (n == 1) "A recorded death" else "$n recorded deaths"} in a special that aired $aired, which we can't place before or after where you are." },
                        named = line,
                    )
                when {
                    finished(season) -> Side.SoFarLine(line)
                    season > position.season -> Side.LaterLine(line)
                    else -> Side.Uncertain(
                        key = "special:$season:${p.airdate ?: ""}",
                        line = { n -> "${if (n == 1) "A recorded death" else "$n recorded deaths"} in a special that aired $aired, during season $season. It may be before or after episode ${position.episode}." },
                        named = line,
                    )
                }
            }

            DeathPlacement.Precision.SEASON -> {
                val season = p.season ?: return unplaced(event)
                val line = "$name: season $season; we can't place the episode."
                val why = if (p.reason == "season_drop") " (the season was released all at once)" else ""
                when {
                    finished(season) -> Side.SoFarLine(line)
                    season > position.season -> Side.LaterLine(line)
                    else -> Side.Uncertain(
                        key = "season:$season",
                        line = { n ->
                            if (n == 1) {
                                "Season $season has a recorded death we can't place in an episode$why. It may be before or after episode ${position.episode}."
                            } else {
                                "Season $season has $n recorded deaths we can't place in an episode$why. They may be before or after episode ${position.episode}."
                            }
                        },
                        named = line,
                    )
                }
            }

            DeathPlacement.Precision.UNPLACED, DeathPlacement.Precision.OTHER_SHOW, DeathPlacement.Precision.UNRECOGNIZED -> unplaced(event)
        }
    }

    private fun unplaced(event: Event): Side {
        val named = "${event.name}: we can't place this death in an episode."
        return when (event.placement.reason) {
            "no_tvmaze_join", "episodes_unavailable", "no_dated_episodes" -> Side.Uncertain(
                key = "no-list",
                line = { "We don't have this show's episode list, so we can only answer for the whole show, in the reveal above." },
                named = named,
            )
            else -> {
                val year = event.year?.toString()
                Side.Uncertain(
                    key = "year:${year ?: ""}",
                    line = { n ->
                        val what = if (n == 1) "a death" else "$n deaths"
                        val whenText = year?.let { " in $it" } ?: ""
                        "LezWatch.TV records $what$whenText that we can't match to an episode, so we can't say whether ${if (n == 1) "it's" else "they're"} before or after where you are."
                    },
                    named = named,
                )
            }
        }
    }

    private val spokenDateFormatter: DateTimeFormatter = DateTimeFormatter.ofPattern("MMMM d, yyyy", Locale.US)

    /** "November 12, 2017" from "2017-11-12"; the raw string if it does not parse. */
    fun spokenDate(iso: String): String = Dates.parseDay(iso)?.format(spokenDateFormatter) ?: iso
}

/**
 * Where the viewer is in each show, kept on this device only (data posture,
 * DECISIONS 0002): never sent, never synced, not in the favorites backup
 * file. It sits in the app's private preferences beside favorites, so, like
 * them, it stays out of Google's cloud backup and moves only with a direct
 * device-to-device transfer (data_extraction_rules.xml).
 */
class WatchPositionStore(private val storage: KeyValueStore) {
    fun position(showId: String): SoFar.Position? {
        val parts = storage.getString(KEY_PREFIX + showId)?.split(",") ?: return null
        if (parts.size != 2) return null
        val season = parts[0].toIntOrNull() ?: return null
        val episode = parts[1].toIntOrNull() ?: return null
        if (season < 1 || episode < 1) return null
        return SoFar.Position(season, episode)
    }

    fun set(position: SoFar.Position, showId: String) {
        storage.putString(KEY_PREFIX + showId, "${position.season},${position.episode}")
    }

    fun clear(showId: String) {
        storage.putString(KEY_PREFIX + showId, null)
    }

    companion object {
        const val KEY_PREFIX = "soFar.position."
    }
}
