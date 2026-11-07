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
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * DECISIONS 0041 adds optional fields to the v1 snapshot: `episode_counts` on a
 * show, `placements` on each death date and `coverage.placements`. The decoder
 * as first built ignored them (this test proved it while `Snapshot.kt` did not
 * declare them). For "so far" (DECISIONS 0044) it reads them, so this test now
 * checks both directions, as GuideCore's PlacementFieldsCompatibilityTests do:
 * a file without them decodes with every new field null (not computed), and a
 * file with them decodes to the same snapshot apart from those fields. The
 * fixture is the v1 fixture plus only the new fields
 * (pipeline/tests/test_snapshot_placements_contract.py checks that, and that it
 * validates against the schema).
 */
class PlacementFieldsCompatibilityTest {
    private val placementsFixture = File(Repo.root, "ios/GuideCore/Tests/Fixtures/snapshot.placements.fixture.json")

    private fun fixtureJson(): JsonObject = Json.parseToJsonElement(placementsFixture.readText()) as JsonObject

    /** The placements fixture with characters[2]'s first death date given [placements]. */
    private fun withPlacements(placements: List<JsonObject>): Snapshot = SnapshotDecoder.decode(
        Repo.bytes(
            fixtureJson().editArray("characters", 2) { character ->
                val death = character["death"] as JsonObject
                val dates = (death["dates"] as JsonArray).toMutableList()
                dates[0] = (dates[0] as JsonObject).with("placements", JsonArray(placements))
                character.with("death", death.with("dates", JsonArray(dates)))
            },
        ),
    )

    private fun p(showId: String?, precision: String, reason: String, season: Int?, episodes: List<Int>?, airdate: String?): JsonObject {
        fun int(v: Int?): JsonElement = if (v == null) JsonNull else JsonPrimitive(v)
        return JsonObject(
            mapOf(
                "show_id" to JsonEdit.str(showId),
                "precision" to JsonPrimitive(precision),
                "reason" to JsonPrimitive(reason),
                "season" to int(season),
                "episodes" to (episodes?.let { l -> JsonArray(l.map { JsonPrimitive(it) }) } ?: JsonNull),
                "airdate" to JsonEdit.str(airdate),
            ),
        )
    }

    @Test
    fun aFileWithoutTheFieldsDecodesWithNothingComputed() {
        val without = Repo.fixture()
        assertNull(without.coverage.placements)
        assertTrue(without.shows.all { it.episodeCounts == null })
        assertTrue(without.characters.flatMap { it.death.dates }.all { it.placements == null })
        assertFalse(SoFar.isAvailable(without))
    }

    @Test
    fun theNewFieldsDecodeToTheSameSnapshotApartFromThem() {
        val withFields = SnapshotDecoder.decode(placementsFixture.readBytes())
        val without = Repo.fixture()
        assertEquals("1", withFields.schemaVersion)
        // Equal once the new fields are taken off again: nothing else moved.
        assertEquals(without.shows, withFields.shows.map { it.copy(episodeCounts = null) })
        assertEquals(
            without.characters,
            withFields.characters.map { c -> c.copy(death = c.death.copy(dates = c.death.dates.map { it.copy(placements = null) })) },
        )
        assertEquals(without.coverage, withFields.coverage.copy(placements = null))
        assertEquals(without.attribution, withFields.attribution)
        assertEquals(without.contentDigest, withFields.contentDigest)

        assertEquals(1, withFields.coverage.placements?.deathEvents)
        assertTrue(SoFar.isAvailable(withFields))
        val cartographers = withFields.show("lwtv:show:102")!!
        assertEquals(listOf(SeasonEpisodeCount(1, 10), SeasonEpisodeCount(2, 10), SeasonEpisodeCount(3, 6)), cartographers.episodeCounts)
        assertNull("null means no list, not zero episodes", withFields.show("lwtv:show:103")!!.episodeCounts)
        val odile = withFields.character("lwtv:character:203")!!
        assertEquals(
            listOf(DeathPlacement.of("lwtv:show:102", Precision.EPISODE, "exact_date", season = 2, episodes = listOf(7))),
            odile.death.dates.first().placements,
        )
    }

    @Test
    fun theFixtureReallyCarriesTheNewFields() {
        // Negative control: if the fields were missing, the test above would prove nothing.
        val root = fixtureJson()
        assertTrue((root["coverage"] as JsonObject).containsKey("placements"))
        val shows = root["shows"] as JsonArray
        assertTrue(shows.all { (it as JsonObject).containsKey("episode_counts") })
        val dates = (root["characters"] as JsonArray).flatMap {
            (((it as JsonObject)["death"] as JsonObject)["dates"] as JsonArray).toList()
        }
        assertTrue(dates.isNotEmpty())
        assertTrue(dates.all { (it as JsonObject).containsKey("placements") })
    }

    @Test
    fun everyPrecisionDecodes() {
        // Each precision the pipeline can write, including a null show id, on one date.
        val decoded = withPlacements(
            listOf(
                p("lwtv:show:102", "episode", "exact_date", 2, listOf(7), null),
                p("lwtv:show:102", "episode_pair", "double_bill", 2, listOf(7, 8), null),
                p("lwtv:show:102", "special", "special_same_day", 2, null, "2017-11-12"),
                p("lwtv:show:102", "season", "season_drop", 2, null, null),
                p("lwtv:show:102", "unplaced", "between_seasons", null, null, null),
                p("lwtv:show:102", "other_show", "crossover_matched_other_show", null, null, null),
                p(null, "unplaced", "no_show_in_death_year", null, null, null),
            ),
        )
        val placements = decoded.characters[2].death.dates[0].placements!!
        assertEquals(
            listOf(Precision.EPISODE, Precision.EPISODE_PAIR, Precision.SPECIAL, Precision.SEASON, Precision.UNPLACED, Precision.OTHER_SHOW, Precision.UNPLACED),
            placements.map { it.precision },
        )
        assertNull(placements.last().showId)
    }

    /** A precision a newer pipeline adds must not make the whole file unreadable: it reads as unrecognized, which "so far" treats as unplaced. */
    @Test
    fun anUnknownPrecisionDecodesAsUnrecognized() {
        val decoded = withPlacements(listOf(p("lwtv:show:102", "scene", "new_rule", 2, listOf(7), null)))
        val placement = decoded.characters[2].death.dates[0].placements!!.first()
        assertEquals(Precision.UNRECOGNIZED, placement.precision)
        assertEquals("scene", placement.precisionRaw)
    }
}
