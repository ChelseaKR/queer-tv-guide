package com.chelseakr.queertvguide.core

import com.chelseakr.queertvguide.core.DeathPlacement.Precision
import com.chelseakr.queertvguide.core.JsonEdit.editArray
import com.chelseakr.queertvguide.core.JsonEdit.with
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * "Has anyone died so far?" (DECISIONS 0043, 0044): one test per precision
 * tier and per edge case, the same 23 as GuideCore's `SoFarTests`, asserting
 * the same words. Names are invented.
 */
class SoFarTest {
    private val show = "lwtv:show:102"
    private val placementsFixture = File(Repo.root, "ios/GuideCore/Tests/Fixtures/snapshot.placements.fixture.json")

    private fun at(season: Int, episode: Int) = SoFar.Position(season, episode)

    private fun event(
        name: String,
        precision: Precision,
        reason: String = "exact_date",
        season: Int? = null,
        episodes: List<Int>? = null,
        airdate: String? = null,
        year: Int? = 2017,
        showId: String? = "lwtv:show:102",
    ) = SoFar.Event(name, year, DeathPlacement.of(showId, precision, reason, season, episodes, airdate))

    /** A precision this app does not know, as a newer pipeline might write it. */
    private fun unrecognized(name: String, raw: String, reason: String, season: Int?, episodes: List<Int>?) =
        SoFar.Event(name, 2017, DeathPlacement(show, raw, reason, season, episodes, null))

    private val tenTenSix = listOf(SeasonEpisodeCount(1, 10), SeasonEpisodeCount(2, 10), SeasonEpisodeCount(3, 6))

    private fun answer(events: List<SoFar.Event>, position: SoFar.Position, counts: List<SeasonEpisodeCount>? = null) =
        SoFar.answer(events, episodeCounts = counts ?: tenTenSix, position = position)

    /** No answer may open with a bare "No" or state a count of zero. */
    private fun assertNeverZeroOrNo(a: SoFar.Answer) {
        for (text in listOf(a.headline, a.laterHeadline) + a.soFar + a.uncertain + a.later) {
            assertFalse(text, Regex("""^\s*No\b""").containsMatchIn(text))
            assertFalse(text, text.contains(" 0 "))
            assertFalse(text, text.contains("none", ignoreCase = true))
            assertFalse(text, text.contains("still dead", ignoreCase = true))
        }
    }

    // Episode tier

    @Test
    fun anEpisodeDeathBeforeTheViewerIsSoFar() {
        val a = answer(listOf(event("Odile", Precision.EPISODE, season = 2, episodes = listOf(7))), at(3, 4))
        assertEquals("Yes. 1 recorded death through season 3, episode 4.", a.headline)
        assertEquals(listOf("Odile: season 2, episode 7."), a.soFar)
        assertEquals(emptyList<String>(), a.uncertain)
        assertEquals(emptyList<String>(), a.later)
        assertTrue(a.laterHeadline.startsWith("Not recorded after season 3, episode 4."))
        assertNeverZeroOrNo(a)
    }

    @Test
    fun theViewersOwnEpisodeCountsAsSoFar() {
        val a = answer(listOf(event("Odile", Precision.EPISODE, season = 2, episodes = listOf(7))), at(2, 7))
        assertEquals(1, a.soFar.size)
    }

    @Test
    fun anEpisodeDeathAfterTheViewerIsOnlyInLater() {
        val a = answer(listOf(event("Odile", Precision.EPISODE, season = 2, episodes = listOf(7))), at(2, 6))
        assertEquals("Not recorded through season 2, episode 6. LezWatch.TV records no death of a listed character up to here.", a.headline)
        assertEquals(emptyList<String>(), a.soFar)
        assertFalse("a later death must not be in the so-far answer: ${a.spoken}", a.spoken.contains("Odile"))
        assertEquals("After season 2, episode 6: 1 recorded death placed later.", a.laterHeadline)
        assertEquals(listOf("Odile: season 2, episode 7."), a.later)
        assertNeverZeroOrNo(a)
    }

    @Test
    fun oneDayOffSaysItWasMatchedByAirDate() {
        val a = answer(listOf(event("Odile", Precision.EPISODE, reason = "one_day_off", season = 1, episodes = listOf(3))), at(1, 3))
        assertEquals(listOf("Odile: season 1, episode 3 (matched to an episode a day from the recorded date)."), a.soFar)
    }

    // Same-day double episodes

    @Test
    fun aPairIsNeverResolvedToOneEpisode() {
        val pair = event("Odile", Precision.EPISODE_PAIR, reason = "double_bill", season = 2, episodes = listOf(7, 8))
        val after = answer(listOf(pair), at(2, 8))
        assertEquals(listOf("Odile: season 2, episode 7 or 8 (both aired the same day)."), after.soFar)

        val before = answer(listOf(pair), at(2, 6))
        assertEquals(emptyList<String>(), before.soFar)
        assertEquals(emptyList<String>(), before.uncertain)
        assertEquals(listOf("Odile: season 2, episode 7 or 8 (both aired the same day)."), before.later)
    }

    @Test
    fun onTheFirstOfAPairItSaysThisEpisodeOrTheNext() {
        val a = answer(listOf(event("Odile", Precision.EPISODE_PAIR, reason = "double_bill", season = 2, episodes = listOf(7, 8))), at(2, 7))
        assertEquals(emptyList<String>(), a.soFar)
        assertEquals(listOf("A recorded death in this episode or the next (episodes 7 and 8 aired the same day)."), a.uncertain)
        assertTrue(a.headline.startsWith("Can't say for sure through season 2, episode 7."))
        assertFalse("an uncertain death is not named in the so-far answer", a.spoken.contains("Odile"))
        assertEquals(listOf("May be before or after where you are:", "Odile: season 2, episode 7 or 8 (both aired the same day)."), a.later)
        assertNeverZeroOrNo(a)
    }

    // Whole-season drops and season-only tiers

    @Test
    fun aDropInsideTheViewersSeasonMayBeEitherSide() {
        val drop = event("Odile", Precision.SEASON, reason = "season_drop", season = 3)
        val a = answer(listOf(drop), at(3, 4))
        assertEquals(listOf("Season 3 has a recorded death we can't place in an episode (the season was released all at once). It may be before or after episode 4."), a.uncertain)
        assertEquals(emptyList<String>(), a.soFar)
        assertFalse(a.spoken.contains("Odile"))
        assertFalse("a drop is never episode 1", a.spoken.contains("episode 1."))
        assertNeverZeroOrNo(a)
    }

    @Test
    fun aDropInAnEarlierSeasonIsSoFarAndALaterOneIsLater() {
        val drop = event("Odile", Precision.SEASON, reason = "season_drop", season = 2)
        assertEquals(listOf("Odile: season 2; we can't place the episode."), answer(listOf(drop), at(3, 1)).soFar)
        val later = answer(listOf(drop), at(1, 10))
        assertEquals(emptyList<String>(), later.soFar)
        assertEquals(emptyList<String>(), later.uncertain)
        assertEquals(listOf("Odile: season 2; we can't place the episode."), later.later)
    }

    @Test
    fun aFinishedSeasonCountsItsSeasonOnlyDeaths() {
        // Season 3 has 6 episodes; at episode 6 the viewer has seen all of it.
        val drop = event("Odile", Precision.SEASON, reason = "season_drop", season = 3)
        assertEquals(listOf("Odile: season 3; we can't place the episode."), answer(listOf(drop), at(3, 6)).soFar)
        assertEquals(emptyList<String>(), answer(listOf(drop), at(3, 5)).soFar)
        // Without an episode count, the season is never taken as finished.
        val unknown = SoFar.answer(listOf(drop), episodeCounts = null, position = at(3, 6))
        assertEquals(emptyList<String>(), unknown.soFar)
        assertEquals(1, unknown.uncertain.size)
    }

    @Test
    fun twoDeathsInOneSeasonAreOneLineWithACount() {
        val a = answer(listOf(event("A", Precision.SEASON, reason = "within_a_week", season = 3), event("B", Precision.SEASON, reason = "within_a_week", season = 3)), at(3, 2))
        assertEquals(listOf("Season 3 has 2 recorded deaths we can't place in an episode. They may be before or after episode 2."), a.uncertain)
        assertEquals(listOf("May be before or after where you are:", "A: season 3; we can't place the episode.", "B: season 3; we can't place the episode."), a.later)
    }

    // Specials

    @Test
    fun aSpecialIsNamedByItsAirDateNotANumber() {
        val special = event("Odile", Precision.SPECIAL, reason = "special_same_day", season = 2, airdate = "2017-11-12")
        val a = answer(listOf(special), at(3, 1))
        assertEquals(listOf("Odile: a special that aired November 12, 2017."), a.soFar)
        val inside = answer(listOf(special), at(2, 4))
        assertEquals(listOf("A recorded death in a special that aired November 12, 2017, during season 2. It may be before or after episode 4."), inside.uncertain)
        val noSeason = answer(listOf(event("Odile", Precision.SPECIAL, reason = "special_same_day", airdate = "2017-11-12")), at(5, 1))
        assertEquals(emptyList<String>(), noSeason.soFar)
        assertEquals(1, noSeason.uncertain.size)
    }

    // Unplaced

    @Test
    fun anUnplacedDeathIsSaidPlainlyNeverZero() {
        val a = answer(listOf(event("Odile", Precision.UNPLACED, reason = "between_seasons", year = 2019)), at(2, 1))
        assertEquals(emptyList<String>(), a.soFar)
        assertEquals(listOf("LezWatch.TV records a death in 2019 that we can't match to an episode, so we can't say whether it's before or after where you are."), a.uncertain)
        assertTrue(a.headline.startsWith("Can't say for sure"))
        assertFalse("an unplaced death must not read as no death", a.headline.startsWith("Not recorded"))
        assertNeverZeroOrNo(a)
    }

    @Test
    fun aShowWithoutAnEpisodeListSaysItCanOnlyAnswerForTheWholeShow() {
        val a = SoFar.answer(
            listOf(event("Odile", Precision.UNPLACED, reason = "no_tvmaze_join"), event("Juno", Precision.UNPLACED, reason = "no_tvmaze_join")),
            episodeCounts = null,
            position = at(1, 1),
        )
        assertEquals(listOf("We don't have this show's episode list, so we can only answer for the whole show, in the reveal above."), a.uncertain)
        assertNeverZeroOrNo(a)
    }

    @Test
    fun anUnrecognizedPrecisionIsUnplaced() {
        val e = unrecognized("Odile", "scene", "new_rule", season = 2, episodes = listOf(7))
        assertEquals(Precision.UNRECOGNIZED, e.placement.precision)
        val a = answer(listOf(e), at(3, 1))
        assertEquals(emptyList<String>(), a.soFar)
        assertEquals(1, a.uncertain.size)
    }

    @Test
    fun anEpisodePlacementMissingItsNumberIsUnplacedNotEpisodeOne() {
        val a = answer(listOf(event("Odile", Precision.EPISODE, season = 2, episodes = null)), at(3, 1))
        assertEquals(emptyList<String>(), a.soFar)
        assertEquals(1, a.uncertain.size)
    }

    // Resurrections and crossovers (on a real decoded snapshot)

    private fun fixtureJson(): JsonObject = Json.parseToJsonElement(placementsFixture.readText()) as JsonObject

    private fun decoded(json: JsonObject = fixtureJson()): Snapshot = SnapshotDecoder.decode(Repo.bytes(json))

    private fun int(value: Int?): JsonElement = if (value == null) JsonNull else JsonPrimitive(value)

    private fun placement(showId: String, precision: String, reason: String, season: Int?, episodes: List<Int>?): JsonObject = JsonObject(
        mapOf(
            "show_id" to JsonPrimitive(showId),
            "precision" to JsonPrimitive(precision),
            "reason" to JsonPrimitive(reason),
            "season" to int(season),
            "episodes" to (episodes?.let { list -> JsonArray(list.map { JsonPrimitive(it) }) } ?: JsonNull),
            "airdate" to JsonNull,
        ),
    )

    private fun date(date: String, year: Int, raw: String, placements: List<JsonObject>?): JsonObject = JsonObject(
        buildMap {
            put("date", JsonPrimitive(date))
            put("year", JsonPrimitive(year))
            put("raw", JsonPrimitive(raw))
            if (placements != null) put("placements", JsonArray(placements))
        },
    )

    /** The placements fixture with Odile Brandt's (characters[2]) death dates replaced. */
    private fun withOdileDates(dates: List<JsonObject>, years: List<Int>? = null): Snapshot = decoded(
        fixtureJson().editArray("characters", 2) { character ->
            var death = (character["death"] as JsonObject).with("dates", JsonArray(dates))
            if (years != null) death = death.with("years", JsonArray(years.map { JsonPrimitive(it) }))
            character.with("death", death)
        },
    )

    @Test
    fun eachDeathOfACharacterWhoDiedTwiceIsPlacedOnItsOwn() {
        val snapshot = withOdileDates(
            listOf(
                date("2017-11-12", 2017, "20171112", listOf(placement(show, "episode", "exact_date", 2, listOf(7)))),
                date("2018-03-01", 2018, "20180301", listOf(placement(show, "episode", "exact_date", 3, listOf(2)))),
            ),
            years = listOf(2017, 2018),
        )
        val cartographers = snapshot.show(show)!!
        val a = SoFar.answer(cartographers, snapshot.charactersInShow(show), at(3, 1))
        // The first death counts so far even though the second is after the viewer.
        assertEquals("Yes. 1 recorded death through season 3, episode 1.", a.headline)
        assertEquals(listOf("Odile Brandt: season 2, episode 7."), a.soFar)
        assertEquals(listOf("Odile Brandt: season 3, episode 2."), a.later)
        assertFalse((a.spoken + a.laterSpoken).contains("still dead", ignoreCase = true))
        assertTrue(a.footer.contains("died at some point, not that they stay dead"))
    }

    @Test
    fun aCrossoverPlacedInAnotherShowIsNotCountedHere() {
        val snapshot = withOdileDates(
            listOf(
                date(
                    "2017-11-12", 2017, "20171112",
                    listOf(
                        placement("lwtv:show:101", "episode", "exact_date", 1, listOf(4)),
                        placement(show, "other_show", "crossover_matched_other_show", null, null),
                    ),
                ),
            ),
        )
        val cartographers = snapshot.show(show)!!
        assertEquals(emptyList<SoFar.Event>(), SoFar.events(snapshot.charactersInShow(show), cartographers))
        val a = SoFar.answer(cartographers, snapshot.charactersInShow(show), at(3, 6))
        assertTrue(a.headline, a.headline.startsWith("Not recorded through season 3, episode 6."))
        assertTrue(a.laterHeadline, a.laterHeadline.startsWith("Not recorded after"))
    }

    @Test
    fun theFixtureAnswersThroughTheDecodedSnapshot() {
        val snapshot = decoded()
        val cartographers = snapshot.show(show)!!
        val cast = snapshot.charactersInShow(show)
        assertEquals(listOf("Odile Brandt: season 2, episode 7."), SoFar.answer(cartographers, cast, at(2, 7)).soFar)
        assertEquals(listOf("Odile Brandt: season 2, episode 7."), SoFar.answer(cartographers, cast, at(1, 1)).later)
    }

    @Test
    fun aDateWithoutPlacementsInAPlacedFileIsUnplacedByTheYearRule() {
        val snapshot = withOdileDates(listOf(date("2017-11-12", 2017, "20171112", null)))
        val cartographers = snapshot.show(show)!!
        val a = SoFar.answer(cartographers, snapshot.charactersInShow(show), at(3, 6))
        assertEquals(listOf("LezWatch.TV records a death in 2017 that we can't match to an episode, so we can't say whether it's before or after where you are."), a.uncertain)
    }

    @Test
    fun aShowWithNoListedCharactersSaysSo() {
        val snapshot = decoded()
        val radio = snapshot.show("lwtv:show:104")!!
        val a = SoFar.answer(radio, snapshot.charactersInShow(radio.id), at(1, 1))
        assertTrue(a.headline, a.headline.startsWith("Not recorded. LezWatch.TV lists no characters"))
    }

    // Position past the list

    @Test
    fun aPositionPastTheSeasonSaysItCountsAllOfIt() {
        val a = answer(emptyList(), at(3, 9))
        assertEquals(listOf("TVmaze lists 6 episodes in season 3, so this counts all of it."), a.notes)
        val past = answer(emptyList(), at(5, 1))
        assertEquals(listOf("TVmaze lists episodes up to season 3, so this counts every listed episode."), past.notes)
    }

    // The picker never depends on the episode list

    @Test
    fun thePickerRangesComeFromLezWatchsSeasonCountOnly() {
        val snapshot = decoded()
        for (s in snapshot.shows) {
            val seasons = s.seasons
            val expected = if (seasons == null || seasons <= 0) 1..99 else 1..(if (s.years.onAir == OnAir.YES) seasons + 1 else seasons)
            assertEquals(s.title, expected, SoFar.seasonRange(s))
        }
        // Negative control: a show with an episode list and one without, same
        // LezWatch season count, get the same picker.
        val withList = snapshot.show(show)!!
        val edited = fixtureJson().editArray("shows", 1) { it.with("episode_counts", JsonNull) }
        val withoutList = decoded(edited).show(show)!!
        assertNotNull(withList.episodeCounts)
        assertNull(withoutList.episodeCounts)
        assertEquals(SoFar.seasonRange(withList), SoFar.seasonRange(withoutList))
        assertEquals(SoFar.clamped(at(40, 2000), withList), SoFar.clamped(at(40, 2000), withoutList))
    }

    // Stored on the device

    @Test
    fun thePositionIsStoredPerShow() {
        val map = HashMap<String, String>()
        val storage = object : KeyValueStore {
            override fun getString(key: String): String? = map[key]
            override fun putString(key: String, value: String?) {
                if (value == null) map.remove(key) else map[key] = value
            }
        }
        val store = WatchPositionStore(storage)
        assertNull(store.position(show))
        store.set(at(3, 4), show)
        assertEquals(at(3, 4), store.position(show))
        assertNull(store.position("lwtv:show:101"))
        assertEquals("kept across launches", at(3, 4), WatchPositionStore(storage).position(show))
        map["soFar.position.lwtv:show:101"] = "0,4"
        assertNull("a bad stored value is ignored, not shown", store.position("lwtv:show:101"))
        store.clear(show)
        assertNull(store.position(show))
    }
}
