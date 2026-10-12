package com.chelseakr.queertvguide.core

import java.net.URI

/**
 * What the app must credit, and where (docs/LICENSES-AND-ATTRIBUTION.md,
 * DECISIONS 0013): every show and character links to its LezWatch.TV page;
 * wherever TVmaze schedule data shows, a TVmaze link and the CC BY-SA 4.0
 * license link show with it; About names both and says neither endorses the
 * app. Every URL comes from the snapshot itself.
 */
object Attribution {
    const val LEZWATCH_SOURCE = "lezwatch"
    const val TVMAZE_SOURCE = "tvmaze"

    /** Shown on the About screen whatever the snapshot's own text says. */
    const val NON_ENDORSEMENT = "LezWatch.TV and TVmaze do not endorse this app."

    const val LEZWATCH_LINK_TITLE = "View on LezWatch.TV"

    /** TalkBack's label for a record's LezWatch.TV link: names the record. */
    fun lezWatchLinkLabel(name: String): String = "View $name on LezWatch.TV"

    data class Link(val title: String, val url: String)

    data class TvmazeCredit(val source: Link, val license: Link) {
        /** The whole credit as one sentence, for TalkBack and tests. */
        val spoken: String get() = "${source.title}, licensed ${license.title}."
    }

    /** The credit for a show's schedule; null when TVmaze never matched the show. */
    fun tvmazeCredit(schedule: Schedule, snapshot: Snapshot): TvmazeCredit? {
        if (!schedule.scheduleKnown) return null
        return tvmazeCredit(snapshot, schedule.tvmazeUrl)
    }

    /** The general TVmaze credit, linking TVmaze itself unless a show page is given. */
    fun tvmazeCredit(snapshot: Snapshot, showPage: String? = null): TvmazeCredit? {
        val item = snapshot.attribution(TVMAZE_SOURCE) ?: return null
        return TvmazeCredit(
            source = Link("Schedule data from TVmaze", showPage ?: item.url),
            license = Link(item.licenseName, item.licenseUrl),
        )
    }
}

/** What Share hands to the system share sheet: a show's LezWatch.TV page and nothing else. */
object Sharing {
    /** [url] without query, fragment or credentials, so a shared link carries nothing about who shared it. */
    fun cleanUrl(url: String): String = try {
        val u = URI(url)
        URI(u.scheme, null, u.host, u.port, u.rawPath?.let { URI(null, null, it, null).path }, null, null).toString()
    } catch (_: Exception) {
        url
    }
}

/** The one network location this app ever contacts, and the pages it opens in the browser. */
object Endpoints {
    /** DECISIONS 0007: the app's one fetch URL. */
    const val SNAPSHOT_URL = "https://chelseakr.github.io/queer-tv-guide/snapshot.v1.json"
    const val PRIVACY_POLICY_URL = "https://chelseakr.github.io/queer-tv-guide/privacy.html"
    const val SUPPORT_URL = "https://chelseakr.github.io/queer-tv-guide/support.html"
}
