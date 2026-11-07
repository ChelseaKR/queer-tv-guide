"""A running show's season count (DECISIONS 0048, extending 0031).

When LezWatch marks a show on air, TVmaze does not list it as Ended, and
TVmaze's latest season is higher than LezWatch's count, the page shows
TVmaze's as "N so far, per TVmaze", but only when TVmaze's premiere year is
within a year of LezWatch's start year. Every case is built from the fixture
snapshot; no test reaches the network. The four real cases are the values the
2026-11-07 fact-check found on the live pages
(_agent-tools/growth/qf-index50-factcheck-2026-11-07.md).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BASE = "https://example.test/qf"
SLUG = "harbor-lights"  # running in the fixture, on air per LezWatch

# (name, LezWatch count, LezWatch start year, TVmaze premiere, TVmaze latest season)
CONFIRMED = [
    ("For All Mankind", 1, 2019, "2019-11-01", 5),
    ("The Loud House", 3, 2016, "2016-05-02", 10),
    ("The Pitt", 1, 2025, "2025-01-09", 2),
    ("Father Brown", 6, 2013, "2013-01-14", 13),
]


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _show(doc: dict) -> dict:
    return next(s for s in doc["shows"] if s["slug"] == SLUG)


def _set(
    show: dict,
    *,
    recorded: int | None,
    start: int | None,
    premiered: str | None,
    last: int | None,
    status: str = "Running",
    on_air: str = "yes",
) -> dict:
    show["seasons"] = recorded
    show["years"]["start"] = start
    show["years"]["end"] = None if on_air == "yes" else show["years"]["end"]
    show["years"]["on_air"] = on_air
    show["schedule"]["status"] = status
    show["schedule"]["premiered"] = premiered
    show["schedule"]["previous_episode"]["season"] = last
    return show


def _page(doc: dict, tmp_path: Path) -> htmlprobe.Page:
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    path = tmp_path / "shows" / SLUG / "index.html"
    return htmlprobe.parse(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(("name", "recorded", "start", "premiered", "last"), CONFIRMED)
def test_a_running_show_shows_tvmazes_higher_count(doc, name, recorded, start, premiered, last):
    show = _set(_show(doc), recorded=recorded, start=start, premiered=premiered, last=last)
    assert show_pages.seasons_fact(show) == ("Seasons, per TVmaze", f"{last} so far", last), name


def test_the_page_and_its_structured_data_carry_the_running_count(doc, tmp_path):
    _set(_show(doc), recorded=1, start=2019, premiered="2019-11-01", last=5)
    page = _page(doc, tmp_path)
    assert page.facts["Seasons, per TVmaze"] == "5 so far"
    assert "Seasons" not in page.facts
    assert htmlprobe.ld_node(page, "TVSeries")["numberOfSeasons"] == 5


def test_negative_control_without_the_rule_the_page_shows_lezwatchs_count(
    doc, tmp_path, monkeypatch
):
    """Sabotage: switch the 0048 rule off. The page must go back to LezWatch's
    "1", which proves the tests above see the rule and not something else."""
    _set(_show(doc), recorded=1, start=2019, premiered="2019-11-01", last=5)
    with_rule = _page(doc, tmp_path / "with").facts
    monkeypatch.setattr(show_pages, "_running_count_lags", lambda *_: False)
    without = _page(doc, tmp_path / "without").facts
    assert without != with_rule  # the sabotage changed the page
    assert without["Seasons"] == "1" and "Seasons, per TVmaze" not in without


@pytest.mark.parametrize(
    ("recorded", "last", "expected"),
    [
        (11, 9, ("Seasons, per TVmaze", "9", 9)),  # 0031: TVmaze wins when they differ
        (6, 8, ("Seasons, per TVmaze", "8", 8)),
        (7, 7, ("Seasons", "7", 7)),
    ],
)
def test_an_ended_show_is_unchanged(doc, recorded, last, expected):
    show = _set(
        _show(doc), recorded=recorded, start=2016, premiered="2016-10-01", last=last, status="Ended"
    )
    assert show_pages.seasons_fact(show) == expected
    # Same answer with the 0048 rule switched off: nothing about ended shows moved.
    assert not show_pages._running_count_lags(show, recorded, last)


def test_a_show_lezwatch_marks_ended_keeps_lezwatchs_count(doc):
    show = _set(_show(doc), recorded=3, start=2016, premiered="2016-10-01", last=4, on_air="no")
    show["years"]["end"] = 2019
    assert show_pages.seasons_fact(show) == ("Seasons", "3", 3)


def test_a_running_show_keeps_a_higher_lezwatch_count(doc):
    show = _set(_show(doc), recorded=4, start=2021, premiered="2021-03-01", last=3)
    assert show_pages.seasons_fact(show) == ("Seasons", "4", 4)


@pytest.mark.parametrize(
    ("start", "premiered"),
    [
        (2019, "2008-09-15"),  # a same-named earlier show: years disagree
        (2010, "2025-01-09"),  # a same-named reboot
        (2019, None),  # TVmaze gives no premiere
        (None, "2019-11-01"),  # LezWatch gives no start year
        (2019, "unknown"),  # not a date
    ],
)
def test_an_ambiguous_match_falls_back_to_lezwatch(doc, start, premiered):
    show = _set(_show(doc), recorded=1, start=start, premiered=premiered, last=5)
    assert show_pages.seasons_fact(show) == ("Seasons", "1", 1)


def test_a_premiere_one_year_off_still_matches(doc):
    # NCIS: LezWatch starts it in 2004, TVmaze premiered 2003-09-23.
    show = _set(_show(doc), recorded=15, start=2004, premiered="2003-09-23", last=23)
    assert show_pages.seasons_fact(show) == ("Seasons, per TVmaze", "23 so far", 23)


def test_no_tvmaze_match_keeps_lezwatchs_count(doc):
    show = _set(_show(doc), recorded=1, start=2019, premiered="2019-11-01", last=5)
    show["schedule"]["schedule_known"] = False
    assert show_pages.seasons_fact(show) == ("Seasons", "1", 1)


@pytest.mark.parametrize("last", [2026, 0, None, True])
def test_a_tvmaze_season_that_is_a_year_or_not_a_count_never_raises(doc, last):
    show = _set(_show(doc), recorded=1, start=2019, premiered="2019-11-01", last=last)
    assert show_pages.seasons_fact(show) == ("Seasons", "1", 1)


def test_unknown_stays_not_recorded(doc):
    show = _set(_show(doc), recorded=None, start=2019, premiered="2019-11-01", last=None)
    assert show_pages.seasons_fact(show) == ("Seasons", "Not recorded", None)
