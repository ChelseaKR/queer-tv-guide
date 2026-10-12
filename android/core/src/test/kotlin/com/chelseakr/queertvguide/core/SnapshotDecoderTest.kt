package com.chelseakr.queertvguide.core

import com.chelseakr.queertvguide.core.JsonEdit.editArray
import com.chelseakr.queertvguide.core.JsonEdit.editObject
import com.chelseakr.queertvguide.core.JsonEdit.with
import com.chelseakr.queertvguide.core.JsonEdit.without
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/** The rules GuideCore's `SnapshotDecoderTests` and friends hold the iOS decoder to, held here too. */
class SnapshotDecoderTest {
    private fun refused(root: JsonObject, containing: String) {
        try {
            SnapshotDecoder.decode(Repo.bytes(root))
            fail("expected the file to be refused ($containing)")
        } catch (e: SnapshotDecodingException) {
            assertTrue("'${e.message}' should mention '$containing'", e.message!!.contains(containing))
        }
    }

    @Test
    fun theFixtureDecodesWithEveryAbsenceKept() {
        val s = Repo.fixture()
        assertEquals(4, s.shows.size)
        assertEquals(5, s.characters.size)
        val salt = s.show("lwtv:show:103")!!
        assertFalse(salt.schedule.scheduleKnown)
        assertNull(salt.seasons)
        assertNull(salt.ratings.worthIt)
        val cartographers = s.show("lwtv:show:102")!!
        assertTrue(cartographers.schedule.scheduleKnown)
        assertNull(cartographers.schedule.nextEpisode)
        assertNull(s.character("lwtv:character:201")!!.death.died)
        assertTrue(s.character("lwtv:character:203")!!.death.isRecorded)
        assertEquals(listOf("lwtv:character:201", "lwtv:character:202"), s.charactersInShow("lwtv:show:101").map { it.id })
    }

    @Test
    fun anotherSchemaVersionIsRefused() {
        try {
            SnapshotDecoder.decode(Repo.bytes(Repo.fixtureJson().with("schema_version", JsonPrimitive("2"))))
            fail("schema 2 decoded")
        } catch (e: SnapshotDecodingException.UnsupportedSchemaVersion) {
            assertEquals("2", e.version)
        }
    }

    /** LezWatch records deaths, not survival: `died: false` is a contract violation. */
    @Test
    fun diedFalseIsRefused() {
        refused(
            Repo.fixtureJson().editArray("characters", 0) { c -> c.editObject("death") { it.with("died", JsonPrimitive(false)) } },
            "died",
        )
    }

    @Test
    fun aRepeatedShowOrCharacterIdIsRefusedWhole() {
        val root = Repo.fixtureJson()
        val shows = root["shows"]!!.jsonArray
        refused(root.with("shows", JsonArray(shows + shows[0])), "duplicate show id lwtv:show:101")
        val characters = root["characters"]!!.jsonArray
        refused(root.with("characters", JsonArray(characters + characters[1])), "duplicate character id lwtv:character:202")
    }

    @Test
    fun eachSourceIsCreditedExactlyOnce() {
        val root = Repo.fixtureJson()
        val attribution = root["attribution"]!!.jsonArray
        val lezwatch = attribution.first { it.jsonObject["source"].toString() == "\"lezwatch\"" }
        refused(root.with("attribution", JsonArray(attribution.filter { it != lezwatch })), "no entry for source lezwatch")
        val tvmaze = attribution.first { it.jsonObject["source"].toString() == "\"tvmaze\"" }
        refused(root.with("attribution", JsonArray(attribution.filter { it != tvmaze })), "no entry for source tvmaze")
        refused(root.with("attribution", JsonArray(attribution + lezwatch)), "2 entries for source lezwatch")
    }

    @Test
    fun aDateThatIsNotAUtcDatetimeIsRefused() {
        refused(Repo.fixtureJson().with("generated_at", JsonPrimitive("2026-09-13")), "generated_at")
        refused(Repo.fixtureJson().with("generated_at", JsonPrimitive("2026-09-13T20:00:00.123Z")), "generated_at")
        refused(Repo.fixtureJson().editArray("shows", 1) { it.with("source_modified_at", JsonPrimitive("yesterday")) }, "shows.1.source_modified_at")
    }

    @Test
    fun aMissingRequiredFieldIsRefusedAndAMissingOptionalOneIsNull() {
        refused(Repo.fixtureJson().editArray("shows", 0) { it.without("title") }, "title")
        refused(Repo.fixtureJson().editArray("shows", 0) { it.with("title", JsonNull) }, "title")
        val s = SnapshotDecoder.decode(Repo.bytes(Repo.fixtureJson().editArray("shows", 0) { it.without("summary") }))
        assertNull(s.shows[0].summary)
    }

    @Test
    fun unknownFieldsAreIgnoredAsTheContractAllows() {
        val s = SnapshotDecoder.decode(Repo.bytes(Repo.fixtureJson().with("added_later", JsonPrimitive("x")).editArray("shows", 0) { it.with("new_field", JsonPrimitive(1)) }))
        assertEquals(4, s.shows.size)
    }

    /** `airstamp` counts only with a recorded air time; a placeholder is never a time. */
    @Test
    fun anAirInstantNeedsARecordedAirTime() {
        fun ep(airtime: String?, airstamp: String?) = Episode(1, 1, 1, null, "2026-09-23", airtime, airstamp, null, "https://example.invalid/e/1")
        assertNull(ep(null, "2026-09-23T12:00:00+00:00").airInstant)
        assertNull(ep("", "2026-09-23T12:00:00+00:00").airInstant)
        assertNull(ep("  ", "2026-09-23T12:00:00+00:00").airInstant)
        assertNull(ep("12:00", null).airInstant)
        assertNull(ep("12:00", "not a date").airInstant)
        assertNull(ep("12:00", "2026-09-23").airInstant)
        assertEquals(java.time.Instant.parse("2026-09-23T12:00:00Z"), ep("12:00", "2026-09-23T12:00:00+00:00").airInstant)
        assertEquals(ep("21:00", "2026-09-20T21:00:00-04:00").airInstant, ep("01:00", "2026-09-21T01:00:00+00:00").airInstant)
    }
}

class AppLinkTest {
    @Test
    fun aShowLinkRoundTripsARealId() {
        val link = AppLink.ShowLink("lwtv:show:26")
        assertEquals("queerframe://show/lwtv:show:26", link.url)
        assertEquals(link, AppLink.parse(link.url))
    }

    @Test
    fun aCharacterLinkRoundTrips() {
        val link = AppLink.CharacterLink("lwtv:character:241")
        assertEquals(link, AppLink.parse(link.url))
    }

    @Test
    fun everyFixtureShowIdRoundTrips() {
        for (show in Repo.fixture().shows) assertEquals(AppLink.ShowLink(show.id), AppLink.parse(AppLink.ShowLink(show.id).url))
    }

    @Test
    fun schemeAndKindAreCaseInsensitive() {
        assertEquals(AppLink.ShowLink("lwtv:show:1"), AppLink.parse("QueerFrame://SHOW/lwtv:show:1"))
    }

    @Test
    fun anythingElseIsNull() {
        for (text in listOf(
            "https://chelseakr.github.io/queer-tv-guide/",
            "queerframe://show",
            "queerframe://show/",
            "queerframe://show/a/b",
            "queerframe://episode/1",
            "otherapp://show/lwtv:show:1",
            "queerframe:show/lwtv:show:1",
            "not a url at all",
        )) {
            assertNull(text, AppLink.parse(text))
        }
    }
}
