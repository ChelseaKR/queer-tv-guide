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
 * Colors chosen for contrast, the values iOS uses (AccessibleStyle.swift).
 * The accent is queerframe.app's aubergine pair (DECISIONS 0040): #6A2C9C is
 * 8.6:1 on white, #D9B8FF 10.9:1 on #121212; [subdued] text ~10:1 in both.
 * Coral ([edgeLight], [edgeDark]) is an edge only, never text.
 * tests/test_app_accent_contrast.py holds every text pair here to 4.5:1.
 * No dynamic (wallpaper) color: its secondary text can fall under WCAG AA's
 * 4.5:1, and these were checked.
 */
object QfColors {
    val accentLight = Color(0xFF6A2C9C)
    val accentDark = Color(0xFFD9B8FF)
    val onAccentLight = Color(0xFFFFFFFF)
    val onAccentDark = Color(0xFF1D1027)
    val edgeLight = Color(0xFFFF6F4F)
    val edgeDark = Color(0xFFFF8A6B)
    val subduedLight = Color(0xFF404040)
    val subduedDark = Color(0xFFC7C7C7)
}

private val Light: ColorScheme = lightColorScheme(
    primary = QfColors.accentLight,
    onPrimary = QfColors.onAccentLight,
    primaryContainer = Color(0xFFECE3F4),
    onPrimaryContainer = Color(0xFF2B1740),
    secondaryContainer = Color(0xFFECE3F4),
    onSecondaryContainer = Color(0xFF2B1740),
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
    onPrimary = QfColors.onAccentDark,
    primaryContainer = Color(0xFF3A2650),
    onPrimaryContainer = Color(0xFFF3ECF7),
    secondaryContainer = Color(0xFF3A2650),
    onSecondaryContainer = Color(0xFFF3ECF7),
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
    CompositionLocalProvider(
        LocalReduceMotion provides reduceMotion,
        LocalAccentEdge provides if (dark) QfColors.edgeDark else QfColors.edgeLight,
    ) {
        MaterialTheme(colorScheme = if (dark) Dark else Light, content = content)
    }
}

/** De-emphasized text that still clears 4.5:1. */
val subdued: Color @Composable get() = MaterialTheme.colorScheme.onSurfaceVariant

/** Coral for an edge (the Reveal control's outline); never a text color. */
val LocalAccentEdge = compositionLocalOf { QfColors.edgeLight }

val accentEdge: Color @Composable get() = LocalAccentEdge.current
