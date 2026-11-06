"""The next-episode row and the season-premiere opening (DECISIONS 0037).

The date is TVmaze's, shown as a dated fact; the row is left out, never
filled with a placeholder, when TVmaze lists nothing usable. No episode name
is ever printed. Every negative control asserts that its sabotage changed
the input before it asserts the outcome.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BASE = "https://example.test/qf"
LABEL = show_pages.NEXT_EPISODE_LABEL
# The fixture's snapshot day; harbor-lights' next episode is 2026-09-20.
TODAY = dt.date(2026, 9, 13)


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _show(doc: dict, slug: str) -> dict:
    return next(s for s in doc["shows"] if s["slug"] == slug)


def _page(doc: dict, tmp_path: Path, slug: str) -> htmlprobe.Page:
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    path = tmp_path / "shows" / slug / "index.html"
    return htmlprobe.parse(path.read_text(encoding="utf-8"))


def _opening(doc: dict, slug: str) -> str:
    show = _show(doc, slug)
    return show_pages.opening(show, show_pages._characters(doc, show))


def test_a_next_episode_is_a_dated_row_with_season_and_episode(doc, tmp_path):
    page = _page(doc, tmp_path, "harbor-lights")
    assert page.facts[LABEL] == "Season 3, episode 4, Sunday, September 20, 2026"
    # The facts note already says where "per TVmaze" rows come from.
    assert any("Facts marked “per TVmaze”" in t for t in page.outside)


def test_a_season_premiere_is_named_in_the_row_and_the_opening(doc, tmp_path):
    show = _show(doc, "harbor-lights")
    before = _opening(doc, "harbor-lights")
    show["schedule"]["next_episode"]["season"] = 4
    show["schedule"]["next_episode"]["number"] = 1
    assert show_pages.next_episode_fact(show, TODAY) == (
        LABEL,
        "Season 4 premiere, Sunday, September 20, 2026",
    )
    after = _opening(doc, "harbor-lights")
    assert after != before
    assert after.endswith(", and the first episode of season 4 is listed for September 20, 2026.")
    page = _page(doc, tmp_path, "harbor-lights")
    assert page.facts[LABEL] == "Season 4 premiere, Sunday, September 20, 2026"


def test_a_premiere_with_no_earlier_episode_says_so(doc):
    show = _show(doc, "harbor-lights")
    show["schedule"]["previous_episode"] = None
    show["schedule"]["next_episode"]["season"] = 1
    show["schedule"]["next_episode"]["number"] = 1
    assert _opening(doc, "harbor-lights").endswith(
        "TVmaze lists the first episode of season 1 for September 20, 2026."
    )


@pytest.mark.parametrize("genre", sorted(show_pages.SOAP_GENRES))
def test_a_soap_gets_only_the_date_and_never_a_premiere(doc, genre):
    show = _show(doc, "harbor-lights")
    show["schedule"]["next_episode"]["number"] = 1
    show["genres"] = [{"slug": genre, "name": "Soap"}]
    assert show_pages.next_episode_fact(show, TODAY) == (LABEL, "Sunday, September 20, 2026")
    assert "first episode of season" not in _opening(doc, "harbor-lights")


@pytest.mark.parametrize(("season", "number"), [(2026, 1), (2026, 215), (None, 4), (3, None)])
def test_numbers_that_are_a_year_or_missing_leave_only_the_date(doc, season, number):
    show = _show(doc, "harbor-lights")
    show["schedule"]["next_episode"]["season"] = season
    show["schedule"]["next_episode"]["number"] = number
    assert show_pages.next_episode_fact(show, TODAY) == (LABEL, "Sunday, September 20, 2026")


def test_no_row_when_there_is_nothing_to_date(doc, tmp_path):
    """Absence is not a value: no "Not recorded", "None" or "Unknown" row."""
    show = _show(doc, "harbor-lights")
    assert show_pages.next_episode_fact(show, TODAY) is not None  # the control
    for broken in ("past", "unreadable", "missing", "unscheduled"):
        doc2 = json.loads(json.dumps(doc))
        s = _show(doc2, "harbor-lights")
        if broken == "past":
            s["schedule"]["next_episode"]["airdate"] = "2026-09-12"
        elif broken == "unreadable":
            s["schedule"]["next_episode"]["airdate"] = "soon"
        elif broken == "missing":
            s["schedule"]["next_episode"] = None
        else:
            s["schedule"]["schedule_known"] = False
        assert show_pages.next_episode_fact(s, TODAY) is None, broken
    page = _page(doc, tmp_path, "the-cartographers")  # TVmaze lists no next episode
    assert LABEL not in page.facts
    assert len(page.facts) == 9


def test_the_episode_name_is_never_printed(doc, tmp_path):
    show = _show(doc, "harbor-lights")
    name = show["schedule"]["next_episode"]["name"]
    assert name  # the fixture has a name to leak
    page = _page(doc, tmp_path, "harbor-lights")
    assert LABEL in page.facts
    visible = [*page.outside, *page.inside, page.title, page.description, *page.ld_json]
    assert not any(name in t for t in visible)


def test_the_row_ignores_every_death_record(doc, tmp_path):
    page = _page(doc, tmp_path, "harbor-lights")
    before = json.dumps(doc["characters"])
    for c in doc["characters"]:
        dead = c["death"]["died"] is True
        c["death"] = (
            {"died": None, "death_known": False, "dates": [], "years": []}
            if dead
            else {
                "died": True,
                "death_known": True,
                "dates": [{"date": "2026-01-01", "year": 2026, "raw": "20260101"}],
                "years": [2026],
            }
        )
    assert json.dumps(doc["characters"]) != before  # the swap applied
    again = _page(doc, tmp_path / "again", "harbor-lights")
    assert again.facts[LABEL] == page.facts[LABEL]
    assert _opening(doc, "harbor-lights") in " ".join(again.outside)
