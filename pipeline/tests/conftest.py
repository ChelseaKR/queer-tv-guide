from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

FIXTURES = Path(__file__).parent / "fixtures"

GRANT_SENTENCE = "use, reuse, and extend the data here for no fees"

SHOW_FILES = [
    "lezwatch_show_derry_girls.json",  # joins via stored tvmaze id, has watch link + no death chars
    "lezwatch_show_no_key.json",  # no join key at all
    "lezwatch_show_ignored.json",  # lezshows_tvmaze_ignore = true
    "lezwatch_show_not_found.json",  # stored tvmaze id TVmaze 404s on
    "lezwatch_show_imdb_only.json",  # joins via imdb lookup
]
CHARACTER_FILES = [
    "lezwatch_character_camille.json",  # no recorded death, actor resolves
    "lezwatch_character_marielle.json",  # recorded death, actor does not resolve
]

TAXONOMY_REST_BASES = [
    "trope",
    "cliche",
    "gender",
    "sexuality",
    "romantic",
    "station",
    "genre",
    "country",
    "format",
    "trigger",
    "intersection",
    "star",
]


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def _json_response(data, *, status=200, headers=None):
    return httpx.Response(status, json=data, headers=headers or {})


def build_handler(*, grant_present: bool = True):
    """A deterministic stand-in for LezWatch.TV + TVmaze, built entirely from
    fixtures captured from the real APIs on 2026-09-13. No network is used."""
    shows = [_load(f) for f in SHOW_FILES]
    characters = [_load(f) for f in CHARACTER_FILES]
    taxonomies = {rb: _load(f"taxonomies/{rb}.json") for rb in TAXONOMY_REST_BASES}
    actors = _load("actors_export.json")
    id_list_shows = _load("lezwatch_id_list_shows.json")
    id_list_characters = _load("lezwatch_id_list_characters.json")
    tvmaze_derry = _load("tvmaze_show_derry_girls.json")
    tvmaze_imdb_only = _load("tvmaze_show_imdb_only.json")

    def tos(_params):
        text = f"<p>You are welcome to {GRANT_SENTENCE if grant_present else 'do something else entirely'}.</p>"
        return httpx.Response(200, text=text)

    def paged(records):
        # `per_page=1` is the pipeline's "how many are available?" probe.
        def route(params):
            if params.get("per_page") == "1":
                return _json_response(
                    [{"id": records[0]["id"]}], headers={"X-WP-Total": str(len(records))}
                )
            return _json_response(
                records, headers={"X-WP-Total": str(len(records)), "X-WP-TotalPages": "1"}
            )

        return route

    def imdb_lookup(params):
        if params.get("imdb") == "tt8888882":
            return _json_response({"id": 55555})
        return httpx.Response(404, json={"message": "not found"})

    routes = {
        "/tos/": tos,
        "/wp-json/wp/v2/show": paged(shows),
        "/wp-json/wp/v2/character": paged(characters),
        "/wp-json/lwtv/v1/export/raw/actors/": lambda _p: _json_response(actors),
        "/wp-json/lwtv/v1/export/list/shows/": lambda _p: _json_response(id_list_shows),
        "/wp-json/lwtv/v1/export/list/characters/": lambda _p: _json_response(id_list_characters),
        "/updates/shows": lambda _p: _json_response({}),
        "/shows/33320": lambda _p: _json_response(tvmaze_derry),
        "/shows/55555": lambda _p: _json_response(tvmaze_imdb_only),
        "/shows/9999999": lambda _p: httpx.Response(404, json={"message": "not found"}),
        "/lookup/shows": imdb_lookup,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        path = url.path
        params = {k: v[0] for k, v in parse_qs(str(url.query, "utf-8")).items()}
        route = routes.get(path)
        if route is not None:
            return route(params)
        rest_base = path.rstrip("/").rsplit("/", 1)[-1]
        if path.startswith("/wp-json/wp/v2/") and rest_base in taxonomies:
            terms = taxonomies[rest_base]
            return _json_response(
                terms, headers={"X-WP-TotalPages": "1", "X-WP-Total": str(len(terms))}
            )
        raise AssertionError(f"unexpected request: {request.method} {url}")

    return handler


@pytest.fixture
def mock_transport():
    return httpx.MockTransport(build_handler())


@pytest.fixture
def mock_transport_no_grant():
    return httpx.MockTransport(build_handler(grant_present=False))


@pytest.fixture
def no_sleep():
    calls: list[float] = []

    def sleep(seconds: float) -> None:
        calls.append(seconds)

    return sleep, calls
