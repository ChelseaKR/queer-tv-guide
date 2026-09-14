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
    "trope", "cliche", "gender", "sexuality", "romantic",
    "station", "genre", "country", "format", "trigger", "intersection", "star",
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

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        path = url.path
        params = {k: v[0] for k, v in parse_qs(str(url.query, "utf-8")).items()}

        if path == "/tos/":
            text = f"<p>You are welcome to {GRANT_SENTENCE if grant_present else 'do something else entirely'}.</p>"
            return httpx.Response(200, text=text)

        if path.startswith("/wp-json/wp/v2/") and path.rstrip("/").rsplit("/", 1)[-1] in taxonomies:
            rest_base = path.rstrip("/").rsplit("/", 1)[-1]
            return _json_response(
                taxonomies[rest_base], headers={"X-WP-TotalPages": "1", "X-WP-Total": str(len(taxonomies[rest_base]))}
            )

        if path == "/wp-json/wp/v2/show":
            if params.get("per_page") == "1":
                return _json_response([{"id": shows[0]["id"]}], headers={"X-WP-Total": str(len(shows))})
            return _json_response(
                shows, headers={"X-WP-Total": str(len(shows)), "X-WP-TotalPages": "1"}
            )

        if path == "/wp-json/wp/v2/character":
            if params.get("per_page") == "1":
                return _json_response(
                    [{"id": characters[0]["id"]}], headers={"X-WP-Total": str(len(characters))}
                )
            return _json_response(
                characters, headers={"X-WP-Total": str(len(characters)), "X-WP-TotalPages": "1"}
            )

        if path == "/wp-json/lwtv/v1/export/raw/actors/":
            return _json_response(actors)

        if path == "/wp-json/lwtv/v1/export/list/shows/":
            return _json_response(id_list_shows)

        if path == "/wp-json/lwtv/v1/export/list/characters/":
            return _json_response(id_list_characters)

        if path == "/updates/shows":
            return _json_response({})

        if path == "/shows/33320":
            return _json_response(tvmaze_derry)

        if path == "/shows/55555":
            return _json_response(tvmaze_imdb_only)

        if path == "/shows/9999999":
            return httpx.Response(404, json={"message": "not found"})

        if path == "/lookup/shows":
            if params.get("imdb") == "tt8888882":
                return _json_response({"id": 55555})
            return httpx.Response(404, json={"message": "not found"})

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
