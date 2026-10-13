package com.chelseakr.queertvguide

import android.content.Intent
import android.graphics.Bitmap
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.junit4.v2.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.performTextClearance
import androidx.compose.ui.test.performTextInput
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chelseakr.queertvguide.core.FavoritesStore
import com.chelseakr.queertvguide.core.SnapshotDecoder
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * Every main screen, on real data, for the review evidence: run by
 * `android/scripts/screenshots.sh` once per device (phone, tablet) and theme
 * (light, dark). Files land in the app's external files directory and the
 * script pulls them. It asserts only that each screen was reached.
 */
@RunWith(AndroidJUnit4::class)
class ScreenshotTour {
    @get:Rule val compose = createEmptyComposeRule()

    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val prefix: String = InstrumentationRegistry.getArguments().getString("shotPrefix", "device-light")
    private val dir = File(context.getExternalFilesDir(null), "screenshots").apply { mkdirs() }

    private fun shot(name: String) {
        compose.waitForIdle()
        Thread.sleep(700)
        val bitmap: Bitmap = instrumentation.uiAutomation.takeScreenshot()
        File(dir, "$prefix-$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    private fun waitForTag(tag: String) = compose.waitUntil(30_000) { compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() }

    private fun launch(vararg extras: Pair<String, Any>): ActivityScenario<MainActivity> {
        val intent = Intent(context, MainActivity::class.java)
        for ((k, v) in extras) {
            when (v) {
                is Boolean -> intent.putExtra(k, v)
                is String -> intent.putExtra(k, v)
            }
        }
        return ActivityScenario.launch(intent)
    }

    @Test
    fun tour() {
        val snapshot = SnapshotDecoder.decode(context.assets.open("snapshot.v1.json"))
        val model = context.appModel
        model.favorites.removeAll()
        val upcoming = snapshot.shows.filter { it.schedule.nextEpisode?.airInstant != null }.take(2)
        upcoming.forEach { model.favorites.toggle(FavoritesStore.Kind.SHOW, it.id) }
        snapshot.shows.firstOrNull { !it.schedule.scheduleKnown && snapshot.charactersInShow(it.id).isNotEmpty() }?.let {
            model.favorites.toggle(FavoritesStore.Kind.SHOW, it.id)
        }
        snapshot.characters.firstOrNull { it.name == "Gabrielle" }?.let { model.favorites.toggle(FavoritesStore.Kind.CHARACTER, it.id) }

        launch("qf.onboardingSeen" to false).use {
            waitForTag("onboarding-welcome")
            shot("01-onboarding-welcome")
            compose.onNodeWithTag("onboarding-next").performClick()
            shot("02-onboarding-spoilers")
            compose.onNodeWithTag("onboarding-skip").performClick()
            waitForTag("hit")
            shot("03-search-browse")
            compose.onNodeWithTag("search-field").performTextInput("xena warrior")
            compose.waitUntil(10_000) { compose.onAllNodes(hasContentDescription("Xena", substring = true)).fetchSemanticsNodes().isNotEmpty() }
            shot("04-search-query")
            compose.onNodeWithTag("filter-button").performClick()
            waitForTag("filters-show-results")
            compose.onNodeWithTag("filter-no-recorded-deaths").performScrollTo().performClick()
            shot("05-filters")
            compose.onNodeWithTag("filter-no-recorded-deaths").performScrollTo().performClick()
            compose.onNodeWithTag("filters-show-results").performClick()
            waitForTag("hit")
            compose.onAllNodesWithTag("hit").onFirst().performClick()
            waitForTag("spoiler-reveal")
            shot("06-show")
            compose.onNodeWithTag("spoiler-reveal").performScrollTo().performClick()
            shot("07-show-revealed")
            compose.onNodeWithTag("tab-search").performClick()
            compose.onNodeWithTag("tab-search").performClick()
            waitForTag("search-field")
            compose.onNodeWithTag("search-field").performTextClearance()
            compose.onNodeWithTag("search-field").performTextInput("gabrielle")
            compose.waitUntil(10_000) { compose.onAllNodes(hasContentDescription("Gabrielle", substring = true)).fetchSemanticsNodes().isNotEmpty() }
            compose.onAllNodesWithTag("hit").onFirst().performClick()
            waitForTag("spoiler-reveal")
            shot("08-character")
            compose.onNodeWithTag("tab-favorites").performClick()
            waitForTag("favorites-list")
            shot("09-favorites")
            compose.onNodeWithTag("favorites-list").performScrollToNode(hasTestTag("reminders-switch"))
            shot("10-favorites-reminders")
            compose.onNodeWithTag("reminders-switch").performClick()
            waitForTag("reminders-accept")
            shot("11-reminder-primer")
            compose.onNodeWithTag("reminders-decline").performClick()
            compose.onNodeWithTag("tab-about").performClick()
            waitForTag("about")
            shot("12-about")
        }
        // Data past its 48-hour promise, and a refresh that failed offline:
        // the banner and the footer's words (debug-only clock and problem).
        val stale = snapshot.generatedAt.plusSeconds(4L * 24 * 3600).toString()
        launch("qf.onboardingSeen" to true, "qf.clock" to stale, "qf.refreshProblem" to "offline").use {
            waitForTag("data-freshness-warning")
            shot("13-search-stale")
            compose.onNodeWithTag("search-results").performScrollToNode(hasTestTag("data-refresh-problem"))
            shot("14-refresh-problem")
        }
    }
}
