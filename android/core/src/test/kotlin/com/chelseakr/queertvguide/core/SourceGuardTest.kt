package com.chelseakr.queertvguide.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * What makes the Play Data safety answer "No data collected" checkable, the
 * Android twin of GuideCore's `SourceTreeGuardTests` (DECISIONS 0018):
 *
 * - the only host any app code names is the snapshot's (plus the Play
 *   listing the "Rate" row opens in the Play app or browser);
 * - exactly one place opens a network connection;
 * - no analytics, crash reporting, ads, Firebase or Play services library is
 *   linked, and the manifest asks for no permission beyond the listed ones;
 * - only `Episode.airInstant` reads `airstamp` (a placeholder is never a time);
 * - nothing about deaths reaches a reminder or the widget's file.
 */
class SourceGuardTest {
    private val android = Repo.androidRoot
    private val sources: List<File> = listOf(File(android, "app/src/main"), File(android, "core/src/main"))
        .flatMap { root -> root.walkTopDown().filter { it.isFile && it.extension in setOf("kt", "xml") }.toList() }
        .filterNot { it.path.contains("/assets/") }

    private fun code(file: File): String = file.readLines()
        .filterNot { it.trim().startsWith("//") || it.trim().startsWith("*") || it.trim().startsWith("/**") }
        .joinToString("\n")

    @Test
    fun theTreeWasRead() {
        assertTrue("only ${sources.size} source files found", sources.size >= 20)
    }

    @Test
    fun onlyTheSnapshotHostAndThePlayListingAppearInCode() {
        val allowed = setOf(
            "chelseakr.github.io",
            "play.google.com",
            // XML namespaces, not hosts anything connects to.
            "schemas.android.com",
        )
        val url = Regex("""https?://([A-Za-z0-9.-]+)""")
        val found = sources.flatMap { f -> url.findAll(code(f)).map { it.groupValues[1] to f.name } }
            .filter { it.first !in allowed }
        assertEquals("hosts outside the allowed set", emptyList<Pair<String, String>>(), found)
    }

    @Test
    fun exactlyOnePlaceOpensANetworkConnection() {
        val opens = sources.filter { code(it).contains("openConnection(") }.map { it.name }
        assertEquals(listOf("SnapshotStore.kt"), opens)
        val other = Regex("""\b(OkHttp|Retrofit|Ktor|Volley|WebView|HttpClient|Socket\()""")
        assertEquals(emptyList<String>(), sources.filter { other.containsMatchIn(code(it)) }.map { it.name })
    }

    @Test
    fun noTrackingOrPlayServicesLibraryIsLinked() {
        val build = File(android, "gradle/libs.versions.toml").readText() + File(android, "app/build.gradle.kts").readText() +
            File(android, "core/build.gradle.kts").readText() + File(android, "build.gradle.kts").readText()
        // DECISIONS 0018: no Google Play code at all (Play services, Play Core, In-App Review, Firebase).
        assertTrue("a Google Play library is in the build", !build.contains("com.google.android.play") && !build.contains("com.google.android.gms") && !build.contains("com.google.firebase"))
        for (banned in listOf("firebase", "crashlytics", "play-services", "gms", "analytics", "sentry", "bugsnag", "admob", "ads", "facebook", "appsflyer", "adjust", "amplitude", "mixpanel", "segment", "play:review", "play:core")) {
            assertTrue("$banned appears in the build", !Regex("""(?i)["':./-]$banned\b""").containsMatchIn(build))
        }
    }

    @Test
    fun theManifestAsksOnlyForTheListedPermissions() {
        val manifest = File(android, "app/src/main/AndroidManifest.xml").readText()
        val permissions = Regex("""uses-permission android:name="([^"]+)"""").findAll(manifest).map { it.groupValues[1] }.toSet()
        assertEquals(
            setOf("android.permission.INTERNET", "android.permission.ACCESS_NETWORK_STATE", "android.permission.POST_NOTIFICATIONS"),
            permissions,
        )
        // Nothing of what someone follows goes to cloud backup.
        val rules = File(android, "app/src/main/res/xml/data_extraction_rules.xml").readText()
        assertTrue(rules.substringAfter("<cloud-backup>").substringBefore("</cloud-backup>").let { !it.contains("<include") })
    }

    @Test
    fun onlyAirInstantReadsTheAirstamp() {
        val readers = sources.filter { it.name != "Snapshot.kt" && Regex("""\.airstamp\b""").containsMatchIn(code(it)) }.map { it.name }
        assertEquals(emptyList<String>(), readers)
    }

    @Test
    fun remindersAndTheWidgetNeverReadDeathData() {
        for (name in listOf("EpisodeReminders.kt", "UpNext.kt", "ReminderScheduler.kt", "UpNextWidget.kt")) {
            val file = sources.first { it.name == name }
            val text = code(file)
            for (word in listOf(".death", "died", "deathKnown", "isRecorded", "cliches")) {
                assertTrue("$name reads $word", !text.contains(word))
            }
        }
    }

    @Test
    fun theOneFetchUrlIsTheContractUrl() {
        assertEquals("https://chelseakr.github.io/queer-tv-guide/snapshot.v1.json", Endpoints.SNAPSHOT_URL)
        val ios = File(Repo.root, "ios/GuideCore/Sources/GuideCore/SnapshotEndpoint.swift").readText()
        assertTrue("iOS and Android fetch the same file", ios.contains(Endpoints.SNAPSHOT_URL))
    }
}
