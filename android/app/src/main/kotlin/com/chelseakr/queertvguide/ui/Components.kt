package com.chelseakr.queertvguide.ui

import androidx.core.net.toUri
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.chelseakr.queertvguide.AppModel
import com.chelseakr.queertvguide.core.Attribution
import com.chelseakr.queertvguide.core.Character
import com.chelseakr.queertvguide.core.Presentation
import com.chelseakr.queertvguide.core.Show
import com.chelseakr.queertvguide.core.Snapshot
import kotlinx.coroutines.launch

/** Opens [url] in the browser (or the app that handles it). The app itself never fetches it. */
fun openExternal(context: Context, url: String) {
    try {
        context.startActivity(Intent(Intent.ACTION_VIEW, url.toUri()).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    } catch (_: ActivityNotFoundException) {
        // No browser: nothing to open.
    }
}

/** A section heading TalkBack's headings navigation can jump between. */
@Composable
fun SectionHeading(text: String, modifier: Modifier = Modifier) {
    Text(
        text,
        style = MaterialTheme.typography.titleMedium,
        fontWeight = FontWeight.SemiBold,
        modifier = modifier.semantics { heading() },
    )
}

/** A label and its value, read as one phrase; stacked at large font scales so neither is squeezed. */
@Composable
fun LabeledValue(label: String, value: String) {
    val large = androidx.compose.ui.platform.LocalDensity.current.fontScale >= 1.6f
    val modifier = Modifier.fillMaxWidth().heightIn(min = 32.dp).semantics(mergeDescendants = true) {}
    if (large) {
        Column(modifier) {
            Text(label)
            Text(value, color = subdued)
        }
    } else {
        Row(modifier, horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(label, modifier = Modifier.weight(1f, fill = false))
            Spacer(Modifier.width(12.dp))
            Text(value, color = subdued)
        }
    }
}

/** A link-styled button opening an outside page, with a hint for TalkBack. */
@Composable
fun LinkButton(
    text: String,
    url: String,
    modifier: Modifier = Modifier,
    spoken: String? = null,
    hint: String = "Opens in your browser",
    showIcon: Boolean = true,
) {
    val context = LocalContext.current
    TextButton(
        onClick = { openExternal(context, url) },
        modifier = modifier
            .heightIn(min = 48.dp)
            .semantics {
                role = Role.Button
                spoken?.let { contentDescription = it }
                onClick(label = hint) { openExternal(context, url); true }
            },
    ) {
        if (showIcon) {
            Icon(Icons.AutoMirrored.Filled.OpenInNew, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(6.dp))
        }
        Text(text)
    }
}

/** A record's link back to its LezWatch.TV page (LezWatch.TV's terms: link back). */
@Composable
fun LezWatchSourceLink(name: String, url: String) {
    LinkButton(
        text = Attribution.LEZWATCH_LINK_TITLE,
        url = url,
        spoken = Attribution.lezWatchLinkLabel(name),
        modifier = Modifier.testTag("lezwatch-source-link"),
    )
}

/** TVmaze's credit with any TVmaze schedule data: a link to TVmaze and to the CC BY-SA 4.0 license. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun TvmazeCreditLinks(credit: Attribution.TvmazeCredit) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        LinkButton(credit.source.title, credit.source.url, hint = "Opens TVmaze in your browser", showIcon = false, modifier = Modifier.testTag("tvmaze-credit-link"))
        LinkButton(credit.license.title, credit.license.url, spoken = "License: ${credit.license.title}", hint = "Opens the license in your browser", showIcon = false, modifier = Modifier.testTag("tvmaze-license-link"))
    }
}

/**
 * A tap-to-reveal control for spoiler content ("does she die"). While
 * closed, the answer is not composed at all, so it is not in the semantics
 * tree and TalkBack cannot read it (hiding it visually would leave it
 * readable). `SpoilerRevealTest` checks this on a device. The answer is a
 * polite live region, so TalkBack reads it out as it appears, and the tap
 * gets a light haptic.
 */
@Composable
fun SpoilerReveal(revealedHint: String, content: @Composable () -> Unit) {
    var revealed by rememberSaveable { mutableStateOf(false) }
    val haptics = LocalHapticFeedback.current
    val reduceMotion = LocalReduceMotion.current
    if (!revealed) {
        FilledTonalButton(
            onClick = {
                haptics.performHapticFeedback(HapticFeedbackType.Confirm)
                revealed = true
            },
            modifier = Modifier
                .heightIn(min = 48.dp)
                .testTag("spoiler-reveal")
                .semantics { onClick(label = revealedHint) { haptics.performHapticFeedback(HapticFeedbackType.Confirm); revealed = true; true } },
        ) {
            Icon(Icons.Filled.VisibilityOff, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp))
            Text("Reveal")
        }
    } else {
        val focus = remember { FocusRequester() }
        LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }
        AnimatedVisibility(visible = true, enter = if (reduceMotion) fadeIn(initialAlpha = 1f) else fadeIn()) {
            Column(
                Modifier
                    .testTag("spoiler-answer")
                    .focusRequester(focus)
                    .semantics { liveRegion = LiveRegionMode.Polite },
            ) { content() }
        }
    }
}

/** A closed-by-default section ("may contain spoilers"); its text is not composed until opened. */
@Composable
fun Disclosure(title: String, body: String) {
    var open by rememberSaveable { mutableStateOf(false) }
    Column {
        TextButton(
            onClick = { open = !open },
            modifier = Modifier.heightIn(min = 48.dp).semantics { stateDescription = if (open) "Expanded" else "Collapsed" },
        ) {
            Text(title, modifier = Modifier.weight(1f, fill = false))
            Icon(if (open) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore, contentDescription = null)
        }
        if (open) Text(body, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(horizontal = 12.dp))
    }
}

/** The warning above a list when the data is past its 48-hour SLA, or its age is unknown (DG-04). */
@Composable
fun DataFreshnessBanner(warning: Presentation.FreshnessWarning) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp)
            .testTag("data-freshness-warning")
            .clearAndSetSemantics { contentDescription = warning.spoken },
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Icon(Icons.Filled.Warning, contentDescription = null)
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(warning.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Text(warning.detail, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

/**
 * When the data was last updated and how long ago, on every screen that reads
 * the snapshot; past its SLA the first line says so. A failed look for new
 * data says which kind of failure and that the data on screen stays, with a
 * Try again button: the same one GET as pull to refresh.
 */
@Composable
fun DataStatusFooter(model: AppModel, snapshot: Snapshot, state: AppModel.State) {
    val scope = rememberCoroutineScope()
    val text = model.dateText()
    val freshness = com.chelseakr.queertvguide.core.DataFreshness.assess(snapshot.generatedAt, state.clock)
    Column(Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Column(Modifier.semantics(mergeDescendants = true) {}) {
            Presentation.freshnessWarning(snapshot.generatedAt, freshness, text)?.let {
                Text("${it.title}.", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
            }
            Text(Presentation.dataAsOf(snapshot.generatedAt, freshness, text), style = MaterialTheme.typography.bodySmall, color = subdued)
        }
        state.problem?.let { problem ->
            Text(problem.message, style = MaterialTheme.typography.bodySmall, color = subdued, modifier = Modifier.testTag("data-refresh-problem"))
            OutlinedButton(
                onClick = { scope.launch { model.requestedRefresh() } },
                enabled = !state.refreshing,
                modifier = Modifier.heightIn(min = 48.dp).semantics {
                    onClick(label = "Checks once for a newer data file") { scope.launch { model.requestedRefresh() }; true }
                },
            ) {
                if (state.refreshing) {
                    CircularProgressIndicator(Modifier.size(18.dp).semantics { contentDescription = "Checking for new data" }, strokeWidth = 2.dp)
                } else {
                    Text("Try again")
                }
            }
        }
    }
}

/** A show in a list: title, worth-it verdict and networks, and an optional extra line. TalkBack hears all of it. */
@Composable
fun ShowRowContent(show: Show, detail: String? = null) {
    val large = androidx.compose.ui.platform.LocalDensity.current.fontScale >= 1.6f
    val networks = show.networks.takeIf { it.isNotEmpty() }?.joinToString(", ") { it.name }
    var spoken = "${show.title}. Worth it: ${Presentation.worthIt(show.ratings.worthIt)}."
    if (networks != null) spoken += " $networks."
    if (detail != null) spoken += " $detail"
    Column(Modifier.fillMaxWidth().clearAndSetSemantics { contentDescription = spoken }, verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(show.title, style = MaterialTheme.typography.titleMedium)
        if (large) {
            Text(Presentation.worthIt(show.ratings.worthIt), style = MaterialTheme.typography.bodyMedium, color = subdued)
            networks?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = subdued) }
        } else {
            Text(
                listOfNotNull(Presentation.worthIt(show.ratings.worthIt), networks).joinToString(" · "),
                style = MaterialTheme.typography.bodyMedium,
                color = subdued,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        detail?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
    }
}

@Composable
fun CharacterRowContent(character: Character, snapshot: Snapshot) {
    val large = androidx.compose.ui.platform.LocalDensity.current.fontScale >= 1.6f
    val titles = character.shows.mapNotNull { snapshot.show(it.showId)?.title }.joinToString(", ")
    Column(
        Modifier.fillMaxWidth().clearAndSetSemantics { contentDescription = if (titles.isEmpty()) character.name else "${character.name}, from $titles" },
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(character.name, style = MaterialTheme.typography.titleMedium)
        if (titles.isNotEmpty()) {
            Text(
                titles,
                style = MaterialTheme.typography.bodyMedium,
                color = subdued,
                maxLines = if (large) Int.MAX_VALUE else 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

/** An empty or failed state, stated in words. */
@Composable
fun EmptyState(title: String, modifier: Modifier = Modifier, message: String? = null) {
    Column(modifier.fillMaxWidth().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.semantics { heading() })
        message?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = subdued) }
    }
}

@Composable
fun ListDivider() = HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
