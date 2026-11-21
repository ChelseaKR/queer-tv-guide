"""The second widening batch (DECISIONS 0057), rolled back by 0067.

0057 opened 44 held-back show pages; 0067 (2026-11-21) holds them back again
under 0028's rollback rule, and keeps the list as a record. The tests below
check the rollback, and that a batch page would still be sound if the batch
were reopened (``reopened``). 0057 chose them as every
page still held back that, in Search Console's 28 days to 2026-11-08, Google
showed at least 5 times, or for a query it reported, or that earned a click.
Only the indexing changes: each page keeps its LezWatch.TV and TVmaze credit,
loads nothing from another host, and says "Unknown" where no death is
recorded. Every negative control asserts its sabotage changed the output
before it concludes anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe
from tests.test_show_pages_indexing import BASE, PINNED, _doc, _locs, _page, _robots, _url
from tests.test_show_pages_pinned import _pins

# A held-back fixture show, and a second-batch id to give it (Charmed (2018)).
HELD = "show-012"
BATCH_ID = 32399


def _render(doc: dict, tmp_path: Path) -> dict[str, str]:
    pins = show_pages.load_pinned(_pins(PINNED, tmp_path))
    return show_pages.render_site(doc, base_url=BASE, pinned=pins)


def _batched(tmp_path: Path) -> tuple[dict, dict[str, str], dict[str, str]]:
    doc = _doc()
    before = _render(doc, tmp_path)
    next(s for s in doc["shows"] if s["slug"] == HELD)["lwtv_id"] = BATCH_ID
    return doc, before, _render(doc, tmp_path)


def _credit_problems(doc: dict, page: htmlprobe.Page) -> list[str]:
    text = " ".join(page.outside)
    problems = []
    for a in doc["attribution"]:
        if a["text"] not in text:
            problems.append(f"{a['source']} credit text")
        for key in ("url", "licence_url", "terms_url"):
            if a[key] not in page.hrefs():
                problems.append(f"{a['source']} {key}")
    if "LezWatch.TV and TVmaze do not endorse Queer Frame." not in text:
        problems.append("endorsement line")
    return problems


def _load_problems(page: htmlprobe.Page) -> list[str]:
    problems = []
    if [s.get("type") for s in page.named("script")] != ["application/ld+json"]:
        problems.append("a script other than the JSON-LD block")
    if [a for t, a in page.tags if "src" in a or "srcset" in a]:
        problems.append("something loaded by src")
    if htmlprobe.foreign_links(page, BASE):
        problems.append("a foreign <link>")
    if any("analytics" in h or "google" in h for h in page.hrefs()):
        problems.append("an analytics link")
    return problems


# ---- the list ----------------------------------------------------------------


def test_the_second_batch_is_kept_on_record_and_left_out_of_the_indexed_set():
    pins = show_pages.load_pinned(show_pages.DEFAULT_PINNED_PATH)
    assert pins is not None
    pinned_ids = {p.lezwatch_id for p in pins}
    second = show_pages.INDEX_SECOND_BATCH
    assert len(second) == 44
    assert not second & pinned_ids
    assert not second & show_pages.INDEX_FIRST_BATCH
    # Rolled back (DECISIONS 0067): only the first batch widens the set.
    assert show_pages.INDEX_EXTRA_IDS == show_pages.INDEX_FIRST_BATCH
    assert not second & show_pages.INDEX_EXTRA_IDS
    assert len(show_pages.INDEX_EXTRA_IDS) == 50
    assert show_pages.INDEX_MIN_LISTED is None  # still a list, not a rule


def test_a_rolled_back_page_is_held_and_out_of_the_sitemap(tmp_path):
    _, before, after = _batched(tmp_path)
    assert _robots(_page(after, HELD)) == ["noindex,follow"]
    assert _locs(after) == _locs(before)
    assert show_pages.index_problems(after, base_url=BASE) == []


@pytest.fixture
def reopened(monkeypatch):
    """The second batch added back to the indexed set, as reopening would."""
    monkeypatch.setattr(
        show_pages, "INDEX_EXTRA_IDS", show_pages.INDEX_EXTRA_IDS | show_pages.INDEX_SECOND_BATCH
    )


# ---- a batch page --------------------------------------------------------------


def test_a_batch_page_is_indexed_with_the_snapshot_date(tmp_path, reopened):
    doc, before, after = _batched(tmp_path)
    assert _robots(_page(before, HELD)) == ["noindex,follow"]
    assert _robots(_page(after, HELD)) == []
    assert set(_locs(after)) - set(_locs(before)) == {_url(HELD)}
    entries = htmlprobe.sitemap(after["sitemap.xml"])
    lastmod = dict(zip(entries["loc"], entries["lastmod"], strict=True))
    assert lastmod[_url(HELD)] == doc["generated_at"][:10]
    assert show_pages.index_problems(after, base_url=BASE) == []


def test_a_batch_page_keeps_the_credit_loads_nothing_and_says_unknown(tmp_path, reopened):
    doc, before, after = _batched(tmp_path)
    page = _page(after, HELD)
    assert _credit_problems(doc, page) == []
    assert _load_problems(page) == []
    assert any(kind == "unknown" for kind, _ in page.statuses)  # the check has work
    assert htmlprobe.no_for_unknown(page) == []
    # Only the robots tag changes: the credit block is the held-back page's.
    held = _page(before, HELD)
    assert _credit_problems(doc, held) == []
    assert [t for t in page.outside if "LezWatch.TV" in t] == [
        t for t in held.outside if "LezWatch.TV" in t
    ]


# ---- negative controls ----------------------------------------------------------


def test_negative_control_the_rollback_is_what_holds_the_page(tmp_path, monkeypatch):
    _, before, after = _batched(tmp_path)
    assert _robots(_page(after, HELD)) == ["noindex,follow"]
    monkeypatch.setattr(
        show_pages, "INDEX_EXTRA_IDS", show_pages.INDEX_EXTRA_IDS | show_pages.INDEX_SECOND_BATCH
    )
    _, _, reopened_site = _batched(tmp_path)
    assert _robots(_page(reopened_site, HELD)) == []  # without the rollback it is open
    assert set(_locs(reopened_site)) - set(_locs(before)) == {_url(HELD)}


@pytest.mark.parametrize(
    ("old", "new", "check"),
    [
        ("LezWatch.TV", "LezWatch", "credit"),
        (
            "</head>",
            '<script src="https://www.googletagmanager.com/gtag/js"></script></head>',
            "load",
        ),
        (">Unknown.", ">0.", "unknown"),
    ],
)
def test_negative_control_each_check_catches_its_sabotage(tmp_path, reopened, old, new, check):
    doc, _, after = _batched(tmp_path)
    html = after[f"shows/{HELD}/index.html"]
    broken = html.replace(old, new)
    assert broken != html  # the sabotage applied
    page = htmlprobe.parse(broken)
    if check == "credit":
        assert _credit_problems(doc, page) != []
    elif check == "load":
        assert _load_problems(page) != []
    else:
        assert htmlprobe.no_for_unknown(page) != []
