"""A TVmaze 5xx on one show must not fail the nightly snapshot.

2026-10-21: api.tvmaze.com/shows/1709 answered 502 on the first request and on both
retries, `qtv fetch` exited 1, and the published snapshot went 42 h old against a
30 h alarm. These tests pin the repair: a show TVmaze keeps failing for keeps what
the cache already had (or stays unjoined, schedule unknown), the run counts it, and
only more than `degraded_limit` failures fail the run.

Every failure here is served by a fake TVmaze, and each test asserts the fake really
answered 502 (request counts), so a sabotage that silently did not apply cannot
read as a pass. Offline: httpx.MockTransport and a recording sleep.
"""

from __future__ import annotations

import json

import httpx
import pytest

from qtv_pipeline import normalize, tvmaze
from qtv_pipeline.http import FetchError, PacedClient, UpstreamUnavailable

from .conftest import build_handler

BODY_OLD = {"id": 1709, "status": "Running", "url": "https://www.tvmaze.com/shows/1709/x"}


class FlakyTvmaze:
    """Answers 502 (or `fail_status`) for the ids in `failing`; 200 for the rest."""

    def __init__(self, failing: set[int] | None = None, *, fail_status: int = 502):
        self.failing = failing or set()
        self.fail_status = fail_status
        self.hits: dict[int, int] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/updates/shows":
            return httpx.Response(200, json={})
        if path.startswith("/shows/"):
            tvmaze_id = int(path.rsplit("/", 1)[-1])
            self.hits[tvmaze_id] = self.hits.get(tvmaze_id, 0) + 1
            if tvmaze_id in self.failing:
                return httpx.Response(self.fail_status, text="Bad Gateway")
            return httpx.Response(200, json={"id": tvmaze_id, "status": "Ended"})
        raise AssertionError(f"unexpected request: {request.url}")


def _show(lwtv_id: int, tvmaze_id: int) -> dict:
    return {"id": lwtv_id, "acf": {}, "meta": {"lezshows_tvmaze_id": [str(tvmaze_id)]}}


def _join(tvmaze_id: int, status: str) -> dict:
    return {
        "method": "lwtv_tvmaze_id",
        "matched": True,
        "tvmaze_id": tvmaze_id,
        "status": status,
        "reason": "ok",
    }


def _seed(cache_dir, joins: dict, bodies: dict[int, dict]) -> None:
    (cache_dir / "tvmaze" / "shows").mkdir(parents=True, exist_ok=True)
    (cache_dir / "tvmaze" / "joins.json").write_text(json.dumps(joins))
    for tvmaze_id, body in bodies.items():
        (cache_dir / "tvmaze" / "shows" / f"{tvmaze_id}.json").write_text(json.dumps(body))


def _sync(cache_dir, site, shows, sleep, *, full=False):
    report = tvmaze.SyncReport()
    with PacedClient(transport=httpx.MockTransport(site), sleep=sleep) as client:
        try:
            joins = tvmaze.sync_shows(client, cache_dir, shows, full=full, report=report)
        except tvmaze.TvmazeDegraded:
            return None, report
    return joins, report


def test_a_show_tvmaze_keeps_failing_for_keeps_its_cached_fields(tmp_path, no_sleep):
    sleep, _ = no_sleep
    _seed(tmp_path, {"1": _join(1709, "Running")}, {1709: BODY_OLD})
    site = FlakyTvmaze({1709})
    joins, report = _sync(tmp_path, site, [_show(1, 1709), _show(2, 12)], sleep)

    assert site.hits[1709] == 3  # the 502 was served: first try plus both retries
    assert joins is not None
    assert report.degraded == ["1"] and report.attempted == 2
    assert joins["1"] == _join(1709, "Running")  # the previous join, untouched
    cached = json.loads((tmp_path / "tvmaze" / "shows" / "1709.json").read_text())
    assert cached == BODY_OLD
    assert joins["2"]["status"] == "Ended"  # the run went on to the next show
    schedule = normalize.normalize_schedule(joins["1"], tvmaze.load_tvmaze_show(tmp_path, 1709))
    assert schedule["schedule_known"] is True and schedule["status"] == "Running"


def test_control_the_same_show_is_refreshed_when_tvmaze_answers(tmp_path, no_sleep):
    """Flip only the sabotage: the cached values are replaced, so the test above
    could not have passed by the sync never touching the show."""
    sleep, _ = no_sleep
    _seed(tmp_path, {"1": _join(1709, "Running")}, {1709: BODY_OLD})
    site = FlakyTvmaze()
    joins, report = _sync(tmp_path, site, [_show(1, 1709)], sleep)
    assert site.hits[1709] == 1
    assert report.degraded == []
    assert joins["1"]["status"] == "Ended"
    assert (
        json.loads((tmp_path / "tvmaze" / "shows" / "1709.json").read_text())["status"] == "Ended"
    )


def test_a_show_with_nothing_cached_stays_unknown_not_not_found(tmp_path, no_sleep):
    sleep, _ = no_sleep
    site = FlakyTvmaze({1709})
    joins, report = _sync(tmp_path, site, [_show(1, 1709), _show(2, 12)], sleep)
    assert site.hits[1709] == 3
    assert report.degraded == ["1"]
    assert "1" not in joins  # no record, so nothing claims "not found" or "no key"
    assert "1" not in json.loads((tmp_path / "tvmaze" / "joins.json").read_text())
    schedule = normalize.normalize_schedule(joins.get("1"), None)
    assert schedule["schedule_known"] is False
    assert schedule["status"] is None and schedule["next_episode"] is None
    # Next night it is simply asked again.
    again = FlakyTvmaze()
    joins, report = _sync(tmp_path, again, [_show(1, 1709)], sleep)
    assert report.degraded == [] and joins["1"]["matched"] is True


def test_a_404_is_still_a_miss_and_a_403_is_still_fatal(tmp_path, no_sleep):
    """Only "try again later" failures are tolerated; a wrong request is not."""
    sleep, _ = no_sleep

    def not_found(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/updates/shows":
            return httpx.Response(200, json={})
        return httpx.Response(404, json={})

    joins, report = _sync(tmp_path, not_found, [_show(1, 5)], sleep)
    assert joins["1"]["reason"] == "not_found" and report.degraded == []

    forbidden = FlakyTvmaze({5}, fail_status=403)
    client = PacedClient(transport=httpx.MockTransport(forbidden), sleep=sleep)
    with client, pytest.raises(FetchError) as caught:
        tvmaze.sync_shows(client, tmp_path / "x", [_show(1, 5)])
    assert not isinstance(caught.value, UpstreamUnavailable)
    assert forbidden.hits[5] == 1


def test_a_run_fails_when_degraded_shows_pass_five_percent(tmp_path, no_sleep):
    sleep, _ = no_sleep
    shows = [_show(i, 1000 + i) for i in range(100)]
    assert tvmaze.degraded_limit(100) == 5

    at_limit = FlakyTvmaze({1000 + i for i in range(5)})
    joins, report = _sync(tmp_path / "a", at_limit, shows, sleep)
    assert all(at_limit.hits[1000 + i] == 3 for i in range(5))  # sabotage applied
    assert joins is not None and len(report.degraded) == 5

    over = FlakyTvmaze({1000 + i for i in range(6)})
    joins, report = _sync(tmp_path / "b", over, shows, sleep)
    assert all(over.hits[1000 + i] == 3 for i in range(6))
    assert joins is None  # TvmazeDegraded
    assert len(report.degraded) == 6


def test_a_small_run_tolerates_the_floor_and_an_outage_stops_early(tmp_path, no_sleep):
    sleep, _ = no_sleep
    shows = [_show(i, 2000 + i) for i in range(20)]
    assert tvmaze.degraded_limit(20) == tvmaze.DEGRADED_FLOOR == 2

    two = FlakyTvmaze({2000, 2001})
    joins, _ = _sync(tmp_path / "a", two, shows, sleep)
    assert two.hits[2000] == 3 and joins is not None  # 10% of the run, still tolerated

    outage = FlakyTvmaze({2000 + i for i in range(20)})
    joins, report = _sync(tmp_path / "b", outage, shows, sleep)
    assert joins is None
    assert sum(outage.hits.values()) == 9  # stopped after the third failed show, not twenty
    assert len(report.degraded) == 3


def test_end_to_end_a_502_on_one_show_still_publishes_with_the_count(tmp_path, no_sleep):
    """Two nightly runs over the fixture mirror; the second gets 502 for Derry Girls'
    TVmaze id. The fetch exits cleanly, run.json and the log carry the count, and the
    built snapshot still has last night's schedule for that show."""
    from qtv_pipeline import build as build_mod

    sleep, _ = no_sleep
    cache_dir = tmp_path / "cache"
    healthy = build_handler()
    served: list[int] = []

    def with_502(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/shows/33320":
            served.append(502)
            return httpx.Response(502, text="Bad Gateway")
        return healthy(request)

    def fetch(handler, lines):
        def factory(**kwargs):
            return PacedClient(transport=httpx.MockTransport(handler), sleep=sleep, **kwargs)

        return build_mod.run_fetch(cache_dir, full=True, log=lines.append, client_factory=factory)

    first_lines: list[str] = []
    first = fetch(healthy, first_lines)
    assert first["tvmaze"]["degraded_shows"] == 0

    lines: list[str] = []
    meta = fetch(with_502, lines)
    assert served == [502, 502, 502]  # the sabotage applied: request plus two retries
    assert meta["tvmaze"]["degraded_shows"] == 1
    assert json.loads((cache_dir / "run.json").read_text())["tvmaze"]["degraded_shows"] == 1
    assert any("1/3 shows degraded" in line for line in lines)

    doc = build_mod.run_build(
        cache_dir, tmp_path / "out", git_sha="deadbeef", workflow_run_id="1", log=lambda _m: None
    )
    derry = next(sh for sh in doc["shows"] if sh["schedule"]["tvmaze_id"] == 33320)
    assert derry["schedule"]["schedule_known"] is True
