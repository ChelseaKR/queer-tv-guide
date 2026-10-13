package com.chelseakr.queertvguide.ui

import androidx.core.net.toUri
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.chelseakr.queertvguide.AppModel
import com.chelseakr.queertvguide.BuildConfig
import com.chelseakr.queertvguide.R
import com.chelseakr.queertvguide.core.Attribution
import com.chelseakr.queertvguide.core.Endpoints
import com.chelseakr.queertvguide.core.Presentation
import com.chelseakr.queertvguide.core.SnapshotStore
import kotlinx.coroutines.launch

/** The Play listing, opened by the "Rate" row. Shown to everyone the same way; nothing is offered for a rating. */
object PlayListing {
    const val MARKET_URL = "market://details?id=${BuildConfig.APPLICATION_ID}"
    const val WEB_URL = "https://play.google.com/store/apps/details?id=${BuildConfig.APPLICATION_ID}"

    fun open(context: Context) {
        try {
            context.startActivity(Intent(Intent.ACTION_VIEW, MARKET_URL.toUri()).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (_: ActivityNotFoundException) {
            openExternal(context, WEB_URL)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AboutScreen(model: AppModel, state: AppModel.State) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val name = stringResource(R.string.app_name)
    var introduction by remember { mutableStateOf(false) }
    RefreshHaptics(state)
    Scaffold(topBar = { TopAppBar(title = { Text("About $name") }) }) { padding ->
        PullToRefreshBox(
            isRefreshing = state.refreshing,
            onRefresh = { scope.launch { model.requestedRefresh() } },
            modifier = Modifier.padding(padding).fillMaxSize(),
        ) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
                Column(
                    Modifier.widthIn(max = 720.dp).fillMaxWidth().verticalScroll(rememberScrollState()).padding(16.dp).testTag("about"),
                    verticalArrangement = Arrangement.spacedBy(20.dp),
                ) {
                    AboutSection("Privacy") {
                        Text(
                            "$name collects nothing: no account, no analytics, no crash reporting, no advertising or tracking code. " +
                                "Nothing leaves this device except one request for the data file this app reads — a plain, cookieless GET " +
                                "of a static file, sent only when you open the app, when you pull to refresh, or when you return to the app " +
                                "${Presentation.returnRefreshRule}.",
                            modifier = Modifier.semantics {
                                contentDescription = "Privacy posture: $name collects nothing. No account, no analytics, no crash reporting, " +
                                    "no advertising or tracking code. Nothing leaves this device except one request for the data file this app reads."
                            },
                        )
                        // DECISIONS 0007: say plainly who serves that file and what a web server sees.
                        Text("That file is served by GitHub Pages, which, like any web server, sees your IP address and logs it for security. The developer never sees that log.")
                        Text("Favorites are stored only on this device and are never sent anywhere.")
                        LinkButton("Privacy policy", Endpoints.PRIVACY_POLICY_URL, showIcon = false)
                        LinkButton("Support", Endpoints.SUPPORT_URL, showIcon = false)
                    }

                    val snapshot = state.snapshot
                    if (snapshot != null) {
                        AboutSection("Data sources") {
                            snapshot.attribution.forEach { item ->
                                Column(verticalArrangement = Arrangement.spacedBy(2.dp), modifier = Modifier.testTag("source-${item.source}")) {
                                    // "LezWatch.TV" is read "LezWatch dot T V" otherwise.
                                    Text(
                                        item.name,
                                        style = MaterialTheme.typography.titleSmall,
                                        modifier = Modifier.semantics { contentDescription = item.name.replace(".", " ") },
                                    )
                                    Text(item.text)
                                    LinkButton("License: ${item.licenseName}", item.licenseUrl, showIcon = false, modifier = Modifier.testTag("license-link-${item.source}"))
                                    LinkButton(item.url, item.url, spoken = "Visit ${item.name.replace(".", " ")}", showIcon = false, modifier = Modifier.testTag("source-link-${item.source}"))
                                }
                            }
                            // Stated by the app itself, whatever the data says.
                            Text(Attribution.NON_ENDORSEMENT, modifier = Modifier.testTag("non-endorsement"))
                        }
                        AboutSection("License") {
                            Text(snapshot.license.notice)
                            LinkButton(snapshot.license.snapshot.name, snapshot.license.snapshot.url, showIcon = false)
                        }
                        AboutSection("Coverage") {
                            val c = snapshot.coverage
                            LabeledValue("Shows", "${c.lezwatch.shows.fetched} of ${c.lezwatch.shows.available?.toString() ?: "an unreported total"}")
                            LabeledValue("Characters", "${c.lezwatch.characters.fetched} of ${c.lezwatch.characters.available?.toString() ?: "an unreported total"}")
                            LabeledValue("Schedules matched", "${c.tvmaze.joined} of ${c.tvmaze.showsTotal}")
                        }
                        AboutSection("This snapshot") {
                            DataStatusFooter(model, snapshot, state)
                            state.origin?.let {
                                Text(if (it == SnapshotStore.Origin.BUNDLED) "Bundled with the app" else "Downloaded", style = MaterialTheme.typography.bodySmall, color = subdued)
                            }
                        }
                    }

                    AboutSection("Version") {
                        LabeledValue("App", "${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})")
                        // The Play listing, opened by the system. Shown to everyone, with nothing offered for a rating.
                        TextButton(
                            onClick = { PlayListing.open(context) },
                            modifier = Modifier.heightIn(min = 48.dp).testTag("rate-app").semantics {
                                onClick(label = "Opens Google Play to rate or review this app") { PlayListing.open(context); true }
                            },
                        ) { Text("Rate $name") }
                    }

                    // The first-run pages again, last, so the sections above keep their place.
                    TextButton(
                        onClick = { introduction = true },
                        modifier = Modifier.heightIn(min = 48.dp).testTag("how-it-works").semantics {
                            onClick(label = "Spoilers, sources and privacy, in five pages") { introduction = true; true }
                        },
                    ) { Text("How $name works") }
                }
            }
        }
    }
    if (introduction) {
        Dialog(onDismissRequest = { introduction = false }, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
            OnboardingScreen(isFirstRun = false, finish = { introduction = false })
        }
    }
}

@Composable
private fun AboutSection(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionHeading(title)
        content()
        ListDivider()
    }
}
