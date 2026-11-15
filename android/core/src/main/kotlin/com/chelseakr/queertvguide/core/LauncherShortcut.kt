package com.chelseakr.queertvguide.core

/**
 * A launcher shortcut: what a long press on the app's icon offers (Android
 * 7.1 and later), each one a tab to open. It carries only which tab, as an
 * intent extra to this app's own activity; it is set on the device and sends
 * nothing anywhere. Off by default (the app's `Features.LAUNCHER_SHORTCUTS`).
 */
enum class LauncherShortcut(
    /** The shortcut's id with the launcher, and the extra's value. Never changes once shipped. */
    val id: String,
    /** The words the launcher shows: the tab's own name, nothing new. */
    val label: String,
) {
    SEARCH("search", "Search"),
    FAVORITES("favorites", "Favorites"),
    ;

    companion object {
        /** The intent extra a shortcut carries its [id] under. */
        const val EXTRA = "qf.shortcut"

        /** Reads a shortcut this app made; anything else is null and does nothing. */
        fun from(value: String?): LauncherShortcut? = entries.firstOrNull { it.id == value }
    }
}
