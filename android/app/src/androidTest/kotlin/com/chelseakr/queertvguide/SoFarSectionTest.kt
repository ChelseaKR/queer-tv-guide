package com.chelseakr.queertvguide

import android.content.Context
import android.graphics.Bitmap
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsNode
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.isRoot
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performSemanticsAction
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.chelseakr.queertvguide.core.FavoritesStore
import com.chelseakr.queertvguide.core.KeyValueStore
import com.chelseakr.queertvguide.core.SnapshotDecoder
import com.chelseakr.queertvguide.core.SnapshotStore
import com.chelseakr.queertvguide.core.SoFar
import com.chelseakr.queertvguide.core.WatchPositionStore
import com.chelseakr.queertvguide.ui.QueerFrameTheme
import com.chelseakr.queertvguide.ui.ShowScreen
import com.chelseakr.queertvguide.ui.SoFarSection
import com.chelseakr.queertvguide.ui.SoFarTags
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.time.Instant

/**
 * "Has anyone died so far?" on a device (DECISIONS 0044), the twin of the iOS
 * AccessibilityAuditTests for 0043. On GuideCore's hand-made placements
 * fixture (invented shows and names), read in place from the test assets: the
 * published snapshot does not carry placements yet. In it, The Cartographers
 * has one recorded death, in season 2, episode 7.
 *
 * Both answers are out of the semantics tree TalkBack reads until their own
 * tap; the later one appears only after the first; each says only its side of
 * the viewer; a new place closes both. At the default and the largest font
 * scale.
 */
@RunWith(AndroidJUnit4::class)
class SoFarSectionTest {
    @get:Rule val compose = createComposeRule()

    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val cartographers = "lwtv:show:102"

    private fun asset(name: String): ByteArray = instrumentation.context.assets.open(name).use { it.readBytes() }

    private val placements by lazy { SnapshotDecoder.decode(asset("snapshot.placements.fixture.json")) }

    private class MapStorage : KeyValueStore {
        val map = HashMap<String, String>()
        override fun getString(key: String): String? = map[key]
        override fun putString(key: String, value: String?) {
            if (value == null) map.remove(key) else map[key] = value
        }
    }

    private fun setSection(store: WatchPositionStore, fontScale: Float? = null) {
        val show = placements.show(cartographers)!!
        // In a scrolling column, as on the show screen: unscrolled, the bottom of the section is
        // squeezed into what is left of the screen at the largest scale (the clipping check caught it).
        compose.setContent {
            Scaled(fontScale) {
                QueerFrameTheme(dark = false) {
                    Column(Modifier.verticalScroll(rememberScrollState())) { SoFarSection(store, show, placements.charactersInShow(show.id)) }
                }
            }
        }
    }

    @Composable
    private fun Scaled(fontScale: Float?, content: @Composable () -> Unit) {
        if (fontScale == null) return content()
        val density = LocalDensity.current
        CompositionLocalProvider(LocalDensity provides Density(density.density, fontScale)) { content() }
    }

    /** Every text and description in the tree, merged or not: what TalkBack could reach. */
    private fun readableText(): List<String> {
        val out = mutableListOf<String>()
        fun walk(node: SemanticsNode) {
            node.config.getOrNull(SemanticsProperties.Text)?.forEach { out += it.text }
            node.config.getOrNull(SemanticsProperties.ContentDescription)?.let { out += it }
            node.config.getOrNull(SemanticsProperties.StateDescription)?.let { out += it }
            node.children.forEach(::walk)
        }
        walk(compose.onNode(isRoot()).fetchSemanticsNode())
        return out
    }

    private fun description(tag: String): String {
        // The answer's one TalkBack stop is the reveal's only child.
        val node = compose.onNodeWithTag(tag, useUnmergedTree = true).fetchSemanticsNode()
        val described = generateSequence(listOf(node)) { level -> level.flatMap { it.children }.takeIf { it.isNotEmpty() } }
            .flatten()
            .firstNotNullOf { it.config.getOrNull(SemanticsProperties.ContentDescription)?.firstOrNull() }
        return described
    }

    private fun stepTo(tag: String, target: Int) {
        compose.onNodeWithTag(tag).performSemanticsAction(SemanticsActions.SetProgress) { it(target.toFloat()) }
        compose.waitForIdle()
        assertEquals(listOf("$target"), listOfNotNull(compose.onNodeWithTag(tag).fetchSemanticsNode().config.getOrNull(SemanticsProperties.StateDescription)))
    }

    private fun gone(tag: String) = compose.onAllNodesWithTag(tag, useUnmergedTree = true).fetchSemanticsNodes().isEmpty()

    private fun runTheSequence(store: WatchPositionStore) {
        // By touch: the plus button, then TalkBack's adjust action.
        compose.onNodeWithTag("${SoFarTags.SEASON}-increment", useUnmergedTree = true).performClick()
        compose.onNodeWithTag("${SoFarTags.SEASON}-increment", useUnmergedTree = true).assertIsNotEnabled()
        stepTo(SoFarTags.EPISODE, 6)

        assertTrue("the closed so-far answer is in the tree", gone(SoFarTags.ANSWER))
        assertTrue("the later answer is in the tree", gone(SoFarTags.LATER_ANSWER))
        assertTrue("the later reveal shows before the so-far one is opened", gone(SoFarTags.LATER_REVEAL))
        val closedTree = readableText()
        assertTrue("the tree read came back nearly empty, so it proves nothing: $closedTree", closedTree.size > 5)
        assertEquals("the death's place is readable before any reveal", emptyList<String>(), closedTree.filter { it.contains("season 2, episode 7") || it.contains("Odile") })

        compose.onNodeWithTag(SoFarTags.REVEAL).performScrollToIfScrollable().performClick()
        compose.onNodeWithTag(SoFarTags.ANSWER, useUnmergedTree = true).assertExists()
        val soFar = description(SoFarTags.ANSWER)
        assertTrue(soFar, soFar.startsWith("Not recorded through season 2, episode 6."))
        assertFalse("a later death is in the so-far answer: $soFar", soFar.contains("Odile"))
        assertTrue(soFar, soFar.endsWith("not that they stay dead."))
        compose.onNodeWithTag(SoFarTags.LATER_REVEAL).assertExists()
        assertTrue("the later answer opened with the first tap", gone(SoFarTags.LATER_ANSWER))
        assertFalse("the later death is readable before its own tap", readableText().any { it.contains("season 2, episode 7") })

        compose.onNodeWithTag(SoFarTags.LATER_REVEAL).performScrollToIfScrollable().performClick()
        val later = description(SoFarTags.LATER_ANSWER)
        assertTrue(later, later.contains("Odile Brandt: season 2, episode 7."))

        // One more episode: both answers close, then say it is so far.
        stepTo(SoFarTags.EPISODE, 7)
        assertTrue("a new place left the old answer open", gone(SoFarTags.ANSWER))
        assertTrue(gone(SoFarTags.LATER_ANSWER))
        assertTrue(gone(SoFarTags.LATER_REVEAL))
        compose.onNodeWithTag(SoFarTags.REVEAL).performScrollToIfScrollable().performClick()
        val now = description(SoFarTags.ANSWER)
        assertTrue(now, now.startsWith("Yes. 1 recorded death through season 2, episode 7."))
        assertEquals("kept on the device", SoFar.Position(2, 7), store.position(cartographers))
    }

    private fun SemanticsNodeInteraction.performScrollToIfScrollable(): SemanticsNodeInteraction =
        apply { runCatching { performScrollTo() } }

    @Test
    fun theAnswersAreClosedUntilTappedAndANewPlaceClosesThem() {
        val store = WatchPositionStore(MapStorage())
        setSection(store)
        runTheSequence(store)
    }

    @Test
    fun eachStepperIsOneAdjustableElementFromLezWatchsSeasonCount() {
        setSection(WatchPositionStore(MapStorage()))
        val season = compose.onNodeWithTag(SoFarTags.SEASON).fetchSemanticsNode().config
        assertEquals("Season", season[SemanticsProperties.ContentDescription].single())
        assertEquals("1", season[SemanticsProperties.StateDescription])
        // The Cartographers: 2 LezWatch.TV seasons, not on air; its TVmaze list has 3, which the picker never reads.
        val range = season[SemanticsProperties.ProgressBarRangeInfo]
        assertEquals(1f..2f, range.range)
        assertEquals(SoFar.EPISODE_RANGE.last.toFloat(), compose.onNodeWithTag(SoFarTags.EPISODE).fetchSemanticsNode().config[SemanticsProperties.ProgressBarRangeInfo].range.endInclusive)
        // The label and the two buttons are for touch only, not separate TalkBack stops.
        for (tag in listOf("${SoFarTags.SEASON}-increment", "${SoFarTags.SEASON}-decrement")) {
            val config = compose.onNodeWithTag(tag, useUnmergedTree = true).fetchSemanticsNode().config
            assertTrue("$tag is a TalkBack stop", config.contains(SemanticsProperties.HideFromAccessibility))
        }
        compose.onNodeWithTag("${SoFarTags.SEASON}-decrement", useUnmergedTree = true).assertIsNotEnabled()
    }

    @Test
    fun aStoredPlaceIsReadBackAndClampedToThePicker() {
        val storage = MapStorage()
        WatchPositionStore(storage).set(SoFar.Position(40, 2000), cartographers)
        setSection(WatchPositionStore(storage))
        assertEquals("2", compose.onNodeWithTag(SoFarTags.SEASON).fetchSemanticsNode().config[SemanticsProperties.StateDescription])
        assertEquals("999", compose.onNodeWithTag(SoFarTags.EPISODE).fetchSemanticsNode().config[SemanticsProperties.StateDescription])
        assertTrue(gone(SoFarTags.ANSWER))
    }

    @Test
    fun atTheLargestFontScaleNothingIsClippedAndTargetsStayLarge() {
        val store = WatchPositionStore(MapStorage())
        setSection(store, fontScale = 2f)
        // Stacked: the label sits above its buttons, so neither is squeezed.
        val label = compose.onNode(androidx.compose.ui.test.hasText("Season 1"), useUnmergedTree = true).fetchSemanticsNode().boundsInRoot
        val plus = compose.onNodeWithTag("${SoFarTags.SEASON}-increment", useUnmergedTree = true).fetchSemanticsNode().boundsInRoot
        assertTrue("label $label and buttons $plus are side by side at the largest scale", plus.top >= label.bottom)
        runTheSequence(store)
        compose.onNodeWithTag(SoFarTags.LATER_REVEAL).performClick()
        assertNothingClippedAndTargetsAtLeast48dp()
    }

    @Test
    fun atTheDefaultFontScaleNothingIsClippedAndTargetsStayLarge() {
        setSection(WatchPositionStore(MapStorage()))
        compose.onNodeWithTag(SoFarTags.REVEAL).performClick()
        compose.onNodeWithTag(SoFarTags.LATER_REVEAL).performClick()
        assertNothingClippedAndTargetsAtLeast48dp()
    }

    /** Each text lays out without overflow or an ellipsis, and each tappable thing is at least 48dp each way. */
    private fun assertNothingClippedAndTargetsAtLeast48dp() {
        compose.waitForIdle()
        val section = compose.onNodeWithTag(SoFarTags.SECTION, useUnmergedTree = true).fetchSemanticsNode()
        val minPx = 48 * instrumentation.targetContext.resources.displayMetrics.density - 1
        var texts = 0
        var targets = 0
        fun walk(node: SemanticsNode) {
            node.config.getOrNull(SemanticsActions.GetTextLayoutResult)?.action?.let { get ->
                val results = mutableListOf<TextLayoutResult>()
                get(results)
                results.forEach { r ->
                    // Height, and each line's drawn right edge against the laid-out width.
                    // (`hasVisualOverflow` also compares the paragraph's own width, the full
                    // constraint, with the text's wrapped size, which reads as overflow for any short line.)
                    assertFalse("clipped: ${r.layoutInput.text} is taller than its box", r.didOverflowHeight)
                    for (line in 0 until r.lineCount) {
                        assertTrue("clipped: ${r.layoutInput.text} line $line runs past its box", r.getLineRight(line) <= r.size.width + 1f)
                    }
                    for (line in 0 until r.lineCount) assertFalse("ellipsized: ${r.layoutInput.text}", r.isLineEllipsized(line))
                    texts += 1
                }
            }
            if (node.config.contains(SemanticsActions.OnClick)) {
                val size = node.touchBoundsInRoot
                assertTrue("target ${node.config} is ${size.width}x${size.height}px", size.width >= minPx && size.height >= minPx)
                targets += 1
            }
            node.children.forEach(::walk)
        }
        walk(section)
        assertTrue("only $texts texts laid out", texts >= 6)
        assertTrue("only $targets targets", targets >= 4)
    }
}

/**
 * The section on the real show screen: there for a snapshot that places
 * deaths (whatever the show), absent for an older one. Also writes the review
 * screenshots to the app's external files directory ("so-far-*.png").
 */
@RunWith(AndroidJUnit4::class)
class SoFarShowScreenTest {
    @get:Rule val compose = createComposeRule()

    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context: Context = instrumentation.targetContext
    private val shots = File(context.getExternalFilesDir(null), "screenshots").apply { mkdirs() }

    private fun model(fixture: String): AppModel {
        val bytes = instrumentation.context.assets.open(fixture).use { it.readBytes() }
        val dir = File(context.cacheDir, "so-far-${System.nanoTime()}").apply { mkdirs() }
        val storage = object : KeyValueStore {
            val map = HashMap<String, String>()
            override fun getString(key: String): String? = map[key]
            override fun putString(key: String, value: String?) {
                if (value == null) map.remove(key) else map[key] = value
            }
        }
        // The fixture's own day, so it is not shown as stale data.
        val model = AppModel(
            context = context,
            store = SnapshotStore(dir) { bytes },
            favorites = FavoritesStore(storage),
            watchPositions = WatchPositionStore(storage),
            prefs = context.getSharedPreferences("so-far-test", Context.MODE_PRIVATE),
            now = { Instant.parse("2026-09-13T21:00:00Z") },
            forcedProblem = { null },
        )
        runBlocking { model.loadInitial() }
        return model
    }

    private fun show(model: AppModel, id: String, fontScale: Float? = null) {
        compose.setContent {
            val state by model.state.collectAsState()
            val content = @Composable { QueerFrameTheme { ShowScreen(model, state, id, canGoBack = true, onBack = {}, open = {}) } }
            if (fontScale == null) {
                content()
            } else {
                val density = LocalDensity.current
                CompositionLocalProvider(LocalDensity provides Density(density.density, fontScale)) { content() }
            }
        }
    }

    private fun shot(name: String) {
        compose.waitForIdle()
        Thread.sleep(700)
        val bitmap: Bitmap = instrumentation.uiAutomation.takeScreenshot()
        File(shots, "so-far-$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    @Test
    fun theSectionIsOnTheShowScreenForAPlacedSnapshotOnly() {
        val placed = model("snapshot.placements.fixture.json")
        // Night Shift Radio has no recorded death and no episode list: the section shows all the same.
        show(placed, "lwtv:show:104")
        compose.onNodeWithTag(SoFarTags.SECTION).assertExists()
    }

    @Test
    fun anOlderSnapshotHasNoSection() {
        show(model("snapshot.fixture.json"), "lwtv:show:102")
        compose.onNodeWithTag("spoiler-reveal").assertExists()
        assertTrue(compose.onAllNodesWithTag(SoFarTags.SECTION, useUnmergedTree = true).fetchSemanticsNodes().isEmpty())
    }

    @Test
    fun screenshots() {
        val model = model("snapshot.placements.fixture.json")
        show(model, "lwtv:show:102")
        compose.onNodeWithTag(SoFarTags.REVEAL).performScrollTo()
        compose.onNodeWithTag("${SoFarTags.SEASON}-increment", useUnmergedTree = true).performScrollTo().performClick()
        compose.onNodeWithTag(SoFarTags.EPISODE).performSemanticsAction(SemanticsActions.SetProgress) { it(6f) }
        compose.onNode(hasTestTag(SoFarTags.SECTION)).performScrollTo()
        shot("1-closed")
        compose.onNodeWithTag(SoFarTags.REVEAL).performClick()
        compose.onNodeWithTag(SoFarTags.LATER_REVEAL).performScrollTo()
        shot("2-so-far-open")
        compose.onNodeWithTag(SoFarTags.LATER_REVEAL).performClick()
        compose.onNodeWithTag(SoFarTags.LATER_ANSWER, useUnmergedTree = true).performScrollTo()
        shot("3-later-open")
        compose.onNodeWithTag(SoFarTags.LATER_ANSWER, useUnmergedTree = true).assertIsDisplayed()
    }

    @Test
    fun screenshotAtTheLargestFontScale() {
        val model = model("snapshot.placements.fixture.json")
        show(model, "lwtv:show:102", fontScale = 2f)
        compose.onNodeWithTag(SoFarTags.EPISODE).performSemanticsAction(SemanticsActions.SetProgress) { it(7f) }
        // Scrolled into view first: a tap off screen lands nowhere.
        compose.onNodeWithTag("${SoFarTags.SEASON}-increment", useUnmergedTree = true).performScrollTo().performClick()
        assertEquals("2", compose.onNodeWithTag(SoFarTags.SEASON).fetchSemanticsNode().config[SemanticsProperties.StateDescription])
        compose.onNodeWithTag(SoFarTags.REVEAL).performScrollTo().performClick()
        compose.onNodeWithTag(SoFarTags.ANSWER, useUnmergedTree = true).performScrollTo()
        shot("4-largest-font-open")
    }
}
