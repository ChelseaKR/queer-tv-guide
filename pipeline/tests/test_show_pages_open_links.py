"""The "More shows" links lead to pages that are open to search (DECISIONS 0064).

A show page's two "More shows" links used to be the shows before and after it
in the published order, whether or not those pages were held back with
``noindex``. They are now the nearest show before and the nearest after whose
page is in the sitemap. So every open page is linked from two other open
pages, and a held-back page links on to two open ones. No sentence on any
page changes: the list still holds show titles only. Every negative control
asserts that its sabotage changed the input before it asserts the outcome.
"""

from __future__ import annotations

from pathlib import Path

from qtv_pipeline import show_pages
from tests import htmlprobe
from tests.test_show_pages_pinned import _pins
from tests.test_show_pages_rule import _qualified

BASE = "https://example.test"
PINNED = [1005, 1003, 1001, 1007]  # the hand-picked list, in its own order
RICH = {1000 + i: 5 + (i % 3) for i in range(20)}  # 20 of 60 shows meet the 0025 rule


def _site(tmp_path: Path) -> tuple[dict[str, str], list[dict], set[str]]:
    doc = _qualified(60, RICH)
    pins = show_pages.load_pinned(_pins(PINNED, tmp_path))
    files = show_pages.render_site(doc, base_url=BASE, pinned=pins)
    shows = show_pages.select_shows(doc, show_pages.DEFAULT_LIMIT, pins)
    open_ids = show_pages.indexed_show_ids(shows, pins, show_pages._listed_characters(doc))
    return files, shows, open_ids


def _url(show: dict) -> str:
    return f"{BASE}/shows/{show['slug']}/"


def _more(files: dict[str, str], show: dict) -> list[str]:
    """The show-page addresses in one page's "More shows" list, in order."""
    raw = files[f"shows/{show['slug']}/index.html"]
    start = raw.index('<ul class="more">')
    block = raw[start : raw.index("</ul>", start) + len("</ul>")]
    hrefs = htmlprobe.parse(f"<body>{block}</body>").hrefs()
    return [h for h in hrefs if h != f"{BASE}/shows/"]


def _shows(n: int) -> list[dict]:
    return [{"id": f"s{i}", "slug": f"s{i}", "title": f"S{i}"} for i in range(n)]


# ---- the function ------------------------------------------------------------


def test_the_nearest_open_shows_are_picked_on_each_side_and_wrap():
    shows = _shows(8)
    open_ids = {"s1", "s4", "s6"}
    # A held page between two open ones links to both.
    assert show_pages.neighbors(shows, 2, open_ids) == [shows[1], shows[4]]
    # An open page skips itself and the held pages beside it.
    assert show_pages.neighbors(shows, 4, open_ids) == [shows[1], shows[6]]
    # The ends wrap.
    assert show_pages.neighbors(shows, 0, open_ids) == [shows[6], shows[1]]
    assert show_pages.neighbors(shows, 7, open_ids) == [shows[6], shows[1]]
    assert show_pages.neighbors(shows, 6, open_ids) == [shows[4], shows[1]]


def test_without_open_ids_the_plain_neighbors_are_unchanged():
    shows = _shows(8)
    assert show_pages.neighbors(shows, 2) == [shows[1], shows[3]]
    assert show_pages.neighbors(shows, 0) == [shows[7], shows[1]]


def test_fewer_than_three_open_pages_falls_back_to_the_plain_neighbors():
    shows = _shows(6)
    assert show_pages.OPEN_RING_MIN == 3
    for open_ids in (set(), {"s2"}, {"s2", "s4"}):
        for i in range(len(shows)):
            assert show_pages.neighbors(shows, i, open_ids) == show_pages.neighbors(shows, i)
    # Negative control: a third open page does change the answer.
    assert show_pages.neighbors(shows, 0, {"s2", "s4", "s5"}) != show_pages.neighbors(shows, 0)


def test_a_page_never_links_to_itself_and_never_to_one_show_twice():
    shows = _shows(9)
    for open_ids in ({"s0", "s1", "s2"}, {"s0", "s4", "s8"}, {s["id"] for s in shows}):
        for i, me in enumerate(shows):
            got = show_pages.neighbors(shows, i, open_ids)
            assert len(got) == 2 and got[0] is not got[1], (open_ids, i)
            assert me not in got, (open_ids, i)
            assert all(s["id"] in open_ids for s in got), (open_ids, i)


def test_when_every_page_is_open_the_links_are_the_plain_neighbors():
    shows = _shows(7)
    everyone = {s["id"] for s in shows}
    for i in range(len(shows)):
        assert show_pages.neighbors(shows, i, everyone) == show_pages.neighbors(shows, i)


# ---- the built site ----------------------------------------------------------


def test_every_more_shows_link_leads_to_a_page_in_the_sitemap(tmp_path):
    files, shows, open_ids = _site(tmp_path)
    in_sitemap = set(htmlprobe.sitemap(files["sitemap.xml"])["loc"])
    held = [s for s in shows if s["id"] not in open_ids]
    assert held and len(open_ids) >= show_pages.OPEN_RING_MIN  # both kinds are in the build
    for show in shows:
        links = _more(files, show)
        assert len(links) == 2 and len(set(links)) == 2, show["slug"]
        assert _url(show) not in links
        for link in links:
            assert link in in_sitemap, (show["slug"], link)


def test_every_open_page_is_linked_from_two_other_open_pages(tmp_path):
    files, shows, open_ids = _site(tmp_path)
    opened = [s for s in shows if s["id"] in open_ids]
    inbound = {_url(s): 0 for s in opened}
    for show in opened:
        for link in _more(files, show):
            inbound[link] += 1
    assert all(n == 2 for n in inbound.values()), inbound


def test_negative_control_the_plain_neighbors_would_link_to_held_back_pages(tmp_path):
    """The old rule, on the same build: at least one open page's neighbor is a
    held-back page, which is what this change removes."""
    _, shows, open_ids = _site(tmp_path)
    plain = [
        other["id"] in open_ids
        for i, show in enumerate(shows)
        if show["id"] in open_ids
        for other in show_pages.neighbors(shows, i)
    ]
    assert not all(plain)
    ring = [
        other["id"] in open_ids
        for i, show in enumerate(shows)
        if show["id"] in open_ids
        for other in show_pages.neighbors(shows, i, open_ids)
    ]
    assert all(ring)


def test_similar_shows_never_repeat_a_more_shows_link(tmp_path):
    files, shows, _ = _site(tmp_path)
    for show in shows:
        raw = files[f"shows/{show['slug']}/index.html"]
        if '<ul class="similar">' not in raw:
            continue
        start = raw.index('<ul class="similar">')
        block = raw[start : raw.index("</ul>", start) + len("</ul>")]
        similar = htmlprobe.parse(f"<body>{block}</body>").hrefs()
        assert not set(similar) & set(_more(files, show)), show["slug"]


def test_the_more_shows_list_still_holds_titles_only(tmp_path):
    files, shows, _ = _site(tmp_path)
    titles = {s["title"] for s in shows}
    for show in shows[:10]:
        raw = files[f"shows/{show['slug']}/index.html"]
        start = raw.index('<ul class="more">')
        block = raw[start : raw.index("</ul>", start) + len("</ul>")]
        texts = [t for t in htmlprobe.parse(f"<body>{block}</body>").outside if t.strip()]
        assert set(texts[:-1]) <= titles, texts
        assert texts[-1] == f"All {len(shows)} shows"
