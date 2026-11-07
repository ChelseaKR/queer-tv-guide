package com.chelseakr.queertvguide.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.hideFromAccessibility
import androidx.compose.ui.semantics.progressBarRangeInfo
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.setProgress
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.chelseakr.queertvguide.core.Character
import com.chelseakr.queertvguide.core.Show
import com.chelseakr.queertvguide.core.SoFar
import com.chelseakr.queertvguide.core.WatchPositionStore
import kotlin.math.roundToInt

/** Test tags, shared with the on-device tests (SoFarSectionTest). */
object SoFarTags {
    const val SECTION = "so-far-section"
    const val SEASON = "so-far-season"
    const val EPISODE = "so-far-episode"
    const val REVEAL = "so-far-reveal"
    const val ANSWER = "so-far-answer"
    const val LATER_REVEAL = "later-deaths-reveal"
    const val LATER_ANSWER = "later-deaths-answer"
}

/**
 * "Has anyone died so far?" (DECISIONS 0043 for iOS, 0044 here), under the
 * show's own reveal. The viewer says where they are; the deaths up to there
 * are behind one tap, and the deaths after it behind a second tap that only
 * appears once the first is open. Changing the place closes both again. The
 * twin of iOS's `SoFarSection`; [SoFar.answer] decides every word.
 *
 * Before any tap, nothing here depends on whether the show has a death: the
 * picker's ranges come from LezWatch.TV's season count (already on the
 * screen), never from the episode list, which exists only for shows with a
 * death ([SoFar.seasonRange]). The answers are not composed while closed, so
 * TalkBack cannot read them ([SpoilerReveal]).
 *
 * Where the viewer is stays on this device ([WatchPositionStore]).
 */
@Composable
fun SoFarSection(store: WatchPositionStore, show: Show, cast: List<Character>) {
    var position by remember(show.id) { mutableStateOf(SoFar.clamped(store.position(show.id) ?: SoFar.Position.START, show)) }
    var soFarOpen by rememberSaveable(show.id) { mutableStateOf(false) }
    var laterOpen by rememberSaveable(show.id) { mutableStateOf(false) }

    fun move(to: SoFar.Position) {
        if (to == position) return
        position = to
        store.set(to, show.id)
        // A new place closes both answers: what was open was for the old one.
        soFarOpen = false
        laterOpen = false
    }

    Column(Modifier.fillMaxWidth().testTag(SoFarTags.SECTION), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        SectionHeading("Has anyone died so far?")
        Text(
            "Where are you?",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.semantics { heading() },
        )
        PositionStepper("Season", position.season, SoFar.seasonRange(show), SoFarTags.SEASON) { move(SoFar.Position(it, position.episode)) }
        PositionStepper("Episode", position.episode, SoFar.EPISODE_RANGE, SoFarTags.EPISODE) { move(SoFar.Position(position.season, it)) }
        Text("Kept on this device only.", style = MaterialTheme.typography.bodySmall, color = subdued)
        SpoilerReveal(
            revealedHint = "Reveals recorded deaths in ${show.title} up to ${position.spoken}.",
            prompt = "Reveal deaths so far",
            tag = SoFarTags.REVEAL,
            answerTag = SoFarTags.ANSWER,
            revealed = soFarOpen,
            onRevealedChange = { soFarOpen = it },
        ) {
            val a = SoFar.answer(show, cast, position)
            Column(
                Modifier.fillMaxWidth().clearAndSetSemantics { contentDescription = a.spoken + " " + a.footer },
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text(a.headline)
                a.soFar.forEach { Text(it) }
                a.uncertain.forEach { Text(it) }
                a.notes.forEach { Text(it, style = MaterialTheme.typography.bodyMedium, color = subdued) }
                Text(a.footer, style = MaterialTheme.typography.bodySmall, color = subdued)
            }
        }
        if (soFarOpen) {
            SpoilerReveal(
                revealedHint = "Reveals recorded deaths after ${position.spoken}. This may spoil what's ahead.",
                prompt = "Reveal later deaths",
                tag = SoFarTags.LATER_REVEAL,
                answerTag = SoFarTags.LATER_ANSWER,
                revealed = laterOpen,
                onRevealedChange = { laterOpen = it },
            ) {
                val a = SoFar.answer(show, cast, position)
                Column(
                    Modifier.fillMaxWidth().clearAndSetSemantics { contentDescription = a.laterSpoken },
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Text(a.laterHeadline)
                    a.later.forEach { Text(it) }
                }
            }
        }
    }
}

/**
 * "Season 3" with minus and plus buttons: side by side, or stacked at large
 * font scales so the label is never squeezed. TalkBack hears one adjustable
 * element, "Season, 3" (swipe up or down, or the volume keys, to change it,
 * plus "Increase season" and "Decrease season" actions); the label and the
 * two buttons are for touch and are not separate stops.
 */
@Composable
private fun PositionStepper(name: String, value: Int, range: IntRange, tag: String, onChange: (Int) -> Unit) {
    val large = LocalDensity.current.fontScale >= 1.6f
    val lower = name.lowercase()
    val modifier = Modifier
        .fillMaxWidth()
        .heightIn(min = 48.dp)
        .testTag(tag)
        .semantics {
            contentDescription = name
            stateDescription = "$value"
            progressBarRangeInfo = ProgressBarRangeInfo(
                current = value.toFloat(),
                range = range.first.toFloat()..range.last.toFloat(),
                steps = (range.last - range.first - 1).coerceAtLeast(0),
            )
            setProgress(label = "Set $lower") { target ->
                val next = target.roundToInt().coerceIn(range)
                if (next != value) onChange(next)
                true
            }
            customActions = listOfNotNull(
                CustomAccessibilityAction("Increase $lower") { onChange(value + 1); true }.takeIf { value < range.last },
                CustomAccessibilityAction("Decrease $lower") { onChange(value - 1); true }.takeIf { value > range.first },
            )
        }
    val label = @Composable {
        Text("$name $value", modifier = Modifier.semantics { hideFromAccessibility() })
    }
    val buttons = @Composable {
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
            FilledTonalIconButton(
                onClick = { onChange(value - 1) },
                enabled = value > range.first,
                modifier = Modifier.testTag("$tag-decrement").semantics { hideFromAccessibility() },
            ) { Icon(Icons.Filled.Remove, contentDescription = "Decrease $lower") }
            FilledTonalIconButton(
                onClick = { onChange(value + 1) },
                enabled = value < range.last,
                modifier = Modifier.testTag("$tag-increment").semantics { hideFromAccessibility() },
            ) { Icon(Icons.Filled.Add, contentDescription = "Increase $lower") }
        }
    }
    if (large) {
        Column(modifier, verticalArrangement = Arrangement.spacedBy(4.dp)) {
            label()
            buttons()
        }
    } else {
        Row(modifier, horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) { label() }
            buttons()
        }
    }
}
