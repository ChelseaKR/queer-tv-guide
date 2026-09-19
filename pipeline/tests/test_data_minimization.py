"""The pipeline keeps actor names and nothing else about real people.

LezWatch.TV's actor export carries each actor's sexuality, gender, birth and
death dates, and social links next to the name. Those describe real people,
and stored they would be L3 data (DATA-GOVERNANCE-STANDARD §0, §4): they could
out someone. The pipeline takes the name only (docs/data/lezwatch.md).

This plants a distinctive value in every other field of the export, runs the
real fetch and build over the fixture API, and requires that none of the
planted values appears anywhere in the mirror cache or the published output.
The actor's name must appear, which proves the export was fetched and used
rather than skipped.
"""

from __future__ import annotations

import httpx

from qtv_pipeline import build as build_mod
from qtv_pipeline.http import PacedClient

ACTOR_ID = 78146  # linked from the camille fixture's lezchars_actor
ACTOR_NAME = "Nia Cassidy"
PLANTED = {
    "sexuality": "PLANTED-SEXUALITY-7c1e",
    "gender": "PLANTED-GENDER-7c1e",
    "born": "PLANTED-BORN-7c1e",
    "died": "PLANTED-DIED-7c1e",
    "website": "https://planted-website-7c1e.invalid/",
    "imdb": "PLANTED-IMDB-7c1e",
    "wikipedia": "PLANTED-WIKIPEDIA-7c1e",
    "twitter": "PLANTED-TWITTER-7c1e",
    "instagram": "PLANTED-INSTAGRAM-7c1e",
}


def _handler_with_a_full_actor_record(fixture_transport: httpx.MockTransport):
    """The fixture API from conftest, with a complete actor record served."""
    base = fixture_transport.handler
    served: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wp-json/lwtv/v1/export/raw/actors/":
            record = {"uid": ACTOR_ID, "id": "an-actor", "name": ACTOR_NAME, **PLANTED}
            served.append(record)
            return httpx.Response(200, json=[record])
        return base(request)

    return handler, served


def _all_output_text(*dirs):
    return "\n".join(
        path.read_text(errors="replace") for d in dirs for path in d.rglob("*") if path.is_file()
    )


def test_actor_personal_fields_never_reach_the_cache_or_the_snapshot(
    tmp_path, mock_transport, no_sleep
):
    sleep, _ = no_sleep
    handler, served = _handler_with_a_full_actor_record(mock_transport)
    transport = httpx.MockTransport(handler)
    cache, out = tmp_path / "cache", tmp_path / "out"

    build_mod.run_fetch(
        cache,
        full=True,
        log=lambda _msg: None,
        client_factory=lambda **kw: PacedClient(transport=transport, sleep=sleep, **kw),
    )
    doc = build_mod.run_build(cache, out, log=lambda _msg: None)

    # The sabotage landed: the export really served every planted field.
    assert served, "the actor export was never requested"
    assert all(served[0][k] == v for k, v in PLANTED.items())
    # The path was exercised: the actor resolved by name on a character.
    actors = [a for c in doc["characters"] for a in c["actors"]]
    assert {"lwtv_id": ACTOR_ID, "slug": None, "name": ACTOR_NAME} in actors

    everything = _all_output_text(cache, out)
    assert ACTOR_NAME in everything
    leaked = sorted(field for field, value in PLANTED.items() if value in everything)
    assert leaked == []
