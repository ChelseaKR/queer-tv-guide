"""The small-cast batch (DECISIONS 0060, proposed).

A show with 3 or 4 listed characters gets a page, open to search, only when
its LezWatch id is in ``SMALL_CAST_BATCH``; every other show still needs the
0025 rule's 5. The page is the same template as any other: it keeps the
LezWatch.TV and TVmaze credit, loads nothing from another host and says
"Unknown" where no death is recorded. Every negative control asserts its
sabotage changed the output before it concludes anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe
from tests.test_show_pages import BUNDLED
from tests.test_show_pages_indexing import BASE, PINNED, _locs, _page, _robots, _url
from tests.test_show_pages_pinned import _pins
from tests.test_show_pages_rule import _qualified
from tests.test_show_pages_second_batch import _credit_problems, _load_problems

# 55 fixture shows meet the 0025 rule, so the 50-page floor never fills in a
# small show. Fixture show 1060 lists 4 characters, 1061 lists 3 and 1062
# lists 2; a real batch id is given to each in turn (Wednesday, Lucifer,
# Wednesday again).
RICH = {**{1000 + i: 5 + (i % 3) for i in range(55)}, 1060: 4, 1061: 3, 1062: 2}
WEDNESDAY, LUCIFER = 84330, 6910


def _doc() -> dict:
    return _qualified(80, RICH)


def _slug(doc: dict, lwtv_id: int) -> str:
    return next(s["slug"] for s in doc["shows"] if s["lwtv_id"] == lwtv_id)


def _render(doc: dict, tmp_path: Path) -> dict[str, str]:
    pins = show_pages.load_pinned(_pins(PINNED, tmp_path))
    return show_pages.render_site(doc, base_url=BASE, pinned=pins)


def _renamed(doc: dict, old: int, new: int) -> str:
    show = next(s for s in doc["shows"] if s["lwtv_id"] == old)
    show["lwtv_id"] = new
    return show["slug"]


# ---- the list ------------------------------------------------------------------


def test_the_batch_is_fifty_new_ids():
    pins = show_pages.load_pinned(show_pages.DEFAULT_PINNED_PATH)
    assert pins is not None
    batch = show_pages.SMALL_CAST_BATCH
    assert len(batch) == 50
    # An id already pinned or in an earlier batch would be a no-op that makes
    # the batch look larger than it is.
    assert not batch & {p.lezwatch_id for p in pins}
    assert not batch & show_pages.INDEX_FIRST_BATCH
    assert not batch & show_pages.INDEX_SECOND_BATCH
    assert (
        show_pages.INDEX_FIRST_BATCH | show_pages.INDEX_SECOND_BATCH | batch
    ) == show_pages.INDEX_EXTRA_IDS
    assert len(show_pages.INDEX_EXTRA_IDS) == 144
    assert show_pages.MIN_LISTED == 5  # the 0025 rule is unchanged for everyone else
    assert show_pages.SMALL_CAST_MIN == 3


@pytest.mark.skipif(not BUNDLED.is_file(), reason="needs `make -C ios bundle-snapshot`")
def test_on_the_bundled_snapshot_every_batch_show_fits_the_rule_it_was_chosen_by():
    doc = json.loads(BUNDLED.read_text(encoding="utf-8"))
    listed = show_pages._listed_characters(doc)
    by_id = {s["lwtv_id"]: s for s in doc["shows"]}
    problems = []
    for lwtv_id in sorted(show_pages.SMALL_CAST_BATCH):
        show = by_id.get(lwtv_id)
        if show is None:
            problems.append(f"{lwtv_id}: not in the snapshot")
            continue
        genres = {g["slug"] for g in show["genres"]}
        countries = {c["name"] for c in show["countries"]}
        if listed.get(show["id"], 0) < show_pages.SMALL_CAST_MIN:
            problems.append(f"{show['slug']}: fewer than {show_pages.SMALL_CAST_MIN} listed")
        if not genres & show_pages.SMALL_CAST_GENRES:
            problems.append(f"{show['slug']}: none of the chosen genres")
        if genres & {"soap-opera", "telenovela"}:
            problems.append(f"{show['slug']}: a soap")
        if "USA" not in countries:
            problems.append(f"{show['slug']}: not a US show")
        if show["schedule"]["join"].get("method") not in show_pages.TVMAZE_ID_JOINS:
            problems.append(f"{show['slug']}: TVmaze match not by id")
    # Data moves nightly; a few drifting shows are fine (they are simply not
    # built), most of the batch drifting means the list needs a fresh look.
    assert len(problems) <= 5, problems


# ---- the rule --------------------------------------------------------------------


def test_three_or_four_qualify_only_in_the_batch():
    doc = _doc()
    listed = show_pages._listed_characters(doc)
    by_id = {s["lwtv_id"]: s for s in doc["shows"]}
    assert not show_pages.qualifies(by_id[1060], listed)  # 4, not in the batch
    by_id[1060]["lwtv_id"] = WEDNESDAY
    assert show_pages.qualifies(by_id[1060], listed)
    by_id[1061]["lwtv_id"] = LUCIFER
    assert show_pages.qualifies(by_id[1061], listed)  # 3 is enough in the batch
    by_id[1062]["lwtv_id"] = WEDNESDAY
    assert not show_pages.qualifies(by_id[1062], listed)  # 2 is never enough
    by_id[1061]["schedule"]["tvmaze_url"] = None
    assert not show_pages.qualifies(by_id[1061], listed)  # a TVmaze match still required


def test_a_batch_show_is_built_indexed_and_dated_with_the_snapshot(tmp_path):
    doc = _doc()
    before = _render(doc, tmp_path)
    slug = _renamed(doc, 1060, WEDNESDAY)
    assert f"shows/{slug}/index.html" not in before  # 4 listed: no page before
    after = _render(doc, tmp_path)
    assert _robots(_page(after, slug)) == []
    assert set(_locs(after)) - set(_locs(before)) == {_url(slug)}
    entries = htmlprobe.sitemap(after["sitemap.xml"])
    lastmod = dict(zip(entries["loc"], entries["lastmod"], strict=True))
    assert lastmod[_url(slug)] == doc["generated_at"][:10]
    assert show_pages.index_problems(after, base_url=BASE) == []
    # Every page that existed before is still there, unchanged in kind.
    assert {k for k in before if k.startswith("shows/")} <= set(after)


def test_a_batch_page_keeps_the_credit_loads_nothing_and_says_unknown(tmp_path):
    doc = _doc()
    slug = _renamed(doc, 1060, WEDNESDAY)
    page = _page(_render(doc, tmp_path), slug)
    assert _credit_problems(doc, page) == []
    assert _load_problems(page) == []
    assert any(kind == "unknown" for kind, _ in page.statuses)  # the check has work
    assert htmlprobe.no_for_unknown(page) == []


# ---- negative controls --------------------------------------------------------------


def test_negative_control_an_id_left_out_of_the_batch_gets_no_page(tmp_path, monkeypatch):
    doc = _doc()
    slug = _renamed(doc, 1060, WEDNESDAY)
    built = _render(doc, tmp_path)
    assert f"shows/{slug}/index.html" in built  # the control has something to remove
    monkeypatch.setattr(show_pages, "SMALL_CAST_BATCH", show_pages.SMALL_CAST_BATCH - {WEDNESDAY})
    monkeypatch.setattr(show_pages, "INDEX_EXTRA_IDS", show_pages.INDEX_EXTRA_IDS - {WEDNESDAY})
    held = _render(doc, tmp_path)
    assert f"shows/{slug}/index.html" not in held
    assert _url(slug) not in _locs(held)


def test_negative_control_a_lower_floor_would_build_two_listed_shows(tmp_path, monkeypatch):
    doc = _doc()
    slug = _renamed(doc, 1062, WEDNESDAY)
    assert f"shows/{slug}/index.html" not in _render(doc, tmp_path)
    monkeypatch.setattr(show_pages, "SMALL_CAST_MIN", 2)
    assert f"shows/{slug}/index.html" in _render(doc, tmp_path)  # the floor is what held it
