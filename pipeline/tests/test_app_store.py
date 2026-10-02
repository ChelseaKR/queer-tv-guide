"""The App Store launch switch for the Pages site (qtv_pipeline/app_store.py).

Off (APP_STORE_LIVE unset, empty or "false"): the assembled site is left
byte for byte as it was, and no file is added. On: every page carries the
Smart App Banner tag with Queer Frame's app ID, and the index carries
Apple's unmodified badge linking to the US listing, with the price.

Every negative control asserts that its sabotage changed the input before it
asserts that the check caught it; a sabotage that silently no-ops would
otherwise read as a pass.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

import pytest

from qtv_pipeline import app_store, site_index
from tests.test_build_end_to_end import _run

REPO = Path(__file__).resolve().parents[2]
DOCS_SITE = REPO / "docs" / "site"
SNAPSHOT_WORKFLOW = REPO / ".github" / "workflows" / "snapshot.yml"

APP_ID = "6818637465"
APP_URL = "https://apps.apple.com/us/app/id6818637465"
BANNER = f'<meta name="apple-itunes-app" content="app-id={APP_ID}">'
PRICE_COPY = "Queer Frame for iPhone. $4.99 on the App Store."
# Apple's artwork as fetched on 2026-10-02. A different hash means the badge
# was edited, which Apple's guidelines forbid.
BADGE_SHA256 = "a26fc5b38380272c92e9019a2eb8b45542a66814b3e2b203772db8904b9fb99f"
LIVE_MARKERS = ("apple-itunes-app", "app-store-badge", "apps.apple.com", "Download on the App")

_BADGE_LINK = re.compile(
    r'<a class="app-store-badge" href="([^"]+)">'
    r'<img src="app-store-badge.svg" width="120" height="40" '
    r'alt="Download on the App Store"></a>'
)


@pytest.fixture
def site(tmp_path, mock_transport, no_sleep) -> Path:
    """The Pages site as snapshot.yml assembles it, before the switch step."""
    sleep, _ = no_sleep
    doc, _cache, out = _run(tmp_path, mock_transport, sleep)
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    shutil.copy(out / "snapshot.v1.json", site_dir / "snapshot.v1.json")
    shutil.copy(DOCS_SITE / "privacy.html", site_dir / "privacy.html")
    shutil.copy(DOCS_SITE / "support.html", site_dir / "support.html")
    (site_dir / "index.html").write_text(site_index.render_index(doc), encoding="utf-8")
    return site_dir


def _files(site_dir: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(site_dir.iterdir())}


def _page_problems(page: Path) -> list[str]:
    problems = []
    html = page.read_text(encoding="utf-8")
    if html.count(BANNER) != 1:
        problems.append(f"{page.name}: banner tag count {html.count(BANNER)}")
    elif html.index(BANNER) > html.index("<title>"):
        problems.append(f"{page.name}: banner tag after <title>, outside the head")
    links = _BADGE_LINK.findall(html)
    if page.name != "index.html":
        if links:
            problems.append(f"{page.name}: badge on a page it does not belong on")
        return problems
    if links != [APP_URL]:
        problems.append(f"index.html: badge links {links!r}")
    if PRICE_COPY not in html:
        problems.append("index.html: price copy missing")
    return problems


def _on_problems(site_dir: Path) -> list[str]:
    pages = sorted(site_dir.glob("*.html"))
    problems = [] if len(pages) == 3 else [f"expected 3 pages, found {[p.name for p in pages]}"]
    for page in pages:
        problems += _page_problems(page)
    badge = site_dir / app_store.BADGE_FILE
    if not badge.exists():
        problems.append("badge file missing")
    elif hashlib.sha256(badge.read_bytes()).hexdigest() != BADGE_SHA256:
        problems.append("badge file is not Apple's artwork byte for byte")
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
    assert app_store.live_or_false(value) is expected


@pytest.mark.parametrize("value", ["ture", "yes", "1", "on", "true false"])
def test_switch_refuses_anything_else(value):
    with pytest.raises(app_store.SwitchError, match="APP_STORE_LIVE"):
        app_store.live_or_false(value)


@pytest.mark.parametrize(("value", "code"), [("", 0), ("false", 0), ("true", 0), ("ture", 1)])
def test_check_mode(value, code):
    assert app_store.main(["--check", value]) == code


def test_usage_error():
    assert app_store.main(["only-one-argument"]) == 2


def test_constants_name_the_real_listing():
    assert app_store.APP_STORE_ID == APP_ID
    assert app_store.APP_STORE_URL == APP_URL
    assert hashlib.sha256(app_store.BADGE_SOURCE.read_bytes()).hexdigest() == BADGE_SHA256


# ---- off


@pytest.mark.parametrize("value", ["", "false", "FALSE"])
def test_off_leaves_the_site_byte_for_byte(site, value):
    before = _files(site)
    assert app_store.main([str(site), value]) == 0
    assert _files(site) == before


def test_bad_value_refuses_and_changes_nothing(site):
    before = _files(site)
    assert app_store.main([str(site), "ture"]) == 1
    assert _files(site) == before


# ---- on


def test_on_adds_banner_everywhere_and_badge_on_the_index(site):
    assert app_store.main([str(site), "true"]) == 0
    assert _on_problems(site) == []
    assert (site / "snapshot.v1.json").read_bytes()  # data file untouched and present


def test_on_copy_is_iphone_only(site):
    assert app_store.main([str(site), "true"]) == 0
    for page in site.glob("*.html"):
        text = page.read_text(encoding="utf-8").lower()
        assert "android" not in text and "google play" not in text, page.name


def test_on_adds_no_script(site):
    assert app_store.main([str(site), "true"]) == 0
    for page in site.glob("*.html"):
        assert "<script" not in page.read_text(encoding="utf-8").lower(), page.name


def test_a_second_run_is_refused_rather_than_doubling_the_tag(site):
    assert app_store.main([str(site), "true"]) == 0
    after_first = _files(site)
    assert app_store.main([str(site), "true"]) == 1
    assert _files(site) == after_first


def test_a_page_without_the_anchor_is_refused_and_nothing_is_written(site):
    privacy = site / "privacy.html"
    privacy.write_text(
        privacy.read_text(encoding="utf-8").replace(app_store.VIEWPORT, ""), encoding="utf-8"
    )
    before = _files(site)
    assert app_store.main([str(site), "true"]) == 1
    assert _files(site) == before


def test_a_site_without_an_index_is_refused(tmp_path):
    with pytest.raises(app_store.PageShapeError, match=r"no index\.html"):
        app_store.apply(tmp_path)


def test_published_pages_have_the_anchors_the_switch_needs():
    for page in ("privacy.html", "support.html"):
        assert (DOCS_SITE / page).read_text(encoding="utf-8").count(app_store.VIEWPORT) == 1, page


def test_index_has_the_anchors_the_switch_needs(site):
    index = (site / "index.html").read_text(encoding="utf-8")
    assert index.count(app_store.VIEWPORT) == 1
    assert index.count(app_store.INDEX_HEADING) == 1


def test_workflow_passes_the_variable_and_checks_it_before_publishing():
    wf = SNAPSHOT_WORKFLOW.read_text(encoding="utf-8")
    assert wf.count("APP_STORE_LIVE: ${{ vars.APP_STORE_LIVE }}") == 2
    check = wf.index('qtv_pipeline.app_store --check "$APP_STORE_LIVE"')
    apply_step = wf.index('qtv_pipeline.app_store site "$APP_STORE_LIVE"')
    upload = wf.index("gh release upload")
    pages = wf.index("actions/upload-pages-artifact")
    assert check < upload < apply_step < pages


# ---- negative controls: the checks above can fail


def test_negative_control_on_check_catches_an_off_site(site):
    problems = _on_problems(site)
    assert "badge file missing" in problems
    assert any("banner tag count 0" in p for p in problems)


def test_negative_control_off_markers_catch_an_on_site(site):
    before = _files(site)
    assert app_store.main([str(site), "true"]) == 0
    assert _files(site) != before
    index = (site / "index.html").read_text(encoding="utf-8")
    assert all(marker in index for marker in LIVE_MARKERS)


def test_negative_control_wrong_app_id_is_caught(site, monkeypatch):
    monkeypatch.setattr(app_store, "BANNER", app_store.BANNER.replace(APP_ID, "6818637427"))
    assert APP_ID not in app_store.BANNER  # the sabotage landed
    assert app_store.main([str(site), "true"]) == 0
    assert any("banner tag count 0" in p for p in _on_problems(site))


def test_negative_control_edited_badge_is_caught(site):
    assert app_store.main([str(site), "true"]) == 0
    badge = site / app_store.BADGE_FILE
    original = badge.read_bytes()
    badge.write_bytes(original.replace(b"#a6a6a6", b"#000000", 1))
    assert badge.read_bytes() != original  # the sabotage landed
    assert "badge file is not Apple's artwork byte for byte" in _on_problems(site)


def test_negative_control_wrong_price_is_caught(site):
    assert app_store.main([str(site), "true"]) == 0
    index = site / "index.html"
    original = index.read_text(encoding="utf-8")
    index.write_text(original.replace("$4.99", "$9.99"), encoding="utf-8")
    assert index.read_text(encoding="utf-8") != original  # the sabotage landed
    assert "index.html: price copy missing" in _on_problems(site)
