package com.chelseakr.queertvguide.ui

import android.content.Context
import android.content.Intent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.StarOutline
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.chelseakr.queertvguide.AppModel
import com.chelseakr.queertvguide.core.Attribution
import com.chelseakr.queertvguide.core.FavoritesStore
import com.chelseakr.queertvguide.core.Presentation
import com.chelseakr.queertvguide.core.Sharing
import com.chelseakr.queertvguide.core.Show
import com.chelseakr.queertvguide.core.Snapshot

/** A readable column on wide screens, instead of a phone layout stretched edge to edge. */
private val READABLE_WIDTH = 720.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DetailScaffold(
    model: AppModel,
    title: String,
    kind: FavoritesStore.Kind,
    id: String,
    canGoBack: Boolean,
    onBack: () -> Unit,
    content: @Composable () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                navigationIcon = {
                    if (canGoBack) IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") }
                },
                actions = { FavoriteButton(model, kind, id) },
            )
        },
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize(), contentAlignment = Alignment.TopCenter) {
            Column(
                Modifier
                    .widthIn(max = READABLE_WIDTH)
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(20.dp),
            ) { content() }
        }
    }
}

/** The one control that changes favorites. A selection haptic answers each tap. */
@Composable
fun FavoriteButton(model: AppModel, kind: FavoritesStore.Kind, id: String) {
    val haptics = LocalHapticFeedback.current
    var isFavorite by remember(kind, id) { mutableStateOf(model.favorites.isFavorite(kind, id)) }
    IconButton(
        onClick = {
            isFavorite = model.favorites.toggle(kind, id)
            haptics.performHapticFeedback(if (isFavorite) HapticFeedbackType.ToggleOn else HapticFeedbackType.ToggleOff)
        },
        modifier = Modifier.testTag("favorite-button"),
    ) {
        Icon(
            if (isFavorite) Icons.Filled.Star else Icons.Outlined.StarOutline,
            contentDescription = if (isFavorite) "Remove from favorites" else "Add to favorites",
        )
    }
}

@Composable
fun ShowScreen(model: AppModel, state: AppModel.State, id: String, canGoBack: Boolean, onBack: () -> Unit, open: (Destination) -> Unit) {
    val snapshot = state.snapshot
    val show = snapshot?.show(id)
    if (snapshot == null || show == null) {
        NotFound("Show not found", canGoBack, onBack)
        return
    }
    val context = LocalContext.current
    val text = model.dateText()
    DetailScaffold(model, show.title, FavoritesStore.Kind.SHOW, show.id, canGoBack, onBack) {
        // Header: the screen's first heading, then its facts as one phrase.
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(show.title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
            Column(Modifier.clearAndSetSemantics { contentDescription = spokenFacts(show) }) {
                Text("${Presentation.years(show.years)} · ${Presentation.seasons(show.seasons)}", style = MaterialTheme.typography.bodyMedium, color = subdued)
                if (show.networks.isNotEmpty()) Text(show.networks.joinToString(", ") { it.name }, style = MaterialTheme.typography.bodyMedium, color = subdued)
            }
            LezWatchSourceLink(show.title, show.sourceUrl)
            TextButton(
                onClick = { share(context, show) },
                modifier = Modifier.heightIn(min = 48.dp).testTag("share-show").semantics {
                    contentDescription = "Share ${show.title}"
                    onClick(label = "Shares its LezWatch.TV page") { share(context, show); true }
                },
            ) {
                Icon(Icons.Filled.Share, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(6.dp))
                Text("Share this show")
            }
        }

        Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            SectionHeading("Ratings")
            LabeledValue("Worth it", Presentation.worthIt(show.ratings.worthIt))
            LabeledValue("Quality", Presentation.ratingValue(show.ratings.quality))
            LabeledValue("Realness", Presentation.ratingValue(show.ratings.realness))
            LabeledValue("Screentime", Presentation.ratingValue(show.ratings.screentime))
        }
        // LezWatch's worth-it explanation can name a death outright, so it stays closed.
        show.ratings.worthItDetails?.takeIf { it.isNotEmpty() }?.let { Disclosure("Why? (may contain spoilers)", it) }

        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Column(Modifier.semantics(mergeDescendants = true) {}) {
                SectionHeading("Next episode")
                Text(Presentation.nextEpisode(show.schedule, state.clock, text), modifier = Modifier.testTag("next-episode"))
            }
            // TVmaze's CC BY-SA 4.0 credit, wherever its data shows.
            Attribution.tvmazeCredit(show.schedule, snapshot)?.let { TvmazeCreditLinks(it) }
        }

        // The show-level "does she die", behind the same closed-by-default reveal as a character's.
        val deaths = Presentation.showDeaths(snapshot.charactersInShow(show.id), show)
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            SectionHeading("Do any queer characters die?")
            SpoilerReveal("Reveals which listed characters in ${show.title} have a recorded death.") {
                Column(Modifier.clearAndSetSemantics { contentDescription = deaths.spoken }, verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(deaths.headline)
                    deaths.lines.forEach { Text(it) }
                    deaths.notes.forEach { Text(it, style = MaterialTheme.typography.bodyMedium, color = subdued) }
                }
            }
        }

        // Death-revealing tropes ("Bury Your Queers") are left out here and stated in the reveal instead.
        val tropes = Presentation.withoutSpoilers(show.tropes, Presentation.deathSpoilerTropeSlugs)
        if (tropes.isNotEmpty() || show.triggers.isNotEmpty()) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (tropes.isNotEmpty()) {
                    SectionHeading("Tropes")
                    Text(Presentation.terms(tropes, Presentation.NO_TROPES))
                }
                if (show.triggers.isNotEmpty()) {
                    SectionHeading("Trigger warnings")
                    Text(Presentation.terms(show.triggers, Presentation.NO_TRIGGERS))
                }
            }
        }

        val cast = snapshot.charactersInShow(show.id)
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            SectionHeading("Characters")
            if (cast.isEmpty()) {
                Text(Presentation.NO_CHARACTERS, color = subdued)
            } else {
                cast.forEach { c -> RowButton({ open(Destination.CharacterScreen(c.id)) }) { CharacterRowContent(c, snapshot) } }
            }
        }

        val similar = snapshot.similarShows(show).take(8)
        if (similar.isNotEmpty()) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                SectionHeading("Similar shows")
                similar.forEach { s -> RowButton({ open(Destination.ShowScreen(s.id)) }) { ShowRowContent(s) } }
            }
        }

        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            SectionHeading("Where to watch")
            if (show.watchLinks.isEmpty()) {
                Text(Presentation.NO_WATCH_LINKS, color = subdued)
            } else {
                // Link out only: this never plays or embeds video.
                show.watchLinks.forEach { link ->
                    LinkButton(
                        Presentation.watchLinkLabel(link, show.networks),
                        link.url,
                        spoken = Presentation.watchLinkSpoken(link, show.networks),
                        hint = "Opens ${Presentation.displayHost(link.host)} in your browser",
                    )
                    // DECISIONS 0019: an affiliate link says so, in words.
                    if (Presentation.isPaidLink(link)) {
                        Text(
                            Presentation.PAID_LINK_NOTE,
                            style = MaterialTheme.typography.bodySmall,
                            color = subdued,
                            modifier = Modifier.padding(start = 12.dp).clearAndSetSemantics {}.testTag("paid-link-note"),
                        )
                    }
                }
            }
        }

        show.notes.plot?.takeIf { it.isNotEmpty() }?.let { Disclosure("Plot notes (may contain spoilers)", it) }

        AttributionFooter(model, snapshot, state)
    }
}

/** "1995 to 2001. 6 seasons. Syndication, USA Network." Words, not "en dash" and "middle dot". */
fun spokenFacts(show: Show): String {
    val years = Presentation.years(show.years)
        .replace(" – ongoing status not recorded", ", ongoing status not recorded")
        .replace(" – ", " to ")
    val parts = mutableListOf(years, Presentation.seasons(show.seasons))
    if (show.networks.isNotEmpty()) parts += show.networks.joinToString(", ") { it.name }
    return parts.joinToString(". ") + "."
}

/** Shares a show's LezWatch.TV page, cleaned of any query or fragment; the system sheet sends it where the person picks. */
private fun share(context: Context, show: Show) {
    val send = Intent(Intent.ACTION_SEND)
        .setType("text/plain")
        .putExtra(Intent.EXTRA_SUBJECT, show.title)
        .putExtra(Intent.EXTRA_TEXT, Sharing.cleanUrl(show.sourceUrl))
    context.startActivity(Intent.createChooser(send, "Share ${show.title}").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
}

@Composable
private fun AttributionFooter(model: AppModel, snapshot: Snapshot, state: AppModel.State) {
    val context = LocalContext.current
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        ListDivider()
        snapshot.attribution.forEach { item ->
            TextButton(onClick = { openExternal(context, item.url) }, modifier = Modifier.heightIn(min = 48.dp)) {
                Text(item.text, style = MaterialTheme.typography.bodySmall, color = subdued)
            }
        }
        DataStatusFooter(model, snapshot, state)
    }
}

@Composable
fun CharacterScreen(model: AppModel, state: AppModel.State, id: String, canGoBack: Boolean, onBack: () -> Unit, open: (Destination) -> Unit) {
    val snapshot = state.snapshot
    val character = snapshot?.character(id)
    if (snapshot == null || character == null) {
        NotFound("Character not found", canGoBack, onBack)
        return
    }
    DetailScaffold(model, character.name, FavoritesStore.Kind.CHARACTER, character.id, canGoBack, onBack) {
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(character.name, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold, modifier = Modifier.semantics { heading() })
            val actors = character.actors.mapNotNull { it.name }
            if (actors.isNotEmpty()) Text("Played by " + actors.joinToString(", "), style = MaterialTheme.typography.bodyMedium, color = subdued)
            LezWatchSourceLink(character.name, character.sourceUrl)
        }
        Column(Modifier.semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
            character.gender?.let { LabeledValue("Gender", it.name) }
            character.sexuality?.let { LabeledValue("Sexuality", it.name) }
            character.romantic?.let { LabeledValue("Romantic orientation", it.name) }
            // "Dead Queers" would answer the question the reveal below keeps closed.
            val cliches = Presentation.withoutSpoilers(character.cliches, Presentation.deathSpoilerClicheSlugs)
            if (cliches.isNotEmpty()) LabeledValue("Tropes", cliches.joinToString(", ") { it.name })
        }
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            // Named, not "she": LezWatch covers trans men and non-binary characters too.
            SectionHeading("Does ${character.name} die?")
            SpoilerReveal("Reveals whether a death is recorded for ${character.name} in this snapshot.") {
                Text(Presentation.death(character.death, character.name))
            }
        }
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            SectionHeading("Appears in")
            character.shows.forEach { link ->
                snapshot.show(link.showId)?.let { show ->
                    RowButton({ open(Destination.ShowScreen(show.id)) }) {
                        Column(Modifier.semantics(mergeDescendants = true) {}) {
                            Text(show.title, style = MaterialTheme.typography.titleMedium)
                            link.role?.let { role ->
                                Text(role.replaceFirstChar { it.uppercase() }, style = MaterialTheme.typography.bodySmall, color = subdued)
                            }
                        }
                    }
                }
            }
        }
        DataStatusFooter(model, snapshot, state)
    }
}

/** A full-width row that opens another screen. */
@Composable
private fun RowButton(onClick: () -> Unit, content: @Composable () -> Unit) {
    val haptics = LocalHapticFeedback.current
    Box(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .clickable {
                haptics.performHapticFeedback(HapticFeedbackType.ContextClick)
                onClick()
            }
            .padding(vertical = 8.dp),
    ) { content() }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun NotFound(title: String, canGoBack: Boolean, onBack: () -> Unit) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(title) },
                navigationIcon = { if (canGoBack) IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") } },
            )
        },
    ) { padding -> EmptyState(title, Modifier.padding(padding), message = "It is not in the data on this device.") }
}
