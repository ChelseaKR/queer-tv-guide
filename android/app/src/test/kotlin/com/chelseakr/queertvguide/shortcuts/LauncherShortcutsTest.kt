package com.chelseakr.queertvguide.shortcuts

import com.chelseakr.queertvguide.Features
import com.chelseakr.queertvguide.core.LauncherShortcut
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** The launcher shortcuts are on (owner, 2026-11-15) and each has its icon in the app. */
class LauncherShortcutsTest {
    private val res = File(System.getProperty("qf.repoRoot") ?: error("qf.repoRoot is not set"), "android/app/src/main/res/drawable")

    @Test
    fun theShortcutsAreOn() {
        assertTrue(Features.LAUNCHER_SHORTCUTS)
    }

    @Test
    fun eachShortcutHasItsIcon() {
        for (shortcut in LauncherShortcut.entries) {
            val icon = File(res, "ic_shortcut_${shortcut.id}.xml")
            assertTrue("$icon is missing", icon.isFile)
        }
        val code = File(res, "../../kotlin/com/chelseakr/queertvguide/shortcuts/LauncherShortcuts.kt").readText()
        for (shortcut in LauncherShortcut.entries) {
            assertTrue("LauncherShortcuts.kt does not use ic_shortcut_${shortcut.id}", code.contains("R.drawable.ic_shortcut_${shortcut.id}"))
        }
    }
}
