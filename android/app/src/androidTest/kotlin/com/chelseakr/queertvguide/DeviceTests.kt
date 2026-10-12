package com.chelseakr.queertvguide

import android.content.Intent
import android.net.Uri
import android.text.format.DateFormat
import androidx.compose.material3.Text
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.junit4.v2.createEmptyComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chelseakr.queertvguide.core.DateText
import com.chelseakr.queertvguide.core.EpisodeReminders
import com.chelseakr.queertvguide.core.Presentation
import com.chelseakr.queertvguide.core.SnapshotDecoder
import com.chelseakr.queertvguide.ui.QueerFrameTheme
import com.chelseakr.queertvguide.ui.SpoilerReveal
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.time.Instant
import java.time.ZoneId
import java.util.Locale

/**
 * While the reveal is closed, the answer is not in the semantics tree at
 * all, so TalkBack cannot read it; after the tap it is (iOS checks the same
 * under VoiceOver in AccessibilityAuditTests).
 */
@RunWith(AndroidJUnit4::class)
class SpoilerRevealTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun aClosedAnswerIsNotInTheTreeTalkBackReads() {
        compose.setContent {
            QueerFrameTheme { SpoilerReveal("Reveals whether a death is recorded.") { Text("Yes. Odile Brandt dies (2017).") } }
        }
        compose.onNodeWithText("Odile Brandt", substring = true, useUnmergedTree = true).assertDoesNotExist()
        compose.onNodeWithTag("spoiler-answer", useUnmergedTree = true).assertDoesNotExist()
        compose.onNodeWithTag("spoiler-reveal").performClick()
        compose.onNodeWithText("Odile Brandt", substring = true, useUnmergedTree = true).assertIsDisplayed()
    }
}

/**
 * The parity file again, on the device: Android's own skeleton patterns
 * (`DateFormat.getBestDateTimePattern`) and the device's ICU date formats
 * give the reminder words and next-episode sentences GuideCore gives, in
 * every zone the file covers.
 */
@RunWith(AndroidJUnit4::class)
class DeviceDateParityTest {
    @Test
    fun theDevicesFormatsGiveGuideCoresWords() {
        val assets = InstrumentationRegistry.getInstrumentation().context.assets
        val golden = Json.parseToJsonElement(assets.open("parity.golden.json").bufferedReader().readText()).jsonObject
        val fixture = Json.parseToJsonElement(assets.open("snapshot.fixture.json").bufferedReader().readText()).jsonObject
        val favorites = golden["favorites"]!!.jsonArray.map { it.jsonPrimitive.content }
        var compared = 0
        val mismatches = mutableListOf<String>()
        for (v in golden["variants"]!!.jsonArray) {
            val variant = v.jsonObject
            if (variant.containsKey("night_shift_edit")) continue
            val edit = variant["edit"]!!.jsonObject
            val shows = fixture["shows"]!!.jsonArray.toMutableList()
            val show0 = shows[0].jsonObject
            val schedule = show0["schedule"]!!.jsonObject
            val episode = JsonObject(schedule["next_episode"]!!.jsonObject + edit)
            shows[0] = JsonObject(show0 + ("schedule" to JsonObject(schedule + ("next_episode" to episode))))
            val snapshot = SnapshotDecoder.decode(JsonObject(fixture + ("shows" to kotlinx.serialization.json.JsonArray(shows))).toString().toByteArray())
            for ((zone, byClock) in variant["by_zone"]!!.jsonObject) {
                val text = DateText(Locale.US, ZoneId.of(zone)) { skeleton, locale -> DateFormat.getBestDateTimePattern(locale, skeleton) }
                for ((clock, case) in byClock.jsonObject) {
                    val now = Instant.parse(clock)
                    val plan = EpisodeReminders.plan(favorites, snapshot, now, text)
                    val expected = case.jsonObject["reminders"]!!.jsonArray.map { it.jsonObject["body"]!!.jsonPrimitive.content }
                    if (expected != plan.map { it.body }) mismatches += "${variant["name"]} $zone $clock: $expected vs ${plan.map { it.body }}"
                    val sentence = case.jsonObject["next_episode"]!!.jsonObject["lwtv:show:101"]!!
                    val got = Presentation.nextEpisode(snapshot.show("lwtv:show:101")!!.schedule, now, text)
                    if (sentence !is JsonNull && sentence.jsonPrimitive.content != got) mismatches += "${variant["name"]} $zone $clock: ${sentence.jsonPrimitive.content} vs $got"
                    compared += 1
                }
            }
        }
        assertTrue("only $compared cases", compared >= 60)
        assertEquals("device formatting differs from GuideCore:\n" + mismatches.take(10).joinToString("\n"), 0, mismatches.size)
    }
}

/** `queerframe://show/<id>` opens that show on Favorites, as on iOS. */
@RunWith(AndroidJUnit4::class)
class DeepLinkTest {
    @get:Rule val compose = createEmptyComposeRule()

    @Test
    fun aShowLinkOpensTheShow() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val snapshot = SnapshotDecoder.decode(context.assets.open("snapshot.v1.json"))
        val show = snapshot.shows.first { it.title.length in 4..30 }
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse("queerframe://show/${show.id}"), context, MainActivity::class.java)
            .putExtra("qf.onboardingSeen", true)
        ActivityScenario.launch<MainActivity>(intent).use {
            compose.waitUntil(30_000) { compose.onAllNodesWithTextCount(show.title) > 0 }
            compose.onNodeWithTag("spoiler-reveal").assertExists()
            compose.onNodeWithTag("lezwatch-source-link").assertExists()
        }
    }
}

private fun androidx.compose.ui.test.junit4.ComposeTestRule.onAllNodesWithTextCount(text: String): Int =
    onAllNodes(androidx.compose.ui.test.hasText(text)).fetchSemanticsNodes().size

/**
 * The one GET's User-Agent is the app's own, "QueerFrame/<version> (Android)",
 * and carries nothing about this device: not its model, Android version or
 * build, nor the platform's default "Dalvik/... (Linux; U; Android ...)".
 */
@RunWith(AndroidJUnit4::class)
class UserAgentDeviceTest {
    @Test
    fun theRequestNamesNoModelVersionOrBuild() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val agent = context.appModel.snapshotRequest().headers.getValue("User-Agent")
        assertEquals("QueerFrame/${BuildConfig.VERSION_NAME} (Android)", agent)
        for (leak in listOf(android.os.Build.MODEL, android.os.Build.DEVICE, android.os.Build.PRODUCT, android.os.Build.ID, android.os.Build.VERSION.RELEASE, android.os.Build.VERSION.SDK_INT.toString(), "Dalvik", "Linux")) {
            assertTrue("User-Agent '$agent' carries '$leak'", leak.isBlank() || !agent.contains(leak))
        }
    }
}
