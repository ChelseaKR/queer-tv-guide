"""Other titles and unknown season counts from Wikidata (DECISIONS 0055).

The rule: a value is used only when the item's LezWatch.TV id and the show's TVmaze
or IMDb id name the same item; junk titles are rejected; LezWatch.TV's and TVmaze's
season counts are never replaced; and a Wikidata outage neither fails the night nor
takes away a value. Every network exchange is httpx.MockTransport. Each rule has a
control that shows the same input passing once the fault is removed.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path

import httpx
import jsonschema
import pytest

from qtv_pipeline import build as build_mod
from qtv_pipeline import cli, show_pages, wikidata
from qtv_pipeline.http import LEZWATCH_POLICY, TVMAZE_POLICY, PacedClient

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
NOW = dt.datetime(2026, 11, 8, 12, tzinfo=dt.UTC)
QID = "Q1"
CACHE_FILE = wikidata.CACHE_PATH


def _item(**fields) -> dict:
    item = {
        "lezwatch": ["dix-pour-cent"],
        "tvmaze": ["42"],
        "imdb": ["tt42"],
        "seasons": [],
        "classes": ["Q5398426"],
        "languages": ["fr"],
        "titles": [],
        "labels": [["en", "Call My Agent!"], ["fr", "Dix pour cent"]],
        "aliases": [],
    }
    item.update(fields)
    return item


def _mirror(*items: dict, fetched_at: str = "2026-11-01T00:00:00Z") -> dict:
    return {
        "endpoint": wikidata.ENDPOINT,
        "fetched_at": fetched_at,
        "requests": 3,
        "bytes": 10,
        "items": {f"Q{i + 1}": item for i, item in enumerate(items)},
    }


def _show(**fields) -> dict:
    show = {
        "id": "lwtv:show:1",
        "slug": "dix-pour-cent",
        "title": "Dix pour cent",
        "alternate_names": [],
        "seasons": None,
        "years": {"start": 2015, "end": 2020, "on_air": "no"},
        "external_ids": {"imdb": "tt42", "tmdb": None, "tvmaze": 42},
        "schedule": {
            "schedule_known": False,
            "tvmaze_id": None,
            "status": None,
            "previous_episode": None,
        },
    }
    show.update(fields)
    return show


def _with_tvmaze_season(show: dict, season: int, status: str = "Ended") -> dict:
    show["schedule"] = {
        "schedule_known": True,
        "tvmaze_id": 42,
        "status": status,
        "premiered": "2015-10-14",
        "ended": None,
        "previous_episode": {"season": season},
    }
    return show


def _attach(show: dict, mirror: dict, rejects: dict | None = None) -> dict:
    wikidata.attach([show], mirror, rejects=rejects or {})
    return show


# -- two ids --------------------------------------------------------------------


def test_two_ids_agreeing_give_a_value_with_its_provenance() -> None:
    show = _attach(_show(), _mirror(_item(seasons=["4.0"])))
    assert show["alternate_names"] == ["Call My Agent!"]
    assert show["seasons"] == 4
    assert show["wikidata"] == {
        "item": QID,
        "matched_by": ["lezwatch", "tvmaze", "imdb"],
        "read_on": "2026-11-01",
        "alternate_names": [{"name": "Call My Agent!", "source": "label", "language": "en"}],
        "seasons": 4,
    }


def test_one_id_alone_gives_nothing() -> None:
    show = _attach(_show(), _mirror(_item(tvmaze=[], imdb=[], seasons=["4.0"])))
    assert show["alternate_names"] == []
    assert show["seasons"] is None
    assert "wikidata" not in show


def test_a_show_whose_lezwatch_id_no_item_carries_gives_nothing() -> None:
    show = _attach(_show(slug="other"), _mirror(_item(seasons=["4.0"])))
    assert "wikidata" not in show


@pytest.mark.parametrize(
    "other",
    [
        pytest.param({"lezwatch": ["someone-else"], "imdb": []}, id="tvmaze id on another item"),
        pytest.param({"lezwatch": ["someone-else"], "tvmaze": []}, id="imdb id on another item"),
        pytest.param({"tvmaze": [], "imdb": []}, id="lezwatch id on two items"),
    ],
)
def test_conflicting_ids_give_no_value(other: dict) -> None:
    second = _item(labels=[["en", "A Wrong Show"]], seasons=["9.0"], **other)
    show = _attach(_show(), _mirror(_item(seasons=["4.0"]), second))
    assert show["alternate_names"] == []
    assert show["seasons"] is None
    assert "wikidata" not in show
    # Control: the first item alone is taken, so the second one is what stopped it.
    assert _attach(_show(), _mirror(_item(seasons=["4.0"])))["seasons"] == 4


# -- junk titles ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("candidate", "title", "reason"),
    [
        ("Dix Pour Cent", "Dix pour cent", "same_as_title"),
        ("Dix-pour-cent", "Dix pour cent", "same_as_title"),
        ("Grey\u2019s Anatomy", "Grey's Anatomy", "same_as_title"),
        ("Shameless", "Shameless (US)", "adds_nothing"),
        ("Pretty Little Liars", "Pretty Little Liars: Original Sin", "adds_nothing"),
        ("DuckTales 2017", "DuckTales", "adds_nothing"),
        ("Chosen (Danish TV series)", "Chosen", "disambiguated"),
        ("Stupid Wife (serie)", "Stupid Wife", "disambiguated"),
        ("Tutta colpa di Freud - La serie", "Tutta colpa di Freud", "disambiguated"),
        ("Rugrats revival", "Rugrats", "disambiguated"),
        ("TLoU", "The Last of Us", "abbreviation"),
        ("ST: TOS", "Star Trek", "abbreviation"),
        ("Lost Season 2", "Lost", "part_of_a_show"),
        ("Pilot Episode", "Rookie Blue", "part_of_a_show"),
        ("The One Where Dana Dies", "The L Word", "spoiler_word"),
        ("Veneno. Vida y muerte de un icono", "Veneno", "spoiler_word"),
        ("A", "Longer Title", "unusable"),
        ("https://example.org/show", "Show", "unusable"),
    ],
)
def test_a_junk_label_is_rejected(candidate: str, title: str, reason: str) -> None:
    assert wikidata.title_rejection(candidate, title) == reason


@pytest.mark.parametrize(
    ("candidate", "title"),
    [
        ("Call My Agent!", "Dix pour cent"),
        ("Money Heist", "La Casa de Papel"),
        ("Shingeki no Kyojin", "Attack on Titan"),
        ("Law & Order: SVU", "Law & Order: Special Victims Unit"),
        ("オオカミさん", "Okami-san"),
    ],
)
def test_a_real_other_title_passes_the_same_rules(candidate: str, title: str) -> None:
    assert wikidata.title_rejection(candidate, title) is None


@pytest.mark.parametrize(
    ("aliases", "kept"),
    [
        pytest.param([["en", "Trial"]], False, id="one word"),
        pytest.param([["en", "Those Old Scientists"]], False, id="an episode"),
        pytest.param([["en", "غلبب"]], False, id="vandalism in another script"),
        pytest.param([["en", "Law & Order: LA"]], True, id="control: shares a word"),
    ],
)
def test_an_english_show_needs_a_word_in_common(aliases: list, kept: bool) -> None:
    item = _item(languages=["en"], labels=[["en", "Law & Order"]], aliases=aliases)
    show = _attach(_show(title="Law & Order"), _mirror(item))
    assert bool(show["alternate_names"]) is kept


@pytest.mark.parametrize(
    ("aliases", "kept"),
    [
        pytest.param([["en", "Maria"]], False, id="a bare short word"),
        pytest.param([["en", "Kuroshitsuji"]], True, id="control: a long one"),
        pytest.param([["en", "Round Six"]], True, id="control: two words"),
    ],
)
def test_a_show_in_another_language_loses_only_a_bare_short_word(aliases: list, kept: bool) -> None:
    item = _item(labels=[], aliases=aliases)
    show = _attach(_show(), _mirror(item))
    assert bool(show["alternate_names"]) is kept


def test_a_label_in_a_language_the_show_is_not_in_is_not_a_name() -> None:
    labels = [["de", "Call My Agent auf Deutsch"], ["en", "Call My Agent!"], ["fr", "Dix"]]
    show = _attach(_show(), _mirror(_item(labels=labels)))
    assert show["alternate_names"] == ["Call My Agent!"]


def test_several_languages_means_no_native_title() -> None:
    item = _item(languages=["fr", "es"], labels=[["fr", "Autre titre français"]])
    show = _attach(_show(), _mirror(item))
    assert show["alternate_names"] == []
    # Control: one language, the same label is the show's own title.
    item["languages"] = ["fr"]
    assert _attach(_show(), _mirror(item))["alternate_names"] == ["Autre titre français"]


def test_another_shows_title_is_rejected() -> None:
    other = _show(id="lwtv:show:2", slug="other", title="Call My Agent!", external_ids={})
    show = _show()
    coverage = wikidata.attach([show, other], _mirror(_item()), rejects={})
    assert show["alternate_names"] == []
    assert coverage["titles_rejected"]["another_shows_title"] == 1


def test_a_title_two_shows_claim_goes_from_both() -> None:
    second = _show(
        id="lwtv:show:2",
        slug="deux",
        title="Deux",
        external_ids={"imdb": "tt43", "tmdb": None, "tvmaze": 43},
    )
    items = (_item(), _item(lezwatch=["deux"], tvmaze=["43"], imdb=["tt43"]))
    first = _show()
    coverage = wikidata.attach([first, second], _mirror(*items), rejects={})
    assert first["alternate_names"] == second["alternate_names"] == []
    assert coverage["titles_rejected"]["claimed_by_two_shows"] == 2


def test_an_episode_item_gives_no_titles() -> None:
    show = _attach(_show(), _mirror(_item(classes=["Q21191270"])))
    assert show["alternate_names"] == []


def test_a_name_rejected_by_hand_stays_out() -> None:
    show = _attach(_show(), _mirror(_item()), rejects={QID: ["Call My Agent!"]})
    assert show["alternate_names"] == []
    assert _attach(_show(), _mirror(_item()), rejects={})["alternate_names"]  # control


# -- seasons --------------------------------------------------------------------


def test_lezwatchs_count_is_never_replaced() -> None:
    show = _attach(_show(seasons=3), _mirror(_item(seasons=["4.0"])))
    assert show["seasons"] == 3
    assert "seasons" not in show["wikidata"]


def test_a_different_tvmaze_count_leaves_the_field_as_it_is() -> None:
    show = _attach(_with_tvmaze_season(_show(), 5), _mirror(_item(seasons=["4.0"])))
    assert show["seasons"] is None
    assert "seasons" not in show["wikidata"]


def test_the_same_tvmaze_count_fills_the_apps_field_and_the_page_still_says_tvmaze() -> None:
    show = _attach(_with_tvmaze_season(_show(), 4), _mirror(_item(seasons=["4.0"])))
    assert show["seasons"] == 4
    assert show_pages.seasons_fact(show) == ("Seasons, per TVmaze", "4", 4)
    # Control: the row is the one the same show gets with no Wikidata value at all.
    bare = _with_tvmaze_season(_show(), 4)
    assert show_pages.seasons_fact(show) == show_pages.seasons_fact(bare)


def test_a_season_numbered_by_year_is_no_tvmaze_count() -> None:
    show = _attach(_with_tvmaze_season(_show(), 2019), _mirror(_item(seasons=["4.0"])))
    assert show["seasons"] == 4


@pytest.mark.parametrize(
    "values",
    [
        pytest.param(["3.0", "2.0"], id="two values disagree"),
        pytest.param(["0.0"], id="zero"),
        pytest.param(["-1.0"], id="negative"),
        pytest.param(["2.5"], id="not whole"),
        pytest.param(["1998.0"], id="a year"),
        pytest.param(["many"], id="not a number"),
    ],
)
def test_an_unusable_count_stays_absent(values: list) -> None:
    show = _attach(_show(), _mirror(_item(seasons=values)))
    assert show["seasons"] is None


@pytest.mark.parametrize("cls", ["Q3464665", "Q21191270", "Q11424", "Q196600"])
def test_an_item_that_is_not_a_whole_show_gives_no_count(cls: str) -> None:
    show = _attach(_show(), _mirror(_item(seasons=["4.0"], classes=[cls])))
    assert show["seasons"] is None


def test_a_count_longer_than_the_run_is_not_used() -> None:
    years = {"start": 1952, "end": 2009, "on_air": "no"}
    show = _attach(_show(years=years), _mirror(_item(seasons=["72.0"])))
    assert show["seasons"] is None
    show = _attach(_show(years=years), _mirror(_item(seasons=["57.0"])))
    assert show["seasons"] == 57  # control


def test_no_start_year_means_no_check_and_no_count() -> None:
    years = {"start": None, "end": None, "on_air": "unknown"}
    assert _attach(_show(years=years), _mirror(_item(seasons=["4.0"])))["seasons"] is None


# -- the website ----------------------------------------------------------------


def _fixture_show() -> dict:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    show = next(s for s in doc["shows"] if s["slug"] == "harbor-lights")
    show["seasons"] = None
    show["schedule"]["previous_episode"] = None
    return show


def test_a_wikidata_count_is_labeled_and_a_running_show_says_so_far() -> None:
    show = _fixture_show()
    assert show_pages.seasons_fact(show)[0:2] == ("Seasons", show_pages.NOT_RECORDED)  # control
    show["seasons"] = 3
    show["wikidata"] = {"seasons": 3}
    show["years"]["on_air"] = "yes"
    show["schedule"]["status"] = "Running"
    assert show_pages.seasons_fact(show) == ("Seasons, per Wikidata", "3 so far", 3)
    show["years"]["on_air"] = "no"
    show["schedule"]["status"] = None
    assert show_pages.seasons_fact(show) == ("Seasons, per Wikidata", "3", 3)


def test_a_wikidata_count_does_not_touch_the_years_row() -> None:
    show = _fixture_show()
    before = show_pages.years_fact(show)
    show["seasons"] = 3
    show["wikidata"] = {"seasons": 3, "item": QID}
    assert show_pages.years_fact(show) == before


# -- reading --------------------------------------------------------------------


def _answer(*rows: dict) -> httpx.Response:
    return httpx.Response(200, json={"results": {"bindings": list(rows)}})


def _uri(q: str) -> dict:
    return {"type": "uri", "value": f"http://www.wikidata.org/entity/{q}"}


def _lit(value: str, lang: str | None = None) -> dict:
    return {"value": value, **({"xml:lang": lang} if lang else {})}


def healthy(request: httpx.Request) -> httpx.Response:
    query = request.url.params["query"]
    if "?alias" in query:
        return _answer({"item": _uri("Q1"), "alias": _lit("Le Dix", "en")})
    if "?label" in query:
        return _answer({"item": _uri("Q1"), "label": _lit("Call My Agent!", "en")})
    return _answer(
        {
            "item": _uri("Q1"),
            "lezwatch": _lit("dix-pour-cent"),
            "tvmaze": _lit("42"),
            "imdb": _lit("tt42"),
            "seasons": _lit("4.0"),
            "class": _uri("Q5398426"),
            "language": _lit("fr"),
            "title": _lit("Dix pour cent", "fr"),
        }
    )


class Waits:
    def __init__(self) -> None:
        self.seen: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.seen.append(seconds)


def _factory(handler, waits: Waits | None = None):
    def factory(**kwargs):
        return PacedClient(transport=httpx.MockTransport(handler), sleep=waits or Waits(), **kwargs)

    return factory


def _refresh(cache: Path, handler, *, waits: Waits | None = None, **kwargs):
    logs: list[str] = []
    kwargs.setdefault("seed", cache / "no-seed.json")
    result = wikidata.refresh(
        cache,
        now=NOW,
        log=logs.append,
        client_factory=_factory(handler, waits),
        **kwargs,
    )
    return result, logs


def test_a_read_stores_only_the_fields_the_rule_reads(tmp_path: Path) -> None:
    result, _ = _refresh(tmp_path, healthy)
    assert result.outcome == "refreshed"
    stored = json.loads((tmp_path / CACHE_FILE).read_text(encoding="utf-8"))
    assert stored["fetched_at"] == "2026-11-08T12:00:00Z"
    assert stored["requests"] == 3
    assert stored["items"]["Q1"]["labels"] == [["en", "Call My Agent!"]]
    assert stored["items"]["Q1"]["seasons"] == ["4.0"]
    assert set(stored["items"]["Q1"]) == set(wikidata._empty_item())


def test_a_read_contacts_only_qlever_with_the_honest_user_agent(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def spy(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return healthy(request)

    _refresh(tmp_path, spy)
    assert {r.url.host for r in seen} == {"qlever.dev"}
    assert all(r.url.path == "/api/wikidata" for r in seen)
    assert all(r.headers["user-agent"].startswith("queer-tv-guide-pipeline/") for r in seen)
    assert len(seen) == 3


def test_queries_ask_for_no_death_field() -> None:
    for query in (wikidata.QUERY_FACTS, wikidata.QUERY_LABELS, wikidata.QUERY_ALIASES):
        for death_property in ("P570", "P1196", "P509", "P157"):
            assert death_property not in query


def test_a_recent_read_makes_no_request(tmp_path: Path) -> None:
    calls: list[str] = []

    def spy(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return healthy(request)

    _refresh(tmp_path, spy)
    assert len(calls) == 3
    result, _ = _refresh(tmp_path, spy)
    assert result.outcome == "fresh"
    assert len(calls) == 3
    # Control: a week later it reads again.
    later = wikidata.refresh(
        tmp_path,
        now=NOW + dt.timedelta(days=8),
        seed=tmp_path / "no-seed.json",
        log=lambda _m: None,
        client_factory=_factory(spy),
    )
    assert later.outcome == "refreshed"
    assert len(calls) == 6


def test_a_429_waits_out_retry_after_then_reads(tmp_path: Path) -> None:
    answers = [httpx.Response(429, headers={"Retry-After": "90"})]

    def flaky(request: httpx.Request) -> httpx.Response:
        return answers.pop() if answers else healthy(request)

    waits = Waits()
    result, _ = _refresh(tmp_path, flaky, waits=waits)
    assert result.outcome == "refreshed"
    assert 90.0 in waits.seen


def test_a_long_retry_after_stops_the_read_and_keeps_the_file(tmp_path: Path) -> None:
    _refresh(tmp_path, healthy)
    before = (tmp_path / CACHE_FILE).read_bytes()
    calls: list[int] = []

    def busy(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, headers={"Retry-After": "3600"})

    result, logs = _refresh(tmp_path, busy, force=True)
    assert result.outcome == "kept"
    assert len(calls) == 1, "no retry sooner than asked"
    assert (tmp_path / CACHE_FILE).read_bytes() == before
    assert any(line.startswith("::notice::") for line in logs)


# -- an outage ------------------------------------------------------------------


def _down_503(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(503)


def _down_network(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("no route", request=request)


def _down_html(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text="<html>maintenance</html>")


def _down_empty(_request: httpx.Request) -> httpx.Response:
    return _answer()


def _down_wrong_shape(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"results": {"bindings": [{"nope": 1}]}})


def _down_second_query(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500) if "?label" in request.url.params["query"] else healthy(request)


OUTAGES = [_down_503, _down_network, _down_html, _down_empty, _down_wrong_shape, _down_second_query]


@pytest.mark.parametrize("outage", OUTAGES, ids=lambda f: f.__name__)
def test_an_outage_leaves_the_last_known_file_byte_for_byte(tmp_path: Path, outage) -> None:
    _refresh(tmp_path, healthy)
    before = (tmp_path / CACHE_FILE).read_bytes()
    result, logs = _refresh(tmp_path, outage, force=True)
    assert result.outcome == "kept"
    assert (tmp_path / CACHE_FILE).read_bytes() == before
    assert any("last known values stay" in line for line in logs)


@pytest.mark.parametrize("outage", OUTAGES, ids=lambda f: f.__name__)
def test_an_outage_with_no_file_writes_none(tmp_path: Path, outage) -> None:
    result, _ = _refresh(tmp_path, outage)
    assert result.outcome == "kept"
    assert not (tmp_path / CACHE_FILE).exists()


def test_a_read_cut_short_does_not_replace_the_file(tmp_path: Path) -> None:
    items = {f"Q{i}": _item() for i in range(100)}
    path = tmp_path / CACHE_FILE
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(_mirror() | {"items": items}), encoding="utf-8")
    before = path.read_bytes()
    result, _ = _refresh(tmp_path, healthy, force=True)
    assert result.outcome == "kept"
    assert path.read_bytes() == before
    # Control: at the size of the last read, the same answer replaces it.
    path.write_text(json.dumps(_mirror(_item())), encoding="utf-8")
    assert _refresh(tmp_path, healthy, force=True)[0].outcome == "refreshed"


def test_no_later_retry_and_little_patience() -> None:
    assert wikidata.POLICY.later_retry_wait == 0
    assert wikidata.POLICY.max_retry_after <= 120
    assert wikidata.POLICY.max_5xx == 1
    assert wikidata.POLICY.min_interval >= 10


def test_the_other_sources_policies_are_what_0054_set() -> None:
    assert LEZWATCH_POLICY.later_retry_wait == 900.0
    assert LEZWATCH_POLICY.min_interval == 10.0
    assert TVMAZE_POLICY.min_interval == 1.0


def test_the_command_exits_0_when_anything_at_all_goes_wrong(monkeypatch, tmp_path, capsys) -> None:
    def explode(*_a, **_k):
        raise RuntimeError("a bug in this module")

    monkeypatch.setattr(wikidata, "refresh", explode)
    assert cli.main(["wikidata", "--cache", str(tmp_path)]) == 0
    assert "::notice::" in capsys.readouterr().out


# -- the night, whole -----------------------------------------------------------


def _night(tmp_path: Path, mock_transport, sleep, wikidata_handler) -> dict:
    """The workflow's order: fetch, the Wikidata step, build."""
    cache, out = tmp_path / "cache", tmp_path / "out"
    seen: list[str] = []

    def factory(**kwargs):
        def counting(request: httpx.Request) -> httpx.Response:
            seen.append(request.url.host)
            return mock_transport.handler(request)

        return PacedClient(transport=httpx.MockTransport(counting), sleep=sleep, **kwargs)

    build_mod.run_fetch(cache, full=True, log=lambda _m: None, client_factory=factory)
    assert "qlever.dev" not in seen
    wikidata.refresh(
        cache,
        force=True,
        now=NOW,
        log=lambda _m: None,
        client_factory=_factory(wikidata_handler),
    )
    return build_mod.run_build(cache, out, log=lambda _m: None)


def _derry(doc: dict) -> dict:
    return next(s for s in doc["shows"] if s["slug"] == "derry-girls")


def _seed_cache(tmp_path: Path, doc_item: dict) -> None:
    path = tmp_path / "cache" / CACHE_FILE
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(_mirror(_item(**doc_item))), encoding="utf-8")


def _derry_ids() -> dict:
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "lezwatch_show_derry_girls.json").read_text()
    )
    return {
        "lezwatch": [fixture["slug"]],
        "imdb": [fixture["acf"]["lezshows_imdb"]],
        "tvmaze": [str(fixture["meta"]["lezshows_tvmaze_id"][0])],
        "languages": ["en"],
        "labels": [["en", "Derry Girls: The Lasses"]],
    }


def test_an_outage_passes_the_night_and_keeps_the_last_known_values(
    tmp_path, mock_transport, no_sleep
) -> None:
    sleep, _ = no_sleep
    _seed_cache(tmp_path, _derry_ids())
    doc = _night(tmp_path, mock_transport, sleep, _down_503)
    assert _derry(doc)["alternate_names"] == ["Derry Girls: The Lasses"]
    assert _derry(doc)["wikidata"]["read_on"] == "2026-11-01"
    assert doc["sources"]["wikidata"]["fetched_at"] == "2026-11-01T00:00:00Z"
    schema = json.loads(build_mod._find_schema_path().read_text())
    jsonschema.Draft202012Validator(schema).validate(doc)


def test_a_good_read_is_what_changes_the_values(tmp_path, mock_transport, no_sleep) -> None:
    # Control for the test above: the same night with Wikidata up does replace the file.
    sleep, _ = no_sleep
    _seed_cache(tmp_path, _derry_ids())
    doc = _night(tmp_path, mock_transport, sleep, healthy)
    assert doc["sources"]["wikidata"]["fetched_at"] == "2026-11-08T12:00:00Z"
    assert _derry(doc)["alternate_names"] == []


def test_with_no_read_at_all_values_are_absent_and_the_night_passes(
    tmp_path, mock_transport, no_sleep, monkeypatch
) -> None:
    sleep, _ = no_sleep
    monkeypatch.setattr(wikidata, "SEED_PATH", tmp_path / "gone.json")
    doc = _night(tmp_path, mock_transport, sleep, _down_503)
    assert "wikidata" not in doc["sources"]
    assert "wikidata" not in doc["coverage"]
    assert all("wikidata" not in s for s in doc["shows"])
    assert all(s["alternate_names"] == [] for s in doc["shows"])


def test_a_damaged_cache_falls_back_to_the_committed_read(tmp_path) -> None:
    (tmp_path / "wikidata").mkdir()
    (tmp_path / CACHE_FILE).write_text("{not json", encoding="utf-8")
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps(_mirror(_item())), encoding="utf-8")
    assert wikidata.load_mirror(tmp_path, seed=seed)["items"][QID]["tvmaze"] == ["42"]
    seed.write_text('{"items": {"Q1": {"lezwatch": "not a list"}}}', encoding="utf-8")
    assert wikidata.load_mirror(tmp_path, seed=seed) is None


@pytest.mark.parametrize(
    "damage",
    [
        pytest.param({"fetched_at": "yesterday"}, id="date"),
        pytest.param({"requests": "many"}, id="counter"),
        pytest.param({"items": {}}, id="no items"),
        pytest.param({"items": {"Q1": {}}}, id="empty item"),
        pytest.param({"items": {"nope": _item()}}, id="item id"),
        pytest.param({"items": {"Q1": _item(labels=[["en"]])}}, id="short pair"),
        pytest.param({"items": {"Q1": _item(labels=[["en", 7]])}}, id="number as a name"),
        pytest.param({"items": {"Q1": _item(tvmaze=[42])}}, id="number as an id"),
    ],
)
def test_a_damaged_file_reads_as_no_file(tmp_path: Path, damage: dict) -> None:
    path = tmp_path / CACHE_FILE
    path.parent.mkdir()
    path.write_text(json.dumps(_mirror(_item())), encoding="utf-8")
    missing = tmp_path / "none.json"
    assert wikidata.load_mirror(tmp_path, seed=missing) is not None  # control
    path.write_text(json.dumps(_mirror(_item()) | damage), encoding="utf-8")
    assert wikidata.load_mirror(tmp_path, seed=missing) is None


def test_two_builds_of_one_mirror_have_one_digest(tmp_path, mock_transport, no_sleep) -> None:
    sleep, _ = no_sleep
    _seed_cache(tmp_path, _derry_ids())
    first = _night(tmp_path, mock_transport, sleep, _down_503)
    second = build_mod.run_build(tmp_path / "cache", tmp_path / "o2", log=lambda _m: None)
    assert first["content_digest"] == second["content_digest"]


def test_the_file_stays_version_1(tmp_path, mock_transport, no_sleep) -> None:
    sleep, _ = no_sleep
    _seed_cache(tmp_path, _derry_ids())
    doc = _night(tmp_path, mock_transport, sleep, _down_503)
    assert doc["schema_version"] == "1"
    assert [a["source"] for a in doc["attribution"]] == ["lezwatch", "tvmaze"]
    assert "Wikidata" in doc["licence"]["notice"]


def test_an_old_reader_sees_only_values_it_already_knows() -> None:
    """A field the installed app reads keeps its type: `seasons` an integer or null,
    `alternate_names` a list of strings. Everything else is a new key."""
    show = _attach(_show(), _mirror(_item(seasons=["4.0"])))
    before = _show()
    assert set(show) - set(before) == {"wikidata"}
    assert isinstance(show["seasons"], int)
    assert all(isinstance(name, str) for name in show["alternate_names"])


# -- the committed files --------------------------------------------------------


def _committed() -> dict:
    mirror = wikidata.load_mirror(Path("/nonexistent"))
    assert mirror is not None
    return mirror


def test_the_committed_read_is_whole() -> None:
    mirror = _committed()
    assert len(mirror["items"]) > 1900
    assert mirror["endpoint"] == wikidata.ENDPOINT


def test_every_name_rejected_by_hand_is_a_real_candidate() -> None:
    mirror = _committed()
    rejects = wikidata.load_rejects()
    assert rejects
    for qid, names in rejects.items():
        offered = {c.name for c in wikidata.candidates(mirror["items"][qid])}
        assert set(names) <= offered, qid


def test_call_my_agent_comes_through_the_committed_read() -> None:
    mirror = _committed()
    qid = wikidata._index(mirror["items"], "lezwatch")["dix-pour-cent"]
    item = mirror["items"][next(iter(qid))]
    show = _show(
        external_ids={
            "imdb": item["imdb"][0],
            "tmdb": None,
            "tvmaze": int(item["tvmaze"][0]),
        }
    )
    assert "Call My Agent!" in _attach(show, copy.deepcopy(mirror))["alternate_names"]
