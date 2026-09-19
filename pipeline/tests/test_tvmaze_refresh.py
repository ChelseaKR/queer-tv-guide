"""Which shows the nightly run asks TVmaze about again.

`tvmaze.sync_shows` skips a matched show whose cached status is `Ended`,
`Canceled` or `To Be Determined` unless `/updates/shows?since=week` lists its
TVmaze id (`_needs_refresh`). The end-to-end tests run full and answer
`/updates/shows` with `{}`, so that rule never ran. These tests pin it by
counting the requests a fake TVmaze actually receives, and each one has a
control that flips the single input the rule depends on.

Offline: httpx.MockTransport and a recording sleep.
"""

from __future__ import annotations

import json

import httpx
import pytest

from qtv_pipeline import tvmaze
from qtv_pipeline.http import PacedClient


class FakeTvmaze:
    """TVmaze as far as the sync touches it, with a log of every request."""

    def __init__(self, *, updates: dict[str, int] | None = None, status: str = "Running"):
        self.updates = updates or {}
        self.status = status
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.imdb_known: dict[str, int] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.requests.append((path, dict(request.url.params)))
        if path == "/updates/shows":
            return httpx.Response(200, json=self.updates)
        if path == "/lookup/shows":
            imdb = request.url.params.get("imdb", "")
            if imdb in self.imdb_known:
                return httpx.Response(200, json={"id": self.imdb_known[imdb]})
            return httpx.Response(404, json={"message": "no such show"})
        if path.startswith("/shows/"):
            tvmaze_id = int(path.rsplit("/", 1)[-1])
            return httpx.Response(200, json={"id": tvmaze_id, "status": self.status})
        raise AssertionError(f"unexpected request: {request.url}")

    def show_requests(self) -> list[int]:
        return sorted(
            int(p.rsplit("/", 1)[-1]) for p, _ in self.requests if p.startswith("/shows/")
        )

    def paths(self) -> list[str]:
        return [p for p, _ in self.requests]


def _show(lwtv_id: int, tvmaze_id: int | None, *, imdb: str | None = None) -> dict:
    meta = {"lezshows_tvmaze_id": [str(tvmaze_id)]} if tvmaze_id is not None else {}
    acf = {"lezshows_imdb": imdb} if imdb else {}
    return {"id": lwtv_id, "acf": acf, "meta": meta}


def _join(tvmaze_id: int, status: str, *, matched: bool = True) -> dict:
    return {
        "method": "lwtv_tvmaze_id",
        "matched": matched,
        "tvmaze_id": tvmaze_id if matched else None,
        "status": status if matched else None,
        "reason": "ok" if matched else "not_found",
    }


def _seed(cache_dir, joins: dict[str, dict]) -> None:
    path = cache_dir / "tvmaze" / "joins.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(joins))


def _sync(cache_dir, site, shows, sleep, *, full: bool = False):
    with PacedClient(transport=httpx.MockTransport(site), sleep=sleep) as client:
        return tvmaze.sync_shows(client, cache_dir, shows, full=full)


# ---- the rule itself ------------------------------------------------------------


@pytest.mark.parametrize(
    ("cached", "updated", "expected"),
    [
        (None, set(), True),  # never fetched
        (_join(1, "Running", matched=False), set(), True),  # a miss is retried
        (_join(1, "Running"), set(), True),  # airing shows always refresh
        (_join(1, "In Development"), set(), True),
        (_join(1, "Ended"), set(), False),  # finished and not reported changed
        (_join(1, "Canceled"), set(), False),
        (_join(1, "To Be Determined"), set(), False),
        (_join(1, "Ended"), {1}, True),  # finished but TVmaze says it changed
        (_join(1, "Ended"), {2}, False),  # a different show changed
    ],
)
def test_needs_refresh_truth_table(cached, updated, expected):
    assert tvmaze._needs_refresh(cached, updated) is expected


# ---- the rule as the sync applies it --------------------------------------------


def test_a_finished_show_is_not_refetched_unless_tvmaze_reports_it_changed(tmp_path, no_sleep):
    sleep, _ = no_sleep
    shows = [_show(1, 11), _show(2, 12), _show(3, 13), _show(4, 14), _show(5, 15)]
    _seed(
        tmp_path,
        {
            "1": _join(11, "Ended"),  # finished, unchanged: skipped
            "2": _join(12, "Running"),  # airing: always refreshed
            "3": _join(13, "Canceled"),  # finished, but in the updates set: refreshed
            # 4 was never fetched: fetched
            "5": _join(15, "Ended", matched=False),  # earlier miss: retried
        },
    )
    site = FakeTvmaze(updates={"13": 1_700_000_000})
    joins = _sync(tmp_path, site, shows, sleep)

    assert site.show_requests() == [12, 13, 14, 15]  # 11 (Ended, unchanged) is absent
    assert site.paths().count("/updates/shows") == 1
    assert dict(site.requests[0][1]) == {"since": "week"}
    assert joins["1"] == _join(11, "Ended")  # untouched
    assert joins["4"]["matched"] is True and joins["4"]["tvmaze_id"] == 14
    assert joins["5"]["matched"] is True  # the earlier miss resolved this time
    assert (tmp_path / "tvmaze" / "shows" / "11.json").exists() is False  # nothing was written
    assert (tmp_path / "tvmaze" / "shows" / "12.json").exists()


def test_the_same_finished_show_is_refetched_when_the_updates_set_names_it(tmp_path, no_sleep):
    """Control for the skip above: change only the updates set."""
    sleep, _ = no_sleep
    shows = [_show(1, 11)]
    _seed(tmp_path, {"1": _join(11, "Ended")})
    quiet = FakeTvmaze(updates={})
    _sync(tmp_path, quiet, shows, sleep)
    assert quiet.show_requests() == []

    changed = FakeTvmaze(updates={"11": 1_700_000_000})
    _sync(tmp_path, changed, shows, sleep)
    assert changed.show_requests() == [11]


def test_a_full_run_refetches_every_show_and_never_reads_the_updates_set(tmp_path, no_sleep):
    sleep, _ = no_sleep
    shows = [_show(1, 11), _show(2, 12)]
    _seed(tmp_path, {"1": _join(11, "Ended"), "2": _join(12, "Canceled")})
    site = FakeTvmaze()
    _sync(tmp_path, site, shows, sleep, full=True)
    assert site.show_requests() == [11, 12]
    assert "/updates/shows" not in site.paths()


def test_the_cached_status_is_replaced_by_what_tvmaze_now_says(tmp_path, no_sleep):
    sleep, _ = no_sleep
    _seed(tmp_path, {"1": _join(11, "Running")})
    site = FakeTvmaze(status="Ended")
    joins = _sync(tmp_path, site, [_show(1, 11)], sleep)
    assert joins["1"]["status"] == "Ended"
    persisted = json.loads((tmp_path / "tvmaze" / "joins.json").read_text())
    assert persisted["1"]["status"] == "Ended"


# ---- the imdb fallback ----------------------------------------------------------


def test_an_imdb_lookup_that_finds_nothing_is_a_miss_with_no_show_request(tmp_path, no_sleep):
    sleep, _ = no_sleep
    site = FakeTvmaze()
    joins = _sync(tmp_path, site, [_show(7, None, imdb="tt0000001")], sleep)
    assert joins["7"]["matched"] is False
    assert joins["7"]["reason"] == "not_found"
    assert joins["7"]["tvmaze_id"] is None and joins["7"]["status"] is None
    assert "/lookup/shows" in site.paths()
    assert site.show_requests() == []  # no /shows/<id> to follow

    # Control: when the lookup does answer, the follow-up request is made.
    found = FakeTvmaze()
    found.imdb_known["tt0000001"] = 77
    joins = _sync(tmp_path / "second", found, [_show(7, None, imdb="tt0000001")], sleep)
    assert joins["7"]["matched"] is True and joins["7"]["tvmaze_id"] == 77
    assert found.show_requests() == [77]
