package com.chelseakr.queertvguide

import androidx.core.content.edit
import android.content.Context
import android.content.SharedPreferences
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.text.format.DateFormat
import com.chelseakr.queertvguide.core.DataFreshness
import com.chelseakr.queertvguide.core.DateText
import com.chelseakr.queertvguide.core.FavoritesBackup
import com.chelseakr.queertvguide.core.FavoritesStore
import com.chelseakr.queertvguide.core.ForegroundRefreshGate
import com.chelseakr.queertvguide.core.KeyValueStore
import com.chelseakr.queertvguide.core.Presentation
import com.chelseakr.queertvguide.core.RefreshProblem
import com.chelseakr.queertvguide.core.SearchIndex
import com.chelseakr.queertvguide.core.Snapshot
import com.chelseakr.queertvguide.core.SnapshotRefresher
import com.chelseakr.queertvguide.core.SnapshotStore
import com.chelseakr.queertvguide.core.UpNext
import com.chelseakr.queertvguide.core.UpNextStore
import com.chelseakr.queertvguide.reminders.ReminderScheduler
import com.chelseakr.queertvguide.widget.UpNextWidget
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.withContext
import java.io.File
import java.time.Instant
import java.time.ZoneId
import java.util.Locale

/**
 * The app's one piece of shared state: the snapshot, how it was loaded, and
 * the one network action (refresh). No accounts, no analytics: it holds
 * exactly what the screens need and nothing about who is using them. The
 * Android twin of the iOS `AppModel`.
 */
class AppModel(
    private val context: Context,
    private val store: SnapshotStore,
    val favorites: FavoritesStore,
    val prefs: SharedPreferences,
    private val now: () -> Instant,
    /** Debug builds only: a refresh problem every look reports, for screenshots and UI tests. */
    private val forcedProblem: () -> RefreshProblem?,
) {
    enum class LoadState { LOADING, LOADED, FAILED }

    data class State(
        val snapshot: Snapshot? = null,
        val index: SearchIndex? = null,
        val load: LoadState = LoadState.LOADING,
        val loadError: String? = null,
        val origin: SnapshotStore.Origin? = null,
        /** Why the last look for new data failed; null after one that worked. */
        val problem: RefreshProblem? = null,
        val refreshing: Boolean = false,
        /** When the clock was last read for judging the data's age. */
        val clock: Instant = Instant.EPOCH,
        /** Refreshes the person asked for, counted as they finish, for a haptic. */
        val requestedRefreshesFinished: Int = 0,
        /** Bumped on every favorites change, so lists redraw. */
        val favoritesVersion: Int = 0,
    )

    private val _state = MutableStateFlow(State(clock = now()))
    val state: StateFlow<State> = _state.asStateFlow()

    private val refresher = SnapshotRefresher(store, isOnline = ::isOnline)
    private val gate = ForegroundRefreshGate()
    private val refreshLock = Mutex()

    init {
        favorites.addListener { _state.update { it.copy(favoritesVersion = it.favoritesVersion + 1) } }
    }

    /** Dates in the viewer's locale and time zone, with Android's own skeleton patterns. */
    fun dateText(): DateText = DateText(Locale.getDefault(), ZoneId.systemDefault()) { skeleton, locale ->
        DateFormat.getBestDateTimePattern(locale, skeleton)
    }

    fun readClock() {
        _state.update { it.copy(clock = now()) }
    }

    fun freshness(snapshot: Snapshot): DataFreshness = DataFreshness.assess(snapshot.generatedAt, state.value.clock)

    fun freshnessWarning(snapshot: Snapshot): Presentation.FreshnessWarning? =
        Presentation.freshnessWarning(snapshot.generatedAt, freshness(snapshot), dateText())

    /** Decodes the snapshot (megabytes of real data) and builds the index off the main thread. */
    suspend fun loadInitial() {
        if (state.value.load == LoadState.LOADED) return
        try {
            val (loaded, index) = withContext(Dispatchers.Default) {
                val loaded = store.load()
                loaded to SearchIndex(loaded.snapshot)
            }
            _state.update {
                it.copy(snapshot = loaded.snapshot, index = index, origin = loaded.origin, load = LoadState.LOADED, clock = now())
            }
        } catch (e: Exception) {
            _state.update { it.copy(load = LoadState.FAILED, loadError = e.message ?: e.toString()) }
        }
    }

    /**
     * Back in the foreground: re-reads the clock and, when the data is more
     * than [ForegroundRefreshGate.STALE_AFTER_SECONDS] old (and no look was
     * made in the last [ForegroundRefreshGate.MINIMUM_INTERVAL_SECONDS]),
     * makes the same single GET as a launch.
     */
    suspend fun refreshIfStaleOnReturn() {
        readClock()
        val snapshot = state.value.snapshot ?: return
        if (!gate.shouldRefresh(snapshot.generatedAt, state.value.clock)) return
        refresh()
    }

    /** A refresh the person asked for (pull, Try again): the same one GET, then counted for a haptic. */
    suspend fun requestedRefresh() {
        refresh()
        _state.update { it.copy(requestedRefreshesFinished = it.requestedRefreshesFinished + 1) }
    }

    /**
     * One GET, conditional on the stored ETag. On a real change, swaps in the
     * new snapshot. On any failure the last good snapshot stays exactly as it
     * was; only [State.problem] changes.
     */
    suspend fun refresh() {
        if (!refreshLock.tryLock()) return
        try {
            _state.update { it.copy(refreshing = true) }
            gate.recordAttempt(now())
            val forced = forcedProblem()
            if (forced != null) {
                _state.update { it.copy(problem = forced, refreshing = false, clock = now()) }
                return
            }
            try {
                val outcome = withContext(Dispatchers.IO) { refresher.refresh() }
                if (outcome is SnapshotRefresher.Outcome.Updated) {
                    val index = withContext(Dispatchers.Default) { SearchIndex(outcome.snapshot) }
                    _state.update {
                        it.copy(snapshot = outcome.snapshot, index = index, origin = SnapshotStore.Origin.DOWNLOADED, load = LoadState.LOADED)
                    }
                }
                _state.update { it.copy(problem = null) }
            } catch (e: Exception) {
                _state.update { it.copy(problem = RefreshProblem.from(e)) }
            }
            _state.update { it.copy(refreshing = false, clock = now()) }
        } finally {
            refreshLock.unlock()
        }
    }

    class CatalogNotLoaded : Exception(
        "The catalog hasn't finished loading, so the backup can't be checked against it yet. Try again in a moment.",
    )

    /** Validates a backup against the loaded snapshot, adds what is new, and says what happened to every entry. */
    fun importFavorites(bytes: ByteArray): String {
        val snapshot = state.value.snapshot ?: throw CatalogNotLoaded()
        val parsed = FavoritesBackup.parse(bytes, now()) { kind, id ->
            when (kind) {
                FavoritesStore.Kind.SHOW -> snapshot.show(id) != null
                FavoritesStore.Kind.CHARACTER -> snapshot.character(id) != null
            }
        }
        val (added, already) = favorites.merge(parsed.entries)
        return Presentation.importSummary(added, already, parsed.notInSnapshot, parsed.unreadable)
    }

    /** Favorite show ids, newest first, as the widget lists them. */
    fun favoriteShowIdsNewestFirst(): List<String> = favorites.entries
        .filter { it.kind == FavoritesStore.Kind.SHOW }
        .sortedByDescending { it.addedAt }
        .map { it.id }

    /** Writes the widget's file when it changed and asks the widget to redraw. */
    suspend fun publishUpNext() {
        val snapshot = state.value.snapshot ?: return
        val changed = withContext(Dispatchers.IO) {
            UpNextStore(upNextDirectory(context)).write(UpNext.build(favoriteShowIdsNewestFirst(), snapshot))
        }
        if (changed) UpNextWidget.updateAll(context)
    }

    /** Replaces this app's pending reminders with the current plan, if the person turned them on. */
    suspend fun rescheduleReminders() {
        val snapshot = state.value.snapshot ?: return
        ReminderScheduler.reschedule(context, snapshot, favorites.entries.filter { it.kind == FavoritesStore.Kind.SHOW }.map { it.id }, dateText())
    }

    private fun isOnline(): Boolean {
        val cm = context.getSystemService(ConnectivityManager::class.java) ?: return true
        val network = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(network) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    companion object {
        const val PREFS = "queer_frame"
        const val ONBOARDING_SEEN = "onboarding.v1.seen"

        /** Debug builds only, set from launch extras by UI tests. */
        @Volatile var debugClock: Instant? = null

        @Volatile var debugProblem: RefreshProblem? = null

        fun upNextDirectory(context: Context): File = File(context.filesDir, "widget")

        fun create(context: Context): AppModel {
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val store = SnapshotStore(File(context.filesDir, "Snapshot")) {
                context.assets.open("snapshot.v1.json").use { it.readBytes() }
            }
            val storage = object : KeyValueStore {
                override fun getString(key: String): String? = prefs.getString(key, null)
                override fun putString(key: String, value: String?) {
                    prefs.edit { if (value == null) remove(key) else putString(key, value) }
                }
            }
            return AppModel(
                context = context.applicationContext,
                store = store,
                favorites = FavoritesStore(storage),
                prefs = prefs,
                now = { (if (BuildConfig.DEBUG) debugClock else null) ?: Instant.now() },
                forcedProblem = { if (BuildConfig.DEBUG) debugProblem else null },
            )
        }
    }
}
