package com.chelseakr.queertvguide.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import com.chelseakr.queertvguide.AppModel
import com.chelseakr.queertvguide.core.SearchIndex
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.NumberFormat
import java.time.Instant

/** The search box and filters, kept across rotation (held by the activity's ViewModel). */
class SearchState {
    var query by mutableStateOf("")
    var filters by mutableStateOf(SearchIndex.Filters())
    var showingFilters by mutableStateOf(false)

    /** The hits for [key], worked out off the main thread so typing never waits. */
    var results by mutableStateOf(Results())

    data class Key(val query: String, val filters: SearchIndex.Filters, val generatedAt: Instant?)
    data class Results(val key: Key? = null, val hits: List<SearchIndex.Hit> = emptyList(), val totalCount: Int = 0)
}

fun filterSummary(active: Int): String = if (active == 1) "1 filter on" else "$active filters on"
fun showCount(count: Int): String = if (count == 1) "1 show" else "${NumberFormat.getIntegerInstance().format(count)} shows"

/** Search returns at most 50 hits, so a full page says "top 50". */
fun matchCount(count: Int): String = when {
    count == 1 -> "1 match"
    count >= 50 -> "Top $count matches"
    else -> "$count matches"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SearchScreen(model: AppModel, state: AppModel.State, search: SearchState, open: (Destination) -> Unit) {
    val trimmed = search.query.trim()
    val key = SearchState.Key(trimmed, search.filters, state.snapshot?.generatedAt)
    val index = state.index
    LaunchedEffect(key, index) {
        if (index == null) return@LaunchedEffect
        val r = withContext(Dispatchers.Default) {
            if (key.query.isEmpty()) {
                SearchIndex.SearchResults(index.browse(key.filters).map { SearchIndex.Hit.ShowHit(it) }, 0)
            } else {
                index.search(key.query, key.filters)
            }
        }
        search.results = SearchState.Results(key, r.hits, r.totalCount)
    }
    val scope = rememberCoroutineScope()
    val haptics = LocalHapticFeedback.current
    val focus = LocalFocusManager.current
    RefreshHaptics(state)

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Search") },
                actions = {
                    val active = search.filters.activeCount
                    IconButton(
                        onClick = { search.showingFilters = true },
                        enabled = index != null,
                        modifier = Modifier.testTag("filter-button").semantics {
                            contentDescription = if (active == 0) "Filter" else "Filter (${filterSummary(active)})"
                        },
                    ) {
                        BadgedBox(badge = { if (active > 0) Badge { Text("$active") } }) {
                            Icon(Icons.Filled.FilterList, contentDescription = null)
                        }
                    }
                },
            )
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            OutlinedTextField(
                value = search.query,
                onValueChange = { search.query = it },
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp).testTag("search-field"),
                placeholder = { Text("Shows, characters, actors") },
                leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
                trailingIcon = {
                    if (search.query.isNotEmpty()) {
                        IconButton(onClick = { search.query = "" }) { Icon(Icons.Filled.Clear, contentDescription = "Clear search") }
                    }
                },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { focus.clearFocus() }),
            )
            when (state.load) {
                AppModel.LoadState.LOADING -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        CircularProgressIndicator()
                        Text("Loading catalog…")
                    }
                }
                AppModel.LoadState.FAILED -> EmptyState("Couldn't load the catalog", message = state.loadError)
                AppModel.LoadState.LOADED -> {
                    val snapshot = state.snapshot ?: return@Column
                    val settled = search.results.key == key
                    val hits = search.results.hits
                    val total = search.results.totalCount
                    PullToRefreshBox(
                        isRefreshing = state.refreshing,
                        onRefresh = { scope.launch { model.requestedRefresh() } },
                        modifier = Modifier.fillMaxSize(),
                    ) {
                        LazyColumn(Modifier.fillMaxSize().testTag("search-results")) {
                            model.freshnessWarning(snapshot)?.let { warning ->
                                item { Box(Modifier.padding(horizontal = 16.dp)) { DataFreshnessBanner(warning) } }
                            }
                            if (!search.filters.isEmpty) {
                                item {
                                    ActiveFiltersRow(search, trimmed, if (settled) hits.size else null)
                                }
                            }
                            if (settled && hits.isEmpty()) {
                                item { SearchEmptyState(search, trimmed) }
                            } else {
                                if (settled && total > hits.size) {
                                    item {
                                        Text(
                                            "Showing the first ${hits.size} of $total matches. Type more to narrow them.",
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = subdued,
                                            modifier = Modifier.padding(16.dp).semantics { contentDescription = "Showing the first ${hits.size} of $total matches" },
                                        )
                                    }
                                }
                                items(hits, key = { it.id }) { hit ->
                                    Box(
                                        Modifier
                                            .fillMaxWidth()
                                            .heightIn(min = 56.dp)
                                            .clickable {
                                                haptics.performHapticFeedback(HapticFeedbackType.ContextClick)
                                                open(
                                                    when (hit) {
                                                        is SearchIndex.Hit.ShowHit -> Destination.ShowScreen(hit.show.id)
                                                        is SearchIndex.Hit.CharacterHit -> Destination.CharacterScreen(hit.character.id)
                                                    },
                                                )
                                            }
                                            .padding(horizontal = 16.dp, vertical = 10.dp)
                                            .testTag("hit"),
                                    ) {
                                        when (hit) {
                                            is SearchIndex.Hit.ShowHit -> ShowRowContent(hit.show)
                                            is SearchIndex.Hit.CharacterHit -> CharacterRowContent(hit.character, snapshot)
                                        }
                                    }
                                    ListDivider()
                                }
                            }
                            item { Box(Modifier.padding(horizontal = 16.dp)) { DataStatusFooter(model, snapshot, state) } }
                        }
                    }
                }
            }
        }
    }
    if (search.showingFilters && index != null) {
        FiltersDialog(index, search.filters, onChange = { search.filters = it }, onDismiss = { search.showingFilters = false })
    }
}

/** Above the results while any filter is on: how many there are, and a way to change or clear them. */
@Composable
private fun ActiveFiltersRow(search: SearchState, query: String, count: Int?) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Column(
            Modifier
                .weight(1f)
                .heightIn(min = 48.dp)
                .clickable(onClickLabel = "Opens the filters") { search.showingFilters = true },
            verticalArrangement = Arrangement.Center,
        ) {
            Text(filterSummary(search.filters.activeCount), style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
            count?.let { Text(if (query.isEmpty()) showCount(it) else matchCount(it), style = MaterialTheme.typography.bodyMedium, color = subdued) }
        }
        OutlinedButton(
            onClick = { search.filters = SearchIndex.Filters() },
            modifier = Modifier.semantics { contentDescription = "Clear filters" },
        ) { Text("Clear") }
    }
}

@Composable
private fun SearchEmptyState(search: SearchState, query: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth()) {
        when {
            query.isEmpty() -> {
                EmptyState("No shows match these filters", message = "Turn a filter off to see more.")
                TextButton(onClick = { search.filters = SearchIndex.Filters() }) { Text("Clear filters") }
            }
            !search.filters.isEmpty -> {
                EmptyState("No matches with these filters", message = "Nothing matches “$query” with ${filterSummary(search.filters.activeCount).lowercase()}.")
                TextButton(onClick = { search.filters = SearchIndex.Filters() }) { Text("Search without filters") }
            }
            else -> EmptyState("No matches", message = "Nothing in this snapshot matches “$query”. Try part of a title, a character's name, an actor or a network.",
            )
        }
    }
}

/** A success or warning haptic as a refresh the person asked for finishes. */
@Composable
fun RefreshHaptics(state: AppModel.State) {
    val haptics = LocalHapticFeedback.current
    val count = state.requestedRefreshesFinished
    val problem = state.problem
    LaunchedEffect(count) {
        if (count > 0) haptics.performHapticFeedback(if (problem == null) HapticFeedbackType.Confirm else HapticFeedbackType.Reject)
    }
}
