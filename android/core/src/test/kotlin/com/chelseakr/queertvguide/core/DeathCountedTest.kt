package com.chelseakr.queertvguide.core

import com.chelseakr.queertvguide.core.JsonEdit.editArray
import com.chelseakr.queertvguide.core.JsonEdit.editObject
import com.chelseakr.queertvguide.core.JsonEdit.with
import com.chelseakr.queertvguide.core.JsonEdit.without
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * DECISIONS 0053 on Android: `death.counted`. A date on a character LezWatch.TV
 * lists as alive is neither a death nor "alive". Absent `counted` (every 1.0.0
 * file) reads as before. Same cases as GuideCore's DeathCountedTests.
 */
class DeathCountedTest {
    private val listedAliveLine =
        "LezWatch.TV records a death date (2017) for Odile Brandt but lists the character as alive, so it is not counted here."

    /** Odile Brandt (character 203) with `counted` set; null removes the key. */
    private fun odile(counted: Boolean?, extra: (JsonObject) -> JsonObject = { it }): Snapshot {
        val root = Repo.fixtureJson().editArray("characters", 2) { odile ->
            extra(
                odile.editObject("death") { death ->
                    if (counted == null) death.without("counted") else death.with("counted", JsonPrimitive(counted))
                },
            )
        }
        return SnapshotDecoder.decode(Repo.bytes(root))
    }

    private fun deaths(s: Snapshot, showId: String): Presentation.ShowDeaths {
        val show = s.show(showId)!!
        return Presentation.showDeaths(s.charactersInShow(show.id), show)
    }

    @Test
    fun anOldSnapshotHasNoCountedFieldAndReadsAsBefore() {
        val s = Repo.fixture()
        assertTrue(s.characters.all { it.death.counted == null })
        val d = deaths(s, "lwtv:show:102")
        assertEquals("1 of 2 listed characters has a recorded death.", d.headline)
        assertEquals(listOf("Odile Brandt dies (2017)."), d.lines)
    }

    @Test
    fun countedTrueReadsAsBeforeAndFalseDecodes() {
        assertEquals(true, odile(true).character("lwtv:character:203")!!.death.counted)
        assertEquals(false, odile(false).character("lwtv:character:203")!!.death.counted)
        assertEquals("1 of 2 listed characters has a recorded death.", deaths(odile(true), "lwtv:show:102").headline)
    }

    @Test
    fun aDateOnACharacterListedAsAliveIsNotADeathAndNotAlive() {
        val s = odile(false)
        val show = s.show("lwtv:show:102")!!
        val cast = s.charactersInShow(show.id)
        val d = deaths(s, show.id)
        assertEquals("Not recorded. LezWatch.TV does not list any of the 2 listed characters as dead.", d.headline)
        assertEquals(listOf("Odile Brandt: not recorded. $listedAliveLine"), d.lines)
        assertTrue(d.notes.contains("One listed character has a recorded death date, but LezWatch.TV lists the character as alive, so it is not counted here."))
        val death = s.character("lwtv:character:203")!!.death
        assertEquals("Not recorded. $listedAliveLine", Presentation.death(death, "Odile Brandt"))
        assertEquals("Death date recorded, listed as alive", Presentation.deathShort(death))
        assertEquals("Not recorded. LezWatch.TV does not list any of the 2 listed characters as dead.", Presentation.deathsSummary(cast, show.id))
        for (text in listOf(d.headline, d.lines[0], Presentation.death(death, "Odile Brandt"))) {
            assertFalse(text, text.contains(" dies"))
            assertFalse(text, text.lowercase().contains("is alive"))
        }
    }

    @Test
    fun aShowWithOnlyAListedAliveDateStaysOutOfTheNoRecordedDeathsFilter() {
        val s = odile(false)
        assertTrue(SearchIndex(s).deathCoverage(s.show("lwtv:show:102")!!).anyRecordedDeath)
    }

    @Test
    fun aMultiShowCharacterListedAliveGetsTheStatusSentenceNotThePlacementOne() {
        val s = odile(false) { odile ->
            val shows = (odile["shows"] as JsonArray) + JsonObject(
                mapOf(
                    "show_id" to JsonPrimitive("lwtv:show:101"),
                    "role" to JsonPrimitive("guest"),
                    "years" to JsonArray(listOf(JsonPrimitive("2022"))),
                ),
            )
            val years = listOf(2014, 2016, 2021)
            odile.with("shows", JsonArray(shows)).editObject("death") { death ->
                death.with("years", JsonArray(years.map { JsonPrimitive(it) }))
                    .with(
                        "dates",
                        JsonArray(years.map { JsonObject(mapOf("date" to JsonNull, "year" to JsonPrimitive(it), "raw" to JsonPrimitive("$it"))) }),
                    )
            }
        }
        val c = s.character("lwtv:character:203")!!
        assertEquals(Presentation.DeathPlacement.ListedAlive, Presentation.deathPlacement(c, "lwtv:show:101"))
        assertEquals(Presentation.DeathPlacement.ListedAlive, Presentation.deathPlacement(c, "lwtv:show:102"))
        assertEquals(
            "Not recorded. LezWatch.TV records death dates (2014, 2016, 2021) for Odile Brandt but lists the character as alive, so it is not counted here.",
            Presentation.death(c.death, "Odile Brandt"),
        )
    }

    @Test
    fun aDeathEntryWithNoYearListedAsAliveSaysSo() {
        val death = Death(died = true, deathKnown = true, dates = emptyList(), years = emptyList(), counted = false)
        assertEquals(
            "Not recorded. LezWatch.TV records a death but no date for Nora West-Allen but lists the character as alive, so it is not counted here.",
            Presentation.death(death, "Nora West-Allen"),
        )
        assertNull(Death(died = null, deathKnown = false, dates = emptyList(), years = emptyList()).counted)
    }

    /** Negative control: with the field removed the same record is a death again. */
    @Test
    fun negativeControlWithoutTheFieldTheDateCountsAgain() {
        assertEquals("1 of 2 listed characters has a recorded death.", deaths(odile(null), "lwtv:show:102").headline)
    }
}
