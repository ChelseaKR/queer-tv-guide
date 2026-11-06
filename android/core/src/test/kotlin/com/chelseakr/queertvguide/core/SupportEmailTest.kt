package com.chelseakr.queertvguide.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** DECISIONS 0039: the About screen's "Email support" link. */
class SupportEmailTest {
    private val name = "Example App"

    @Test
    fun isAMailtoToTheSupportAddressWithTheVersionInTheSubject() {
        assertEquals("mailto:${SupportEmail.ADDRESS}?subject=Example%20App%201.0.1", SupportEmail.uri(name, "1.0.1"))
    }

    /** Absence is never a value: no version means no version in the subject. */
    @Test
    fun aMissingOrBlankVersionIsLeftOut() {
        assertEquals(name, SupportEmail.subject(name, null))
        assertEquals(name, SupportEmail.subject(name, ""))
        assertEquals(name, SupportEmail.subject(name, "  \n"))
        assertEquals("Example App 2.3", SupportEmail.subject(name, " 2.3 "))
        assertFalse(SupportEmail.uri(name, null).contains("null"))
    }

    /** Nothing in the version can end the subject or add another header. */
    @Test
    fun theSubjectCannotAddOtherHeaders() {
        val uri = SupportEmail.uri(name, "1.0&cc=someone@example.com")
        val query = uri.substringAfter("?")
        assertEquals(1, query.split("&").size)
        assertTrue(query.startsWith("subject=Example%20App%201.0%26cc%3Dsomeone%40example.com"))
    }

    /** The same address the published support page and the Play listing give. */
    @Test
    fun addressMatchesTheSupportPageAndThePlayListing() {
        val repo = Repo.androidRoot.parentFile
        assertTrue(File(repo, "docs/site/support.html").readText().contains("mailto:${SupportEmail.ADDRESS}"))
        assertTrue(File(repo, "docs/play-store/play-listing.json").readText().contains("\"contact_email\": \"${SupportEmail.ADDRESS}\""))
    }
}
