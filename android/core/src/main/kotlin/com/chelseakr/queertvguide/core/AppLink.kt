package com.chelseakr.queertvguide.core

import java.net.URI

/**
 * A place inside the app that something outside the current screen can open:
 * a widget row, a reminder. The same form as iOS (`AppLink.swift` on the
 * parity branch): `queerframe://show/<id>`. It never leaves the device,
 * carries only a snapshot id, and opening it sends no request.
 */
sealed class AppLink {
    abstract val id: String

    data class ShowLink(override val id: String) : AppLink()
    data class CharacterLink(override val id: String) : AppLink()

    val url: String
        get() = when (this) {
            is ShowLink -> "$SCHEME://show/$id"
            is CharacterLink -> "$SCHEME://character/$id"
        }

    companion object {
        const val SCHEME = "queerframe"

        /** The notification extra a reminder carries its show id under. */
        const val REMINDER_SHOW_ID_KEY = "showID"

        /**
         * Reads a link this app made. Anything else (another scheme, an
         * unknown kind, an empty or nested id) is null, so a malformed link
         * does nothing rather than open the wrong screen.
         */
        fun parse(url: String): AppLink? {
            val uri = try {
                URI(url)
            } catch (_: Exception) {
                return null
            }
            if (!uri.scheme.equals(SCHEME, ignoreCase = true)) return null
            // "queerframe://show/lwtv:show:26": java.net.URI reads
            // "show" as the authority (or, with the colon-bearing path,
            // leaves it to the scheme-specific part), so the parts are read
            // from that instead.
            val rest = uri.rawSchemeSpecificPart ?: return null
            if (!rest.startsWith("//")) return null
            val afterSlashes = rest.substring(2)
            val slash = afterSlashes.indexOf('/')
            if (slash < 0) return null
            val kind = afterSlashes.substring(0, slash).lowercase()
            val path = afterSlashes.substring(slash + 1).substringBefore('?')
            val id = try {
                java.net.URLDecoder.decode(path.replace("+", "%2B"), "UTF-8")
            } catch (_: IllegalArgumentException) {
                return null
            }
            if (id.isEmpty() || id.contains('/')) return null
            return when (kind) {
                "show" -> ShowLink(id)
                "character" -> CharacterLink(id)
                else -> null
            }
        }
    }
}

/**
 * Why a look for new data failed, sorted the way a person can act on it (iOS
 * `RefreshProblem` on the parity branch). In every case the data already on
 * the device stays exactly as it was, and the words say so.
 */
enum class RefreshProblem(val message: String) {
    /** No connection at all. */
    OFFLINE("Couldn't check for new data: this device is offline. The data on screen stays as it is."),

    /** Online, but no usable answer: a timeout, DNS or TLS failure, or an HTTP error status. */
    UNREACHABLE("Couldn't reach the data server. The data on screen stays as it is."),

    /** A file arrived but failed the app's checks, so it was not used. */
    UNUSABLE("A new data file arrived but failed the app's checks, so it wasn't used. The data on screen stays as it is."),
    ;

    companion object {
        fun from(error: Throwable): RefreshProblem = when (error) {
            is SnapshotRefresher.RefreshException.Transport -> if (error.offline) OFFLINE else UNREACHABLE
            is SnapshotRefresher.RefreshException.Rejected -> UNUSABLE
            else -> UNREACHABLE
        }
    }
}
