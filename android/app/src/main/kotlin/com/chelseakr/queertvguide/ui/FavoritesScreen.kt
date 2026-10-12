package com.chelseakr.queertvguide.ui

import androidx.core.content.edit
import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.ui.semantics.Role
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Event
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.PhoneAndroid
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.compose.LifecycleResumeEffect
import com.chelseakr.queertvguide.AppModel
import com.chelseakr.queertvguide.core.Attribution
import com.chelseakr.queertvguide.core.FavoritesBackup
import com.chelseakr.queertvguide.core.FavoritesStore
import com.chelseakr.queertvguide.core.Presentation
import com.chelseakr.queertvguide.core.Snapshot
import com.chelseakr.queertvguide.reminders.ReminderScheduler
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FavoritesScreen(model: AppModel, state: AppModel.State, open: (Destination) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    // Read on every favorites change (state.favoritesVersion), newest first.
    val entries = remember(state.favoritesVersion) { model.favorites.entries.sortedByDescending { it.addedAt } }
    var menu by remember { mutableStateOf(false) }
    var outcome by remember { mutableStateOf<Pair<String, String>?>(null) }
    RefreshHaptics(state)

    // Backup without a server or an account (DG-10): export writes a file
    // where the person chooses; import reads one they pick. The app sends nothing.
    val exporter = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            outcome = try {
                withContext(Dispatchers.IO) {
                    context.contentResolver.openOutputStream(uri, "wt")!!.use { it.write(FavoritesBackup.export(model.favorites.entries)) }
                }
                "Favorites exported" to "The backup file is saved where you chose. Import it on another device from this menu."
            } catch (e: Exception) {
                "Couldn't export favorites" to (e.message ?: "The file could not be written.")
            }
        }
    }
    val importer = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            outcome = try {
                // Read at most one byte past the cap, so an oversized file is refused by size, not read whole.
                val bytes = withContext(Dispatchers.IO) {
                    context.contentResolver.openInputStream(uri)!!.use { it.readNBytesCompat(FavoritesBackup.MAX_BYTES + 1) }
                }
                "Favorites imported" to model.importFavorites(bytes)
            } catch (e: Exception) {
                "Couldn't import favorites" to (e.message ?: "The file could not be read.")
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Favorites") },
                actions = {
                    if (state.snapshot != null) {
                        Box {
                            IconButton(onClick = { menu = true }, modifier = Modifier.testTag("backup-menu")) {
                                Icon(Icons.Filled.MoreVert, contentDescription = "Back up or restore favorites")
                            }
                            DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                                DropdownMenuItem(
                                    text = { Text("Export favorites") },
                                    enabled = entries.isNotEmpty(),
                                    onClick = {
                                        menu = false
                                        exporter.launch(FavoritesBackup.SUGGESTED_FILE_NAME)
                                    },
                                )
                                DropdownMenuItem(
                                    text = { Text("Import favorites") },
                                    onClick = {
                                        menu = false
                                        importer.launch(arrayOf("application/json", "application/octet-stream", "text/plain"))
                                    },
                                )
                            }
                        }
                    }
                },
            )
        },
    ) { padding ->
        val snapshot = state.snapshot
        Box(Modifier.padding(padding).fillMaxSize()) {
            when {
                snapshot == null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                entries.isEmpty() -> EmptyState("No favorites yet", message = "Tap the star on a show or character to save it here. Favorites stay on this device. To move them to " +
                        "another one, use the More options menu (⋮) at the top of this screen to export a backup file, then import it there.",
                )
                else -> PullToRefreshBox(
                    isRefreshing = state.refreshing,
                    onRefresh = { scope.launch { model.requestedRefresh() } },
                    modifier = Modifier.fillMaxSize(),
                ) {
                    FavoritesList(model, state, snapshot, entries, open)
                }
            }
        }
    }
    outcome?.let { (title, message) ->
        AlertDialog(
            onDismissRequest = { outcome = null },
            confirmButton = { TextButton(onClick = { outcome = null }) { Text("OK") } },
            title = { Text(title) },
            text = { Text(message) },
        )
    }
}

/** `InputStream.readNBytes` is Java 11 (Android 13); this reads up to [limit] bytes on every version. */
private fun java.io.InputStream.readNBytesCompat(limit: Int): ByteArray {
    val out = java.io.ByteArrayOutputStream()
    val buffer = ByteArray(64 * 1024)
    while (out.size() < limit) {
        val n = read(buffer, 0, minOf(buffer.size, limit - out.size()))
        if (n < 0) break
        out.write(buffer, 0, n)
    }
    return out.toByteArray()
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun FavoritesList(model: AppModel, state: AppModel.State, snapshot: Snapshot, entries: List<FavoritesStore.Entry>, open: (Destination) -> Unit) {
    val text = model.dateText()
    val haptics = LocalHapticFeedback.current
    val hasShows = entries.any { it.kind == FavoritesStore.Kind.SHOW }
    LazyColumn(Modifier.fillMaxSize().testTag("favorites-list")) {
        model.freshnessWarning(snapshot)?.let { warning -> item { Box(Modifier.padding(horizontal = 16.dp)) { DataFreshnessBanner(warning) } } }
        items(entries, key = { it.key }) { entry ->
            val remove = {
                haptics.performHapticFeedback(HapticFeedbackType.ToggleOff)
                model.favorites.remove(entry.kind, entry.id)
            }
            val dismiss = rememberSwipeToDismissBoxState()
            LaunchedEffect(dismiss.currentValue) {
                if (dismiss.currentValue != SwipeToDismissBoxValue.Settled) remove()
            }
            SwipeToDismissBox(
                state = dismiss,
                backgroundContent = {
                    Row(Modifier.fillMaxSize().padding(horizontal = 24.dp), horizontalArrangement = Arrangement.End, verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Filled.Delete, contentDescription = null)
                    }
                },
            ) {
                Surface {
                    val destination = when (entry.kind) {
                        FavoritesStore.Kind.SHOW -> snapshot.show(entry.id)?.let { Destination.ShowScreen(it.id) }
                        FavoritesStore.Kind.CHARACTER -> snapshot.character(entry.id)?.let { Destination.CharacterScreen(it.id) }
                    }
                    Box(
                        Modifier
                            .fillMaxWidth()
                            .heightIn(min = 56.dp)
                            .then(if (destination != null) Modifier.clickable { open(destination) } else Modifier)
                            // Swiping is not the only way: TalkBack's actions menu offers it too.
                            .semantics { customActions = listOf(CustomAccessibilityAction("Remove from favorites") { remove(); true }) }
                            .padding(horizontal = 16.dp, vertical = 10.dp),
                    ) {
                        when (entry.kind) {
                            FavoritesStore.Kind.SHOW -> snapshot.show(entry.id)?.let {
                                // "When's the next episode" for everything followed, at a glance.
                                ShowRowContent(it, Presentation.nextEpisode(it.schedule, state.clock, text))
                            } ?: Text("A favorited show is not in this snapshot.", color = subdued)
                            FavoritesStore.Kind.CHARACTER -> snapshot.character(entry.id)?.let { CharacterRowContent(it, snapshot) }
                                ?: Text("A favorited character is not in this snapshot.", color = subdued)
                        }
                    }
                }
            }
            ListDivider()
        }
        if (hasShows) {
            // Show rows carry TVmaze next-episode data; credit it here (CC BY-SA 4.0).
            Attribution.tvmazeCredit(snapshot)?.let { credit -> item { Box(Modifier.padding(horizontal = 8.dp)) { TvmazeCreditLinks(credit) } } }
            item { RemindersSection(model) }
        }
        item { Box(Modifier.padding(horizontal = 16.dp)) { DataStatusFooter(model, snapshot, state) } }
    }
}

/**
 * The reminders switch. Turning it on first explains what a reminder is and
 * is not; only "Turn on reminders" there asks Android for permission (13+).
 */
@Composable
private fun RemindersSection(model: AppModel) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val haptics = LocalHapticFeedback.current
    val prefs = model.prefs
    var on by remember { mutableStateOf(ReminderScheduler.isEnabled(context) && ReminderScheduler.canNotify(context)) }
    var primer by remember { mutableStateOf(false) }
    // Only after the person has been asked: before that, "off in Settings" is not true yet.
    var blocked by remember { mutableStateOf(false) }
    LifecycleResumeEffect(Unit) {
        // Back from Settings: notifications may have been turned on or off there.
        on = ReminderScheduler.isEnabled(context) && ReminderScheduler.canNotify(context)
        blocked = !on && prefs.getBoolean(ASKED_PREF, false) && !ReminderScheduler.canNotify(context)
        onPauseOrDispose { }
    }
    fun settle(granted: Boolean) {
        prefs.edit { putBoolean(ASKED_PREF, true) }
        ReminderScheduler.setEnabled(context, granted)
        on = granted && ReminderScheduler.canNotify(context)
        blocked = !on
        if (on) haptics.performHapticFeedback(HapticFeedbackType.ToggleOn)
        scope.launch { model.rescheduleReminders() }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted -> settle(granted) }
    fun request(wantsOn: Boolean) {
        if (wantsOn) {
            primer = true
        } else {
            haptics.performHapticFeedback(HapticFeedbackType.ToggleOff)
            ReminderScheduler.setEnabled(context, false)
            on = false
            blocked = false
            scope.launch { ReminderScheduler.cancelAll(context) }
        }
    }
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(
            Modifier
                .fillMaxWidth()
                .heightIn(min = 48.dp)
                .toggleable(value = on, role = Role.Switch, onValueChange = ::request)
                .testTag("reminders-switch"),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("New-episode reminders", modifier = Modifier.weight(1f))
            Switch(checked = on, onCheckedChange = null)
        }
        if (blocked) {
            Text("Notifications are off for this app in Settings, so no reminder can appear.", color = subdued)
            OutlinedButton(onClick = {
                val intent = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
                context.startActivity(intent)
            }) { Text("Open Settings") }
        }
        Text(
            "Reminders are set on this device and follow the data file, so a schedule changed since the last refresh can make one wrong.",
            style = MaterialTheme.typography.bodySmall,
            color = subdued,
        )
    }
    if (primer) {
        ReminderPrimer { accepted ->
            primer = false
            if (!accepted) return@ReminderPrimer
            if (Build.VERSION.SDK_INT >= 33 && !ReminderScheduler.canNotify(context)) {
                permission.launch(Manifest.permission.POST_NOTIFICATIONS)
            } else {
                settle(ReminderScheduler.canNotify(context))
            }
        }
    }
}

private const val ASKED_PREF = "reminders.v1.asked"

/** Before Android's permission prompt: what a reminder says, where it comes from, what it never carries. */
@Composable
private fun ReminderPrimer(finish: (Boolean) -> Unit) {
    Dialog(onDismissRequest = { finish(false) }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            Box(contentAlignment = Alignment.TopCenter) {
                Column(
                    Modifier.widthIn(max = 640.dp).fillMaxWidth().verticalScroll(rememberScrollState()).padding(24.dp),
                    verticalArrangement = Arrangement.spacedBy(24.dp),
                ) {
                    Text("New-episode reminders", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
                    for ((icon, text) in REMINDER_POINTS) {
                        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                            Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                            Text(text)
                        }
                    }
                    Text("Android asks next whether to allow notifications. You can change your mind in Settings at any time.", color = subdued)
                    Button(onClick = { finish(true) }, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp).testTag("reminders-accept")) {
                        Text("Turn on reminders")
                    }
                    OutlinedButton(onClick = { finish(false) }, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp).testTag("reminders-decline")) {
                        Text("Not now")
                    }
                    Spacer(Modifier.width(1.dp))
                }
            }
        }
    }
}

private val REMINDER_POINTS = listOf(
    Icons.Filled.Event to "On the day a favorite show has a new episode listed, you get one reminder: the show's name and the episode number. If TVmaze lists no air time, it comes at 10 a.m. on the listed date and says so.",
    Icons.Filled.VisibilityOff to "Episode titles are left out, and nothing about any character, so a reminder cannot spoil anything on your lock screen.",
    Icons.Filled.PhoneAndroid to "This device sets the reminders itself. Nothing is sent to a server, and nothing about you leaves it.",
    Icons.Filled.Refresh to "Reminders follow the data file. If a schedule changes after your last refresh, one can be early, late or wrong.",
)
