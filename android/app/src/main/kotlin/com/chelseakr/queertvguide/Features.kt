package com.chelseakr.queertvguide

/**
 * Switches for work that is built and tested before it is shown. Each is off
 * until the owner approves its words; turning one on is a one-line change and
 * a CHANGELOG entry.
 */
object Features {
    /**
     * "Search" and "Favorites" in the menu a long press on the app's icon
     * opens (`shortcuts/LauncherShortcuts.kt`). On since the owner approved
     * both labels (2026-11-15). Off again: the app removes the ones it set
     * and ignores a shortcut's extra.
     */
    const val LAUNCHER_SHORTCUTS = true
}
