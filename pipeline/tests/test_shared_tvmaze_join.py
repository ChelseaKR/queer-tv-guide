"""Two LezWatch shows that resolve to one TVmaze show (#52).

The join is by id, and nothing proves the TVmaze show is the one LezWatch
means. When two LezWatch shows claim the same TVmaze show, at most one of them
is right, and the build cannot tell which, so neither gets that show's
schedule: both read "schedule unknown", and the build lists the pair.

The fixture reproduces the two pairs measured in the published snapshot of
2026-09-19: Amar en Tiempos Revueltos and Amar es para Siempre both carry
LezWatch's stored TVmaze id 26865; A Very Peculiar Practice and A Very Polish
Practice both carry IMDb id tt0090541, which TVmaze resolves to 8505. Derry
Girls and the IMDb-only show from the base fixtures are the negative control:
each has a TVmaze show to itself and keeps its schedule.
"""

from __future__ import annotations

import copy
import json

import httpx
import jsonschema
import pytest

from qtv_pipeline import build as build_mod
from qtv_pipeline import coverage
from qtv_pipeline.http import PacedClient

from .conftest import _load, build_handler


def _lezwatch_show(
    lwtv_id: int, slug: str, title: str, *, tvmaze_id: str = "", imdb: str = ""
) -> dict:
    show = copy.deepcopy(_load("lezwatch_show_imdb_only.json"))
    show["id"] = lwtv_id
    show["slug"] = slug
    show["link"] = f"https://lezwatchtv.com/show/{slug}/"
    show["title"] = {"rendered": title}
    show["meta"]["lezshows_tvmaze_id"] = [tvmaze_id]
    show["meta"]["lezshows_imdb"] = [imdb]
    show["acf"]["lezshows_imdb"] = imdb
    return show


def _tvmaze_show(tvmaze_id: int, name: str, premiered: str) -> dict:
    body = copy.deepcopy(_load("tvmaze_show_imdb_only.json"))
    body["id"] = tvmaze_id
    body["url"] = f"https://www.tvmaze.com/shows/{tvmaze_id}/x"
    body["name"] = name
    body["premiered"] = premiered
    return body


PAIRS_SHOWS = [
    _lezwatch_show(
        1992, "amar-en-tiempos-revueltos", "Amar en Tiempos Revueltos", tvmaze_id="26865"
    ),
    _lezwatch_show(1995, "amar-es-para-siempre", "Amar es para Siempre", tvmaze_id="26865"),
    _lezwatch_show(10010, "a-very-peculiar-practice", "A Very Peculiar Practice", imdb="tt0090541"),
    _lezwatch_show(10013, "a-very-polish-practice", "A Very Polish Practice", imdb="tt0090541"),
]
PAIRS_TVMAZE = {
    26865: _tvmaze_show(26865, "Amar en tiempos revueltos", "2005-09-27"),
    8505: _tvmaze_show(8505, "A Very Peculiar Practice", "1986-05-21"),
}
PAIRS_IMDB = {"tt0090541": 8505}
FLAGGED = {
    "lwtv:show:1992",
    "lwtv:show:1995",
    "lwtv:show:10010",
    "lwtv:show:10013",
}


@pytest.fixture
def built(tmp_path, no_sleep):
    sleep, _ = no_sleep
    transport = httpx.MockTransport(
        build_handler(extra_shows=PAIRS_SHOWS, extra_tvmaze=PAIRS_TVMAZE, extra_imdb=PAIRS_IMDB)
    )

    def client_factory(**kwargs):
        return PacedClient(transport=transport, sleep=sleep, **kwargs)

    cache_dir = tmp_path / "cache"
    out_dir = tmp_path / "out"
    log: list[str] = []
    build_mod.run_fetch(cache_dir, full=True, log=lambda _m: None, client_factory=client_factory)
    doc = build_mod.run_build(cache_dir, out_dir, log=log.append)
    return doc, out_dir, log


def _shows_by_id(doc):
    return {s["id"]: s for s in doc["shows"]}


def test_the_fetch_really_joins_both_pairs_to_one_show_each(built):
    """Precondition: the mirror holds the duplicated joins the build must catch,
    so the tests below cannot pass because the fixture never joined at all."""
    doc, _out, _log = built
    by_id = _shows_by_id(doc)
    for sid in FLAGGED:
        assert by_id[sid]["schedule"]["join"]["method"] in ("lwtv_tvmaze_id", "imdb_lookup")


def test_a_shared_tvmaze_show_gives_neither_claimant_a_schedule(built):
    doc, _out, _log = built
    by_id = _shows_by_id(doc)
    for sid in FLAGGED:
        schedule = by_id[sid]["schedule"]
        assert schedule["schedule_known"] is False, sid
        assert schedule["join"]["matched"] is False, sid
        for key in ("tvmaze_id", "tvmaze_url", "premiered", "next_episode", "previous_episode"):
            assert schedule[key] is None, (sid, key)


def test_a_clean_join_is_not_flagged(built):
    """Negative control: shows that have a TVmaze show to themselves keep it."""
    doc, _out, _log = built
    by_id = _shows_by_id(doc)
    derry = by_id["lwtv:show:25206"]["schedule"]
    assert derry["schedule_known"] is True
    assert derry["tvmaze_id"] == 33320
    imdb_only = by_id["lwtv:show:30004"]["schedule"]
    assert imdb_only["schedule_known"] is True
    assert imdb_only["next_episode"]["name"] == "Episode 2"


def test_coverage_counts_and_lists_the_pairs(built):
    doc, out_dir, _log = built
    tv = doc["coverage"]["tvmaze"]
    assert tv["shows_total"] == 9
    assert tv["joined"] == 2
    assert tv["misses"] == {
        "no_key": 1,
        "ignored_by_source": 1,
        "not_found": 1,
        "shared_tvmaze_id": 4,
        "other": 0,
    }
    assert tv["shared_tvmaze_ids"] == [
        {"tvmaze_id": 8505, "show_ids": ["lwtv:show:10010", "lwtv:show:10013"]},
        {"tvmaze_id": 26865, "show_ids": ["lwtv:show:1992", "lwtv:show:1995"]},
    ]
    assert json.loads((out_dir / "coverage.json").read_text())["tvmaze"] == tv


def test_the_build_log_names_each_pair(built):
    _doc, _out, log = built
    text = "\n".join(log)
    assert "shared_tvmaze_id=4" in text
    assert "tvmaze 8505 claimed by lwtv:show:10010, lwtv:show:10013" in text
    assert "tvmaze 26865 claimed by lwtv:show:1992, lwtv:show:1995" in text


def test_the_snapshot_still_validates(built):
    doc, _out, _log = built
    schema = json.loads(build_mod._find_schema_path().read_text())
    jsonschema.Draft202012Validator(schema).validate(doc)


def test_a_planted_duplicate_is_flagged_and_a_clean_set_is_not():
    """Unit-level negative control on the coverage function itself."""

    def show(sid, *, shared=None, known=True):
        return {
            "id": sid,
            "schedule": {
                "schedule_known": known,
                "join": {"method": "lwtv_tvmaze_id"},
            },
            "_join_ignored_by_source": False,
            "_shared_tvmaze_id": shared,
        }

    clean = coverage.tvmaze_coverage([show("lwtv:show:1"), show("lwtv:show:2")])
    assert clean["misses"]["shared_tvmaze_id"] == 0
    assert clean["shared_tvmaze_ids"] == []

    planted = coverage.tvmaze_coverage(
        [
            show("lwtv:show:1"),
            show("lwtv:show:3", shared=7, known=False),
            show("lwtv:show:2", shared=7, known=False),
        ]
    )
    assert planted["misses"]["shared_tvmaze_id"] == 2
    assert planted["misses"]["not_found"] == 0
    assert planted["shared_tvmaze_ids"] == [
        {"tvmaze_id": 7, "show_ids": ["lwtv:show:2", "lwtv:show:3"]}
    ]
