package com.chelseakr.queertvguide

import androidx.core.content.edit
import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.viewModels
import androidx.lifecycle.ViewModel
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.lifecycleScope
import com.chelseakr.queertvguide.core.AppLink
import com.chelseakr.queertvguide.core.RefreshProblem
import com.chelseakr.queertvguide.ui.QueerFrameTheme
import com.chelseakr.queertvguide.ui.RootScreen
import com.chelseakr.queertvguide.ui.Router
import com.chelseakr.queertvguide.ui.SearchState
import kotlinx.coroutines.launch
import java.time.Instant

/**
 * The one activity. At launch: load the snapshot, hand the widget its file,
 * look once for new data, set any reminders. Leaving the foreground rewrites
 * the widget's file and the reminders, so a star added or removed anywhere
 * reaches both. Coming back re-reads the clock and, if the data is old
 * enough, looks once for new data (ForegroundRefreshGate).
 */
class MainActivity : ComponentActivity() {
    /** Survives rotation and resizing (a ViewModel), so the tab, the stacks and the search stay put. */
    class Navigation : ViewModel() {
        val router = Router()
        val search = SearchState()
    }

    private val navigation: Navigation by viewModels()
    private val router: Router get() = navigation.router

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        applyDebugExtras(intent)
        val model = appModel
        // A recreated activity (rotation) keeps its screens; only a fresh
        // launch acts on the link it was started with.
        if (savedInstanceState == null) handleLink(intent)
        setContent {
            QueerFrameTheme {
                RootScreen(model = model, router = router, search = navigation.search)
            }
        }
        if (savedInstanceState == null) {
            lifecycleScope.launch {
                model.loadInitial()
                model.publishUpNext()
                model.refresh()
                model.publishUpNext()
                model.rescheduleReminders()
            }
        }
        lifecycle.addObserver(object : DefaultLifecycleObserver {
            private var started = false

            override fun onStart(owner: LifecycleOwner) {
                if (!started) {
                    started = true
                    return
                }
                lifecycleScope.launch { model.refreshIfStaleOnReturn() }
            }

            override fun onStop(owner: LifecycleOwner) {
                lifecycleScope.launch {
                    model.publishUpNext()
                    model.rescheduleReminders()
                }
            }
        })
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleLink(intent)
    }

    /** A `queerframe://` link from a widget row, a reminder, or elsewhere. Anything else is ignored. */
    private fun handleLink(intent: Intent?) {
        val data = intent?.data ?: return
        val link = AppLink.parse(data.toString()) ?: return
        router.pendingLink = link
    }

    /**
     * Debug builds only: UI tests and the screenshot tour pin the clock
     * (`qf.clock`, an ISO 8601 instant) to show data past its SLA, force a
     * refresh problem (`qf.refreshProblem`: offline, unreachable, unusable),
     * and start past or at the first-run pages (`qf.onboardingSeen`). A
     * release build never reads them.
     */
    private fun applyDebugExtras(intent: Intent?) {
        if (!BuildConfig.DEBUG || intent == null) return
        intent.getStringExtra("qf.clock")?.let { AppModel.debugClock = runCatching { Instant.parse(it) }.getOrNull() }
        intent.getStringExtra("qf.refreshProblem")?.let { name ->
            AppModel.debugProblem = RefreshProblem.entries.firstOrNull { it.name.equals(name, ignoreCase = true) }
        }
        if (intent.hasExtra("qf.onboardingSeen")) {
            appModel.prefs.edit { putBoolean(AppModel.ONBOARDING_SEEN, intent.getBooleanExtra("qf.onboardingSeen", false)) }
        }
    }
}
