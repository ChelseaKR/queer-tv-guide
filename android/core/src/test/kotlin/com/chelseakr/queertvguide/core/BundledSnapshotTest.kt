package com.chelseakr.queertvguide.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneId
import java.util.Locale

/**
 * The snapshot the Android app ships: the published file, byte for byte
 * (`make -C android bundle-snapshot` fetches it and checks the published
 * SHA-256). Real LezWatch.TV and TVmaze data, so these tests check the port
 * on what people will see, as GuideCore's `BundledSnapshotTests` and
 * `EpisodeRemindersTests` do on iOS.
 */
class BundledSnapshotTest {
    private val snapshot: Snapshot by lazy {
        check(Repo.bundledSnapshot.exists()) {
            "${Repo.bundledSnapshot} is missing: run `make -C android bundle-snapshot` (CI does, before the tests)"
        }
        SnapshotDecoder.decode(Repo.bundledSnapshot.inputStream())
    }

    @Test
    fun itIsAPublishedSnapshotNotAFixture() {
        val text = Repo.bundledSnapshot.readText()
        assertFalse("a fixture was bundled", text.contains("0.0.0-fixture"))
        assertTrue(snapshot.shows.size > 1000)
        assertTrue(snapshot.characters.size > 5000)
        assertEquals(Snapshot.SUPPORTED_SCHEMA_VERSION, snapshot.schemaVersion)
    }

    /** With every show starred: at most 60, soonest first, all in the future, no episode name, no word about death. */
    @Test
    fun aPlanOnRealDataIsCappedSortedAndSpoilerFree() {
        val now = snapshot.generatedAt
        val text = DateText(Locale.US, ZoneId.of("America/Los_Angeles"))
        val plan = EpisodeReminders.plan(snapshot.shows.map { it.id }, snapshot, now, text)
        assertFalse("the real snapshot lists no upcoming episode", plan.isEmpty())
        assertTrue(plan.size <= EpisodeReminders.LIMIT)
        assertEquals(plan.map { it.fireAt }.sorted(), plan.map { it.fireAt })
        assertTrue(plan.all { it.fireAt > now })
        assertEquals(plan.size, plan.map { it.identifier }.toSet().size)
        val titles = snapshot.shows.map { it.title }.toSet()
        val names = snapshot.shows.mapNotNull { it.schedule.nextEpisode?.name }.filter { it.length > 3 && it != "TBA" && it !in titles }
        for (r in plan) {
            val body = r.body.lowercase()
            for (word in listOf("dies", "died", "death", "dead")) assertFalse("${r.identifier} says $word", body.contains(word))
            assertEquals(snapshot.show(r.showId)!!.title, r.title)
            for (name in names) assertFalse("${r.identifier} carries the episode name $name", r.body.contains(name))
        }
    }

    /** An episode with no recorded air time fires at 10:00 local on its date and claims no air time. */
    @Test
    fun dateOnlyEpisodesFireAtTenLocalOnTheirDate() {
        val zone = ZoneId.of("UTC")
        val plan = EpisodeReminders.plan(snapshot.shows.map { it.id }, snapshot, snapshot.generatedAt, DateText(Locale.US, zone), limit = Int.MAX_VALUE)
        for (r in plan) {
            val episode = snapshot.show(r.showId)!!.schedule.nextEpisode!!
            if (!episode.airtime.isNullOrBlank()) {
                assertEquals(r.identifier, episode.airInstant, r.fireAt)
            } else {
                val local = r.fireAt.atZone(zone)
                assertEquals(r.identifier, episode.airdate, local.toLocalDate().toString())
                assertEquals(r.identifier, EpisodeReminders.FALLBACK_HOUR, local.hour)
                assertFalse(r.body.contains("to air now"))
                assertTrue(r.body.contains("no air time"))
            }
        }
    }

    @Test
    fun theNoRecordedDeathsFilterNeverKeepsAShowWithARecordedDeathOrNoCast() {
        val index = SearchIndex(snapshot)
        val kept = index.browse(SearchIndex.Filters(noRecordedDeaths = true))
        assertTrue(kept.isNotEmpty())
        for (show in kept) {
            val cast = snapshot.charactersInShow(show.id)
            assertTrue(show.id, cast.isNotEmpty())
            assertTrue(show.id, cast.none { it.death.isRecorded })
        }
        assertTrue(kept.size < snapshot.shows.size)
    }

    @Test
    fun searchFindsRealTitlesWithoutTheirPunctuation() {
        val index = SearchIndex(snapshot)
        val hit = index.search("greys anatomy").hits.firstOrNull()
        assertTrue("$hit", hit is SearchIndex.Hit.ShowHit && hit.show.title.startsWith("Grey"))
    }
}
