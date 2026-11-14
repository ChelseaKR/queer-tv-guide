"""The second widening batch (DECISIONS 0057).

44 held-back show pages join the sitemap and lose ``noindex,follow``: every
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


def test_the_second_batch_adds_44_new_shows():
    pins = show_pages.load_pinned(show_pages.DEFAULT_PINNED_PATH)
    assert pins is not None
    pinned_ids = {p.lezwatch_id for p in pins}
    second = show_pages.INDEX_SECOND_BATCH
    assert len(second) == 44
    # Every entry must widen the set: an id already pinned or in the first
    # batch would be a no-op that makes the batch look larger than it is.
    assert not second & pinned_ids
    assert not second & show_pages.INDEX_FIRST_BATCH
    # The small-cast batch (DECISIONS 0060) is the only other widening.
    widened = show_pages.INDEX_EXTRA_IDS - show_pages.SMALL_CAST_BATCH
    assert show_pages.INDEX_FIRST_BATCH | second == widened
    assert len(widened) == 94
    assert show_pages.INDEX_MIN_LISTED is None  # still a list, not a rule


# ---- a batch page --------------------------------------------------------------


def test_a_batch_page_is_indexed_with_the_snapshot_date(tmp_path):
    doc, before, after = _batched(tmp_path)
    assert _robots(_page(before, HELD)) == ["noindex,follow"]
    assert _robots(_page(after, HELD)) == []
    assert set(_locs(after)) - set(_locs(before)) == {_url(HELD)}
    entries = htmlprobe.sitemap(after["sitemap.xml"])
    lastmod = dict(zip(entries["loc"], entries["lastmod"], strict=True))
    assert lastmod[_url(HELD)] == doc["generated_at"][:10]
    assert show_pages.index_problems(after, base_url=BASE) == []


def test_a_batch_page_keeps_the_credit_loads_nothing_and_says_unknown(tmp_path):
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


def test_negative_control_an_id_left_out_of_the_batch_stays_held(tmp_path, monkeypatch):
    monkeypatch.setattr(show_pages, "INDEX_EXTRA_IDS", show_pages.INDEX_EXTRA_IDS - {BATCH_ID})
    _, before, after = _batched(tmp_path)
    assert _robots(_page(after, HELD)) == ["noindex,follow"]
    assert _locs(after) == _locs(before)


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
def test_negative_control_each_check_catches_its_sabotage(tmp_path, old, new, check):
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
