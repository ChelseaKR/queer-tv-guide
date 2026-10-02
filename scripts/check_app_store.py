#!/usr/bin/env python3
"""App Store readiness and release preflight for the Queer Frame iOS app.

Adapted from the same check in the Trout Truck app's repository. The
difference that matters here: this project keeps its build settings in
`ios/Config/*.xcconfig` (XcodeGen writes a project.pbxproj that points each
target configuration at one of them), and the app's Info.plist is generated
from `INFOPLIST_KEY_*` settings. So every setting below is read the way
Xcode resolves it: project-level settings, then the target's xcconfig chain
with its `#include`s, then the target's own settings in the project file.

Two modes:

- With no tag (`make appstore`, so `make verify`): the readiness audit. It
  reads the files App Store Connect and App Review judge the binary by and
  fails on anything that would bounce an upload or contradict the listing:

  - every target resolves to one MARKETING_VERSION (X.Y.Z) and one integer
    CURRENT_PROJECT_VERSION, both set only in ios/Config/Shared.xcconfig (an
    extension whose version differs from its app is rejected on upload);
  - every target is iPhone-only (TARGETED_DEVICE_FAMILY = 1, DECISIONS
    0009) and signs device builds with team 6X5YH93QNM, and the enrollment
    ID appears nowhere in the build files;
  - the app's generated Info.plist declares export compliance
    (ITSAppUsesNonExemptEncryption NO), a launch screen, the display name
    "Queer Frame" and the working bundle ID (DECISIONS 0006), and the
    widget's bundle ID sits under the app's; no target declares a
    background mode, and the widget's Info.plist takes its versions from
    the build settings;
  - the project has no remote Swift package and GuideCore depends on no
    package, no Swift file that ships imports a module outside Apple's SDK
    and GuideCore, and nothing ships StoreKit or a .storekit file: the app
    is paid up front with no in-app purchase (DECISIONS 0003, 0011);
  - entitlements hold only the one App Group (no push, no iCloud);
  - both privacy manifests say no tracking, no tracking domains and no
    collected data, and every required-reason API the shipped Swift calls
    has its category declared, with a reason, in the manifest of the
    bundle that ships it;
  - the app icon set has every file it names, at the pixel size it names,
    with no alpha channel, including the 1024x1024 marketing icon.

- With `--release-tag vX.Y.Z` (the release workflow): the preflight. The tag
  must be stable SemVer equal to MARKETING_VERSION, the build number must be
  higher than the one at every earlier `v*` tag passed with
  `--earlier-xcconfig` (App Store Connect refuses a reused build number),
  and CHANGELOG.md must have a dated, non-empty `## [X.Y.Z]` section, which
  `--notes-out` writes as the release notes.

`--self-test` feeds each check an input it must reject and one it must
accept, and exits non-zero if any check fails to discriminate, so a check
that has quietly stopped matching cannot report a ready app.
"""

from __future__ import annotations

import argparse
import json
import plistlib
import re
import struct
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
IOS = ROOT / "ios"
CONFIG = IOS / "Config"
PBXPROJ = IOS / "QueerTVGuide.xcodeproj" / "project.pbxproj"
PROJECT_YML = IOS / "project.yml"
PACKAGE_SWIFT = IOS / "GuideCore" / "Package.swift"
# The one file that may set the version and build number.
VERSION_XCCONFIG = CONFIG / "Shared.xcconfig"
WIDGET_INFO = IOS / "QueerTVGuideWidgets" / "Info.plist"
ICONSET = IOS / "QueerTVGuide" / "Assets.xcassets" / "AppIcon.appiconset"
CHANGELOG = ROOT / "CHANGELOG.md"

APP_TARGET = "QueerTVGuide"
WIDGET_TARGET = "QueerTVGuideWidgets"
DISPLAY_NAME = "Queer Frame"
BUNDLE_ID = "com.chelseakr.queertvguide"
APP_GROUP = "group.com.chelseakr.queertvguide"

# Each shipped bundle: its privacy manifest and the Swift compiled into it.
# GuideCore is a static library linked into the app, so its sources count
# against the app's manifest. The widget links GuideCore too, but uses only
# its UpNext reader; the release workflow checks the built widget binary for
# required-reason symbols, which is where a linked-in call would show.
BUNDLES: Mapping[str, tuple[Path, tuple[Path, ...]]] = {
    "app": (
        IOS / "QueerTVGuide" / "PrivacyInfo.xcprivacy",
        (IOS / "QueerTVGuide", IOS / "GuideCore" / "Sources"),
    ),
    "widget": (
        IOS / "QueerTVGuideWidgets" / "PrivacyInfo.xcprivacy",
        (IOS / "QueerTVGuideWidgets",),
    ),
}

TEAM_ID = "6X5YH93QNM"
# The Apple Developer enrollment ID. It looks like a team ID and is not one.
ENROLLMENT_ID = "ACKGM9XK9V"
# Apple frameworks the shipped code may import, plus the local package.
# Anything else is third-party code and needs a decision (DECISIONS 0002).
# StoreKit is deliberately absent: the app is paid up front (DECISIONS 0003).
ALLOWED_IMPORTS = frozenset(
    {
        "Foundation",
        "GuideCore",
        "Observation",
        "OSLog",
        "SwiftUI",
        "UIKit",
        "UserNotifications",
        "WidgetKit",
    }
)
ALLOWED_ENTITLEMENTS = frozenset({"com.apple.security.application-groups"})

# Apple's required-reason API categories and the Swift spellings that reach
# them (developer.apple.com, "Describing use of required reason API").
REQUIRED_REASON: Mapping[str, re.Pattern[str]] = {
    "NSPrivacyAccessedAPICategoryUserDefaults": re.compile(
        r"\b(?:NS)?UserDefaults\b|@AppStorage\b"
    ),
    "NSPrivacyAccessedAPICategoryFileTimestamp": re.compile(
        r"\.(?:creationDate|modificationDate|contentModificationDate"
        r"|creationDateKey|contentModificationDateKey|contentAccessDateKey)\b"
        r"|\battributesOfItem\b|\bgetattrlist\b|\b[fl]?stat\("
    ),
    "NSPrivacyAccessedAPICategorySystemBootTime": re.compile(
        r"\bsystemUptime\b|\bmach_(?:absolute|continuous)_time\b"
    ),
    "NSPrivacyAccessedAPICategoryDiskSpace": re.compile(
        r"\bvolume(?:Available|Total)Capacity\w*|\bsystem(?:Free)?Size\b|\bf?statv?fs\("
    ),
    "NSPrivacyAccessedAPICategoryActiveKeyboards": re.compile(r"\bactiveInputModes\b"),
}

_XCCONFIG_LINE = re.compile(
    r"^\s*(?P<key>[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?)\s*=\s*(?P<value>.*?)\s*;?\s*$"
)
_INCLUDE = re.compile(r'^\s*#include\??\s+"(?P<path>[^"]+)"')
_PBX_CONFIG = re.compile(
    r"^\t\t(?P<id>[0-9A-F]{24}) /\* (?P<name>[^*]+) \*/ = \{\n"
    r"\t\t\tisa = XCBuildConfiguration;\n"
    r"(?:\t\t\tbaseConfigurationReference = [0-9A-F]{24} /\* (?P<base>[^*]+) \*/;\n)?"
    r"\t\t\tbuildSettings = \{\n(?P<body>.*?)\n\t\t\t\};",
    re.MULTILINE | re.DOTALL,
)
_PBX_LIST = re.compile(
    r"/\* Build configuration list for (?P<kind>PBXNativeTarget|PBXProject) "
    r'"(?P<owner>[^"]+)" \*/ = \{\n\t\t\tisa = XCConfigurationList;\n'
    r"\t\t\tbuildConfigurations = \(\n(?P<ids>.*?)\);",
    re.DOTALL,
)
_PBX_SETTING = re.compile(
    r"^\t\t\t\t(?P<key>[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?) = (?P<value>[^;(]*);", re.MULTILINE
)
_IMPORT = re.compile(
    r"^[ \t]*(?:@\w+[ \t]+)*import[ \t]+"
    r"(?:(?:struct|class|enum|protocol|func|var|let|typealias)[ \t]+)?(?P<module>\w+)",
    re.MULTILINE,
)
_SEMVER_TAG = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


# MARK: build settings, resolved the way Xcode does


def parse_xcconfig(text: str, include: Any = None) -> dict[str, str]:
    """Settings from one xcconfig, with `#include`s resolved through `include`.

    `include(path)` returns the included file's text. Later lines override
    earlier ones, as in Xcode; `//` comments are ignored.
    """
    settings: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.split("//", 1)[0] if "://" not in raw else raw
        inc = _INCLUDE.match(line)
        if inc:
            if include is not None:
                settings.update(parse_xcconfig(include(inc.group("path")), include))
            continue
        m = _XCCONFIG_LINE.match(line)
        if m:
            settings[m.group("key")] = m.group("value").strip().strip('"')
    return settings


def _xcconfig_file(name: str) -> dict[str, str]:
    path = CONFIG / name
    return parse_xcconfig(
        path.read_text(encoding="utf-8"),
        lambda inc: (CONFIG / inc).read_text(encoding="utf-8"),
    )


def target_settings(
    pbxproj: str, xcconfig: Any = _xcconfig_file
) -> dict[tuple[str, str], dict[str, str]]:
    """(target, configuration) -> resolved settings, for every native target.

    Layers, lowest first: the project-level configuration of the same name,
    the target's base xcconfig (with includes), the target's own settings.
    """
    configs = {m.group("id"): m for m in _PBX_CONFIG.finditer(pbxproj)}

    def layer(config_id: str) -> tuple[str, dict[str, str]]:
        m = configs[config_id]
        own = {
            s.group("key"): s.group("value").strip().strip('"')
            for s in _PBX_SETTING.finditer(m.group("body"))
        }
        base = xcconfig(m.group("base")) if m.group("base") else {}
        return m.group("name"), {**base, **own}

    project: dict[str, dict[str, str]] = {}
    targets: dict[str, list[str]] = {}
    for lst in _PBX_LIST.finditer(pbxproj):
        ids = re.findall(r"([0-9A-F]{24}) /\*", lst.group("ids"))
        if lst.group("kind") == "PBXProject":
            project = dict(layer(i) for i in ids)
        else:
            targets[lst.group("owner")] = ids
    resolved: dict[tuple[str, str], dict[str, str]] = {}
    for target, ids in targets.items():
        for config_id in ids:
            name, settings = layer(config_id)
            resolved[(target, name)] = {**project.get(name, {}), **settings}
    return resolved


def _single(resolved: Mapping[tuple[str, str], Mapping[str, str]], key: str) -> set[str]:
    return {s.get(key, "") for s in resolved.values()}


def check_versions(
    resolved: Mapping[tuple[str, str], Mapping[str, str]],
    pbxproj: str,
    other_xcconfigs: Mapping[str, str],
) -> list[str]:
    """One X.Y.Z version and one integer build, set in Shared.xcconfig only."""
    problems: list[str] = []
    versions = _single(resolved, "MARKETING_VERSION")
    if len(versions) != 1 or not re.fullmatch(r"\d+\.\d+\.\d+", next(iter(versions))):
        problems.append(f"MARKETING_VERSION must be one X.Y.Z across targets: {sorted(versions)}")
    builds = _single(resolved, "CURRENT_PROJECT_VERSION")
    if len(builds) != 1 or not re.fullmatch(r"[1-9]\d*", next(iter(builds))):
        problems.append(f"CURRENT_PROJECT_VERSION must be one positive integer: {sorted(builds)}")
    for key in ("MARKETING_VERSION", "CURRENT_PROJECT_VERSION"):
        if re.search(rf"^\s*{key}\b", pbxproj, re.MULTILINE):
            problems.append(f"project.pbxproj sets {key}; set it only in Config/Shared.xcconfig")
        for name, text in sorted(other_xcconfigs.items()):
            if re.search(rf"^\s*{key}\b", text, re.MULTILINE):
                problems.append(f"Config/{name} sets {key}; set it only in Config/Shared.xcconfig")
    return problems


def check_targets(resolved: Mapping[tuple[str, str], Mapping[str, str]]) -> list[str]:
    """Device family and signing team, for every target and configuration."""
    problems: list[str] = []
    if not resolved:
        return ["no target build configurations were read from project.pbxproj"]
    for (target, config), s in sorted(resolved.items()):
        if s.get("TARGETED_DEVICE_FAMILY") != "1":
            problems.append(f"{target}/{config}: TARGETED_DEVICE_FAMILY must be 1 (iPhone)")
        if s.get("DEVELOPMENT_TEAM") != TEAM_ID:
            problems.append(f"{target}/{config}: DEVELOPMENT_TEAM must be {TEAM_ID}")
        for key, value in s.items():
            device_override = key.startswith("DEVELOPMENT_TEAM[") and "iphonesimulator" not in key
            if device_override and value != TEAM_ID:
                problems.append(
                    f"{target}/{config}: {key} = {value!r} overrides the team for devices"
                )
            if key.startswith("INFOPLIST_KEY_UIBackgroundModes"):
                problems.append(f"{target}/{config}: declares background modes ({value})")
    return problems


def check_app_settings(app: Mapping[str, str], widget: Mapping[str, str], label: str) -> list[str]:
    """The app's generated Info.plist keys and the bundle identities."""
    problems: list[str] = []
    expected = {
        "GENERATE_INFOPLIST_FILE": "YES",
        "INFOPLIST_KEY_ITSAppUsesNonExemptEncryption": "NO",
        "INFOPLIST_KEY_UILaunchScreen_Generation": "YES",
        "INFOPLIST_KEY_CFBundleDisplayName": DISPLAY_NAME,
        "PRODUCT_BUNDLE_IDENTIFIER": BUNDLE_ID,
        "ASSETCATALOG_COMPILER_APPICON_NAME": "AppIcon",
    }
    for key, want in expected.items():
        if app.get(key) != want:
            problems.append(f"app {label}: {key} is {app.get(key)!r}, expected {want!r}")
    if app.get("INFOPLIST_KEY_LSRequiresIPhoneOS", "YES") != "YES":
        problems.append(f"app {label}: LSRequiresIPhoneOS must not be turned off")
    if widget.get("PRODUCT_BUNDLE_IDENTIFIER") != f"{BUNDLE_ID}.widgets":
        problems.append(f"widget {label}: bundle ID must be {BUNDLE_ID}.widgets")
    return problems


def check_widget_info(info: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    if info.get("CFBundleShortVersionString") != "$(MARKETING_VERSION)":
        problems.append(
            "widget Info.plist: CFBundleShortVersionString must be $(MARKETING_VERSION)"
        )
    if info.get("CFBundleVersion") != "$(CURRENT_PROJECT_VERSION)":
        problems.append("widget Info.plist: CFBundleVersion must be $(CURRENT_PROJECT_VERSION)")
    if "UIBackgroundModes" in info:
        problems.append("widget Info.plist declares background modes")
    return problems


def check_no_third_party(pbxproj: str, project_yml: str, package_swift: str) -> list[str]:
    problems: list[str] = []
    if "XCRemoteSwiftPackageReference" in pbxproj:
        problems.append("the project references a remote Swift package")
    if re.search(r"^\s*url:", project_yml, re.MULTILINE):
        problems.append("project.yml declares a remote package (url:)")
    if ".package(" in package_swift:
        problems.append("GuideCore/Package.swift depends on another package")
    for name, text in (("project.pbxproj", pbxproj), ("project.yml", project_yml)):
        if ENROLLMENT_ID in text:
            problems.append(f"{name}: {ENROLLMENT_ID} is the enrollment ID, not a team ID")
    return problems


# MARK: privacy, code and assets


def check_manifest(label: str, manifest: Mapping[str, Any], used: Iterable[str]) -> list[str]:
    """A privacy manifest against the posture and the APIs the code calls."""
    problems: list[str] = []
    if manifest.get("NSPrivacyTracking") is not False:
        problems.append(f"{label}: NSPrivacyTracking must be false")
    if manifest.get("NSPrivacyTrackingDomains"):
        problems.append(f"{label}: NSPrivacyTrackingDomains must be empty")
    if manifest.get("NSPrivacyCollectedDataTypes"):
        problems.append(f"{label}: NSPrivacyCollectedDataTypes must be empty (Data Not Collected)")
    declared = {
        entry.get("NSPrivacyAccessedAPIType")
        for entry in manifest.get("NSPrivacyAccessedAPITypes", [])
        if entry.get("NSPrivacyAccessedAPITypeReasons")
    }
    for category in sorted(set(used) - declared):
        problems.append(f"{label}: the code calls a {category} API the manifest does not declare")
    return problems


def required_reason_uses(sources: Mapping[str, str]) -> dict[str, list[str]]:
    """Category -> 'file:line' for each required-reason API call."""
    found: dict[str, list[str]] = {}
    for name, text in sources.items():
        for number, line in enumerate(text.splitlines(), 1):
            code = line.split("//", 1)[0]
            for category, pattern in REQUIRED_REASON.items():
                if pattern.search(code):
                    found.setdefault(category, []).append(f"{name}:{number}")
    return found


def foreign_imports(sources: Mapping[str, str]) -> list[str]:
    """'file: module' for every import outside the allowed set."""
    return [
        f"{name}: {m.group('module')}"
        for name, text in sources.items()
        for m in _IMPORT.finditer(text)
        if m.group("module") not in ALLOWED_IMPORTS
    ]


def check_entitlements(label: str, entitlements: Mapping[str, Any]) -> list[str]:
    problems = [
        f"{label}: {key} is not an entitlement this app uses (no push, no iCloud)"
        for key in sorted(set(entitlements) - ALLOWED_ENTITLEMENTS)
    ]
    groups = entitlements.get("com.apple.security.application-groups", [])
    if groups != [APP_GROUP]:
        problems.append(f"{label}: App Groups must be exactly [{APP_GROUP}], got {groups}")
    return problems


def png_header(data: bytes) -> tuple[int, int, bool]:
    """(width, height, has_alpha) from a PNG's IHDR chunk."""
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("not a PNG")
    width, height, _depth, color_type = struct.unpack(">IIBB", data[16:26])
    # Color types 4 and 6 carry an alpha channel. A tRNS chunk adds one too.
    return width, height, color_type in (4, 6) or b"tRNS" in data[:4096]


def check_iconset(contents: Mapping[str, Any], pngs: Mapping[str, bytes]) -> list[str]:
    """Every icon named exists, at its pixel size, opaque; 1024 is present."""
    problems: list[str] = []
    has_marketing = False
    for image in contents.get("images", []):
        filename = image.get("filename")
        if filename not in pngs:
            problems.append(
                f"icon slot {image.get('size')} @{image.get('scale')}: {filename!r} is missing"
            )
            continue
        points = float(str(image["size"]).split("x")[0])
        expected = round(points * int(str(image.get("scale", "1x")).rstrip("x")))
        width, height, alpha = png_header(pngs[filename])
        if (width, height) != (expected, expected):
            problems.append(f"icon {filename} is {width}x{height}, expected {expected}x{expected}")
        if alpha:
            problems.append(f"icon {filename} has an alpha channel")
        has_marketing |= image.get("idiom") == "ios-marketing" and expected == 1024
    if not has_marketing:
        problems.append("the icon set has no 1024x1024 ios-marketing image")
    return problems


# MARK: release preflight


def changelog_section(changelog: str, version: str) -> str:
    """The body of `## [version]`, or '' when there is none."""
    pattern = re.compile(
        r"^## \[" + re.escape(version) + r"\][^\n]*\n(?P<body>.*?)(?=^## \[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(changelog)
    return m.group("body").strip() if m else ""


def changelog_dated(changelog: str, version: str) -> bool:
    """True when `## [version]` carries a release date, `- YYYY-MM-DD`."""
    pattern = r"^## \[" + re.escape(version) + r"\] - \d{4}-\d{2}-\d{2}[ \t]*$"
    return re.search(pattern, changelog, re.MULTILINE) is not None


def check_release(
    tag: str, version: str, build: str, changelog: str, earlier_builds: Mapping[str, int]
) -> tuple[list[str], str]:
    """Preflight for one release tag. Returns (problems, release notes)."""
    if not _SEMVER_TAG.match(tag):
        return [f"release tag {tag!r} must be stable SemVer, vX.Y.Z"], ""
    problems: list[str] = []
    if tag[1:] != version:
        problems.append(f"tag {tag} does not match MARKETING_VERSION {version!r}")
    number = int(build) if build.isdigit() else 0
    for earlier_tag, earlier_build in sorted(earlier_builds.items()):
        if number <= earlier_build:
            problems.append(
                f"build {number} is not higher than build {earlier_build} at {earlier_tag}; "
                "raise CURRENT_PROJECT_VERSION in ios/Config/Shared.xcconfig"
            )
    notes = changelog_section(changelog, tag[1:])
    if not notes:
        problems.append(f"CHANGELOG.md has no non-empty '## [{tag[1:]}]' section")
    elif not changelog_dated(changelog, tag[1:]):
        problems.append(
            f"CHANGELOG.md '## [{tag[1:]}]' has no release date (does it still say TBD?); "
            "date it (docs/app-store/OWNER-STEPS.md, step 8)"
        )
    return problems, notes


def _earlier_builds(pairs: Iterable[str], tag: str) -> dict[str, int]:
    """CURRENT_PROJECT_VERSION per earlier tag, from TAG=PATH arguments.

    The release workflow writes each earlier tag's ios/Config/Shared.xcconfig
    to a file (`git show <tag>:ios/Config/Shared.xcconfig`) and passes it
    here, so this script stays file reads only. The readiness audit holds the
    build number to that one file, so it is the whole story at every tag.
    """
    builds: dict[str, int] = {}
    for pair in pairs:
        other, _, path = pair.partition("=")
        if other == tag or not _SEMVER_TAG.match(other) or not path:
            continue
        value = parse_xcconfig(Path(path).read_text(encoding="utf-8")).get(
            "CURRENT_PROJECT_VERSION", ""
        )
        if value.isdigit():
            builds[other] = int(value)
    return builds


# MARK: running it


def _swift_sources(roots: Iterable[Path]) -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
        for root in roots
        for path in sorted(root.rglob("*.swift"))
    }


def _plist(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        data: dict[str, Any] = plistlib.load(handle)
    return data


def readiness() -> list[str]:
    pbxproj = PBXPROJ.read_text(encoding="utf-8")
    resolved = target_settings(pbxproj)
    others = {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted(CONFIG.glob("*.xcconfig"))
        if p != VERSION_XCCONFIG
    }
    problems = check_versions(resolved, pbxproj, others)
    problems += check_targets(resolved)
    for config in ("Debug", "Release"):
        problems += check_app_settings(
            resolved.get((APP_TARGET, config), {}),
            resolved.get((WIDGET_TARGET, config), {}),
            config,
        )
    problems += check_widget_info(_plist(WIDGET_INFO))
    problems += check_no_third_party(
        pbxproj,
        PROJECT_YML.read_text(encoding="utf-8"),
        PACKAGE_SWIFT.read_text(encoding="utf-8"),
    )
    problems += [
        f"a StoreKit configuration file ships: {p.relative_to(ROOT)}"
        for p in sorted(IOS.rglob("*.storekit"))
    ]
    for label, (manifest, roots) in BUNDLES.items():
        sources = _swift_sources(roots)
        if not sources:
            problems.append(f"{label}: no Swift sources were read")
        problems += [f"non-Apple import: {item}" for item in foreign_imports(sources)]
        problems += check_manifest(
            manifest.relative_to(ROOT).as_posix(), _plist(manifest), required_reason_uses(sources)
        )
    entitlements = sorted(IOS.rglob("*.entitlements"))
    if len(entitlements) != 2:
        problems.append(
            f"expected the app's and the widget's .entitlements, found {len(entitlements)}"
        )
    for path in entitlements:
        problems += check_entitlements(path.relative_to(ROOT).as_posix(), _plist(path))
    contents = json.loads((ICONSET / "Contents.json").read_text(encoding="utf-8"))
    problems += check_iconset(contents, {p.name: p.read_bytes() for p in ICONSET.glob("*.png")})
    return problems


def _png(width: int, height: int, color_type: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR"
        + struct.pack(">IIBB", width, height, 8, color_type)
    )


_SELF_TEST_PBXPROJ = """\
\t\tAAAAAAAAAAAAAAAAAAAAAAAA /* Release */ = {
\t\t\tisa = XCBuildConfiguration;
\t\t\tbaseConfigurationReference = 111111111111111111111111 /* App-Release.xcconfig */;
\t\t\tbuildSettings = {
\t\t\t\tASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
\t\t\t};
\t\t\tname = Release;
\t\t};
\t\tBBBBBBBBBBBBBBBBBBBBBBBB /* Release */ = {
\t\t\tisa = XCBuildConfiguration;
\t\t\tbuildSettings = {
\t\t\t\tSDKROOT = iphoneos;
\t\t\t};
\t\t\tname = Release;
\t\t};
/* Build configuration list for PBXNativeTarget "QueerTVGuide" */ = {
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\tAAAAAAAAAAAAAAAAAAAAAAAA /* Release */,
\t\t\t);
/* Build configuration list for PBXProject "QueerTVGuide" */ = {
\t\t\tisa = XCConfigurationList;
\t\t\tbuildConfigurations = (
\t\t\t\tBBBBBBBBBBBBBBBBBBBBBBBB /* Release */,
\t\t\t);
"""


def _self_test_resolve(shared: str) -> dict[tuple[str, str], dict[str, str]]:
    files = {
        "App-Release.xcconfig": '#include "Shared.xcconfig"\nINFOPLIST_KEY_CFBundleDisplayName = Queer Frame // name\n',
        "Shared.xcconfig": shared,
    }

    def load(name: str) -> dict[str, str]:
        return parse_xcconfig(files[name], lambda inc: files[inc])

    return target_settings(_SELF_TEST_PBXPROJ, load)


def self_test() -> list[str]:
    """Each check must reject its bad input and accept its good one."""
    shared = f"DEVELOPMENT_TEAM = {TEAM_ID}\nMARKETING_VERSION = 1.0.0\nCURRENT_PROJECT_VERSION = 3\nTARGETED_DEVICE_FAMILY = 1\n"
    good = _self_test_resolve(shared)
    app = {
        "GENERATE_INFOPLIST_FILE": "YES",
        "INFOPLIST_KEY_ITSAppUsesNonExemptEncryption": "NO",
        "INFOPLIST_KEY_UILaunchScreen_Generation": "YES",
        "INFOPLIST_KEY_CFBundleDisplayName": DISPLAY_NAME,
        "PRODUCT_BUNDLE_IDENTIFIER": BUNDLE_ID,
        "ASSETCATALOG_COMPILER_APPICON_NAME": "AppIcon",
    }
    widget = {"PRODUCT_BUNDLE_IDENTIFIER": f"{BUNDLE_ID}.widgets"}
    widget_info = {
        "CFBundleShortVersionString": "$(MARKETING_VERSION)",
        "CFBundleVersion": "$(CURRENT_PROJECT_VERSION)",
    }
    manifest: dict[str, Any] = {
        "NSPrivacyTracking": False,
        "NSPrivacyTrackingDomains": [],
        "NSPrivacyCollectedDataTypes": [],
        "NSPrivacyAccessedAPITypes": [],
    }
    declared = {
        **manifest,
        "NSPrivacyAccessedAPITypes": [
            {
                "NSPrivacyAccessedAPIType": "NSPrivacyAccessedAPICategoryUserDefaults",
                "NSPrivacyAccessedAPITypeReasons": ["CA92.1"],
            }
        ],
    }
    defaults = ["NSPrivacyAccessedAPICategoryUserDefaults"]
    icons = {
        "images": [
            {"filename": "a.png", "idiom": "ios-marketing", "size": "1024x1024", "scale": "1x"}
        ]
    }
    groups = {"com.apple.security.application-groups": [APP_GROUP]}
    changelog = "## [Unreleased]\n\n## [1.0.0] - 2026-10-01\n\n### Added\n\n- The app.\n"
    cases: list[tuple[str, bool]] = [
        (
            "resolves through includes",
            good.get((APP_TARGET, "Release"), {}).get("MARKETING_VERSION") == "1.0.0",
        ),
        (
            "project layer is lowest",
            good.get((APP_TARGET, "Release"), {}).get("SDKROOT") == "iphoneos",
        ),
        (
            "comment stripped",
            good.get((APP_TARGET, "Release"), {}).get("INFOPLIST_KEY_CFBundleDisplayName")
            == DISPLAY_NAME,
        ),
        ("versions ok", not check_versions(good, "", {})),
        (
            "version not semver",
            bool(check_versions(_self_test_resolve(shared.replace("1.0.0", "1.0")), "", {})),
        ),
        (
            "build not int",
            bool(check_versions(_self_test_resolve(shared.replace("= 3", "= 3.1")), "", {})),
        ),
        (
            "version set twice",
            bool(check_versions(good, "", {"Widgets.xcconfig": "MARKETING_VERSION = 1.0.1\n"})),
        ),
        (
            "version in pbxproj",
            bool(check_versions(good, "\t\t\t\tCURRENT_PROJECT_VERSION = 4;\n", {})),
        ),
        ("targets ok", not check_targets(good)),
        ("nothing read", bool(check_targets({}))),
        (
            "ipad",
            bool(check_targets(_self_test_resolve(shared.replace("FAMILY = 1", 'FAMILY = "1,2"')))),
        ),
        (
            "enrollment id as team",
            bool(check_targets(_self_test_resolve(shared.replace(TEAM_ID, ENROLLMENT_ID)))),
        ),
        (
            "simulator team blank ok",
            not check_targets(
                _self_test_resolve(shared + "DEVELOPMENT_TEAM[sdk=iphonesimulator*] =\n")
            ),
        ),
        (
            "device team override",
            bool(
                check_targets(_self_test_resolve(shared + "DEVELOPMENT_TEAM[sdk=iphoneos*] = X\n"))
            ),
        ),
        (
            "background mode",
            bool(
                check_targets(
                    _self_test_resolve(shared + "INFOPLIST_KEY_UIBackgroundModes = fetch\n")
                )
            ),
        ),
        ("app settings ok", not check_app_settings(app, widget, "t")),
        (
            "no export flag",
            bool(
                check_app_settings(
                    {**app, "INFOPLIST_KEY_ITSAppUsesNonExemptEncryption": "YES"}, widget, "t"
                )
            ),
        ),
        (
            "wrong name",
            bool(
                check_app_settings(
                    {**app, "INFOPLIST_KEY_CFBundleDisplayName": "QueerTVGuide"}, widget, "t"
                )
            ),
        ),
        (
            "widget id",
            bool(check_app_settings(app, {"PRODUCT_BUNDLE_IDENTIFIER": "x.widgets"}, "t")),
        ),
        ("widget info ok", not check_widget_info(widget_info)),
        (
            "widget hardcoded build",
            bool(check_widget_info({**widget_info, "CFBundleVersion": "1"})),
        ),
        (
            "first party ok",
            not check_no_third_party("", "packages:\n  GuideCore:\n    path: GuideCore\n", ""),
        ),
        (
            "remote package",
            bool(check_no_third_party("/* XCRemoteSwiftPackageReference */", "", "")),
        ),
        (
            "yml url",
            bool(
                check_no_third_party(
                    "", "packages:\n  X:\n    url: https://example.invalid/x\n", ""
                )
            ),
        ),
        ("package dep", bool(check_no_third_party("", "", '.package(url: "x", from: "1.0.0")'))),
        ("enrollment id anywhere", bool(check_no_third_party(ENROLLMENT_ID, "", ""))),
        ("manifest ok", not check_manifest("m", manifest, [])),
        ("tracking", bool(check_manifest("m", {**manifest, "NSPrivacyTracking": True}, []))),
        (
            "collected",
            bool(check_manifest("m", {**manifest, "NSPrivacyCollectedDataTypes": [{"x": 1}]}, [])),
        ),
        ("undeclared api", bool(check_manifest("m", manifest, defaults))),
        ("declared api", not check_manifest("m", declared, defaults)),
        ("finds defaults", bool(required_reason_uses({"a": "let d = UserDefaults.standard"}))),
        ("finds app storage", bool(required_reason_uses({"a": "@AppStorage(key) var on = false"}))),
        ("finds timestamp", bool(required_reason_uses({"a": "attrs[.modificationDate]"}))),
        ("ignores comment", not required_reason_uses({"a": "// no UserDefaults here"})),
        ("foreign import", bool(foreign_imports({"a": "import FirebaseAnalytics\n"}))),
        ("storekit import", bool(foreign_imports({"a": "import StoreKit\n"}))),
        (
            "apple import",
            not foreign_imports(
                {
                    "a": "import SwiftUI\n@preconcurrency import WidgetKit\nimport struct Foundation.URL\n"
                }
            ),
        ),
        ("entitlements ok", not check_entitlements("e", groups)),
        (
            "push entitlement",
            bool(check_entitlements("e", {**groups, "aps-environment": "production"})),
        ),
        (
            "icloud entitlement",
            bool(check_entitlements("e", {**groups, "com.apple.developer.icloud-services": []})),
        ),
        (
            "wrong group",
            bool(check_entitlements("e", {"com.apple.security.application-groups": ["group.x"]})),
        ),
        ("icon ok", not check_iconset(icons, {"a.png": _png(1024, 1024, 2)})),
        ("icon alpha", bool(check_iconset(icons, {"a.png": _png(1024, 1024, 6)}))),
        ("icon size", bool(check_iconset(icons, {"a.png": _png(512, 512, 2)}))),
        ("icon missing", bool(check_iconset(icons, {}))),
        ("release ok", not check_release("v1.0.0", "1.0.0", "3", changelog, {"v0.9.0": 2})[0]),
        (
            "release notes",
            check_release("v1.0.0", "1.0.0", "3", changelog, {})[1] == "### Added\n\n- The app.",
        ),
        ("tag mismatch", bool(check_release("v1.0.1", "1.0.0", "3", changelog, {})[0])),
        ("not semver", bool(check_release("v1.0", "1.0.0", "3", changelog, {})[0])),
        ("build reused", bool(check_release("v1.0.0", "1.0.0", "3", changelog, {"v0.9.0": 3})[0])),
        (
            "undated notes",
            bool(
                check_release("v1.0.0", "1.0.0", "3", changelog.replace("2026-10-01", "TBD"), {})[0]
            ),
        ),
        ("no notes", bool(check_release("v1.0.0", "1.0.0", "3", "## [Unreleased]\n", {})[0])),
    ]
    return [name for name, ok in cases if not ok]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--self-test", action="store_true", help="check the checks, then exit")
    parser.add_argument("--release-tag", help="run the release preflight for this vX.Y.Z tag")
    parser.add_argument("--notes-out", type=Path, help="write the tag's CHANGELOG section here")
    parser.add_argument(
        "--earlier-xcconfig",
        action="append",
        default=[],
        metavar="TAG=PATH",
        help="an earlier release tag and a copy of its ios/Config/Shared.xcconfig (repeatable)",
    )
    args = parser.parse_args(argv)
    if args.self_test:
        failures = self_test()
        for name in failures:
            print(f"self-test failed: {name}", file=sys.stderr)
        print(f"check_app_store self-test: {'FAILED' if failures else 'ok'}")
        return 1 if failures else 0
    problems = readiness()
    notes = ""
    if args.release_tag:
        shared = parse_xcconfig(VERSION_XCCONFIG.read_text(encoding="utf-8"))
        release_problems, notes = check_release(
            args.release_tag,
            shared.get("MARKETING_VERSION", ""),
            shared.get("CURRENT_PROJECT_VERSION", ""),
            CHANGELOG.read_text(encoding="utf-8"),
            _earlier_builds(args.earlier_xcconfig, args.release_tag),
        )
        problems += release_problems
    for problem in problems:
        print(f"app store: {problem}", file=sys.stderr)
    if problems:
        print(f"app store check: FAILED ({len(problems)} problems)", file=sys.stderr)
        return 1
    if args.notes_out:
        args.notes_out.write_text(notes + "\n", encoding="utf-8")
    print("app store check: ok" + (f" for {args.release_tag}" if args.release_tag else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
