"""The Google Play launch switch for the Pages site (qtv_pipeline/play_store.py).

Off (PLAY_STORE_LIVE unset, empty or "false"): the assembled site is left
byte for byte as it was, and no file is added. On: the index, and only the
index, carries one text link to the Play listing with the price and
Google's trademark line, inside an android-app region, below the App Store
badge when that switch is on too.

Every negative control asserts that its sabotage changed the input before it
asserts that the check caught it; a sabotage that silently no-ops would
otherwise read as a pass.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from qtv_pipeline import app_store, play_store, site_index
from tests.test_app_store import ANDROID_PAGES, _android_problems, _files, _on_problems
from tests.test_build_end_to_end import _run

REPO = Path(__file__).resolve().parents[2]
DOCS_SITE = REPO / "docs" / "site"
SNAPSHOT_WORKFLOW = REPO / ".github" / "workflows" / "snapshot.yml"
PLAY_LISTING = REPO / "docs" / "play-store" / "play-listing.json"
APP_GRADLE = REPO / "android" / "app" / "build.gradle.kts"
ABOUT_SCREEN = REPO / "android/app/src/main/kotlin/com/chelseakr/queertvguide/ui/AboutScreen.kt"

PLAY_URL = "https://play.google.com/store/apps/details?id=com.chelseakr.queertvguide"
LINK = f'<a href="{PLAY_URL}">Queer Frame on Google Play</a>'
PRICE_COPY = "for Android, $4.99."
TRADEMARK = "Google Play is a trademark of Google LLC."
# With the Play link on, the index may describe Android inside its region.
PLAY_PAGES = ANDROID_PAGES | {"index.html"}


@pytest.fixture
def site(tmp_path, mock_transport, no_sleep) -> Path:
    """The Pages site as snapshot.yml assembles it, before the switch steps."""
    sleep, _ = no_sleep
    doc, _cache, out = _run(tmp_path, mock_transport, sleep)
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    shutil.copy(out / "snapshot.v1.json", site_dir / "snapshot.v1.json")
    shutil.copy(DOCS_SITE / "privacy.html", site_dir / "privacy.html")
    shutil.copy(DOCS_SITE / "support.html", site_dir / "support.html")
    (site_dir / "index.html").write_text(site_index.render_index(doc), encoding="utf-8")
    return site_dir


def _index_problems(html: str) -> list[str]:
    problems = []
    if html.count(PLAY_URL) != 1:
        problems.append(f"Play URL count {html.count(PLAY_URL)}")
    if html.count(LINK) != 1:
        problems.append("link text or target changed")
    if PRICE_COPY not in html:
        problems.append("price copy missing")
    if TRADEMARK not in html:
        problems.append("trademark line missing")
    lines = [line for line in html.splitlines() if "play.google.com" in line]
    if len(lines) != 1:
        problems.append(f"the link spans {len(lines)} lines; OWNER-STEPS greps for one")
    return problems


# ---- the switch's parser


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, False),
        ("", False),
        ("false", False),
        (" FALSE ", False),
        ("true", True),
        ("True\n", True),
    ],
)
def test_switch_values(value, expected):
    assert play_store.live_or_false(value) is expected


@pytest.mark.parametrize("value", ["ture", "yes", "1", "on", "true false"])
def test_switch_refuses_anything_else(value):
    with pytest.raises(play_store.SwitchError, match="PLAY_STORE_LIVE"):
        play_store.live_or_false(value)


@pytest.mark.parametrize(("value", "code"), [("", 0), ("false", 0), ("true", 0), ("ture", 1)])
def test_check_mode(value, code):
    assert play_store.main(["--check", value]) == code


def test_usage_error():
    assert play_store.main(["only-one-argument"]) == 2


# ---- the link names the real listing and price


def test_constants_name_the_real_listing_and_price():
    assert play_store.PLAY_URL == PLAY_URL
    gradle = APP_GRADLE.read_text(encoding="utf-8")
    assert re.search(rf'applicationId = "{re.escape(play_store.PACKAGE)}"', gradle)
    # The app's own "Rate" row opens the same listing.
    about = ABOUT_SCREEN.read_text(encoding="utf-8")
    assert "https://play.google.com/store/apps/details?id=${BuildConfig.APPLICATION_ID}" in about
    listing = json.loads(PLAY_LISTING.read_text(encoding="utf-8"))
    assert listing["package_name"] == play_store.PACKAGE
    assert f"${listing['price_usd']}." in play_store.PRICE_COPY


# ---- off


@pytest.mark.parametrize("value", ["", "false", "FALSE"])
def test_off_leaves_the_site_byte_for_byte(site, value):
    before = _files(site)
    assert play_store.main([str(site), value]) == 0
    assert _files(site) == before


def test_bad_value_refuses_and_changes_nothing(site):
    before = _files(site)
    assert play_store.main([str(site), "ture"]) == 1
    assert _files(site) == before


# ---- on


def test_on_adds_the_link_to_the_index_only(site):
    before = _files(site)
    assert play_store.main([str(site), "true"]) == 0
    after = _files(site)
    assert set(after) == set(before), "a file was added or removed"
    changed = sorted(name for name in after if after[name] != before[name])
    assert changed == ["index.html"]
    index = (site / "index.html").read_text(encoding="utf-8")
    assert _index_problems(index) == []
    assert index.index(app_store.INDEX_SLOT) < index.index(PLAY_URL)


def test_on_keeps_android_wording_inside_its_region(site):
    assert play_store.main([str(site), "true"]) == 0
    for page in site.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        assert _android_problems(page.name, text, PLAY_PAGES) == [], page.name


def test_on_adds_no_script_and_no_image(site):
    assert play_store.main([str(site), "true"]) == 0
    index = (site / "index.html").read_text(encoding="utf-8").lower()
    assert "<script" not in index
    assert "<img" not in index


@pytest.mark.parametrize("play_first", [False, True])
def test_both_switches_on_put_the_app_store_first_in_either_order(site, play_first):
    steps = [app_store.main, play_store.main]
    for step in reversed(steps) if play_first else steps:
        assert step([str(site), "true"]) == 0
    assert _on_problems(site) == []
    index = (site / "index.html").read_text(encoding="utf-8")
    assert _index_problems(index) == []
    assert index.index(app_store.APP_STORE_URL) < index.index(PLAY_URL)
    for page in site.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        assert _android_problems(page.name, text, PLAY_PAGES) == [], page.name


def test_a_second_run_is_refused_rather_than_doubling_the_link(site):
    assert play_store.main([str(site), "true"]) == 0
    after_first = _files(site)
    assert play_store.main([str(site), "true"]) == 1
    assert _files(site) == after_first


def test_an_index_without_the_coming_soon_line_is_refused_and_left_alone(site):
    index = site / "index.html"
    original = index.read_text(encoding="utf-8")
    index.write_text(original.replace(app_store.INDEX_SLOT, "<h1>Other</h1>"), encoding="utf-8")
    assert index.read_text(encoding="utf-8") != original  # the sabotage landed
    before = _files(site)
    assert play_store.main([str(site), "true"]) == 1
    assert _files(site) == before


def test_a_site_without_an_index_is_refused(tmp_path):
    with pytest.raises(app_store.PageShapeError, match=r"no index\.html"):
        play_store.apply(tmp_path)


def test_workflow_passes_the_variable_and_checks_it_before_publishing():
    wf = SNAPSHOT_WORKFLOW.read_text(encoding="utf-8")
    assert wf.count("PLAY_STORE_LIVE: ${{ vars.PLAY_STORE_LIVE }}") == 2
    check = wf.index('qtv_pipeline.play_store --check "$PLAY_STORE_LIVE"')
    apply_step = wf.index('qtv_pipeline.play_store site "$PLAY_STORE_LIVE"')
    upload = wf.index("gh release upload")
    pages = wf.index("actions/upload-pages-artifact")
    assert check < upload < apply_step < pages


# ---- negative controls: the checks above can fail


def test_negative_control_index_check_catches_an_off_site(site):
    index = (site / "index.html").read_text(encoding="utf-8")
    assert "Play URL count 0" in _index_problems(index)


def test_negative_control_wording_outside_the_region_is_caught(site):
    assert play_store.main([str(site), "true"]) == 0
    index = (site / "index.html").read_text(encoding="utf-8")
    moved = index.replace(play_store.ANDROID_END, "", 1).replace(play_store.ANDROID_BEGIN, "", 1)
    assert moved != index  # the sabotage landed
    assert "index.html: 'google play' outside a marked region" in _android_problems(
        "index.html", moved, PLAY_PAGES
    )


def test_negative_control_region_on_the_index_needs_the_play_page_set(site):
    assert play_store.main([str(site), "true"]) == 0
    index = (site / "index.html").read_text(encoding="utf-8")
    assert play_store.ANDROID_BEGIN in index
    assert any("region outside" in p for p in _android_problems("index.html", index))


def test_negative_control_wrong_price_is_caught(site):
    assert play_store.main([str(site), "true"]) == 0
    index = site / "index.html"
    original = index.read_text(encoding="utf-8")
    index.write_text(original.replace("$4.99", "$9.99"), encoding="utf-8")
    assert index.read_text(encoding="utf-8") != original  # the sabotage landed
    assert "price copy missing" in _index_problems(index.read_text(encoding="utf-8"))


def test_negative_control_wrong_package_is_caught(site, monkeypatch):
    monkeypatch.setattr(
        play_store, "PLAY_BLOCK", play_store.PLAY_BLOCK.replace("queertvguide", "x")
    )
    assert "queertvguide" not in play_store.PLAY_BLOCK  # the sabotage landed
    assert play_store.main([str(site), "true"]) == 0
    index = (site / "index.html").read_text(encoding="utf-8")
    assert "Play URL count 0" in _index_problems(index)
