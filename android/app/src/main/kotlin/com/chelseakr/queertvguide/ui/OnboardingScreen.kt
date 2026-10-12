package com.chelseakr.queertvguide.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.HelpOutline
import androidx.compose.material.icons.automirrored.filled.LibraryBooks
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Tv
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.chelseakr.queertvguide.R
import com.chelseakr.queertvguide.core.Attribution
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.launch

/**
 * The first-run pages: a welcome page, then how spoilers are kept closed,
 * what "not recorded" means, where the data comes from, and what the app
 * does not collect (the iOS pager on the parity branch, page for page).
 * Next and Back are real buttons, so nobody needs the swipe; a swipe works
 * too, and each change of page is a light tick. TalkBack hears "Page 2 of 5".
 * With animations removed in system settings, pages change without the slide.
 * Skippable from the first moment; About opens it again.
 */
@Composable
fun OnboardingScreen(isFirstRun: Boolean, finish: () -> Unit) {
    val name = stringResource(R.string.app_name)
    val pages = listOf(
        Page("onboarding-welcome", Icons.Filled.Tv, "Welcome to $name", "A spoiler-safe guide to queer characters on TV. Here is how it works, in four short pages."),
        Page(
            "onboarding-point-spoilers",
            Icons.Filled.VisibilityOff,
            "Spoilers stay closed",
            "Whether a character dies is behind a Reveal button on every show and character. Until you open it, nothing on the screen gives the answer away, and TalkBack cannot read it either. Plot notes stay folded too.",
        ),
        Page(
            "onboarding-point-not-recorded",
            Icons.AutoMirrored.Filled.HelpOutline,
            "“Not recorded” is not “no”",
            "LezWatch.TV records deaths, not survival. When no death is recorded, the app says “Not recorded”. It never tells you a character lives.",
        ),
        Page(
            "onboarding-point-sources",
            Icons.AutoMirrored.Filled.LibraryBooks,
            "Where the data comes from",
            "Shows, characters and ratings come from LezWatch.TV, a community-run database. Episode schedules come from TVmaze, under CC BY-SA 4.0. Every show and character links back to its LezWatch.TV page. ${Attribution.NON_ENDORSEMENT}",
        ),
        Page(
            "onboarding-point-privacy",
            Icons.Filled.Lock,
            "Nothing about you leaves this device",
            "No account, no analytics, no tracking. Favorites stay on this device. The app downloads one data file, the same file for everyone.",
        ),
    )
    val pager = rememberPagerState { pages.size }
    val scope = rememberCoroutineScope()
    val haptics = LocalHapticFeedback.current
    val reduceMotion = LocalReduceMotion.current
    val large = LocalDensity.current.fontScale >= 1.6f
    LaunchedEffect(pager) {
        snapshotFlow { pager.currentPage }.drop(1).collect { haptics.performHapticFeedback(HapticFeedbackType.SegmentTick) }
    }
    fun go(page: Int) {
        val target = page.coerceIn(0, pages.size - 1)
        scope.launch { if (reduceMotion) pager.scrollToPage(target) else pager.animateScrollToPage(target) }
    }
    val last = pager.currentPage == pages.size - 1

    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxSize().safeDrawingPadding()) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), horizontalArrangement = Arrangement.End) {
                // Kept on the last page too, so the corner never jumps; there, the main button does the same.
                if (!(last && isFirstRun)) {
                    TextButton(onClick = finish, modifier = Modifier.heightIn(min = 48.dp).testTag("onboarding-skip")) {
                        Text(if (isFirstRun) "Skip" else "Close", fontWeight = FontWeight.SemiBold)
                    }
                } else {
                    Box(Modifier.heightIn(min = 48.dp))
                }
            }
            HorizontalPager(state = pager, modifier = Modifier.weight(1f).fillMaxWidth()) { index ->
                val page = pages[index]
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
                    Column(
                        Modifier
                            .widthIn(max = 560.dp)
                            .fillMaxWidth()
                            .verticalScroll(rememberScrollState())
                            .padding(horizontal = 24.dp, vertical = 16.dp)
                            .testTag(page.tag)
                            .semantics { stateDescription = "Page ${index + 1} of ${pages.size}" },
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        Icon(page.icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(56.dp))
                        Text(page.title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
                        Text(page.body, style = MaterialTheme.typography.bodyLarge)
                    }
                }
            }
            Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                PageIndicator(count = pages.size, current = pager.currentPage, onSelect = ::go)
                val back: @Composable (Modifier) -> Unit = { m ->
                    OutlinedButton(onClick = { go(pager.currentPage - 1) }, modifier = m.heightIn(min = 52.dp)) { Text("Back") }
                }
                val forward: @Composable (Modifier) -> Unit = { m ->
                    Button(
                        onClick = { if (last) finish() else go(pager.currentPage + 1) },
                        modifier = m.heightIn(min = 52.dp).testTag(if (last) "onboarding-finish" else "onboarding-next"),
                    ) { Text(if (!last) "Next" else if (isFirstRun) "Start browsing" else "Done") }
                }
                // Side by side; stacked at the largest font sizes.
                if (large) {
                    forward(Modifier.fillMaxWidth())
                    if (pager.currentPage > 0) back(Modifier.fillMaxWidth())
                } else {
                    Row(Modifier.widthIn(max = 560.dp).fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        if (pager.currentPage > 0) back(Modifier.weight(1f))
                        forward(Modifier.weight(1f))
                    }
                }
            }
        }
    }
}

private data class Page(val tag: String, val icon: ImageVector, val title: String, val body: String)

/** Dots that are also buttons (48 dp targets): "Page 2 of 5", and a tap goes there. */
@Composable
private fun PageIndicator(count: Int, current: Int, onSelect: (Int) -> Unit) {
    Row(
        Modifier.clearAndSetSemantics { contentDescription = "Page ${current + 1} of $count" },
        horizontalArrangement = Arrangement.Center,
    ) {
        repeat(count) { i ->
            Box(Modifier.sizeIn(minWidth = 32.dp, minHeight = 48.dp).clickable { onSelect(i) }, contentAlignment = Alignment.Center) {
                Box(
                    Modifier
                        .size(if (i == current) 10.dp else 8.dp)
                        .background(if (i == current) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline, CircleShape),
                )
            }
        }
    }
}
