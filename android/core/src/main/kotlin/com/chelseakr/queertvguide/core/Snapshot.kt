package com.chelseakr.queertvguide.core

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.time.Instant
import java.time.LocalDate

// The snapshot contract as `schema/snapshot.v1.json` defines it: the Kotlin
// mirror of GuideCore's `Snapshot.swift`, field for field. Reconcile both
// whenever the schema changes.
//
// The two absence rules from `schema/README.md` hold here exactly as in
// GuideCore:
//
// 1. LezWatch records deaths, not survival. `Death.died` is `true` or
//    `null`; `false` is a contract violation and the whole file is refused.
// 2. A show's schedule has two kinds of "no next episode": TVmaze matched the
//    show and lists nothing upcoming (`scheduleKnown == true`), or TVmaze was
//    never matched (`scheduleKnown == false`). They never read the same.
//
// A nullable field defaults to null when its key is absent, as Swift's
// `decodeIfPresent` does; a non-null field with no default must be present,
// or the file is refused (`SnapshotDecoder`).

@Serializable
data class Term(val slug: String, val name: String)

@Serializable
data class TermCount(
    @SerialName("lwtv_id") val lwtvId: Int,
    val slug: String,
    val name: String,
    val count: Int? = null,
)

@Serializable
data class Taxonomies(
    val tropes: List<TermCount>,
    val cliches: List<TermCount>,
    val genders: List<TermCount>,
    val sexualities: List<TermCount>,
    val romantic: List<TermCount>,
    val stations: List<TermCount>,
    val genres: List<TermCount>,
    val countries: List<TermCount>,
    val formats: List<TermCount>,
    val triggers: List<TermCount>,
    val intersections: List<TermCount>,
    val stars: List<TermCount>,
)

@Serializable
data class SnapshotLicense(val spdx: String, val name: String, val url: String)

@Serializable
data class License(
    val snapshot: SnapshotLicense,
    /** Plain-language notice the app shows verbatim on the About screen. */
    val notice: String,
)

@Serializable
data class AttributionItem(
    val source: String,
    val name: String,
    val url: String,
    val text: String,
    // Published snapshot field names: spelling kept so every v1 file still decodes.
    @SerialName("licence_name") val licenseName: String,
    @SerialName("licence_url") val licenseUrl: String,
    @SerialName("terms_url") val termsUrl: String,
    /** YYYY-MM-DD, displayed as-is. */
    @SerialName("terms_read_on") val termsReadOn: String,
)

@Serializable
data class FetchedVsAvailable(val available: Int? = null, val fetched: Int)

@Serializable
data class PresentVsAbsent(val present: Int, val absent: Int)

@Serializable
data class Coverage(
    val lezwatch: LezWatchCoverage,
    val tvmaze: TvmazeCoverage,
    /** Keyed by dotted field path, e.g. "shows.watch_links". */
    val fields: Map<String, PresentVsAbsent>,
) {
    @Serializable
    data class LezWatchCoverage(
        val shows: FetchedVsAvailable,
        val characters: FetchedVsAvailable,
        val actors: FetchedVsAvailable,
    )

    @Serializable
    data class TvmazeCoverage(
        @SerialName("shows_total") val showsTotal: Int,
        @SerialName("with_join_key") val withJoinKey: Int,
        val joined: Int,
        @SerialName("join_rate") val joinRate: Double,
        val misses: Misses,
    ) {
        @Serializable
        data class Misses(
            @SerialName("no_key") val noKey: Int,
            @SerialName("ignored_by_source") val ignoredBySource: Int,
            @SerialName("not_found") val notFound: Int,
            val other: Int,
        )
    }
}

@Serializable
enum class OnAir {
    @SerialName("yes") YES,
    @SerialName("no") NO,
    @SerialName("unknown") UNKNOWN,
}

@Serializable
data class Years(
    val start: Int? = null,
    /** Null whether the show is ongoing or the field is blank; read [onAir]. */
    val end: Int? = null,
    @SerialName("on_air") val onAir: OnAir,
)

/** LezWatch's known worth-it verdicts, for filtering. */
enum class WorthIt(val raw: String) {
    YES("Yes"),
    MEH("Meh"),
    NO("No"),
    TBD("TBD"),
    ;

    companion object {
        fun from(raw: String?): WorthIt? = entries.firstOrNull { it.raw == raw }
    }
}

@Serializable
data class Ratings(
    /** Open text ("Yes", "Meh", "No", "TBD" observed); null when not rated. */
    @SerialName("worth_it") val worthIt: String? = null,
    @SerialName("worth_it_details") val worthItDetails: String? = null,
    val quality: Int? = null,
    val realness: Int? = null,
    val screentime: Int? = null,
    val score: Double? = null,
    @SerialName("show_we_love") val showWeLove: Boolean,
) {
    /** The known subset of [worthIt]; null covers "not rated" and an unrecognized value. */
    val worthItKnown: WorthIt? get() = WorthIt.from(worthIt)
}

@Serializable
data class Counts(
    val characters: Int,
    val deaths: Int,
    @SerialName("characters_source_reported") val charactersSourceReported: Int? = null,
    @SerialName("deaths_source_reported") val deathsSourceReported: Int? = null,
)

@Serializable
data class ExternalIds(val imdb: String? = null, val tmdb: String? = null, val tvmaze: Int? = null)

@Serializable
data class WatchLink(
    val url: String,
    /** Registrable host, e.g. "netflix.com": the label the app shows. Never a guessed service name. */
    val host: String,
)

@Serializable
data class ShowNotes(
    /** May contain spoilers; the app hides it behind a tap. */
    val plot: String? = null,
    @SerialName("queer_episodes") val queerEpisodes: String? = null,
)

@Serializable
data class Channel(val name: String, @SerialName("country_code") val countryCode: String? = null)

@Serializable
data class Episode(
    @SerialName("tvmaze_id") val tvmazeId: Int,
    val season: Int? = null,
    /** Null for specials. */
    val number: Int? = null,
    val name: String? = null,
    /** YYYY-MM-DD as TVmaze records it. */
    val airdate: String? = null,
    val airtime: String? = null,
    val airstamp: String? = null,
    val runtime: Int? = null,
    val url: String,
) {
    /** [airdate] as a calendar day; null if it does not parse. */
    val airdateDay: LocalDate? get() = Dates.parseDay(airdate)

    /**
     * The real broadcast instant, only when the episode has a non-blank
     * [airtime] and a parseable [airstamp]. With no air time, the stamp is a
     * placeholder (usually noon UTC), not a broadcast time, so this is null:
     * nothing may show or schedule a made-up time. The one reader of
     * [airstamp] (`AirstampReaderTest` holds the source tree to that).
     */
    val airInstant: Instant?
        get() {
            val time = airtime ?: return null
            if (time.isBlank()) return null
            return Dates.parseInstant(airstamp ?: return null)
        }
}

@Serializable
data class ScheduleJoin(val method: Method, val matched: Boolean) {
    @Serializable
    enum class Method {
        @SerialName("lwtv_tvmaze_id") LWTV_TVMAZE_ID,
        @SerialName("lwtv_tvmaze_id_manual") LWTV_TVMAZE_ID_MANUAL,
        @SerialName("imdb_lookup") IMDB_LOOKUP,
        @SerialName("none") NONE,
    }
}

@Serializable
data class Schedule(
    /** True iff TVmaze returned a show record. False: "schedule unknown", never "no upcoming episode". */
    @SerialName("schedule_known") val scheduleKnown: Boolean,
    val join: ScheduleJoin,
    @SerialName("tvmaze_id") val tvmazeId: Int? = null,
    @SerialName("tvmaze_url") val tvmazeUrl: String? = null,
    val status: String? = null,
    val premiered: String? = null,
    val ended: String? = null,
    val network: Channel? = null,
    @SerialName("web_channel") val webChannel: Channel? = null,
    /** Null with [scheduleKnown] true: nothing upcoming. Null with it false: unknown. */
    @SerialName("next_episode") val nextEpisode: Episode? = null,
    @SerialName("previous_episode") val previousEpisode: Episode? = null,
)

@Serializable
data class Show(
    val id: String,
    @SerialName("lwtv_id") val lwtvId: Int,
    val slug: String,
    val title: String,
    @SerialName("alternate_names") val alternateNames: List<String>,
    @SerialName("source_url") val sourceUrl: String,
    val summary: String? = null,
    val years: Years,
    val seasons: Int? = null,
    val format: Term? = null,
    val networks: List<Term>,
    val countries: List<Term>,
    val genres: List<Term>,
    val tropes: List<Term>,
    val triggers: List<Term>,
    val intersections: List<Term>,
    val stars: List<Term>,
    val ratings: Ratings,
    val counts: Counts,
    @SerialName("external_ids") val externalIds: ExternalIds,
    @SerialName("watch_links") val watchLinks: List<WatchLink>,
    @SerialName("similar_show_ids") val similarShowIds: List<String>,
    val notes: ShowNotes,
    val schedule: Schedule,
    @SerialName("source_modified_at") val sourceModifiedAt: String,
)

@Serializable
data class DeathDate(val date: String? = null, val year: Int? = null, val raw: String)

/**
 * LezWatch records deaths, not survival: [died] is true or null, never false.
 * `deathKnown == false` reads as "no recorded death", never "survives".
 */
@Serializable
data class Death(
    val died: Boolean? = null,
    @SerialName("death_known") val deathKnown: Boolean,
    /** One entry per recorded death (a character can die more than once). */
    val dates: List<DeathDate>,
    val years: List<Int>,
) {
    val isRecorded: Boolean get() = deathKnown && died == true
}

@Serializable
data class CharacterActor(
    @SerialName("lwtv_id") val lwtvId: Int,
    val slug: String? = null,
    /** Null when the actor id did not resolve in the actor export. */
    val name: String? = null,
)

@Serializable
data class CharacterShowLink(
    @SerialName("show_id") val showId: String,
    /** LezWatch chartype: "regular", "recurring", "guest". */
    val role: String? = null,
    val years: List<String>,
)

@Serializable
data class Character(
    val id: String,
    @SerialName("lwtv_id") val lwtvId: Int,
    val slug: String,
    val name: String,
    @SerialName("source_url") val sourceUrl: String,
    val gender: Term? = null,
    val sexuality: Term? = null,
    val romantic: Term? = null,
    /** Includes "Dead" for dead characters; `death.died` is the authority. */
    val cliches: List<Term>,
    val actors: List<CharacterActor>,
    val shows: List<CharacterShowLink>,
    val death: Death,
    @SerialName("source_modified_at") val sourceModifiedAt: String,
)

/** The document as it is on the wire, before the decoder's own checks. */
@Serializable
internal data class SnapshotWire(
    @SerialName("schema_version") val schemaVersion: String,
    @SerialName("generated_at") val generatedAt: String,
    @SerialName("content_digest") val contentDigest: String,
    // Published snapshot field name: spelling kept so every v1 file still decodes.
    @SerialName("licence") val license: License,
    val attribution: List<AttributionItem>,
    val coverage: Coverage,
    val taxonomies: Taxonomies,
    val shows: List<Show>,
    val characters: List<Character>,
)

/**
 * A decoded, checked snapshot with lookup tables built once (shows and
 * characters can each number in the thousands, so lookups are never linear).
 * Built in code it keeps the first of any repeated id; a file that repeats an
 * id never gets here (`SnapshotDecoder` refuses it whole).
 */
class Snapshot(
    val schemaVersion: String,
    val generatedAt: Instant,
    val contentDigest: String,
    val license: License,
    val attribution: List<AttributionItem>,
    val coverage: Coverage,
    val taxonomies: Taxonomies,
    shows: List<Show>,
    characters: List<Character>,
) {
    val shows: List<Show> = shows.distinctBy { it.id }
    val characters: List<Character> = characters.distinctBy { it.id }

    private val showsById: Map<String, Show> = this.shows.associateBy { it.id }
    private val charactersById: Map<String, Character> = this.characters.associateBy { it.id }
    private val characterIdsByShow: Map<String, List<String>> = buildMap<String, MutableList<String>> {
        for (character in this@Snapshot.characters) {
            // A character listed twice for one show (two stints) appears once.
            for (showId in character.shows.map { it.showId }.toSet()) {
                getOrPut(showId) { mutableListOf() }.add(character.id)
            }
        }
    }

    fun show(id: String): Show? = showsById[id]
    fun character(id: String): Character? = charactersById[id]

    /** Characters listed for a show, in snapshot order. */
    fun charactersInShow(id: String): List<Character> =
        characterIdsByShow[id].orEmpty().mapNotNull { charactersById[it] }

    fun showsForCharacter(id: String): List<Show> =
        character(id)?.shows?.mapNotNull { show(it.showId) }.orEmpty()

    fun similarShows(to: Show): List<Show> = to.similarShowIds.mapNotNull { show(it) }

    fun attribution(source: String): AttributionItem? = attribution.firstOrNull { it.source == source }

    companion object {
        const val SUPPORTED_SCHEMA_VERSION = "1"
    }
}
