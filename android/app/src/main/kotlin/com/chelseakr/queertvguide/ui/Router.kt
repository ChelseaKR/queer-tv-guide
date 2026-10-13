package com.chelseakr.queertvguide.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.chelseakr.queertvguide.core.AppLink

/** A screen pushed over a tab's list. */
sealed interface Destination {
    data class ShowScreen(val id: String) : Destination
    data class CharacterScreen(val id: String) : Destination
}

enum class Tab(val title: String) { SEARCH("Search"), FAVORITES("Favorites"), ABOUT("About") }

/**
 * Which tab is showing and each tab's stack of pushed screens. A link (a
 * widget row, a reminder) opens on Favorites with its screen pushed, so Back
 * returns to Favorites, as on iOS. A link that arrives before the first-run
 * pages are finished waits until they are.
 */
class Router {
    var tab by mutableStateOf(Tab.SEARCH)
    val stacks: Map<Tab, MutableList<Destination>> = Tab.entries.associateWith { mutableStateListOf() }
    var pendingLink by mutableStateOf<AppLink?>(null)

    fun stack(tab: Tab = this.tab): MutableList<Destination> = stacks.getValue(tab)

    fun push(destination: Destination, tab: Tab = this.tab) {
        val stack = stack(tab)
        if (stack.lastOrNull() != destination) stack.add(destination)
    }

    /** On a wide screen a list row replaces the detail pane rather than piling up. */
    fun show(destination: Destination, replace: Boolean) {
        val stack = stack()
        if (replace) stack.clear()
        push(destination)
    }

    fun pop(): Boolean {
        val stack = stack()
        if (stack.isEmpty()) return false
        stack.removeAt(stack.lastIndex)
        return true
    }

    fun open(link: AppLink) {
        tab = Tab.FAVORITES
        val stack = stack(Tab.FAVORITES)
        stack.clear()
        stack.add(
            when (link) {
                is AppLink.ShowLink -> Destination.ShowScreen(link.id)
                is AppLink.CharacterLink -> Destination.CharacterScreen(link.id)
            },
        )
    }
}
