package com.chelseakr.queertvguide.ui

import androidx.core.content.edit
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.StarOutline
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.VerticalDivider
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.isCtrlPressed
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.chelseakr.queertvguide.AppModel
import kotlinx.coroutines.launch
import androidx.compose.runtime.rememberCoroutineScope

/** Widths at which the layout changes (Material's window size classes). */
object Widths {
    /** A navigation rail instead of a bottom bar. */
    val RAIL = 600.dp

    /** Search and Favorites become list and detail side by side. */
    val TWO_PANE = 720.dp
}

/**
 * The first-run pages until they are finished or skipped once; then the
 * three tabs. A phone gets a bottom navigation bar and one screen at a time;
 * a tablet, a foldable open, or a wide window gets a navigation rail and,
 * on Search and Favorites, the list beside the show or character it opened.
 */
@Composable
fun RootScreen(model: AppModel, router: Router, search: SearchState) {
    var onboardingSeen by remember { mutableStateOf(model.prefs.getBoolean(AppModel.ONBOARDING_SEEN, false)) }
    val state by model.state.collectAsState()
    val pending = router.pendingLink
    LaunchedEffect(pending, onboardingSeen) {
        if (pending != null && onboardingSeen) {
            router.open(pending)
            router.pendingLink = null
        }
    }
    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        if (!onboardingSeen) {
            OnboardingScreen(isFirstRun = true, finish = {
                model.prefs.edit { putBoolean(AppModel.ONBOARDING_SEEN, true) }
                onboardingSeen = true
            })
            return@Surface
        }
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val rail = maxWidth >= Widths.RAIL
            val twoPane = maxWidth >= Widths.TWO_PANE
            val scope = rememberCoroutineScope()
            val keys = Modifier.onPreviewKeyEvent { event ->
                // Ctrl-1/2/3 for the tabs and Ctrl-R to check for new data,
                // for a keyboard on a tablet or a Chromebook (as iOS's Go menu).
                if (event.type != KeyEventType.KeyDown || !event.isCtrlPressed) return@onPreviewKeyEvent false
                when (event.key) {
                    Key.One -> { router.tab = Tab.SEARCH; true }
                    Key.Two -> { router.tab = Tab.FAVORITES; true }
                    Key.Three -> { router.tab = Tab.ABOUT; true }
                    Key.R -> { scope.launch { model.requestedRefresh() }; true }
                    else -> false
                }
            }
            BackHandler(enabled = router.stack().isNotEmpty()) { router.pop() }
            if (rail) {
                Row(Modifier.fillMaxSize().then(keys)) {
                    NavigationRail(Modifier.fillMaxHeight()) {
                        Tab.entries.forEach { tab ->
                            NavigationRailItem(
                                selected = router.tab == tab,
                                onClick = { selectTab(router, tab) },
                                icon = { Icon(tab.icon(router.tab == tab), contentDescription = null) },
                                label = { Text(tab.title) },
                                modifier = Modifier.testTag("tab-${tab.name.lowercase()}"),
                            )
                        }
                    }
                    VerticalDivider()
                    Box(Modifier.weight(1f)) { TabContent(model, router, search, state, twoPane) }
                }
            } else {
                Scaffold(
                    modifier = Modifier.then(keys),
                    bottomBar = {
                        NavigationBar {
                            Tab.entries.forEach { tab ->
                                NavigationBarItem(
                                    selected = router.tab == tab,
                                    onClick = { selectTab(router, tab) },
                                    icon = { Icon(tab.icon(router.tab == tab), contentDescription = null) },
                                    label = { Text(tab.title) },
                                    modifier = Modifier.testTag("tab-${tab.name.lowercase()}"),
                                )
                            }
                        }
                    },
                    contentWindowInsets = androidx.compose.foundation.layout.WindowInsets(0, 0, 0, 0),
                ) { padding ->
                    Box(Modifier.fillMaxSize().padding(padding)) { TabContent(model, router, search, state, twoPane = false) }
                }
            }
        }
    }
}

/** Tapping the tab you are on goes back to its list, as on iOS. */
private fun selectTab(router: Router, tab: Tab) {
    if (router.tab == tab) router.stack(tab).clear() else router.tab = tab
}

private fun Tab.icon(selected: Boolean): ImageVector = when (this) {
    Tab.SEARCH -> Icons.Filled.Search
    Tab.FAVORITES -> if (selected) Icons.Filled.Star else Icons.Outlined.StarOutline
    Tab.ABOUT -> if (selected) Icons.Filled.Info else Icons.Outlined.Info
}

@Composable
private fun TabContent(model: AppModel, router: Router, search: SearchState, state: AppModel.State, twoPane: Boolean) {
    val stack = router.stack()
    when (router.tab) {
        Tab.ABOUT -> AboutScreen(model, state)
        Tab.SEARCH, Tab.FAVORITES -> {
            val list: @Composable () -> Unit = {
                if (router.tab == Tab.SEARCH) {
                    SearchScreen(model, state, search) { router.show(it, replace = twoPane) }
                } else {
                    FavoritesScreen(model, state) { router.show(it, replace = twoPane) }
                }
            }
            if (twoPane) {
                Row(Modifier.fillMaxSize()) {
                    Box(Modifier.width(380.dp).fillMaxHeight()) { list() }
                    VerticalDivider()
                    Box(Modifier.weight(1f).fillMaxHeight()) {
                        val top = stack.lastOrNull()
                        if (top == null) {
                            DetailPlaceholder(router.tab)
                        } else {
                            DetailScreen(model, state, top, canGoBack = stack.size > 1, onBack = { router.pop() }, open = { router.push(it) })
                        }
                    }
                }
            } else {
                val top = stack.lastOrNull()
                if (top == null) list() else DetailScreen(model, state, top, canGoBack = true, onBack = { router.pop() }, open = { router.push(it) })
            }
        }
    }
}

@Composable
private fun DetailPlaceholder(tab: Tab) {
    EmptyState(
        title = if (tab == Tab.SEARCH) "Pick a show or character" else "Pick a favorite",
        message = "It opens here, beside the list.",
        modifier = Modifier.testTag("detail-placeholder"),
    )
}

@Composable
fun DetailScreen(model: AppModel, state: AppModel.State, destination: Destination, canGoBack: Boolean, onBack: () -> Unit, open: (Destination) -> Unit) {
    when (destination) {
        is Destination.ShowScreen -> ShowScreen(model, state, destination.id, canGoBack, onBack, open)
        is Destination.CharacterScreen -> CharacterScreen(model, state, destination.id, canGoBack, onBack, open)
    }
}
