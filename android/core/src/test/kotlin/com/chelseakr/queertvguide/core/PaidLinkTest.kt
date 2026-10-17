package com.chelseakr.queertvguide.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * DECISIONS 0019: only an Apple TV or iTunes link carrying an `at=` token is a
 * paid link, and it says so. The same cases as GuideCore's `PaidLinkTests`.
 */
class PaidLinkTest {
    private fun link(host: String, query: String?) =
        WatchLink("https://$host/us/show/example/umc.cmc.1" + (query?.let { "?$it" } ?: ""), host)

    @Test
    fun anAppleLinkWithTheTokenIsPaid() {
        assertTrue(Presentation.isPaidLink(link("tv.apple.com", "action=play&at=1l3vabc")))
        assertTrue(Presentation.isPaidLink(link("itunes.apple.com", "i=1&at=1l3vabc")))
        assertEquals("Watch on tv.apple.com, paid link", Presentation.watchLinkSpoken(link("tv.apple.com", "at=1l3vabc"), emptyList()))
        assertEquals("Paid link", Presentation.PAID_LINK_NOTE)
    }

    /** The negative control: the same links without a token, an empty one, or on another host are not paid. */
    @Test
    fun anythingElseIsNotPaid() {
        assertFalse(Presentation.isPaidLink(link("tv.apple.com", "action=play")))
        assertFalse(Presentation.isPaidLink(link("tv.apple.com", null)))
        assertFalse(Presentation.isPaidLink(link("tv.apple.com", "at=")))
        assertFalse(Presentation.isPaidLink(link("music.apple.com", "at=1l3vabc")))
        assertFalse(Presentation.isPaidLink(link("www.netflix.com", "at=1l3vabc")))
        assertFalse(Presentation.isPaidLink(WatchLink("not a url", "x")))
        val plain = link("tv.apple.com", "action=play")
        assertEquals(Presentation.watchLinkLabel(plain, emptyList()), Presentation.watchLinkSpoken(plain, emptyList()))
    }
}
