"""The apps' accent is the website's aubergine pair, and every text use clears AA.

DECISIONS 0040 moves the iOS app, the iOS widget, the Android theme and the
Android widget from blue (#0057B3 / #73B8FF) to queerframe.app's aubergine
(#6A2C9C light, #D9B8FF dark; DECISIONS 0038), with coral only as an edge.
These tests read the colors from the Swift and Kotlin sources and hold:

- the same accent pair on all four surfaces, and no blue left;
- WCAG AA (4.5:1) for every text, link and selected-tab use of the accent,
  and for text drawn on an accent or container fill, in light and dark;
- coral used only as an edge (a stroke or border), never as text.

Each checker has a negative control that sabotages the real source text,
asserts the text actually changed, and expects the checker to fail.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
IOS_STYLE = REPO / "ios/QueerTVGuide/Views/Components/AccessibleStyle.swift"
IOS_WIDGET = REPO / "ios/QueerTVGuideWidgets/UpNextWidgetView.swift"
ANDROID_THEME = REPO / "android/app/src/main/kotlin/com/chelseakr/queertvguide/ui/Theme.kt"
ANDROID_WIDGET = (
    REPO / "android/app/src/main/kotlin/com/chelseakr/queertvguide/widget/UpNextWidget.kt"
)
IOS_SOURCES = REPO / "ios"
ANDROID_SOURCES = REPO / "android/app/src/main/kotlin"

# queerframe.app's link colors (DECISIONS 0038, pipeline/templates/style.css).
SITE_ACCENT = ("6A2C9C", "D9B8FF")  # (light, dark)
CORAL = {"FF6F4F", "FF8A6B"}
OLD_BLUE = ("0057B3", "73B8FF", "red: 0.0, green: 0.34", "red: 0.45, green: 0.72")
AA = 4.5

# iOS system backgrounds the accent is drawn on: systemBackground and
# secondarySystemGroupedBackground (white / #000 and #1C1C1E), the grouped
# list gray #F2F2F7, and the dark tertiary cell #2C2C2E.
IOS_BACKGROUNDS = {"light": ["FFFFFF", "F2F2F7"], "dark": ["000000", "1C1C1E", "2C2C2E"]}
# The system widget background, approximated by its lightest light-mode and
# lightest dark-mode values.
IOS_WIDGET_BACKGROUNDS = {"light": ["FFFFFF", "F2F2F7"], "dark": ["000000", "2C2C2E"]}


def luminance(hex6: str) -> float:
    channels = [int(hex6[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# --- parsers ---------------------------------------------------------------


def ios_palette(text: str) -> dict[str, tuple[str, str]]:
    """`static var name: Color` blocks built from `UIColor(rgb:)`: name -> (light, dark)."""
    pattern = re.compile(
        r"static var (\w+): Color \{.*?\?\s*UIColor\(rgb: 0x([0-9A-Fa-f]{6})\)"
        r"\s*:\s*UIColor\(rgb: 0x([0-9A-Fa-f]{6})\)",
        re.S,
    )
    return {m[1]: (m[3].upper(), m[2].upper()) for m in pattern.finditer(text)}


def ios_widget_accent(text: str) -> tuple[str, str] | None:
    comp = r"UIColor\(red: 0x(\w\w) / 255, green: 0x(\w\w) / 255, blue: 0x(\w\w) / 255"
    m = re.search(r"static let accent = .*?\?\s*" + comp + r".*?:\s*" + comp, text, re.S)
    if not m:
        return None
    return ("".join(m.groups()[3:]).upper(), "".join(m.groups()[:3]).upper())


def _kotlin_color(expr: str, named: dict[str, str]) -> str | None:
    expr = expr.strip()
    if expr == "Color.White":
        return "FFFFFF"
    if m := re.fullmatch(r"Color\(0xFF([0-9A-Fa-f]{6})\)", expr):
        return m[1].upper()
    if m := re.fullmatch(r"QfColors\.(\w+)", expr):
        return named.get(m[1])
    return None


def android_named(text: str) -> dict[str, str]:
    block = re.search(r"object QfColors \{(.*?)\n\}", text, re.S)
    if not block:
        return {}
    return {
        m[1]: m[2].upper()
        for m in re.finditer(r"val (\w+) = Color\(0xFF([0-9A-Fa-f]{6})\)", block[1])
    }


def android_scheme(text: str, which: str) -> dict[str, str]:
    """`lightColorScheme(...)` or `darkColorScheme(...)`: role -> hex."""
    named = android_named(text)
    block = re.search(which + r"ColorScheme\((.*?)\n\)", text, re.S)
    if not block:
        return {}
    roles: dict[str, str] = {}
    for m in re.finditer(r"(\w+) = ([^,\n]+),", block[1]):
        value = _kotlin_color(m[2], named)
        if value:
            roles[m[1]] = value
    return roles


def android_widget(text: str) -> dict[str, tuple[str, str]]:
    pattern = re.compile(r"val (\w+) = ColorProvider\(day = ([^,]+), night = (.+)\)\n")
    out = {}
    for m in pattern.finditer(text):
        day, night = _kotlin_color(m[2], {}), _kotlin_color(m[3], {})
        if day and night:
            out[m[1]] = (day, night)
    return out


# --- checkers: each returns a list of problems -----------------------------


def check_accent_everywhere(ios_style: str, ios_widget: str, theme: str, widget: str) -> list[str]:
    found = {
        "iOS app": ios_palette(ios_style).get("accessibleAccent"),
        "iOS widget": ios_widget_accent(ios_widget),
        "Android theme": (
            android_named(theme).get("accentLight"),
            android_named(theme).get("accentDark"),
        ),
        "Android widget": android_widget(widget).get("accent"),
    }
    problems = [f"{k}: {v} is not {SITE_ACCENT}" for k, v in found.items() if v != SITE_ACCENT]
    for name, text in [
        ("iOS app", ios_style),
        ("iOS widget", ios_widget),
        ("Android theme", theme),
        ("Android widget", widget),
    ]:
        problems += [f"{name}: old blue {b!r} left" for b in OLD_BLUE if b in text]
    return problems


def _below_aa(label: str, fg: str, bg: str) -> list[str]:
    r = contrast(fg, bg)
    return [f"{label}: {fg} on {bg} is {r:.2f}"] if r < AA else []


def check_ios_contrast(ios_style: str, ios_widget: str) -> list[str]:
    palette = ios_palette(ios_style)
    missing = [f"iOS: {n} not found" for n in ("accessibleAccent", "onAccent") if n not in palette]
    widget_accent = ios_widget_accent(ios_widget)
    if widget_accent is None:
        missing.append("iOS widget: accent not found")
    if missing:
        return missing
    accent, on_accent = palette["accessibleAccent"], palette["onAccent"]
    problems = []
    for i, scheme in enumerate(("light", "dark")):
        for bg in IOS_BACKGROUNDS[scheme]:
            problems += _below_aa(f"iOS {scheme}: accent", accent[i], bg)
        problems += _below_aa(f"iOS {scheme}: label on accent fill", on_accent[i], accent[i])
        for bg in IOS_WIDGET_BACKGROUNDS[scheme]:
            problems += _below_aa(f"iOS widget {scheme}: accent", widget_accent[i], bg)
    return problems


ANDROID_SURFACES = (
    "background",
    "surface",
    "surfaceVariant",
    "surfaceContainer",
    "surfaceContainerHigh",
    "surfaceContainerHighest",
    "surfaceContainerLow",
)
# (foreground, background): text drawn on a fill. Material 3 draws the
# selected tab's icon in onSecondaryContainer on secondaryContainer, the
# Reveal button's label likewise, and a filled button's in onPrimary.
ANDROID_FILL_PAIRS = (
    ("onPrimary", "primary"),
    ("onPrimaryContainer", "primaryContainer"),
    ("onSecondaryContainer", "secondaryContainer"),
    ("primary", "secondaryContainer"),
)


def _android_scheme_problems(roles: dict[str, str], which: str) -> list[str]:
    if "primary" not in roles:
        return [f"Android {which}: no primary found"]
    pairs = [
        (text_role, surface)
        for surface in ANDROID_SURFACES
        for text_role in ("primary", "onSurface", "onSurfaceVariant")
    ]
    problems = []
    for fg, bg in [*pairs, *ANDROID_FILL_PAIRS]:
        if fg not in roles or bg not in roles:
            problems.append(f"Android {which}: {fg}/{bg} not found")
        else:
            problems += _below_aa(f"Android {which}: {fg} on {bg}", roles[fg], roles[bg])
    return problems


def check_android_contrast(theme: str, widget: str) -> list[str]:
    problems = []
    for which in ("light", "dark"):
        problems += _android_scheme_problems(android_scheme(theme, which), which)
    colors = android_widget(widget)
    if "accent" not in colors or "background" not in colors:
        return [*problems, "Android widget: accent or background not found"]
    for i, scheme in enumerate(("light", "dark")):
        problems += _below_aa(
            f"Android widget {scheme}: accent", colors["accent"][i], colors["background"][i]
        )
    return problems


EDGE_USE = re.compile(r"strokeBorder\(\.accentEdge|BorderStroke\([^)]*accentEdge")
EDGE_DEFINITION = re.compile(r"static var accentEdge|val accentEdge|LocalAccentEdge")


def check_coral_edge_only(sources: dict[str, str]) -> list[str]:
    """Coral appears only in its definitions and as a stroke or border."""
    problems = []
    for path, text in sources.items():
        last_definition = -99
        for n, line in enumerate(text.splitlines(), 1):
            if EDGE_DEFINITION.search(line) or "val edge" in line:
                last_definition = n
            is_comment = line.strip().startswith(("//", "*", "/*"))
            allowed = EDGE_USE.search(line) or EDGE_DEFINITION.search(line)
            if "accentEdge" in line and not allowed and not is_comment:
                problems.append(f"{path}:{n}: coral used other than as an edge: {line.strip()}")
            # A coral hex value may appear only in, or just under, an edge
            # definition line (the Swift dynamic color spans a few lines).
            upper = line.upper()
            for hex6 in CORAL:
                if hex6 in upper and n - last_definition > 4:
                    problems.append(f"{path}:{n}: coral {hex6} outside an edge definition")
    return problems


def app_sources() -> dict[str, str]:
    files = [
        *IOS_SOURCES.glob("QueerTVGuide/**/*.swift"),
        *IOS_SOURCES.glob("QueerTVGuideWidgets/**/*.swift"),
        *ANDROID_SOURCES.glob("**/*.kt"),
    ]
    return {str(p.relative_to(REPO)): p.read_text(encoding="utf-8") for p in files}


def sabotage(text: str, old: str, new: str) -> str:
    changed = text.replace(old, new)
    if changed == text:
        raise AssertionError(f"sabotage did not apply: {old!r} not in the source")
    return changed


class AccentContrastTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ios_style = IOS_STYLE.read_text(encoding="utf-8")
        self.ios_widget = IOS_WIDGET.read_text(encoding="utf-8")
        self.theme = ANDROID_THEME.read_text(encoding="utf-8")
        self.widget = ANDROID_WIDGET.read_text(encoding="utf-8")

    def test_parsers_find_every_color(self) -> None:
        palette = ios_palette(self.ios_style)
        self.assertEqual(palette["accessibleAccent"], SITE_ACCENT)
        self.assertEqual(palette["onAccent"], ("FFFFFF", "1D1027"))
        self.assertEqual(palette["accentEdge"], ("FF6F4F", "FF8A6B"))
        self.assertEqual(ios_widget_accent(self.ios_widget), SITE_ACCENT)
        self.assertEqual(android_scheme(self.theme, "light")["primary"], "6A2C9C")
        self.assertEqual(android_scheme(self.theme, "dark")["primary"], "D9B8FF")
        self.assertGreaterEqual(len(android_scheme(self.theme, "light")), 15)
        self.assertEqual(android_widget(self.widget)["accent"], SITE_ACCENT)

    def test_accent_is_the_site_aubergine_everywhere(self) -> None:
        self.assertEqual(
            check_accent_everywhere(self.ios_style, self.ios_widget, self.theme, self.widget), []
        )

    def test_accent_check_fails_on_old_blue(self) -> None:
        bad = sabotage(self.theme, "Color(0xFF6A2C9C)", "Color(0xFF0057B3)")
        problems = check_accent_everywhere(self.ios_style, self.ios_widget, bad, self.widget)
        self.assertTrue(any("old blue" in p for p in problems), problems)
        bad_widget = sabotage(self.ios_widget, "0xD9 / 255", "0x73 / 255")
        problems = check_accent_everywhere(self.ios_style, bad_widget, self.theme, self.widget)
        self.assertTrue(any("iOS widget" in p for p in problems), problems)

    def test_ios_text_uses_clear_aa_in_both_schemes(self) -> None:
        self.assertEqual(check_ios_contrast(self.ios_style, self.ios_widget), [])

    def test_ios_check_fails_on_white_label_on_lilac(self) -> None:
        bad = sabotage(self.ios_style, "UIColor(rgb: 0x1D1027)", "UIColor(rgb: 0xFFFFFF)")
        problems = check_ios_contrast(bad, self.ios_widget)
        self.assertTrue(any("dark: label" in p for p in problems), problems)

    def test_ios_check_fails_on_a_pale_light_accent(self) -> None:
        bad = sabotage(self.ios_style, ": UIColor(rgb: 0x6A2C9C)", ": UIColor(rgb: 0xB38AE0)")
        problems = check_ios_contrast(bad, self.ios_widget)
        self.assertTrue(any("light: accent" in p for p in problems), problems)

    def test_android_text_uses_clear_aa_in_both_schemes(self) -> None:
        self.assertEqual(check_android_contrast(self.theme, self.widget), [])

    def test_android_check_fails_on_low_contrast_selected_tab(self) -> None:
        bad = sabotage(
            self.theme,
            "onSecondaryContainer = Color(0xFFF3ECF7)",
            "onSecondaryContainer = Color(0xFF4A2D66)",
        )
        problems = check_android_contrast(bad, self.widget)
        self.assertTrue(any("onSecondaryContainer" in p for p in problems), problems)

    def test_android_widget_check_fails_on_pale_accent(self) -> None:
        bad = sabotage(self.widget, "day = Color(0xFF6A2C9C)", "day = Color(0xFFD9B8FF)")
        problems = check_android_contrast(self.theme, bad)
        self.assertTrue(any("Android widget light" in p for p in problems), problems)

    def test_coral_is_only_an_edge(self) -> None:
        sources = app_sources()
        self.assertGreater(len(sources), 20)
        self.assertEqual(check_coral_edge_only(sources), [])
        uses = [t for t in sources.values() if EDGE_USE.search(t)]
        self.assertEqual(len(uses), 2, "one coral edge on iOS, one on Android")

    def test_coral_check_fails_on_coral_text(self) -> None:
        sources = app_sources()
        key = str(IOS_STYLE.relative_to(REPO))
        sources[key] = sabotage(
            sources[key],
            ".foregroundStyle(.subdued)\n            .accessibilityAddTraits(.isHeader)",
            ".foregroundStyle(.accentEdge)\n            .accessibilityAddTraits(.isHeader)",
        )
        self.assertTrue(check_coral_edge_only(sources))

    def test_coral_check_fails_on_a_coral_hex_elsewhere(self) -> None:
        sources = app_sources()
        key = str(ANDROID_WIDGET.relative_to(REPO))
        sources[key] = sabotage(
            sources[key], "night = Color(0xFFD9B8FF)", "night = Color(0xFFFF8A6B)"
        )
        self.assertTrue(any("coral FF8A6B" in p for p in check_coral_edge_only(sources)))


if __name__ == "__main__":
    unittest.main()
