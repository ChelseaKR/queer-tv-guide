"""The TVSeries structured data names the show's IMDb page and Wikidata item
in ``sameAs`` (DECISIONS 0064).

A title like "FROM" or "Ghosts" does not say which series a page is about.
``sameAs`` already named the show's LezWatch.TV and TVmaze pages; it now also
names IMDb, from the title id LezWatch.TV records, and the Wikidata item the
snapshot holds where two ids agreed on it (DECISIONS 0055). Nothing is
guessed from a title, nothing shows on the page, and the page still links to
and loads nothing from either site. Every negative control asserts that its
sabotage changed the input before it asserts the outcome.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BASE = "https://example.test/qf"


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _with_imdb(doc: dict) -> dict:
    return next(s for s in show_pages.select_shows(doc) if s["external_ids"]["imdb"])


def _series(doc: dict, show: dict) -> dict:
    page = htmlprobe.parse(show_pages.render_show(doc, show, base_url=BASE))
    return htmlprobe.ld_node(page, "TVSeries")


@pytest.mark.parametrize(
    ("value", "url"),
    [
        ("tt9813792", "https://www.imdb.com/title/tt9813792/"),
        ("tt0123456", "https://www.imdb.com/title/tt0123456/"),
        ("tt12345678", "https://www.imdb.com/title/tt12345678/"),
        (None, None),
        ("", None),
        ("nm0000123", None),  # a person, not a title
        ("tt123", None),  # too short to be a title id
        ("tt9813792/episodes", None),
        ("https://www.imdb.com/title/tt9813792/", None),
        ("tt9813792 ", None),
        (9813792, None),
    ],
)
def test_the_imdb_address_is_built_only_from_a_title_id(value, url):
    assert show_pages.imdb_url({"external_ids": {"imdb": value}}) == url


def test_a_show_with_no_external_ids_has_no_imdb_address():
    assert show_pages.imdb_url({}) is None
    assert show_pages.imdb_url({"external_ids": None}) is None


@pytest.mark.parametrize(
    ("wikidata", "url"),
    [
        ({"item": "Q38497"}, "https://www.wikidata.org/wiki/Q38497"),
        (None, None),
        ({}, None),
        ({"item": "Q0"}, None),
        ({"item": "P345"}, None),
        ({"item": "Q38497/x"}, None),
        ({"item": 38497}, None),
    ],
)
def test_the_wikidata_address_is_built_only_from_an_item_id(wikidata, url):
    show = {} if wikidata is None else {"wikidata": wikidata}
    assert show_pages.wikidata_url(show) == url


def test_same_as_names_lezwatch_tvmaze_imdb_and_wikidata_in_that_order(doc):
    show = copy.deepcopy(_with_imdb(doc))
    show["wikidata"] = {"item": "Q38497", "matched_by": ["lezwatch", "imdb"], "read_on": "x"}
    expected = [
        u
        for u in (
            show["source_url"],
            show["schedule"]["tvmaze_url"],
            f"https://www.imdb.com/title/{show['external_ids']['imdb']}/",
            "https://www.wikidata.org/wiki/Q38497",
        )
        if u
    ]
    assert _series(doc, show)["sameAs"] == expected
    assert expected[-2:] == [
        f"https://www.imdb.com/title/{show['external_ids']['imdb']}/",
        "https://www.wikidata.org/wiki/Q38497",
    ]


def test_a_show_without_either_id_keeps_the_old_same_as(doc):
    show = copy.deepcopy(_with_imdb(doc))
    before = _series(doc, show)["sameAs"]
    assert any("imdb.com" in u for u in before)
    show["external_ids"]["imdb"] = None  # the sabotage: no id on record
    show.pop("wikidata", None)
    after = _series(doc, show)["sameAs"]
    assert after == [u for u in (show["source_url"], show["schedule"]["tvmaze_url"]) if u]
    assert after != before


def test_the_ids_are_in_the_structured_data_only_never_a_link_or_a_request(doc):
    """The page has no visible IMDb or Wikidata link and loads nothing."""
    show = copy.deepcopy(_with_imdb(doc))
    show["wikidata"] = {"item": "Q38497", "matched_by": ["lezwatch", "imdb"], "read_on": "x"}
    raw = show_pages.render_show(doc, show, base_url=BASE)
    page = htmlprobe.parse(raw)
    assert "imdb.com" in "".join(page.ld_json) and "wikidata.org" in "".join(page.ld_json)
    for href in page.hrefs():
        assert "imdb.com" not in href and "wikidata.org" not in href, href
    visible = " ".join(page.outside + page.inside)
    assert "imdb" not in visible.lower() and "wikidata.org" not in visible.lower()
    assert htmlprobe.foreign_links(page, BASE) == []
    assert [a for a in page.named("script") if a.get("src")] == []


def test_the_structured_data_still_says_nothing_about_deaths(doc):
    for show in show_pages.select_shows(doc):
        series = _series(doc, show)
        assert set(series) <= {
            "@type",
            "name",
            "url",
            "sameAs",
            "startDate",
            "endDate",
            "numberOfSeasons",
            "genre",
            "countryOfOrigin",
            "character",
        }, show["slug"]
