package com.chelseakr.queertvguide.ui

import org.junit.Assert.assertEquals
import org.junit.Test
import java.text.NumberFormat
import java.util.Locale

/** The count under "N filters on" and the note above a capped list (iOS's `SearchCountTests`). */
class SearchCountTest {
    @Test
    fun topOnlyWhenSearchHeldMatchesBack() {
        assertEquals("1 match", matchCount(1, isCapped = false))
        assertEquals("12 matches", matchCount(12, isCapped = false))
        // Exactly as many matches as search returns: all of them are shown.
        assertEquals("50 matches", matchCount(50, isCapped = false))
        assertEquals("Top 50 matches", matchCount(50, isCapped = true))
    }

    @Test
    fun theCappedNotesTotalHasAThousandsSeparator() {
        assertEquals(
            "Showing the first 50 of 1,204 matches. Type more to narrow them.",
            cappedNote(50, 1204, NumberFormat.getIntegerInstance(Locale.US)),
        )
    }
}
