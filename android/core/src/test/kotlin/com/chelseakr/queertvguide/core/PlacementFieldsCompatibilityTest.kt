package com.chelseakr.queertvguide.core

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * DECISIONS 0041 adds optional fields to the v1 snapshot: `episode_counts` on a show,
 * `placements` on each death date and `coverage.placements`. The app must read such a
 * file exactly as it read the file without them (GuideCore's
 * PlacementFieldsCompatibilityTests holds the iOS decoder to the same rule).
 */
class PlacementFieldsCompatibilityTest {
    private val placementsFixture = File(Repo.root, "ios/GuideCore/Tests/Fixtures/snapshot.placements.fixture.json")

    @Test
    fun theNewFieldsDecodeToTheSameSnapshot() {
        val withFields = SnapshotDecoder.decode(placementsFixture.readBytes())
        val without = Repo.fixture()
        assertEquals("1", withFields.schemaVersion)
        assertEquals(without.shows, withFields.shows)
        assertEquals(without.characters, withFields.characters)
        assertEquals(without.coverage, withFields.coverage)
        assertEquals(without.attribution, withFields.attribution)
        assertEquals(without.contentDigest, withFields.contentDigest)
    }

    @Test
    fun theFixtureReallyCarriesTheNewFields() {
        // Negative control: if the fields were missing, the test above would prove nothing.
        val root = Json.parseToJsonElement(placementsFixture.readText()) as JsonObject
        assertTrue((root["coverage"] as JsonObject).containsKey("placements"))
        val shows = root["shows"] as JsonArray
        assertTrue(shows.all { (it as JsonObject).containsKey("episode_counts") })
        val dates = (root["characters"] as JsonArray).flatMap {
            (((it as JsonObject)["death"] as JsonObject)["dates"] as JsonArray).toList()
        }
        assertTrue(dates.isNotEmpty())
        assertTrue(dates.all { (it as JsonObject).containsKey("placements") })
    }
}
