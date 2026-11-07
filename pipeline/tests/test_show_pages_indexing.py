"""Which show pages search engines may index (DECISIONS 0028).

The hand-picked list is in the sitemap and carries no robots tag. Every other
show page is still built and linked, but carries
``<meta name="robots" content="noindex,follow">`` and is left out of the
sitemap. One function (``indexed_show_ids``) decides both, and
``index_problems`` refuses a build where the sitemap and the robots tags
disagree. Every negative control asserts its sabotage changed the output
before it concludes anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe
from tests.test_show_pages_pinned import _pins
from tests.test_show_pages_rule import _qualified

BASE = "https://example.test"
PINNED = [1005, 1003, 1001, 1007]  # the hand-picked list, in its own order
RICH = {1000 + i: 5 + (i % 3) for i in range(20)}  # 20 of 60 shows meet the 0025 rule


def _doc() -> dict:
    return _qualified(60, RICH)


def _site(tmp_path: Path, **kw) -> tuple[dict[str, str], list[dict]]:
    doc = _doc()
    pins = show_pages.load_pinned(_pins(PINNED, tmp_path))
    files = show_pages.render_site(doc, base_url=BASE, pinned=pins, **kw)
    shows = show_pages.select_shows(doc, show_pages.DEFAULT_LIMIT, pins)
    return files, shows


def _page(files: dict[str, str], slug: str) -> htmlprobe.Page:
    return htmlprobe.parse(files[f"shows/{slug}/index.html"])


def _robots(page: htmlprobe.Page) -> list[str | None]:
    return [a.get("content") for a in page.named("meta") if a.get("name") == "robots"]


def _locs(files: dict[str, str]) -> list[str]:
    return htmlprobe.sitemap(files["sitemap.xml"])["loc"]


def _url(slug: str) -> str:
    return f"{BASE}/shows/{slug}/"


# ---- the indexed set ---------------------------------------------------------


def test_only_the_pinned_pages_are_in_the_sitemap(tmp_path):
    files, shows = _site(tmp_path)
    pinned_slugs = [f"show-{i - 1000:03d}" for i in PINNED]
    assert len(shows) > len(PINNED)  # the rule built more pages than the pins
    assert _locs(files) == [
        f"{BASE}/",
        f"{BASE}/shows/",
        f"{BASE}/airing/",
        f"{BASE}/findings/finales/",
        f"{BASE}/press/",
        *map(_url, pinned_slugs),
    ]
    assert show_pages.index_problems(files, base_url=BASE) == []


def test_pinned_pages_carry_no_robots_tag_and_the_rest_carry_noindex_follow(tmp_path):
    files, shows = _site(tmp_path)
    pinned = {f"show-{i - 1000:03d}" for i in PINNED}
    held = [s["slug"] for s in shows if s["slug"] not in pinned]
    assert held  # there is something held back to look at
    for slug in pinned:
        assert _robots(_page(files, slug)) == []
    for slug in held:
        assert _robots(_page(files, slug)) == ["noindex,follow"]
    assert _robots(htmlprobe.parse(files["shows/index.html"])) == []


def test_held_back_pages_stay_built_and_linked(tmp_path):
    files, shows = _site(tmp_path)
    index = htmlprobe.parse(files["shows/index.html"])
    for s in shows:
        assert f"shows/{s['slug']}/index.html" in files
        assert f"{s['slug']}/" in index.hrefs()  # the index links relative
    # A held-back page still links on to its neighbors and the index.
    held = next(s for s in shows if s["lwtv_id"] not in PINNED)
    links = _page(files, held["slug"]).hrefs()
    assert f"{BASE}/shows/" in links
    assert sum(h.startswith(f"{BASE}/shows/show-") for h in links) >= 2


def test_the_robots_tag_is_the_only_difference_on_a_held_back_page():
    doc = _doc()
    show = doc["shows"][0]
    shown = show_pages.render_show(doc, show, base_url=BASE, indexed=True)
    held = show_pages.render_show(doc, show, base_url=BASE, indexed=False)
    tag = '\n<meta name="robots" content="noindex,follow">'
    assert tag not in shown and tag in held
    assert held.replace(tag, "", 1) == shown


def test_without_a_pinned_list_the_first_fifty_are_indexed():
    doc = _qualified(80, {1000 + i: 5 + (i % 3) for i in range(70)})  # 70 qualify
    shows = show_pages.select_shows(doc)
    ids = show_pages.indexed_show_ids(shows, None, show_pages._listed_characters(doc))
    assert len(shows) == 70 and ids == {s["id"] for s in shows[:50]}


def test_the_indexed_set_is_a_subset_of_the_built_pages(tmp_path):
    doc = _doc()
    pins = show_pages.load_pinned(_pins([*PINNED, 9999], tmp_path))  # 9999 is not in the data
    shows = show_pages.select_shows(doc, show_pages.DEFAULT_LIMIT, pins)
    ids = show_pages.indexed_show_ids(shows, pins, show_pages._listed_characters(doc))
    assert ids == {s["id"] for s in shows if s["lwtv_id"] in PINNED}


# ---- widening ----------------------------------------------------------------


def test_widen_by_list(tmp_path, monkeypatch):
    monkeypatch.setattr(show_pages, "INDEX_EXTRA_IDS", frozenset({1010, 1011}))
    files, _ = _site(tmp_path)
    assert _url("show-010") in _locs(files) and _url("show-011") in _locs(files)
    assert _robots(_page(files, "show-010")) == []
    assert _url("show-012") not in _locs(files)
    assert show_pages.index_problems(files, base_url=BASE) == []


def test_widen_by_rule(tmp_path, monkeypatch):
    monkeypatch.setattr(show_pages, "INDEX_MIN_LISTED", 7)
    files, shows = _site(tmp_path)
    listed = show_pages._listed_characters(_doc())
    seven = {s["slug"] for s in shows if listed[s["id"]] >= 7}
    assert seven - {f"show-{i - 1000:03d}" for i in PINNED}  # the rule adds pages
    for slug in seven:
        assert _url(slug) in _locs(files)
        assert _robots(_page(files, slug)) == []
    assert show_pages.index_problems(files, base_url=BASE) == []


# ---- the agreement check and its negative controls ---------------------------


def test_negative_control_a_held_back_page_in_the_sitemap_refuses_the_build(tmp_path, monkeypatch):
    real = show_pages.render_sitemap

    def every_show(doc, shows, *, base_url, indexed=None, airing=False):
        return real(doc, shows, base_url=base_url, indexed=None, airing=airing)

    # The sabotage changes the sitemap: it lists every show, not only the pins.
    files, shows = _site(tmp_path)
    assert len(htmlprobe.sitemap(every_show(_doc(), shows, base_url=BASE))["loc"]) > len(
        _locs(files)
    )
    monkeypatch.setattr(show_pages, "render_sitemap", every_show)
    with pytest.raises(show_pages.ShowPagesError, match="in the sitemap but tagged"):
        _site(tmp_path)


def test_negative_control_a_held_back_page_without_its_tag_refuses_the_build(tmp_path, monkeypatch):
    real = show_pages.render_show

    def no_tag(*args, **kw):
        kw["indexed"] = True
        return real(*args, **kw)

    monkeypatch.setattr(show_pages, "render_show", no_tag)
    doc = _doc()
    held = next(s for s in doc["shows"] if s["lwtv_id"] not in PINNED)
    assert "noindex" not in show_pages.render_show(doc, held, base_url=BASE, indexed=False)
    with pytest.raises(show_pages.ShowPagesError, match="left out of the sitemap"):
        _site(tmp_path)


def test_negative_control_the_check_catches_each_kind_of_disagreement(tmp_path):
    files, shows = _site(tmp_path)
    assert show_pages.index_problems(files, base_url=BASE) == []
    held = next(s["slug"] for s in shows if s["lwtv_id"] not in PINNED)
    pinned = f"show-{PINNED[0] - 1000:03d}"
    tag = '<meta name="robots" content="noindex,follow">'

    # A pinned page that gains the tag.
    broken = dict(files)
    key = f"shows/{pinned}/index.html"
    broken[key] = broken[key].replace("</title>", "</title>\n" + tag, 1)
    assert tag in broken[key]
    assert any(pinned in p for p in show_pages.index_problems(broken, base_url=BASE))

    # A held-back page with another robots value.
    broken = dict(files)
    key = f"shows/{held}/index.html"
    broken[key] = broken[key].replace("noindex,follow", "noindex,nofollow")
    assert "noindex,nofollow" in broken[key]
    assert any(held in p for p in show_pages.index_problems(broken, base_url=BASE))

    # The sitemap names a page this build did not write.
    broken = dict(files)
    ghost = f"<url><loc>{_url('no-such-show')}</loc></url>"
    broken["sitemap.xml"] = broken["sitemap.xml"].replace("</urlset>", ghost + "</urlset>")
    assert "no-such-show" in broken["sitemap.xml"]
    assert any("no-such-show" in p for p in show_pages.index_problems(broken, base_url=BASE))

    # The sitemap drops the shows index.
    broken = dict(files)
    broken["sitemap.xml"] = broken["sitemap.xml"].replace(f"<loc>{BASE}/shows/</loc>", "")
    assert f"<loc>{BASE}/shows/</loc>" not in broken["sitemap.xml"]
    assert any("/shows/" in p for p in show_pages.index_problems(broken, base_url=BASE))


def test_the_build_log_counts_the_held_back_pages(tmp_path, capsys):
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(_doc()), encoding="utf-8")
    pins = _pins(PINNED, tmp_path)
    code = show_pages.main([str(snapshot), str(tmp_path / "out"), "--pinned", str(pins)])
    assert code == 0
    out = capsys.readouterr().out
    built = len(list((tmp_path / "out" / "shows").glob("*/index.html")))
    held = built - len(PINNED)
    assert held > 0
    assert (
        f"show_pages: {len(PINNED)} show pages in the sitemap, {held} held back with "
        "noindex,follow (DECISIONS 0028)"
    ) in out


# ---- the first widening batch (DECISIONS 0046) --------------------------------


def test_the_first_batch_adds_50_shows_none_of_them_pinned():
    # Every entry must widen the set: an id that is already pinned would be a
    # no-op that makes the batch look larger than it is.
    pins = show_pages.load_pinned(show_pages.DEFAULT_PINNED_PATH)
    assert pins is not None
    pinned_ids = {p.lezwatch_id for p in pins}
    assert len(show_pages.INDEX_EXTRA_IDS) == 50
    assert not show_pages.INDEX_EXTRA_IDS & pinned_ids
    assert show_pages.INDEX_MIN_LISTED is None  # the batch is a list, not a rule


def test_a_batch_show_is_indexed_when_built_and_ignored_when_not(tmp_path):
    # FROM (98062) is in the batch. Give a held-back fixture show its id: it is
    # then in the sitemap with no robots tag. Every other batch id has no page
    # in this data, so the sitemap gains exactly one show page.
    doc = _doc()
    pins = show_pages.load_pinned(_pins(PINNED, tmp_path))
    before = show_pages.render_site(doc, base_url=BASE, pinned=pins)
    held = next(s for s in doc["shows"] if s["slug"] == "show-012")
    assert _robots(_page(before, "show-012")) == ["noindex,follow"]
    held["lwtv_id"] = 98062
    after = show_pages.render_site(doc, base_url=BASE, pinned=pins)
    assert _robots(_page(after, "show-012")) == []
    assert set(_locs(after)) - set(_locs(before)) == {_url("show-012")}
    assert show_pages.index_problems(after, base_url=BASE) == []
