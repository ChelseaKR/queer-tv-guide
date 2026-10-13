package com.chelseakr.queertvguide.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.outlined.Circle
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.chelseakr.queertvguide.core.SearchIndex
import com.chelseakr.queertvguide.core.WorthIt
import java.text.NumberFormat

/**
 * Every browse filter on one screen: worth it, where to watch, tropes,
 * trigger warnings and recorded deaths. Changes apply as they are made; the
 * button at the bottom says how many shows the choice leaves.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FiltersDialog(index: SearchIndex, filters: SearchIndex.Filters, onChange: (SearchIndex.Filters) -> Unit, onDismiss: () -> Unit) {
    var picker by remember { mutableStateOf<String?>(null) }
    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            when (picker) {
                "sites" -> TermPicker(
                    title = "Where to watch",
                    explanation = "Shows with a link to any site you pick.",
                    terms = index.filterOptions.watchHosts.map { SearchIndex.FilterTerm(it.key, it.key, it.showCount) },
                    selection = filters.watchHosts,
                    onSelection = { onChange(filters.copy(watchHosts = it)) },
                    onBack = { picker = null },
                )
                "tropes" -> TermPicker(
                    title = "Tropes",
                    explanation = "Shows tagged with any trope you pick. Tropes that give away a death are not listed.",
                    terms = index.filterOptions.tropes,
                    selection = filters.tropes,
                    onSelection = { onChange(filters.copy(tropes = it)) },
                    onBack = { picker = null },
                )
                else -> FiltersMain(index, filters, onChange, onDismiss) { picker = it }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun FiltersMain(index: SearchIndex, filters: SearchIndex.Filters, onChange: (SearchIndex.Filters) -> Unit, onDismiss: () -> Unit, openPicker: (String) -> Unit) {
    val matching = remember(filters) { index.browse(filters).size }
    val large = LocalDensity.current.fontScale >= 1.6f
    val results: @Composable () -> Unit = {
        Button(onClick = onDismiss, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp).testTag("filters-show-results")) {
            Text(showResultsTitle(matching))
        }
    }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Filters") },
                actions = { IconButton(onClick = onDismiss) { Icon(Icons.Filled.Check, contentDescription = "Done") } },
            )
        },
        bottomBar = {
            // At the largest font sizes the button ends the page instead: pinned, it covered too much of the screen.
            if (!large) {
                Column {
                    HorizontalDivider()
                    Column(Modifier.padding(16.dp)) { results() }
                }
            }
        },
    ) { padding ->
        Column(
            Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp),
        ) {
            if (!filters.isEmpty) {
                OutlinedButton(onClick = { onChange(SearchIndex.Filters()) }) { Text("Clear all filters") }
            }
            FilterGroup("Worth it", "LezWatch.TV's verdict. Shows it has not rated are left out while any of these is on.") {
                for (value in WorthIt.entries) {
                    CheckRow(value.raw, filters.worthIt.contains(value), spoken = "Worth it: ${value.raw}") { on ->
                        onChange(filters.copy(worthIt = if (on) filters.worthIt + value else filters.worthIt - value))
                    }
                }
            }
            FilterGroup("Where to watch") {
                CheckRow("Has a where-to-watch link", filters.hasWatchLink) { onChange(filters.copy(hasWatchLink = it)) }
                PickerRow("Sites", filters.watchHosts.size) { openPicker("sites") }
            }
            FilterGroup("Tropes") {
                PickerRow("Tropes", filters.tropes.size) { openPicker("tropes") }
            }
            val triggers = index.filterOptions.triggerWarnings
            if (triggers.isNotEmpty()) {
                FilterGroup(
                    "Trigger warnings",
                    "LezWatch.TV rates some shows' trigger warnings ${triggers.joinToString(", ") { it.name }}. Shows with no rating listed are always kept.",
                ) {
                    for (level in triggers) {
                        CheckRow("Hide shows rated ${level.name}", level.slug in filters.hiddenTriggerWarnings) { on ->
                            onChange(filters.copy(hiddenTriggerWarnings = if (on) filters.hiddenTriggerWarnings + level.slug else filters.hiddenTriggerWarnings - level.slug))
                        }
                    }
                }
            }
            FilterGroup(
                "Deaths",
                "Shows whose listed queer characters have no recorded death. A show with no listed characters is left out, because that is not the same as nobody dying.",
            ) {
                CheckRow("No recorded deaths", filters.noRecordedDeaths, tag = "filter-no-recorded-deaths") { onChange(filters.copy(noRecordedDeaths = it)) }
            }
            if (large) results()
        }
    }
}

fun showResultsTitle(count: Int): String = if (count == 1) "Show 1 show" else "Show ${NumberFormat.getIntegerInstance().format(count)} shows"

@Composable
private fun FilterGroup(title: String, footer: String? = null, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        SectionHeading(title, Modifier.padding(bottom = 4.dp))
        content()
        footer?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = subdued, modifier = Modifier.padding(top = 4.dp)) }
    }
}

/** A row that is on or off: the whole row one control, read as selected or not. */
@Composable
fun CheckRow(title: String, isOn: Boolean, detail: String? = null, spoken: String? = null, tag: String? = null, onToggle: (Boolean) -> Unit) {
    val haptics = LocalHapticFeedback.current
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .toggleable(value = isOn, role = Role.Checkbox) {
                haptics.performHapticFeedback(if (it) HapticFeedbackType.ToggleOn else HapticFeedbackType.ToggleOff)
                onToggle(it)
            }
            .then(if (tag != null) Modifier.testTag(tag) else Modifier)
            .semantics { if (spoken != null) contentDescription = spoken },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            if (isOn) Icons.Filled.CheckCircle else Icons.Outlined.Circle,
            contentDescription = null,
            tint = if (isOn) MaterialTheme.colorScheme.primary else subdued,
        )
        Spacer(Modifier.width(12.dp))
        Text(title, modifier = Modifier.weight(1f))
        detail?.let { Text(it, color = subdued) }
    }
}

/** "Sites" and how many are picked, read as one phrase. */
@Composable
private fun PickerRow(title: String, count: Int, onClick: () -> Unit) {
    val value = if (count == 0) "Any" else "$count picked"
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .clickable(role = Role.Button, onClick = onClick)
            .clearAndSetSemantics { contentDescription = if (count == 0) "$title, any" else "$title, $count picked" },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(title, modifier = Modifier.weight(1f))
        Text(value, color = subdued)
        Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = null, tint = subdued)
    }
}

/** A searchable multiple-choice list of terms or sites, each with how many shows carry it. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TermPicker(
    title: String,
    explanation: String,
    terms: List<SearchIndex.FilterTerm>,
    selection: Set<String>,
    onSelection: (Set<String>) -> Unit,
    onBack: () -> Unit,
) {
    var query by remember { mutableStateOf("") }
    BackHandler(onBack = onBack)
    val visible = query.trim().let { q -> if (q.isEmpty()) terms else terms.filter { it.name.contains(q, ignoreCase = true) } }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(title) },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back to filters") } },
                actions = {
                    if (selection.isNotEmpty()) {
                        IconButton(onClick = { onSelection(emptySet()) }) { Icon(Icons.Filled.Close, contentDescription = "Clear") }
                    }
                },
            )
        },
    ) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize().padding(horizontal = 16.dp)) {
            item {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("Find in ${title.lowercase()}") },
                    singleLine = true,
                )
                Text(explanation, style = MaterialTheme.typography.bodySmall, color = subdued, modifier = Modifier.padding(vertical = 8.dp))
            }
            items(visible, key = { it.slug }) { term ->
                CheckRow(
                    term.name,
                    term.slug in selection,
                    detail = NumberFormat.getIntegerInstance().format(term.showCount),
                    spoken = "${term.name}, ${term.showCount} ${if (term.showCount == 1) "show" else "shows"}",
                    tag = "filter-term",
                ) { on -> onSelection(if (on) selection + term.slug else selection - term.slug) }
            }
            if (visible.isEmpty()) item { Text("Nothing listed matches “$query”.", color = subdued) }
        }
    }
}
