package com.chelseakr.queertvguide.core

import com.chelseakr.queertvguide.core.JsonEdit.editArray
import com.chelseakr.queertvguide.core.JsonEdit.editObject
import com.chelseakr.queertvguide.core.JsonEdit.with
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * DECISIONS 0030 on Android: the same cases GuideCore's PresentationTests hold
 * the iOS app to. The parity golden cannot carry them, because the shared
 * fixture has no character in more than one show.
 */
class DeathRuleTest {
    /** Odile Brandt (dies 2017, a regular on show 102 in 2016-2018) also linked to show 101. */
    private fun odileAlsoIn101(years: List<String>, deathYears: List<Int>? = null): Snapshot {
        val root = Repo.fixtureJson().editArray("characters", 2) { odile ->
            val shows = (odile["shows"] as JsonArray) + JsonObject(
                mapOf(
                    "show_id" to JsonPrimitive("lwtv:show:101"),
                    "role" to JsonPrimitive("guest"),
                    "years" to JsonArray(years.map { JsonPrimitive(it) }),
                ),
            )
            var edited = odile.with("shows", JsonArray(shows))
            if (deathYears != null) {
                edited = edited.editObject("death") { death ->
                    death.with("years", JsonArray(deathYears.map { JsonPrimitive(it) }))
                        .with(
                            "dates",
                            JsonArray(
                                deathYears.map {
                                    JsonObject(mapOf("date" to JsonNull, "year" to JsonPrimitive(it), "raw" to JsonPrimitive("$it")))
                                },
                            ),
                        )
                }
            }
            edited
        }
        val s = SnapshotDecoder.decode(Repo.bytes(root))
        assertEquals("the edit landed", 2, s.character("lwtv:character:203")!!.shows.size)
        return s
    }

    @Test
    fun aDeathOutsideTheCharactersYearsInThisShowIsNotCountedHere() {
        val s = odileAlsoIn101(listOf("2022"))
        val show = s.show("lwtv:show:101")!!
        val deaths = Presentation.showDeaths(s.charactersInShow(show.id), show)
        assertEquals("Not recorded. This snapshot does not record a death in this show for any of the 3 listed characters.", deaths.headline)
        assertEquals(
            listOf("Odile Brandt: not recorded in this show. LezWatch.TV records a death for Odile Brandt (2017), but not in a year Odile Brandt appears in this show. It may happen in another show."),
            deaths.lines,
        )
        assertEquals(listOf("One listed character has a recorded death that LezWatch.TV does not place in this show, so it is not counted here."), deaths.notes)
        assertEquals("Not recorded for any of the 3 listed characters.", Presentation.deathsSummary(s.charactersInShow(show.id), show.id))
        assertFalse(SearchIndex(s).deathCoverage(show).anyRecordedDeath)

        val home = s.show("lwtv:show:102")!!
        val there = Presentation.showDeaths(s.charactersInShow(home.id), home)
        assertEquals("1 of 2 listed characters has a recorded death.", there.headline)
        assertEquals(
            listOf("Odile Brandt dies (2017). The record belongs to the character, not to one show; it is counted here because 2017 is among Odile Brandt’s years in this show."),
            there.lines,
        )
    }

    @Test
    fun aDeathInTheCharactersYearsInThisShowIsCountedHere() {
        val s = odileAlsoIn101(listOf("2017", "2018"))
        val show = s.show("lwtv:show:101")!!
        val deaths = Presentation.showDeaths(s.charactersInShow(show.id), show)
        assertEquals("1 of 3 listed characters has a recorded death.", deaths.headline)
        assertEquals(listOf("LezWatch.TV's own tally for this show is 0 deaths; its character records list 1."), deaths.notes)
    }

    @Test
    fun aDeathThatCannotBePlacedIsUnknownHereAndKeepsTheShowOutOfTheFilter() {
        val noLinkYears = odileAlsoIn101(emptyList())
        val show = noLinkYears.show("lwtv:show:101")!!
        val a = Presentation.showDeaths(noLinkYears.charactersInShow(show.id), show)
        assertEquals(
            listOf("Odile Brandt: not recorded in this show. LezWatch.TV records a death for Odile Brandt (2017) but not Odile Brandt’s years in this show, so it cannot say whether it happens here."),
            a.lines,
        )
        assertTrue(SearchIndex(noLinkYears).deathCoverage(show).anyRecordedDeath)

        val noDeathYear = odileAlsoIn101(listOf("2021"), deathYears = emptyList())
        val home = noDeathYear.show("lwtv:show:102")!!
        val b = Presentation.showDeaths(noDeathYear.charactersInShow(home.id), home)
        assertEquals("Not recorded. This snapshot does not record a death in this show for any of the 2 listed characters.", b.headline)
        assertEquals(
            listOf(
                "One listed character has a recorded death that LezWatch.TV does not place in this show, so it is not counted here.",
                "LezWatch.TV's own tally for this show is 1 death; its character records place 0 in this show.",
            ),
            b.notes,
        )
    }

    @Test
    fun theSpoilerTropesMatchGuideCore() {
        assertEquals(setOf("dead-queers", "happy-then-not", "none"), Presentation.deathSpoilerTropeSlugs)
        assertEquals("LezWatch.TV lists no tropes for this show (“None!”).", Presentation.spoilerTagNote(Term("none", "None!")))
        assertEquals("LezWatch.TV tags this show “Happiness then Tragedy”.", Presentation.spoilerTagNote(Term("happy-then-not", "Happiness then Tragedy")))
    }

    @Test
    fun theTriggerLevelIsLabeledExplainedOrNotRated() {
        val high = Presentation.triggerWarning(listOf(Term("high", "High")))
        assertEquals("LezWatch.TV trigger-warning level", high.heading)
        assertEquals("High", high.level)
        assertEquals(
            "LezWatch.TV: “Scenes of explicit violence, drug use, suicide, sex, and/or abuse occur regularly. Not intended for children or sensitive viewers.”",
            high.meaning,
        )
        val none = Presentation.triggerWarning(emptyList())
        assertEquals("Not rated", none.level)
        assertEquals("LezWatch.TV has not given this show a level. That does not mean it has no difficult content.", none.meaning)
        val unknown = Presentation.triggerWarning(listOf(Term("violence", "Violence")))
        assertEquals("Violence", unknown.level)
        assertEquals("LezWatch.TV gives this level without a description in this snapshot.", unknown.meaning)
    }
}
