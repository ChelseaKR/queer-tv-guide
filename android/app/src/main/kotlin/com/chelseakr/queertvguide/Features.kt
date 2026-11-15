package com.chelseakr.queertvguide

/**
 * Switches for work that is built and tested but not yet shown to anyone.
 * Each is off until the owner approves its words; turning one on is a
 * one-line change and a CHANGELOG entry.
 */
object Features {
    /**
     * "Search" and "Favorites" in the menu a long press on the app's icon
     * opens (`shortcuts/LauncherShortcuts.kt`). Off: the app publishes none
     * and ignores a shortcut's extra.
     */
    const val LAUNCHER_SHORTCUTS = false
}
