"""Where a recorded death falls in a show (DECISIONS 0041): the matching rules,
the crossover and resurrection cases, the placebo control, and the fetch.

Every show, character and episode here is invented. No real death is named.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import httpx
import pytest

from qtv_pipeline import build as build_mod
from qtv_pipeline import episodes
from qtv_pipeline.http import PacedClient
from qtv_pipeline.tvmaze import TvmazeDegraded

D = dt.date.fromisoformat


def _ep(season: int, number: int | None, airdate: str, kind: str = "regular") -> dict[str, Any]:
    return {"season": season, "number": number, "airdate": airdate, "type": kind}


def weekly(season: int, first: str, count: int) -> list[dict[str, Any]]:
    start = D(first)
    return [
        _ep(season, n, (start + dt.timedelta(weeks=n - 1)).isoformat()) for n in range(1, count + 1)
    ]


# Season 1 weekly from 2020-01-06 (ep 1-10, last 2020-03-09); a hiatus; season 2
# weekly from 2020-09-07 with a double bill on 2020-10-05; season 3 dropped whole
# on 2021-06-04; a special on 2020-12-20.
SEASON_2 = [*weekly(2, "2020-09-07", 4), _ep(2, 5, "2020-10-05"), _ep(2, 6, "2020-10-05")]
SHOW = episodes.parse(
    [
        *weekly(1, "2020-01-06", 10),
        *SEASON_2,
        *[_ep(3, n, "2021-06-04") for n in range(1, 9)],
        _ep(2, None, "2020-12-20", "significant_special"),
        _ep(1, 99, None),  # TVmaze lists it with no air date: never matched
    ]
)


def placed(day: str, eps: list[episodes.Episode] = SHOW) -> tuple[str, str, int | None, Any]:
    p = episodes.place(D(day), eps)
    return p["precision"], p["reason"], p["season"], p["episodes"]


# ---- the rules, one fixture each -------------------------------------------


def test_exact_date_names_the_episode() -> None:
    assert placed("2020-01-20") == ("episode", "exact_date", 1, [3])


def test_one_day_off_with_a_single_nearby_episode_names_it() -> None:
    assert placed("2020-01-21") == ("episode", "one_day_off", 1, [3])
    assert placed("2020-01-19") == ("episode", "one_day_off", 1, [3])


def test_two_episodes_the_same_day_are_a_pair_never_one_guess() -> None:
    assert placed("2020-10-05") == ("episode_pair", "double_bill", 2, [5, 6])


def test_a_whole_season_drop_is_the_season_only_never_episode_one() -> None:
    p = episodes.place(D("2021-06-04"), SHOW)
    assert (p["precision"], p["reason"], p["season"]) == ("season", "season_drop", 3)
    assert p["episodes"] is None


def test_a_special_is_named_by_its_air_date_not_a_number() -> None:
    p = episodes.place(D("2020-12-20"), SHOW)
    assert (p["precision"], p["reason"], p["season"]) == ("special", "special_same_day", 2)
    assert p["episodes"] is None
    assert p["airdate"] == "2020-12-20"


def test_within_a_week_of_one_season_is_that_season() -> None:
    assert placed("2020-01-10") == ("season", "within_a_week", 1, None)


def test_several_episodes_within_a_day_from_one_season_is_the_season() -> None:
    eps = episodes.parse([_ep(1, 1, "2020-01-01"), _ep(1, 2, "2020-01-03")])
    assert placed("2020-01-02", eps) == ("season", "one_day_off_several", 1, None)


def test_inside_a_season_span_but_far_from_any_episode_is_the_season() -> None:
    eps = episodes.parse([_ep(4, 1, "2022-01-01"), _ep(4, 2, "2022-03-01")])
    assert placed("2022-02-01", eps) == ("season", "inside_season_span", 4, None)


def test_a_hiatus_is_not_placed() -> None:
    assert placed("2020-06-01") == ("unplaced", "between_seasons", None, None)


def test_before_the_first_and_after_the_last_episode_are_not_placed() -> None:
    assert placed("2019-01-01")[:2] == ("unplaced", "before_first_episode")
    assert placed("2023-01-01")[:2] == ("unplaced", "after_last_episode")


def test_episodes_from_two_seasons_the_same_day_are_not_placed() -> None:
    eps = episodes.parse([_ep(1, 9, "2020-05-01"), _ep(2, 1, "2020-05-01")])
    assert placed("2020-05-01", eps)[:2] == ("unplaced", "several_seasons_same_day")


def test_near_episodes_from_two_seasons_are_not_placed() -> None:
    eps = episodes.parse([_ep(1, 9, "2020-05-01"), _ep(2, 1, "2020-05-03")])
    assert placed("2020-05-02", eps)[:2] == ("unplaced", "near_several_seasons")
    assert placed("2020-05-06", eps)[:2] == ("unplaced", "near_several_seasons")


def test_overlapping_season_spans_are_not_placed() -> None:
    eps = episodes.parse(
        [
            _ep(1, 1, "2020-01-01"),
            _ep(1, 2, "2020-06-01"),
            _ep(2, 1, "2020-02-01"),
            _ep(2, 2, "2020-07-01"),
        ]
    )
    assert placed("2020-04-01", eps)[:2] == ("unplaced", "overlapping_seasons")


def test_specials_alone_or_nothing_dated_are_not_placed() -> None:
    assert placed("2020-01-01", [])[:2] == ("unplaced", "no_dated_episodes")
    only_special = episodes.parse([_ep(1, None, "2020-01-01", "insignificant_special")])
    assert placed("2020-03-01", only_special)[:2] == ("unplaced", "no_dated_episodes")
    two_specials = episodes.parse(
        [
            _ep(1, None, "2020-01-01", "significant_special"),
            _ep(1, None, "2020-01-01", "significant_special"),
        ]
    )
    assert placed("2020-01-01", two_specials) == ("season", "specials_same_day", 1, None)


def test_episode_counts_count_numbered_regular_episodes_only() -> None:
    slimmed = [
        *weekly(1, "2020-01-06", 3),
        _ep(1, None, "2020-02-01", "significant_special"),
        _ep(2, 1, None),  # announced, no air date yet: still an episode of season 2
        _ep(2, 1, "2021-01-01"),  # TVmaze listing one number twice counts once
    ]
    assert episodes.episode_counts(slimmed) == [
        {"season": 1, "episodes": 3},
        {"season": 2, "episodes": 1},
    ]
    assert episodes.episode_counts([]) == []


def test_slim_keeps_only_season_number_airdate_and_type() -> None:
    raw = [
        {**_ep(1, 1, "2020-01-01"), "name": "x", "summary": "<p>y</p>", "image": {"medium": "z"}}
    ]
    assert episodes.slim(raw) == [_ep(1, 1, "2020-01-01")]
    assert episodes.slim({"not": "a list"}) == []


# ---- per character x date x show (DECISIONS 0030) ---------------------------


def _character(dates: list[str | None], shows: list[tuple[str, list[str]]]) -> dict[str, Any]:
    return {
        "id": "lwtv:character:1",
        "name": "Invented Person",
        "shows": [{"show_id": sid, "role": "regular", "years": years} for sid, years in shows],
        "death": {
            "died": True,
            "death_known": True,
            "dates": [
                {"date": d, "year": int(d[:4]) if d else None, "raw": d or ""} for d in dates
            ],
            "years": [],
        },
    }


A, B, C = "lwtv:show:10", "lwtv:show:20", "lwtv:show:30"


def test_a_death_counts_only_in_shows_whose_years_include_it() -> None:
    char = _character(["2020-01-20"], [(A, ["2020"]), (B, ["2019"])])
    episodes.place_all([char], {A: SHOW, B: SHOW})
    [placement] = char["death"]["dates"][0]["placements"]
    assert placement["show_id"] == A
    assert placement["precision"] == "episode"


def test_a_death_year_in_none_of_the_shows_is_unplaced_with_no_show() -> None:
    char = _character(["2020-01-20"], [(A, ["2018"])])
    episodes.place_all([char], {A: SHOW})
    assert char["death"]["dates"][0]["placements"] == [
        {
            "show_id": None,
            "precision": "unplaced",
            "reason": "no_show_in_death_year",
            "season": None,
            "episodes": None,
            "airdate": None,
        }
    ]


def test_no_join_and_no_fetched_list_are_different_reasons() -> None:
    char = _character(["2020-01-20"], [(A, ["2020"]), (B, ["2020"])])
    episodes.place_all([char], {B: None})  # A has no join; B's list was not fetched
    reasons = {p["show_id"]: p["reason"] for p in char["death"]["dates"][0]["placements"]}
    assert reasons == {A: "no_tvmaze_join", B: "episodes_unavailable"}


def test_a_crossover_is_kept_only_where_it_lands_on_an_episode() -> None:
    elsewhere = episodes.parse(weekly(1, "2020-01-08", 10))  # never on 2020-01-20
    char = _character(["2020-01-20"], [(B, ["2020"]), (A, ["2020"])])
    episodes.place_all([char], {A: SHOW, B: elsewhere})
    by_show = {p["show_id"]: p for p in char["death"]["dates"][0]["placements"]}
    assert list(by_show) == [A, B]  # by show id, numerically
    assert by_show[A]["precision"] == "episode"
    assert by_show[B]["precision"] == "other_show"
    assert by_show[B]["reason"] == "crossover_matched_other_show"
    assert by_show[B]["season"] is None


def test_a_crossover_that_lands_in_both_shows_stays_in_both() -> None:
    char = _character(["2020-01-20"], [(A, ["2020"]), (C, ["2020"])])
    episodes.place_all([char], {A: SHOW, C: SHOW})
    assert [p["precision"] for p in char["death"]["dates"][0]["placements"]] == [
        "episode",
        "episode",
    ]


def test_each_of_several_deaths_is_placed_on_its_own() -> None:
    """A character who dies, comes back and dies again has one date per death. Each
    is placed separately; nothing says the character is still dead."""
    char = _character(["2020-01-20", "2020-10-05", "2020-06-01"], [(A, ["2020"])])
    episodes.place_all([char], {A: SHOW})
    got = [p["precision"] for e in char["death"]["dates"] for p in e["placements"]]
    assert got == ["episode", "episode_pair", "unplaced"]
    flat = json.dumps(char["death"])
    assert "still" not in flat and "alive" not in flat


def test_a_year_only_or_missing_date_is_unplaced_with_its_reason() -> None:
    char = _character([None], [(A, ["2020"])])
    char["death"]["dates"].append({"date": None, "year": 2020, "raw": "2020"})
    episodes.place_all([char], {A: SHOW})
    reasons = [p["reason"] for e in char["death"]["dates"] for p in e["placements"]]
    assert reasons == ["date_not_recorded", "year_only"]


# ---- coverage numbers -------------------------------------------------------


def test_coverage_counts_every_precision_and_never_invents_a_rate() -> None:
    char = _character(["2020-01-20", "2020-06-01"], [(A, ["2020"])])
    episodes.place_all([char], {A: SHOW})
    control = episodes.shifted_control([char], {A: SHOW})
    block = episodes.coverage([char], lists_wanted=1, lists_cached=1, control=control)
    assert block["death_events"] == 2
    assert block["by_precision"]["episode"] == 1
    assert block["by_precision"]["unplaced"] == 1
    assert block["by_reason"] == {"between_seasons": 1, "exact_date": 1}
    assert control["enforced"] is False  # 2 dates is far too few to judge

    empty = episodes.shifted_control([], {})
    assert empty["eligible"] == 0
    assert empty["episode_level_rate"] is None  # unknown, never 0
    assert empty["shifted_episode_level_rate"] is None
    none_block = episodes.coverage([], lists_wanted=0, lists_cached=0, control=empty)
    assert episodes.summary_lines(none_block) == ["death placement: no recorded death events"]


# ---- the placebo control ------------------------------------------------------


def _many_deaths(n: int = 60) -> tuple[list[dict[str, Any]], dict[str, list[episodes.Episode]]]:
    """n invented characters, each dying on the air date of a weekly episode of an
    invented show; one show per character so each is its own event."""
    chars, eps_by_show = [], {}
    for i in range(n):
        show_id = f"lwtv:show:{100 + i}"
        season = weekly(1, "2020-01-06", 10)
        eps_by_show[show_id] = episodes.parse(season)
        char = _character([season[i % 10]["airdate"]], [(show_id, ["2020"])])
        char["id"] = f"lwtv:character:{100 + i}"
        chars.append(char)
    return chars, eps_by_show


def test_the_control_passes_a_matcher_that_finds_real_dates_only() -> None:
    chars, eps = _many_deaths()
    control = episodes.shifted_control(chars, eps)
    assert control["enforced"] is True
    assert control["episode_level_rate"] == 1.0
    assert control["shifted_episode_level_rate"] == 0.0
    assert episodes.control_problem(control) is None


def test_the_control_fails_a_matcher_that_matches_everything() -> None:
    """Negative control: a matcher that places any date at all must be caught."""
    chars, eps = _many_deaths()

    def matches_everything(_day: dt.date, _eps: Any) -> dict[str, Any]:
        return {
            "precision": "episode",
            "reason": "exact_date",
            "season": 1,
            "episodes": [1],
            "airdate": None,
        }

    control = episodes.shifted_control(chars, eps, matcher=matches_everything)
    assert control["shifted_episode_level_rate"] == 1.0  # the sabotage really applied
    problem = episodes.control_problem(control)
    assert problem is not None and "placebo control" in problem


def test_the_control_fails_on_a_daily_show_where_shifted_dates_still_hit() -> None:
    """A show with an episode every day: a date moved 3 days still lands on one,
    so episode matching proves nothing there, and the control says so."""
    daily = episodes.parse(
        [_ep(1, n, (D("2020-01-01") + dt.timedelta(days=n)).isoformat()) for n in range(1, 200)]
    )
    chars, _ = _many_deaths()
    eps = {c["shows"][0]["show_id"]: daily for c in chars}
    for c in chars:
        c["death"]["dates"][0]["date"] = "2020-03-01"
    control = episodes.shifted_control(chars, eps)
    assert control["shifted_episode_level_rate"] == 1.0
    assert episodes.control_problem(control) is not None


def test_the_build_refuses_when_the_control_fails(tmp_path) -> None:
    chars, eps = _many_deaths()
    shows = []
    for show_id in eps:
        tvmaze_id = int(show_id.rsplit(":", 1)[-1])
        (tmp_path / "tvmaze" / "episodes").mkdir(parents=True, exist_ok=True)
        episodes.cache_path(tmp_path, tvmaze_id).write_text(json.dumps(weekly(1, "2020-01-06", 10)))
        shows.append(
            {
                "id": show_id,
                "schedule": {"schedule_known": True, "tvmaze_id": tvmaze_id},
                "counts": {"deaths": 1},
            }
        )
    block = build_mod._place_deaths(shows, chars, tmp_path)
    assert block["by_precision"]["episode"] == 60
    assert all(s["episode_counts"] == [{"season": 1, "episodes": 10}] for s in shows)

    def matches_everything(_day: dt.date, _eps: Any) -> dict[str, Any]:
        return {
            "precision": "episode",
            "reason": "exact_date",
            "season": 1,
            "episodes": [1],
            "airdate": None,
        }

    with pytest.raises(build_mod.BuildError, match="placebo control"):
        build_mod._place_deaths(shows, chars, tmp_path, matcher=matches_everything)


# ---- the fetch ------------------------------------------------------------------


def _client(handler, sleeps: list[float]) -> PacedClient:
    return PacedClient(
        transport=httpx.MockTransport(handler), sleep=sleeps.append, clock=lambda: 0.0
    )


def _joins(**status: str) -> dict[str, dict[str, Any]]:
    return {
        lwtv: {
            "matched": True,
            "tvmaze_id": int(lwtv) * 10,
            "status": s,
            "method": "lwtv_tvmaze_id",
        }
        for lwtv, s in status.items()
    }


def test_sync_fetches_only_wanted_joined_shows_and_keeps_four_fields(tmp_path) -> None:
    from tests.conftest import synthetic_episode_list

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path + "?" + request.url.query.decode())
        if request.url.path.endswith("/episodes"):
            return httpx.Response(200, json=synthetic_episode_list())
        raise AssertionError(request.url)

    sleeps: list[float] = []
    joins = {**_joins(**{"1": "Running", "2": "Ended"}), "3": {"matched": False, "tvmaze_id": None}}
    with _client(handler, sleeps) as client:
        report = episodes.sync_episodes(client, tmp_path, joins, {"1", "3", "4"}, full=True)
    assert seen == ["/shows/10/episodes?specials=1"]
    assert (report.wanted, report.attempted, report.degraded) == (1, 1, [])
    cached = episodes.load(tmp_path, 10)
    assert cached is not None and all(set(e) == set(episodes.KEPT_FIELDS) for e in cached)
    assert "Invented" not in episodes.cache_path(tmp_path, 10).read_text()
    assert episodes.load(tmp_path, 20) is None


def test_sync_is_paced_like_every_other_tvmaze_request(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    sleeps: list[float] = []
    with _client(handler, sleeps) as client:
        episodes.sync_episodes(
            client, tmp_path, _joins(**{"1": "Running", "2": "Running"}), {"1", "2"}, full=True
        )
        assert client.counters_as_dict()["api.tvmaze.com"]["requests"] == 2
    assert sleeps == [1.0]  # TVMAZE_POLICY's one request a second, between the two


def test_incremental_sync_skips_an_ended_show_unless_tvmaze_says_it_changed(tmp_path) -> None:
    for tvmaze_id in (10, 20, 30):
        episodes.cache_path(tmp_path, tvmaze_id).parent.mkdir(parents=True, exist_ok=True)
        episodes.cache_path(tmp_path, tvmaze_id).write_text("[]")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/updates/shows":
            return httpx.Response(200, json={"20": 1700000000})
        return httpx.Response(200, json=[])

    joins = _joins(**{"1": "Ended", "2": "Ended", "3": "Running"})
    with _client(handler, []) as client:
        episodes.sync_episodes(client, tmp_path, joins, {"1", "2", "3"})
    assert seen == ["/updates/shows", "/shows/20/episodes", "/shows/30/episodes"]


def test_a_404_drops_the_old_list_and_a_failure_keeps_it(tmp_path) -> None:
    for tvmaze_id in (10, 20):
        episodes.cache_path(tmp_path, tvmaze_id).parent.mkdir(parents=True, exist_ok=True)
        episodes.cache_path(tmp_path, tvmaze_id).write_text(json.dumps([_ep(1, 1, "2020-01-01")]))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/shows/10/episodes":
            return httpx.Response(404, json={})
        return httpx.Response(503, json={})

    joins = _joins(**{"1": "Running", "2": "Running"})
    with _client(handler, []) as client:
        report = episodes.sync_episodes(client, tmp_path, joins, {"1", "2"}, full=True)
    assert episodes.load(tmp_path, 10) is None
    assert episodes.load(tmp_path, 20) == [_ep(1, 1, "2020-01-01")]
    assert report.degraded == [20]


def test_too_many_failures_fail_the_run(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    joins = _joins(**{str(i): "Running" for i in range(1, 5)})
    with _client(handler, []) as client, pytest.raises(TvmazeDegraded):
        episodes.sync_episodes(client, tmp_path, joins, set(joins), full=True)


def test_shows_with_a_death_reads_the_raw_character_records() -> None:
    raw = [
        {
            "acf": {
                "lezchars_death_year": [{"date": "20200101"}],
                "lezchars_show_group": [{"show": 7}, {"show": "8"}, {}],
            }
        },
        {"acf": {"lezchars_death_year": None, "lezchars_show_group": [{"show": 9}]}},
        {"acf": {"lezchars_death_year": [], "lezchars_show_group": [{"show": 10}]}},
    ]
    assert episodes.shows_with_a_death(raw) == {"7", "8"}
