"""The sitemap's lastmod is the day a page last changed (DECISIONS 0061).

``indexnow.py manifest --carry-dates`` reads the live ``lastmod.json``; a page
whose fingerprint (its HTML without the footer's build date, 0034) is the
same as live keeps the live day, and any other page gets the snapshot's day.
That day goes into the manifest and into the sitemap's ``lastmod``. Any
failure dates a page today, which is what the sitemap said before, so a
failure can make a date newer but never hide a change. Every negative
control asserts its sabotage changed the output before it concludes
anything. Nothing here touches the network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from qtv_pipeline import indexnow as ix
from tests.test_indexnow import DOMAIN, WORKFLOW, _build, _doc

DAY13, DAY14 = "2026-11-13T09:20:00Z", "2026-11-14T09:20:00Z"


def _live(entries: dict[str, tuple[str, str]]) -> str:
    return json.dumps(
        {
            "schema": 1,
            "pages": {p: {"fingerprint": f, "changed": d} for p, (f, d) in entries.items()},
        }
    )


def _lastmods(site: Path) -> dict[str, str]:
    return ix.parse_sitemap((site / "sitemap.xml").read_text(encoding="utf-8"))


def _carried_build(
    tmp_path: Path,
    name: str,
    doc: dict[str, Any],
    live: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Build as the workflow does, then run the manifest again with
    --carry-dates against ``live`` as the live site's lastmod.json."""
    site = _build(tmp_path, name, doc)
    monkeypatch.setattr(ix, "fetch_text", lambda url, missing_is_empty: live)
    snap = tmp_path / f"{name}.json"
    argv = ["manifest", "--site-dir", str(site), "--base-url", DOMAIN, "--snapshot", str(snap)]
    assert ix.main([*argv, "--carry-dates"]) == 0
    return site


# ---- the rule ----------------------------------------------------------------------


def test_an_unchanged_page_keeps_its_day_and_a_changed_or_new_page_gets_today():
    pages = {"/a/": {"fingerprint": "1"}, "/b/": {"fingerprint": "2"}, "/c/": {"fingerprint": "3"}}
    live = _live({"/a/": ("1", "2026-11-02"), "/b/": ("old", "2026-11-02")})
    out = ix.carry_dates(pages, live, "2026-11-14")
    assert out["/a/"] == {"fingerprint": "1", "changed": "2026-11-02"}
    assert out["/b/"]["changed"] == "2026-11-14"  # its content changed
    assert out["/c/"]["changed"] == "2026-11-14"  # new


@pytest.mark.parametrize(
    "live",
    [
        None,  # unreadable
        "",  # no live file yet
        "not json",
        json.dumps({"schema": 1}),
        json.dumps({"schema": 1, "pages": []}),
        _live({"/a/": ("1", "2026-11-20")}),  # a day after today
        _live({"/a/": ("1", "Nov 2")}),  # not a plain day
        json.dumps({"schema": 1, "pages": {"/a/": {"fingerprint": "1"}}}),  # 0034's schema
    ],
)
def test_anything_doubtful_dates_the_page_today(live):
    out = ix.carry_dates({"/a/": {"fingerprint": "1"}}, live, "2026-11-14")
    assert out["/a/"]["changed"] == "2026-11-14"


def test_the_sitemap_takes_each_covered_pages_day_and_leaves_the_rest():
    xml = (
        "<urlset>\n"
        f"<url><loc>{DOMAIN}/a/</loc><lastmod>2026-11-14</lastmod></url>\n"
        f"<url><loc>{DOMAIN}/b/</loc><lastmod>2026-11-14</lastmod></url>\n"
        "</urlset>\n"
    )
    dated = ix.date_sitemap(xml, DOMAIN, {"/a/": {"fingerprint": "1", "changed": "2026-11-02"}})
    assert ix.parse_sitemap(dated) == {f"{DOMAIN}/a/": "2026-11-02", f"{DOMAIN}/b/": "2026-11-14"}


# ---- the real build, run the way snapshot.yml runs it ---------------------------------


def test_the_nightly_rebuild_keeps_yesterdays_days_except_the_airing_page(tmp_path, monkeypatch):
    first = _carried_build(tmp_path, "first", _doc(generated_at=DAY13), "", monkeypatch)
    assert set(_lastmods(first).values()) == {"2026-11-13"}  # the first deploy: every page new
    live = (first / "lastmod.json").read_text(encoding="utf-8")
    again = _carried_build(tmp_path, "again", _doc(generated_at=DAY14), live, monkeypatch)
    days = _lastmods(again)
    airing = f"{DOMAIN}/airing/"
    assert days[airing] == "2026-11-14"  # its window starts on the build day (0033)
    assert {u: d for u, d in days.items() if u != airing} == {
        u: "2026-11-13" for u in days if u != airing
    }
    # The manifest agrees with the sitemap, and IndexNow's selection is unchanged.
    manifest = json.loads((again / "lastmod.json").read_text(encoding="utf-8"))["pages"]
    assert {DOMAIN + p: e["changed"] for p, e in manifest.items()} == days
    assert ix.select_changed(
        ix.tokens("manifest", live, DOMAIN),
        ix.tokens("manifest", (again / "lastmod.json").read_text(encoding="utf-8"), DOMAIN),
    ) == [airing]


def test_negative_control_a_renamed_show_is_dated_today(tmp_path, monkeypatch):
    first = _carried_build(tmp_path, "first", _doc(generated_at=DAY13), "", monkeypatch)
    live = (first / "lastmod.json").read_text(encoding="utf-8")
    renamed = _doc(generated_at=DAY14)
    old = renamed["shows"][0]["title"]
    renamed["shows"][0]["title"] = old + " (renamed)"
    assert renamed["shows"][0]["title"] != old  # the sabotage applied
    changed = _carried_build(tmp_path, "changed", renamed, live, monkeypatch)
    fresh = {u for u, d in _lastmods(changed).items() if d == "2026-11-14"}
    assert len(fresh) > 1  # more than the airing page: the renamed show's pages moved


def test_negative_control_an_unreadable_live_site_dates_everything_today(tmp_path, monkeypatch):
    first = _carried_build(tmp_path, "first", _doc(generated_at=DAY13), "", monkeypatch)
    assert (first / "lastmod.json").is_file()
    blind = _carried_build(tmp_path, "blind", _doc(generated_at=DAY14), None, monkeypatch)
    assert set(_lastmods(blind).values()) == {"2026-11-14"}  # newer, never older


def test_without_the_flag_every_lastmod_is_the_snapshot_day(tmp_path):
    site = _build(tmp_path, "plain", _doc(generated_at=DAY14))
    assert set(_lastmods(site).values()) == {"2026-11-14"}
    manifest = json.loads((site / "lastmod.json").read_text(encoding="utf-8"))["pages"]
    assert all("changed" not in e for e in manifest.values())


def test_the_workflow_carries_dates_before_the_upload():
    text = WORKFLOW.read_text(encoding="utf-8")
    step = text[text.index("indexnow manifest") : text.index("indexnow select")]
    assert "--carry-dates" in step
    assert text.index("--carry-dates") < text.index("actions/upload-pages-artifact")
