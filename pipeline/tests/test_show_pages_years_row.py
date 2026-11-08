"""The Years row (DECISIONS 0049, proposed).

TVmaze's premiere year replaces LezWatch.TV's start year only when the TVmaze
join is by id, no character is placed in the show before TVmaze's premiere
year, and the gap is one year (or 2 to 10 years earlier when LezWatch's own
character records already start before its start year). A show TVmaze lists
as Ended never says "to present": it shows TVmaze's end year when TVmaze has
one, else "ended" with no year. Every case is built from the fixture
snapshot; no test reaches the network. The three real cases are the values
the 2026-11-07 fact-check found on the live pages
(_agent-tools/growth/qf-index50-factcheck-2026-11-07.md).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BASE = "https://example.test/qf"
SLUG = "harbor-lights"  # running in the fixture, on air per LezWatch, joined by id
SHOW_ID = "lwtv:show:101"


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _show(doc: dict) -> dict:
    return next(s for s in doc["shows"] if s["slug"] == SLUG)


def _set(
    doc: dict,
    *,
    start: int | None,
    end: int | None = None,
    on_air: str = "yes",
    premiered: str | None,
    status: str = "Running",
    ended: str | None = None,
    character_years: tuple[int, ...] | None = None,
    method: str = "lwtv_tvmaze_id",
) -> dict:
    """Harbor Lights with the given LezWatch years, TVmaze fields and, when
    given, the years LezWatch records for its two characters."""
    show = _show(doc)
    show["years"].update(start=start, end=end, on_air=on_air)
    sched = show["schedule"]
    sched.update(premiered=premiered, status=status, ended=ended)
    sched["join"]["method"] = method
    if character_years is not None:
        for c in doc["characters"]:
            for link in c["shows"]:
                if link["show_id"] == SHOW_ID:
                    link["years"] = [str(y) for y in character_years]
    return show


def _row(doc: dict) -> tuple[str, str]:
    show = _show(doc)
    return show_pages.years_fact(show, show_pages.first_character_years(doc).get(show["id"]))


def _opening(doc: dict) -> str:
    show = _show(doc)
    return show_pages.opening(show, show_pages._characters(doc, show))


def _page(doc: dict, tmp_path: Path) -> htmlprobe.Page:
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    path = tmp_path / "shows" / SLUG / "index.html"
    return htmlprobe.parse(path.read_text(encoding="utf-8"))


def _index_years(tmp_path: Path) -> str:
    text = (tmp_path / "shows" / "index.html").read_text(encoding="utf-8")
    found = re.findall(rf'href="{SLUG}/">[^<]*</a> \(([^)]*)\)', text)
    assert found, "the index lists the show"
    assert len(set(found)) == 1
    return found[0]


def _years_rows(page: htmlprobe.Page) -> dict[str, str]:
    rows = {k: v for k, v in page.facts.items() if k.startswith("Years")}
    assert len(rows) == 1  # one Years row, under one label
    return rows


# --- the three confirmed errors ------------------------------------------


def _chicago_med(doc: dict) -> dict:
    # LezWatch: 2020 to present. TVmaze 2246 premiered 2015-11-17 (Wikipedia
    # agrees). LezWatch's own Danny dies in 2016, so its characters start in 2016.
    return _set(
        doc,
        start=2020,
        premiered="2015-11-17",
        character_years=(2016, 2017, 2018, 2019),
    )


def _nine_one_one(doc: dict) -> dict:
    # LezWatch: 2017 to present. TVmaze 28152 premiered 2018-01-03.
    return _set(doc, start=2017, premiered="2018-01-03", character_years=(2018, 2019, 2026))


def _all_american(doc: dict) -> dict:
    # LezWatch: 2018 to present. TVmaze 34653: Ended, 2018-10-10 to 2026-09-28.
    return _set(
        doc,
        start=2018,
        premiered="2018-10-10",
        status="Ended",
        ended="2026-09-28",
        character_years=(2018, 2019, 2020),
    )


def test_chicago_med_starts_in_2015(doc, tmp_path):
    _chicago_med(doc)
    assert _row(doc) == ("Years, per TVmaze", "2015 to present")
    page = _page(doc, tmp_path)
    assert _years_rows(page) == {"Years, per TVmaze": "2015 to present"}
    assert "2015 to present" in _opening(doc)  # the opening sentence
    assert any(_opening(doc) in t for t in page.outside)  # ...is the page's
    assert "2020" not in _opening(doc)
    assert htmlprobe.ld_node(page, "TVSeries")["startDate"] == "2015"
    assert _index_years(tmp_path) == "2015 to present"


def test_nine_one_one_starts_in_2018(doc, tmp_path):
    _nine_one_one(doc)
    assert _row(doc) == ("Years, per TVmaze", "2018 to present")
    page = _page(doc, tmp_path)
    assert "2018 to present" in _opening(doc)
    assert htmlprobe.ld_node(page, "TVSeries")["startDate"] == "2018"
    assert _index_years(tmp_path) == "2018 to present"


def test_all_american_ended_in_2026(doc, tmp_path):
    _all_american(doc)
    assert _row(doc) == ("Years, per TVmaze", "2018 to 2026")
    page = _page(doc, tmp_path)
    assert _years_rows(page) == {"Years, per TVmaze": "2018 to 2026"}
    assert page.facts["Run status, per TVmaze"] == "Ended"
    assert "2018 to 2026" in _opening(doc)
    assert not any("present" in t for t in [*page.facts.values(), _opening(doc)])
    series = htmlprobe.ld_node(page, "TVSeries")
    assert (series["startDate"], series["endDate"]) == ("2018", "2026")
    assert _index_years(tmp_path) == "2018 to 2026"


# --- negative controls: the tests see the rule, not something else --------


def test_negative_control_without_the_start_rule_chicago_med_is_2020(doc, tmp_path, monkeypatch):
    _chicago_med(doc)
    with_rule = _page(doc, tmp_path / "with")
    monkeypatch.setattr(show_pages, "_tvmaze_start", lambda *_: None)
    without = _page(doc, tmp_path / "without")
    assert without.facts != with_rule.facts  # the sabotage changed the page
    assert _years_rows(without) == {"Years": "2020 to present"}
    assert htmlprobe.ld_node(without, "TVSeries")["startDate"] == "2020"


def test_negative_control_without_the_rule_all_american_says_present(doc, tmp_path, monkeypatch):
    _all_american(doc)
    with_rule = _page(doc, tmp_path / "with")
    monkeypatch.setattr(
        show_pages, "shown_years", lambda show, earliest=None: (show["years"], False)
    )
    without = _page(doc, tmp_path / "without")
    assert without.facts != with_rule.facts
    assert _years_rows(without) == {"Years": "2018 to present"}
    assert "2018 to present" in _opening(doc)
    assert _index_years(tmp_path / "without") == "2018 to present"


def test_negative_control_the_character_check_is_what_holds_a_case_back(doc, monkeypatch):
    """Servir y proteger's shape (LezWatch 2017, TVmaze 2018, a character in
    2017): held back only by the character check, so with the check disabled
    TVmaze's year would win."""
    _set(doc, start=2017, end=2023, on_air="no", premiered="2018-05-09", character_years=(2017,))
    assert _row(doc) == ("Years", "2017 to 2023")
    show = _show(doc)
    assert show_pages._tvmaze_start(show, None) == 2018


# --- fallbacks: LezWatch's years stay ------------------------------------


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(
            lambda s: s["schedule"]["join"].update(method="none", matched=False), id="no-match"
        ),
        pytest.param(
            lambda s: s["schedule"]["join"].update(method="title_search"), id="not-an-id-join"
        ),
        # A TVmaze id two LezWatch shows share: the snapshot marks the
        # schedule unknown (coverage.tvmaze.shared_tvmaze_ids).
        pytest.param(
            lambda s: s["schedule"].update(schedule_known=False), id="ambiguous-shared-id"
        ),
        pytest.param(lambda s: s["schedule"].update(premiered=None), id="no-premiere-date"),
        pytest.param(
            lambda s: s["schedule"].update(premiered="not a date"), id="bad-premiere-date"
        ),
    ],
)
def test_no_trusted_tvmaze_year_keeps_lezwatchs(doc, change):
    show = _chicago_med(doc)
    change(show)
    assert _row(doc) == ("Years", "2020 to present")


def test_a_missing_start_year_is_not_filled(doc, tmp_path):
    _set(doc, start=None, premiered="2015-11-17", character_years=(2016,))
    assert _row(doc) == ("Years", "Not recorded")
    assert "startDate" not in htmlprobe.ld_node(_page(doc, tmp_path), "TVSeries")


KEPT, TVMAZE = "Years", "Years, per TVmaze"


@pytest.mark.parametrize(
    ("start", "end", "on_air", "premiered", "character_years", "expected"),
    [
        # Amar es para siempre: TVmaze's 2005 is the predecessor show; LezWatch's
        # characters start in its own start year, so nothing corroborates.
        (2013, 2024, "no", "2005-09-27", (2013, 2024), (KEPT, "2013 to 2024")),
        # Two years earlier with no character before LezWatch's start year.
        (2015, 2017, "no", "2013-03-04", (2015, 2016), (KEPT, "2015 to 2017")),
        # Two years earlier, corroborated by a character in 2013.
        (2015, 2017, "no", "2013-03-04", (2013, 2016), (TVMAZE, "2013 to 2017")),
        # Home and Away's shape: 10 years earlier, corroborated.
        (1998, None, "yes", "1988-01-17", (1994, 2021), (TVMAZE, "1988 to present")),
        # Corroborated, but more than 10 years earlier.
        (2000, None, "yes", "1985-01-01", (1990, 2000), (KEPT, "2000 to present")),
        # TVmaze premieres after a character LezWatch places in the show.
        (2020, None, "yes", "2015-11-17", (2014, 2016), (KEPT, "2020 to present")),
        # TVmaze later by more than a year.
        (2012, 2023, "no", "2022-08-19", (2015,), (KEPT, "2012 to 2023")),
        # TVmaze later than LezWatch's own end year.
        (2021, 2021, "no", "2022-02-06", (2021,), (KEPT, "2021")),
        # A one-year gap either way with no character years at all still applies.
        (2017, None, "yes", "2018-01-03", (), (TVMAZE, "2018 to present")),
        (2004, None, "yes", "2003-09-23", (), (TVMAZE, "2003 to present")),
    ],
)
def test_start_year_cases(doc, start, end, on_air, premiered, character_years, expected):
    _set(
        doc,
        start=start,
        end=end,
        on_air=on_air,
        premiered=premiered,
        character_years=character_years,
    )
    assert _row(doc) == expected


def test_ended_without_an_end_date_says_ended_without_a_year(doc, tmp_path):
    _set(
        doc, start=2018, premiered="2018-10-10", status="Ended", ended=None, character_years=(2018,)
    )
    assert _row(doc) == ("Years, per TVmaze", "2018, ended (end year not recorded)")
    page = _page(doc, tmp_path)
    assert not any("present" in t for t in [*page.facts.values(), _opening(doc)])
    assert "endDate" not in htmlprobe.ld_node(page, "TVSeries")


def test_a_tvmaze_end_before_the_start_is_not_used(doc):
    _set(doc, start=2018, premiered="2018-10-10", status="Ended", ended="2017-01-01")
    assert _row(doc) == ("Years, per TVmaze", "2018, ended (end year not recorded)")


def test_lezwatch_marked_ended_without_a_year_says_ended(doc):
    _set(doc, start=2016, on_air="no", premiered="2016-10-01", status="Running")
    assert _row(doc) == ("Years", "2016, ended (end year not recorded)")


def test_ended_on_a_doubtful_join_says_neither_present_nor_ended(doc, tmp_path):
    """Club Friday The Series' shape: LezWatch 2012 and on air, TVmaze's record
    premiered in 2022 and is Ended. The join may be another season's record,
    so its end year is not used, and "present" is not said either."""
    _set(doc, start=2012, premiered="2022-08-19", status="Ended", ended="2023-03-31")
    assert _row(doc) == ("Years", "2012 (end year not recorded)")
    page = _page(doc, tmp_path)
    assert not any("present" in t or "2023" in t for t in [*page.facts.values(), _opening(doc)])


def test_ended_with_no_trusted_join_keeps_lezwatchs_present(doc):
    """Without an id join, TVmaze's record is not this show's for any purpose."""
    show = _set(doc, start=2018, premiered="2018-10-10", status="Ended", ended="2026-09-28")
    show["schedule"]["schedule_known"] = False
    assert _row(doc) == ("Years", "2018 to present")


def test_lezwatchs_end_year_is_kept_when_it_has_one(doc):
    _set(
        doc,
        start=2016,
        end=2018,
        on_air="no",
        premiered="2016-10-01",
        status="Ended",
        ended="2019-05-20",
    )
    assert _row(doc) == ("Years", "2016 to 2018")


def test_the_fixture_pages_are_unchanged(doc, tmp_path):
    """The untouched fixture has no year gap and no TVmaze end that LezWatch
    lacks, so no page's Years row moves."""
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    for slug, expected in [
        ("harbor-lights", {"Years": "2021 to present"}),
        ("the-cartographers", {"Years": "2016 to 2018"}),
        ("salt-and-ember", {"Years": "Not recorded"}),
    ]:
        page = htmlprobe.parse((tmp_path / "shows" / slug / "index.html").read_text("utf-8"))
        assert _years_rows(page) == expected, slug


def test_the_years_row_never_moves_with_a_death(doc):
    """Only the earliest character year is read, and deaths are not years in
    the show, so marking every character dead changes nothing."""
    _chicago_med(doc)
    before = _row(doc)
    for c in doc["characters"]:
        c["death"].update(died=True, death_known=True, years=[2016])
    assert _row(doc) == before
