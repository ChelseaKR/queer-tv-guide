package com.chelseakr.queertvguide.ui

import android.provider.Settings
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.remember
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

/**
 * Colors chosen for contrast, the values iOS measured (AccessibleStyle.swift):
 * the accent is ~7:1 on white and ~9:1 on near-black; [subdued] text ~10:1 in
 * both. No dynamic (wallpaper) color: its secondary text can fall under
 * WCAG AA's 4.5:1, and these were checked.
 */
object QfColors {
    val accentLight = Color(0xFF0057B3)
    val accentDark = Color(0xFF73B8FF)
    val subduedLight = Color(0xFF404040)
    val subduedDark = Color(0xFFC7C7C7)
}

private val Light: ColorScheme = lightColorScheme(
    primary = QfColors.accentLight,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD6E6FA),
    onPrimaryContainer = Color(0xFF002B5C),
    secondaryContainer = Color(0xFFDDE6F3),
    onSecondaryContainer = Color(0xFF111111),
    background = Color.White,
    onBackground = Color(0xFF111111),
    surface = Color.White,
    onSurface = Color(0xFF111111),
    surfaceVariant = Color(0xFFF0F0F3),
    onSurfaceVariant = QfColors.subduedLight,
    surfaceContainer = Color(0xFFF3F3F6),
    surfaceContainerHigh = Color(0xFFEDEDF0),
    surfaceContainerHighest = Color(0xFFE6E6EA),
    surfaceContainerLow = Color(0xFFF7F7F9),
    outline = Color(0xFF6B6B6B),
    outlineVariant = Color(0xFFC9C9CE),
    error = Color(0xFFB3261E),
)

private val Dark: ColorScheme = darkColorScheme(
    primary = QfColors.accentDark,
    onPrimary = Color(0xFF00213F),
    primaryContainer = Color(0xFF0B3D73),
    onPrimaryContainer = Color(0xFFE3EEFF),
    secondaryContainer = Color(0xFF2A3442),
    onSecondaryContainer = Color(0xFFF2F2F2),
    background = Color(0xFF121212),
    onBackground = Color(0xFFF2F2F2),
    surface = Color(0xFF121212),
    onSurface = Color(0xFFF2F2F2),
    surfaceVariant = Color(0xFF26262A),
    onSurfaceVariant = QfColors.subduedDark,
    surfaceContainer = Color(0xFF1E1E21),
    surfaceContainerHigh = Color(0xFF26262A),
    surfaceContainerHighest = Color(0xFF303035),
    surfaceContainerLow = Color(0xFF1A1A1C),
    outline = Color(0xFF9A9AA0),
    outlineVariant = Color(0xFF45454B),
    error = Color(0xFFF2B8B5),
)

/** Whether the system's "Remove animations" is on: then nothing slides or fades. */
val LocalReduceMotion = compositionLocalOf { false }

@Composable
fun QueerFrameTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val context = LocalContext.current
    val reduceMotion = remember {
        Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
    }
    CompositionLocalProvider(LocalReduceMotion provides reduceMotion) {
        MaterialTheme(colorScheme = if (dark) Dark else Light, content = content)
    }
}

/** De-emphasized text that still clears 4.5:1. */
val subdued: Color @Composable get() = MaterialTheme.colorScheme.onSurfaceVariant
