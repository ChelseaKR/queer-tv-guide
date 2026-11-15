package com.chelseakr.queertvguide.shortcuts

import android.content.Context
import android.content.Intent
import androidx.core.content.pm.ShortcutInfoCompat
import androidx.core.content.pm.ShortcutManagerCompat
import androidx.core.graphics.drawable.IconCompat
import com.chelseakr.queertvguide.Features
import com.chelseakr.queertvguide.MainActivity
import com.chelseakr.queertvguide.R
import com.chelseakr.queertvguide.core.LauncherShortcut

/**
 * The launcher's long-press menu: "Search" opens Search with the keyboard
 * up, "Favorites" opens Favorites and its next episodes. Dynamic shortcuts,
 * so [Features.LAUNCHER_SHORTCUTS] decides whether they exist: on, they are
 * set; off, any this app set before are taken away. Set on the device only,
 * with the system's own shortcut service; nothing is reported about which
 * shortcut is used.
 */
object LauncherShortcuts {
    fun sync(context: Context) {
        if (!Features.LAUNCHER_SHORTCUTS) {
            ShortcutManagerCompat.removeDynamicShortcuts(context, LauncherShortcut.entries.map { it.id })
            return
        }
        ShortcutManagerCompat.setDynamicShortcuts(context, LauncherShortcut.entries.map { info(context, it) })
    }

    /** The shortcut a launched intent carries, when the feature is on; null otherwise. */
    fun from(intent: Intent?): LauncherShortcut? {
        if (!Features.LAUNCHER_SHORTCUTS || intent == null) return null
        return LauncherShortcut.from(intent.getStringExtra(LauncherShortcut.EXTRA))
    }

    private fun info(context: Context, shortcut: LauncherShortcut): ShortcutInfoCompat {
        val intent = Intent(context, MainActivity::class.java)
            .setAction(Intent.ACTION_VIEW)
            .putExtra(LauncherShortcut.EXTRA, shortcut.id)
        val icon = when (shortcut) {
            LauncherShortcut.SEARCH -> R.drawable.ic_shortcut_search
            LauncherShortcut.FAVORITES -> R.drawable.ic_shortcut_favorites
        }
        return ShortcutInfoCompat.Builder(context, shortcut.id)
            .setShortLabel(shortcut.label)
            .setLongLabel(shortcut.label)
            .setIcon(IconCompat.createWithResource(context, icon))
            .setIntent(intent)
            .build()
    }
}
