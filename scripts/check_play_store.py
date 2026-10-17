#!/usr/bin/env python3
"""Google Play readiness for Queer Frame for Android (DECISIONS 0018).

The Play twin of scripts/check_app_store.py, with the same shape: plain file
reads, so it runs on Linux CI with no JDK or Android SDK, and a `--self-test`
that feeds each check an input it must reject and one it must accept.

`make playstore` (so `make verify`, and CI's pipeline job) fails when the
Play listing or the App content answers in docs/play-store/play-listing.json
would bounce in Play Console or contradict the build:

- the listing strings fit Play's limits (title 30, short description 80,
  full description 4,000), the title is the app's name (DECISIONS 0006),
  and the copy keeps the repository's rules: no "only", "first", "best" or
  ranking words, no emoji, nothing about the iPhone or the App Store, and no
  promotional words in the title;
- the package name, version name and version code are the build's, and
  the version name is the iOS app's MARKETING_VERSION (0018: as iOS);
- the price is the App Store's USD price, the one storefront is the United
  States, and there are no ads and no in-app purchase (0011, 0015, 0018);
- the privacy and support URLs are pages the Pages site publishes, the
  privacy page has its Android section, and the contact email is the one
  the support page lists (0015);
- the Data safety answer is "no data collected or shared" (0002, 0018),
  and the build still makes that true: exactly the three permissions the
  manifest documents, no Play services, Firebase, analytics, ads or billing
  library, no web view, location, advertising-ID or Android-ID read, and
  nothing in cloud backup;
- every content-rating answer has a reason, and the answers the build
  fixes (no user interaction, no location sharing, no digital purchases,
  no unrestricted internet, no gambling) say "No";
- the target SDK meets Play's floor for new apps, and upload-key files
  stay out of git (.gitignore).

What it cannot check is listed in docs/play-store/OWNER-STEPS.md: the Play
Console account, payments profile, closed test, graphics, and the answers
as actually submitted.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "android"
LISTING = ROOT / "docs" / "play-store" / "play-listing.json"
APP_STORE_LISTING = ROOT / "docs" / "app-store-listing.json"
SITE = ROOT / "docs" / "site"
IOS_VERSION_XCCONFIG = ROOT / "ios" / "Config" / "Shared.xcconfig"
APP_GRADLE = ANDROID / "app" / "build.gradle.kts"
GRADLE_FILES = (
    APP_GRADLE,
    ANDROID / "core" / "build.gradle.kts",
    ANDROID / "build.gradle.kts",
    ANDROID / "settings.gradle.kts",
    ANDROID / "gradle" / "libs.versions.toml",
)
MANIFEST = ANDROID / "app" / "src" / "main" / "AndroidManifest.xml"
STRINGS = ANDROID / "app" / "src" / "main" / "res" / "values" / "strings.xml"
DATA_EXTRACTION = ANDROID / "app" / "src" / "main" / "res" / "xml" / "data_extraction_rules.xml"
SOURCE_ROOTS = (ANDROID / "app" / "src" / "main", ANDROID / "core" / "src" / "main")
GITIGNORE = ROOT / ".gitignore"

PACKAGE = "com.chelseakr.queertvguide"
SITE_BASE = "https://chelseakr.github.io/queer-tv-guide/"
ANDROID_REGION = "<!-- android-app:begin -->"

# Play Console's field limits (characters).
LIMITS = {"title": 30, "short_description": 80, "full_description": 4000}

# The permissions the manifest's own comment documents (DECISIONS 0018).
# WorkManager's library manifest adds its own at merge time; those are the
# library's, read by Play from the bundle, not declared by this app.
PERMISSIONS = frozenset(
    {
        "android.permission.INTERNET",
        "android.permission.ACCESS_NETWORK_STATE",
        "android.permission.POST_NOTIFICATIONS",
    }
)

# Google's floor for new apps from 2025-08-31 (Android 15). Raise it when
# Google announces the next one; the app already targets above it.
MIN_TARGET_SDK = 35

# Libraries whose presence would make "No data collected" untrue or put
# Google Play code in the app (DECISIONS 0018), and the billing library a
# paid-up-front app has no use for.
BANNED_LIBRARIES = re.compile(
    r"com\.google\.android\.(?:gms|play)|com\.google\.firebase|com\.android\.billingclient"
    r"|crashlytics|play-services|admob|sentry|bugsnag|appsflyer|amplitude|mixpanel"
    r"|segment\.analytics|facebook",
    re.IGNORECASE,
)

# APIs whose use would need a Data safety or content-rating answer other
# than the one drafted.
BANNED_CODE = re.compile(
    r"\bWebView\b|\bLocationManager\b|\bFusedLocation\w*|\bAdvertisingIdClient\b"
    r"|\bANDROID_ID\b|\bBillingClient\b|\bAccountManager\b"
)

# Repository copy rule (docs/APP-STORE.md, "Description"), plus Play's
# ranking words. Matched as whole words, case-insensitively.
UNIQUENESS = re.compile(r"\b(?:only|first|best|top|number one)\b|#1\b", re.IGNORECASE)
# The Play copy is for Android; another platform's words do not belong.
OTHER_PLATFORM = re.compile(r"\b(?:iPhone|iPad|iOS|App Store|Apple|TestFlight)\b")
# Promotional words Play's store listing policy keeps out of a title.
TITLE_PROMO = re.compile(r"\b(?:free|sale|discount|new|install now|download now)\b", re.I)
EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿️]")

DATA_SAFETY_KEYS = ("collects_or_shares_required_user_data", "data_collected", "data_shared")
# Content-rating answers the build itself fixes at "No".
FIXED_NO = (
    "gambling",
    "user_interaction",
    "shares_location",
    "digital_purchases",
    "unrestricted_internet",
)
RATING_TOPICS = frozenset(
    {"violence", "sexuality", "language", "controlled_substances", "horror_or_fear", *FIXED_NO}
)


# MARK: the listing


def check_copy(listing: Mapping[str, Any]) -> list[str]:
    """Play's limits and the repository's copy rules on the three strings."""
    problems: list[str] = []
    for key, limit in LIMITS.items():
        value = listing.get(key)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{key} is missing or empty")
            continue
        if len(value) > limit:
            problems.append(f"{key} is {len(value)} characters; Play allows {limit}")
        for pattern, why in (
            (UNIQUENESS, "a uniqueness or ranking claim"),
            (OTHER_PLATFORM, "another platform's name"),
            (EMOJI, "an emoji"),
        ):
            m = pattern.search(value)
            if m:
                problems.append(f"{key} has {why}: {m.group(0)!r}")
    title = listing.get("title")
    if isinstance(title, str):
        m = TITLE_PROMO.search(title)
        if m:
            problems.append(f"title has a promotional word: {m.group(0)!r}")
        if title.isupper():
            problems.append("title is in capitals")
    return problems


def check_identity(
    listing: Mapping[str, Any], app_name: str, build: Mapping[str, str], ios_version: str
) -> list[str]:
    """The listing's names and the build's versions agree."""
    problems: list[str] = []
    if listing.get("title") != app_name:
        problems.append(f"title {listing.get('title')!r} is not the app's name {app_name!r}")
    if listing.get("package_name") != PACKAGE or build.get("applicationId") != PACKAGE:
        problems.append(
            f"package name must be {PACKAGE} in the listing and the build "
            f"({listing.get('package_name')!r}, {build.get('applicationId')!r})"
        )
    version = build.get("versionName", "")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        problems.append(f"versionName {version!r} is not X.Y.Z")
    elif version != ios_version:
        problems.append(f"versionName {version} is not the iOS MARKETING_VERSION {ios_version!r}")
    if not re.fullmatch(r"[1-9]\d*", build.get("versionCode", "")):
        problems.append(f"versionCode {build.get('versionCode')!r} is not a positive integer")
    target = build.get("targetSdk", "")
    if not target.isdigit() or int(target) < MIN_TARGET_SDK:
        problems.append(
            f"targetSdk {target!r} is below Play's floor for new apps, {MIN_TARGET_SDK}"
        )
    return problems


def check_commerce(listing: Mapping[str, Any], app_store_price: str) -> list[str]:
    """Paid up front, the App Store's price, the US only, no ads (0011, 0015, 0018)."""
    problems: list[str] = []
    if listing.get("price_usd") != app_store_price:
        problems.append(
            f"price_usd {listing.get('price_usd')!r} is not the App Store's {app_store_price!r}"
        )
    if listing.get("countries") != ["US"]:
        problems.append(
            f"countries must be ['US'] (DECISIONS 0015), got {listing.get('countries')}"
        )
    for key in ("contains_ads", "in_app_purchases", "appeals_to_children", "news_app"):
        if listing.get(key) is not False:
            problems.append(f"{key} must be false")
    if listing.get("category") != "Entertainment":
        problems.append("category must be Entertainment, as on the App Store")
    return problems


def check_urls(listing: Mapping[str, Any], site_pages: Mapping[str, str]) -> list[str]:
    """URLs are pages the site publishes; the privacy page covers Android."""
    problems: list[str] = []
    for key in ("privacy_policy_url", "website"):
        url = str(listing.get(key, ""))
        page = url.removeprefix(SITE_BASE)
        if not url.startswith(SITE_BASE) or page not in site_pages:
            problems.append(f"{key} {url!r} is not a page in docs/site/")
    if listing.get("privacy_policy_url") != f"{SITE_BASE}privacy.html":
        problems.append("privacy_policy_url must be the privacy page")
    if ANDROID_REGION not in site_pages.get("privacy.html", ""):
        problems.append("privacy.html has no Android section (DECISIONS 0018)")
    support = site_pages.get("support.html", "")
    email = str(listing.get("contact_email", ""))
    if not email or f'href="mailto:{email}"' not in support:
        problems.append(f"contact_email {email!r} is not the address support.html lists")
    return problems


# MARK: the App content answers against the build


def check_data_safety(answers: Mapping[str, Any]) -> list[str]:
    """No data collected, none shared (DECISIONS 0002, 0018)."""
    problems: list[str] = []
    if any(key not in answers for key in DATA_SAFETY_KEYS):
        return [f"data_safety must answer {', '.join(DATA_SAFETY_KEYS)}"]
    if answers["collects_or_shares_required_user_data"] is not False:
        problems.append("data_safety: the answer to 'collects or shares user data' must be false")
    for key in ("data_collected", "data_shared"):
        if answers[key] != []:
            problems.append(f"data_safety: {key} must be empty, got {answers[key]}")
    if not answers.get("why"):
        problems.append("data_safety: no reasons given")
    return problems


def check_content_rating(rating: Mapping[str, Any]) -> list[str]:
    """Every topic answered with a reason; the build's facts say No."""
    answers = rating.get("answers", {})
    problems = [f"content_rating: no answer for {t}" for t in sorted(RATING_TOPICS - set(answers))]
    for topic, entry in sorted(answers.items()):
        if not str(entry.get("answer", "")).strip() or not str(entry.get("why", "")).strip():
            problems.append(f"content_rating: {topic} needs an answer and a reason")
    for topic in FIXED_NO:
        if topic in answers and answers[topic].get("answer") != "No":
            problems.append(f"content_rating: {topic} must be 'No'; the build has none")
    return problems


def manifest_permissions(manifest: str) -> set[str]:
    return set(re.findall(r'<uses-permission[^>]*android:name="([^"]+)"', strip_comments(manifest)))


def strip_comments(text: str) -> str:
    """Kotlin/XML/Gradle text without comments, so a comment naming a banned
    thing (as the manifest's does) is not mistaken for using it."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)(?<!:)//.*$|^\s*#.*$", "", text)


def check_build_posture(
    manifest: str, gradle: Mapping[str, str], sources: Mapping[str, str], extraction: str
) -> list[str]:
    """What makes the Data safety answer true, read from the build."""
    problems: list[str] = []
    perms = manifest_permissions(manifest)
    if perms != PERMISSIONS:
        problems.append(
            f"manifest permissions {sorted(perms)} are not exactly {sorted(PERMISSIONS)}; "
            "a new one needs its Data safety answer reviewed"
        )
    for name, text in sorted(gradle.items()):
        m = BANNED_LIBRARIES.search(strip_comments(text))
        if m:
            problems.append(f"{name}: links {m.group(0)!r}, which the Data safety answer rules out")
    for name, text in sorted(sources.items()):
        m = BANNED_CODE.search(strip_comments(text))
        if m:
            problems.append(f"{name}: uses {m.group(0)}, which the drafted answers rule out")
    cloud = extraction.partition("<cloud-backup>")[2].partition("</cloud-backup>")[0]
    if "<cloud-backup>" not in extraction or "<include" in cloud:
        problems.append("data_extraction_rules.xml: cloud backup must include nothing")
    return problems


def check_gitignore(gitignore: str) -> list[str]:
    """The upload key and its passwords never reach git."""
    lines = {line.strip() for line in gitignore.splitlines()}
    return [
        f".gitignore does not ignore {pattern} (the Play upload key)"
        for pattern in ("*.jks", "*.keystore", "android/signing.properties")
        if pattern not in lines
    ]


# MARK: reading the build


def gradle_settings(text: str) -> dict[str, str]:
    """applicationId, versionCode, versionName, minSdk, targetSdk from build.gradle.kts."""
    found: dict[str, str] = {}
    for key in ("applicationId", "versionCode", "versionName", "minSdk", "targetSdk"):
        m = re.search(rf'^\s*{key}\s*=\s*"?([^"\s]+)"?\s*$', strip_comments(text), re.M)
        if m:
            found[key] = m.group(1)
    return found


def app_name(strings: str) -> str:
    m = re.search(r'<string name="app_name">([^<]*)</string>', strings)
    return m.group(1) if m else ""


def ios_marketing_version(xcconfig: str) -> str:
    m = re.search(r"^\s*MARKETING_VERSION\s*=\s*(\S+)", xcconfig, re.M)
    return m.group(1) if m else ""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def readiness() -> list[str]:
    listing: dict[str, Any] = json.loads(_read(LISTING))
    app_store: dict[str, Any] = json.loads(_read(APP_STORE_LISTING))
    site_pages = {p.name: _read(p) for p in sorted(SITE.glob("*.html"))}
    sources = {
        p.relative_to(ROOT).as_posix(): _read(p)
        for root in SOURCE_ROOTS
        for p in sorted(root.rglob("*"))
        if p.suffix in (".kt", ".xml") and "assets" not in p.parts
    }
    problems = [] if len(sources) >= 20 else [f"only {len(sources)} Android sources were read"]
    problems += check_copy(listing)
    problems += check_identity(
        listing,
        app_name(_read(STRINGS)),
        gradle_settings(_read(APP_GRADLE)),
        ios_marketing_version(_read(IOS_VERSION_XCCONFIG)),
    )
    problems += check_commerce(listing, str(app_store.get("price_usd", "")))
    problems += check_urls(listing, site_pages)
    problems += check_data_safety(listing.get("data_safety", {}))
    problems += check_content_rating(listing.get("content_rating", {}))
    problems += check_build_posture(
        _read(MANIFEST),
        {p.relative_to(ROOT).as_posix(): _read(p) for p in GRADLE_FILES},
        sources,
        _read(DATA_EXTRACTION),
    )
    problems += check_gitignore(_read(GITIGNORE))
    return problems


# MARK: self-test


def self_test() -> list[str]:
    """Each check must reject its bad input and accept its good one."""
    good: dict[str, Any] = {
        "package_name": PACKAGE,
        "title": "Queer Frame",
        "short_description": "Does she die? Lesbian TV guide.",
        "full_description": "Favorites stay on your phone.\n\n• Where to stream it.",
        "category": "Entertainment",
        "contact_email": "a@example.org",
        "website": f"{SITE_BASE}support.html",
        "privacy_policy_url": f"{SITE_BASE}privacy.html",
        "price_usd": "4.99",
        "countries": ["US"],
        "contains_ads": False,
        "in_app_purchases": False,
        "appeals_to_children": False,
        "news_app": False,
    }
    build = {
        "applicationId": PACKAGE,
        "versionName": "1.0.0",
        "versionCode": "1",
        "targetSdk": "36",
    }
    pages = {
        "privacy.html": f"<p>iPhone{ANDROID_REGION} and Android<!-- android-app:end --></p>",
        "support.html": '<a href="mailto:a@example.org">a@example.org</a>',
    }
    safety = {
        "collects_or_shares_required_user_data": False,
        "data_collected": [],
        "data_shared": [],
        "why": ["one GET"],
    }
    rating = {"answers": {t: {"answer": "No", "why": "none"} for t in RATING_TOPICS}}
    manifest = "".join(f'<uses-permission android:name="{p}" />' for p in sorted(PERMISSIONS))
    extraction = '<cloud-backup><exclude domain="root" path="." /></cloud-backup>'
    gitignore = "*.keystore\n*.jks\nandroid/signing.properties\n"

    def copy(**change: Any) -> list[str]:
        return check_copy({**good, **change})

    cases: list[tuple[str, bool]] = [
        ("copy ok", not check_copy(good)),
        ("title too long", bool(copy(title="Q" * 31))),
        ("short too long", bool(copy(short_description="x" * 81))),
        ("full too long", bool(copy(full_description="x" * 4001))),
        ("empty field", bool(copy(short_description=" "))),
        ("uniqueness", bool(copy(full_description="The only guide."))),
        ("ranking", bool(copy(short_description="The #1 TV guide"))),
        ("other platform", bool(copy(full_description="Favorites stay on your iPhone."))),
        ("app store", bool(copy(full_description="Also on the App Store."))),
        ("emoji", bool(copy(short_description="Does she die? \U0001f3f3"))),
        ("title promo", bool(copy(title="Queer Frame Free"))),
        ("title capitals", bool(copy(title="QUEER FRAME"))),
        ("identity ok", not check_identity(good, "Queer Frame", build, "1.0.0")),
        ("title not app name", bool(check_identity(good, "Queer Frame TV", build, "1.0.0"))),
        (
            "package",
            bool(check_identity(good, "Queer Frame", {**build, "applicationId": "x.y"}, "1.0.0")),
        ),
        ("version drift", bool(check_identity(good, "Queer Frame", build, "1.0.1"))),
        (
            "version not semver",
            bool(check_identity(good, "Queer Frame", {**build, "versionName": "1.0"}, "1.0")),
        ),
        (
            "version code",
            bool(check_identity(good, "Queer Frame", {**build, "versionCode": "0"}, "1.0.0")),
        ),
        (
            "old target sdk",
            bool(check_identity(good, "Queer Frame", {**build, "targetSdk": "34"}, "1.0.0")),
        ),
        ("commerce ok", not check_commerce(good, "4.99")),
        ("price drift", bool(check_commerce(good, "5.99"))),
        ("more countries", bool(check_commerce({**good, "countries": ["US", "CA"]}, "4.99"))),
        ("ads", bool(check_commerce({**good, "contains_ads": True}, "4.99"))),
        ("iap", bool(check_commerce({**good, "in_app_purchases": True}, "4.99"))),
        ("iap missing", bool(check_commerce({**good, "in_app_purchases": None}, "4.99"))),
        ("category", bool(check_commerce({**good, "category": "Lifestyle"}, "4.99"))),
        ("urls ok", not check_urls(good, pages)),
        ("url off site", bool(check_urls({**good, "website": "https://example.org/"}, pages))),
        ("page missing", bool(check_urls({**good, "website": f"{SITE_BASE}x.html"}, pages))),
        (
            "no android section",
            bool(check_urls(good, {**pages, "privacy.html": "<p>iPhone</p>"})),
        ),
        ("wrong email", bool(check_urls({**good, "contact_email": "b@example.org"}, pages))),
        ("safety ok", not check_data_safety(safety)),
        (
            "collects",
            bool(check_data_safety({**safety, "collects_or_shares_required_user_data": True})),
        ),
        ("shared type", bool(check_data_safety({**safety, "data_shared": ["App activity"]}))),
        ("safety unanswered", bool(check_data_safety({}))),
        ("safety no reason", bool(check_data_safety({**safety, "why": []}))),
        ("rating ok", not check_content_rating(rating)),
        ("rating missing topic", bool(check_content_rating({"answers": {}}))),
        (
            "rating no reason",
            bool(
                check_content_rating(
                    {"answers": {**rating["answers"], "violence": {"answer": "Some", "why": ""}}}
                )
            ),
        ),
        (
            "rating purchases yes",
            bool(
                check_content_rating(
                    {
                        "answers": {
                            **rating["answers"],
                            "digital_purchases": {"answer": "Yes", "why": "x"},
                        }
                    }
                )
            ),
        ),
        ("posture ok", not check_build_posture(manifest, {}, {}, extraction)),
        (
            "posture ignores comments",
            not check_build_posture(
                "<!-- no WebView, no firebase -->" + manifest,
                {"g": "// no com.google.firebase here\n"},
                {"a.kt": "/** never a WebView */\nval x = 1\n"},
                extraction,
            ),
        ),
        (
            "location permission",
            bool(
                check_build_posture(
                    manifest
                    + '<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />',
                    {},
                    {},
                    extraction,
                )
            ),
        ),
        ("permission removed", bool(check_build_posture("", {}, {}, extraction))),
        (
            "firebase",
            bool(
                check_build_posture(
                    manifest,
                    {"g": 'implementation("com.google.firebase:analytics")'},
                    {},
                    extraction,
                )
            ),
        ),
        (
            "play review",
            bool(
                check_build_posture(
                    manifest, {"g": 'review = "com.google.android.play:review:2.0"'}, {}, extraction
                )
            ),
        ),
        (
            "billing",
            bool(
                check_build_posture(
                    manifest,
                    {"g": 'billing = "com.android.billingclient:billing:7.0"'},
                    {},
                    extraction,
                )
            ),
        ),
        (
            "web view",
            bool(check_build_posture(manifest, {}, {"a.kt": "val w = WebView(ctx)"}, extraction)),
        ),
        (
            "android id",
            bool(
                check_build_posture(
                    manifest, {}, {"a.kt": "Settings.Secure.ANDROID_ID"}, extraction
                )
            ),
        ),
        (
            "cloud backup include",
            bool(
                check_build_posture(
                    manifest,
                    {},
                    {},
                    '<cloud-backup><include domain="sharedpref" path="." /></cloud-backup>',
                )
            ),
        ),
        ("no extraction rules", bool(check_build_posture(manifest, {}, {}, ""))),
        ("gitignore ok", not check_gitignore(gitignore)),
        ("gitignore lacks key", bool(check_gitignore("*.keystore\n"))),
        (
            "reads gradle",
            gradle_settings(
                'applicationId = "a.b"\n  versionCode = 3\n  versionName = "1.2.3"\n  targetSdk = 36\n'
            )
            == {
                "applicationId": "a.b",
                "versionCode": "3",
                "versionName": "1.2.3",
                "targetSdk": "36",
            },
        ),
        (
            "reads app name",
            app_name('<string name="app_name">Queer Frame</string>') == "Queer Frame",
        ),
        (
            "reads ios version",
            ios_marketing_version("// v\nMARKETING_VERSION = 1.0.0\n") == "1.0.0",
        ),
    ]
    return [name for name, ok in cases if not ok]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--self-test", action="store_true", help="check the checks, then exit")
    args = parser.parse_args(argv)
    if args.self_test:
        failures = self_test()
        for name in failures:
            print(f"self-test failed: {name}", file=sys.stderr)
        print(f"check_play_store self-test: {'FAILED' if failures else 'ok'}")
        return 1 if failures else 0
    problems = readiness()
    for problem in problems:
        print(f"play store: {problem}", file=sys.stderr)
    if problems:
        print(f"play store check: FAILED ({len(problems)} problems)", file=sys.stderr)
        return 1
    print("play store check: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
