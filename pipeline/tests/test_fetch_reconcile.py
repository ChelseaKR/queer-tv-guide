"""The incremental LezWatch fetch: the cursor overlap and the id reconciliation.

The published snapshot once lacked 3 shows and 10 characters that LezWatch
lists, while every nightly run logged "0 fetched": the cursor had moved past the
missing records, and nothing asked for them by id. Two things are pinned here.

1. The cursor. LezWatch compares `modified_after` with the site's local time
   (UTC-4 in September), so a cursor taken from `modified_gmt` skips a record
   edited within that offset after it. `FakeSite` reproduces that comparison,
   and the negative control turns the overlap off to show the record is lost.
2. The id list decides membership. A listed id the cache lacks is fetched by
   id; a cached id the list lacks is removed only when the site says it is not
   published; a listed id that cannot be fetched fails the run with its number.

Every control asserts its sabotage landed (the record really is missing, the old
`find_deleted` really would have removed it) before it asserts the outcome.
Offline: httpx.MockTransport and a recording sleep.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import httpx
import pytest

from qtv_pipeline import build as build_mod
from qtv_pipeline import cli, lezwatch
from qtv_pipeline.http import FetchError, PacedClient

from .conftest import _load, build_handler

SITE_OFFSET = timedelta(hours=-4)  # LezWatch's local time on 2026-09-17
FMT = lezwatch.CURSOR_FORMAT


def _local(gmt: str) -> str:
    return (datetime.strptime(gmt, FMT) + SITE_OFFSET).strftime(FMT)


class FakeSite:
    """LezWatch's `wp/v2/{show,character}` and `lwtv/v1/export/list/*`, faithful
    to the behaviors the mirror depends on: `modified_after` is compared with the
    site's local time, `status=publish` hides everything else, `include` narrows
    to ids, and the export list can lag the site."""

    def __init__(self, *, honors_include: bool = True):
        self.records: dict[str, dict[int, dict]] = {"show": {}, "character": {}}
        self.list_omits: dict[str, set[int]] = {"shows": set(), "characters": set()}
        self.honors_include = honors_include
        self.requests: list[tuple[str, dict[str, str]]] = []

    def add(self, rest_base: str, record_id: int, gmt: str, *, status: str = "publish") -> dict:
        record = {
            "id": record_id,
            "slug": f"{rest_base}-{record_id}",
            "status": status,
            "modified_gmt": gmt,
            "title": {"rendered": f"{rest_base} {record_id}"},
        }
        self.records[rest_base][record_id] = record
        return record

    def include_requests(self, rest_base: str) -> list[list[int]]:
        return [
            [int(i) for i in params["include"].split(",")]
            for path, params in self.requests
            if path.endswith(f"/wp/v2/{rest_base}") and "include" in params
        ]

    def list_requests(self, rest_base: str) -> list[dict[str, str]]:
        return [
            params
            for path, params in self.requests
            if path.endswith(f"/wp/v2/{rest_base}") and "include" not in params
        ]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        self.requests.append((request.url.path, params))
        path = request.url.path
        for kind, rest_base in (("shows", "show"), ("characters", "character")):
            if path == f"/wp-json/lwtv/v1/export/list/{kind}/":
                items = [
                    {"uid": i, "id": f"{rest_base}-{i}", "name": f"{rest_base} {i}"}
                    for i, r in sorted(self.records[rest_base].items())
                    if r["status"] == "publish" and i not in self.list_omits[kind]
                ]
                return httpx.Response(200, json=items)
            if path == f"/wp-json/wp/v2/{rest_base}":
                return self._collection(rest_base, params)
        raise AssertionError(f"unexpected request: {request.url}")

    def _collection(self, rest_base: str, params: dict[str, str]) -> httpx.Response:
        rows = [r for r in self.records[rest_base].values() if r["status"] == "publish"]
        if params.get("include") and self.honors_include:
            wanted = {int(i) for i in params["include"].split(",")}
            rows = [r for r in rows if r["id"] in wanted]
        if "modified_after" in params:
            rows = [r for r in rows if _local(r["modified_gmt"]) > params["modified_after"]]
        rows.sort(key=lambda r: r["modified_gmt"])
        per_page = int(params.get("per_page", "10"))
        page = int(params.get("page", "1"))
        window = rows[(page - 1) * per_page : page * per_page]
        wanted_fields = params.get("_fields", "").split(",")
        body = [{k: v for k, v in r.items() if k in wanted_fields} for r in window]
        return httpx.Response(
            200,
            json=body,
            headers={
                "X-WP-Total": str(len(rows)),
                "X-WP-TotalPages": str(-(-len(rows) // per_page)),
            },
        )


def _client(site: FakeSite, sleep) -> PacedClient:
    return PacedClient(transport=httpx.MockTransport(site), sleep=sleep)


def _cache_ids(cache_dir, rest_base: str) -> set[int]:
    subdir = cache_dir / "lezwatch" / ("shows" if rest_base == "show" else "characters")
    return {int(p.stem) for p in subdir.glob("*.json")} if subdir.exists() else set()


def _set_cursor(cache_dir, **cursor: str) -> None:
    path = cache_dir / "lezwatch" / "cursor.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cursor))


def _cursor(cache_dir) -> dict[str, str]:
    return json.loads((cache_dir / "lezwatch" / "cursor.json").read_text())


# ---- the cursor overlap ---------------------------------------------------------


def test_an_incremental_request_looks_back_a_day_before_the_cursor(tmp_path, no_sleep):
    sleep, _ = no_sleep
    site = FakeSite()
    _set_cursor(tmp_path, shows="2026-09-17T19:07:39")
    with _client(site, sleep) as client:
        lezwatch.fetch_shows(client, tmp_path)
    assert timedelta(hours=24) == lezwatch.CURSOR_OVERLAP  # what pipeline/README.md promises
    assert site.list_requests("show")[0]["modified_after"] == "2026-09-16T19:07:39"


def test_a_record_edited_within_the_sites_offset_after_the_cursor_is_not_skipped(
    tmp_path, no_sleep
):
    """The measured defect. The cursor is show A's modified_gmt; show B is edited
    one hour 52 minutes later in GMT, which is *earlier* than the cursor in the
    site's local time, so an unpadded `modified_after` never returns it."""
    sleep, _ = no_sleep
    site = FakeSite()
    site.add("show", 99118, "2026-09-17T19:07:39")
    site.add("show", 99200, "2026-09-17T21:00:00")
    _set_cursor(tmp_path, shows="2026-09-17T19:07:39")

    with _client(site, sleep) as client:
        result, cursor = lezwatch.fetch_shows(client, tmp_path)

    assert _cache_ids(tmp_path, "show") == {99118, 99200}  # B was fetched, and so was A again
    assert result.fetched == 2
    assert cursor["shows"] == "2026-09-17T21:00:00"  # advances to the newest record seen
    assert _cursor(tmp_path) == {"shows": "2026-09-17T21:00:00"}  # and is stored unpadded


def test_without_the_overlap_that_record_is_lost(tmp_path, no_sleep, monkeypatch):
    """Negative control for the test above: with the overlap off (the old
    behavior) the same site returns nothing, so the fake does reproduce the skip."""
    sleep, _ = no_sleep
    monkeypatch.setattr(lezwatch, "CURSOR_OVERLAP", timedelta(0))
    site = FakeSite()
    site.add("show", 99200, "2026-09-17T21:00:00")
    _set_cursor(tmp_path, shows="2026-09-17T19:07:39")

    with _client(site, sleep) as client:
        result, _cursor_now = lezwatch.fetch_shows(client, tmp_path)

    assert site.list_requests("show")[0]["modified_after"] == "2026-09-17T19:07:39"
    assert result.fetched == 0
    assert _cache_ids(tmp_path, "show") == set()  # skipped, exactly as in production


def test_the_cursor_never_moves_backward_when_the_overlap_returns_older_records(tmp_path, no_sleep):
    sleep, _ = no_sleep
    site = FakeSite()
    site.add("show", 1, "2026-09-17T10:00:00")  # inside the 24 h look-back, older than the cursor
    _set_cursor(tmp_path, shows="2026-09-17T19:07:39")
    with _client(site, sleep) as client:
        result, cursor = lezwatch.fetch_shows(client, tmp_path)
    assert result.fetched == 1
    assert cursor["shows"] == "2026-09-17T19:07:39"
    assert _cursor(tmp_path) == {"shows": "2026-09-17T19:07:39"}


def test_an_unreadable_cursor_means_a_full_fetch(tmp_path, no_sleep):
    sleep, _ = no_sleep
    site = FakeSite()
    site.add("show", 1, "2026-01-01T00:00:00")
    _set_cursor(tmp_path, shows="last night")
    with _client(site, sleep) as client:
        result, cursor = lezwatch.fetch_shows(client, tmp_path)
    assert "modified_after" not in site.list_requests("show")[0]
    assert result.fetched == 1
    assert cursor["shows"] == "2026-01-01T00:00:00"


# ---- reconciling with the id list -----------------------------------------------


def _reconcile(site, cache_dir, sleep, *, kind: str = "shows"):
    rest_base = "show" if kind == "shows" else "character"
    with _client(site, sleep) as client:
        ids = lezwatch.fetch_id_list(client, cache_dir, kind=kind)
        return lezwatch.reconcile(client, cache_dir, kind=kind, live_ids=ids), rest_base


def _cache(cache_dir, rest_base: str, *ids: int) -> None:
    subdir = cache_dir / "lezwatch" / ("shows" if rest_base == "show" else "characters")
    subdir.mkdir(parents=True, exist_ok=True)
    for i in ids:
        (subdir / f"{i}.json").write_text(json.dumps({"id": i, "stale": True}))


def test_an_id_the_list_has_and_the_cache_lacks_is_fetched_by_id(tmp_path, no_sleep):
    sleep, _ = no_sleep
    site = FakeSite()
    for i in (1, 2, 99118):
        site.add("show", i, "2026-09-17T19:07:39")
    _cache(tmp_path, "show", 1, 2)  # 99118 was seen once, then lost from the cache
    live = [{"uid": 1}, {"uid": 2}, {"uid": 99118}]
    # Sabotage landed: the old path (find_deleted) sees nothing wrong, and the
    # cursor is past the record, so nothing else would ever ask for it.
    assert lezwatch.find_deleted(tmp_path, kind="shows", live_ids=live) == []
    _set_cursor(tmp_path, shows="2026-09-17T19:07:39")
    assert 99118 not in _cache_ids(tmp_path, "show")

    outcome, _ = _reconcile(site, tmp_path, sleep)

    assert outcome.refetched == [99118]
    assert _cache_ids(tmp_path, "show") == {1, 2, 99118}
    assert json.loads((tmp_path / "lezwatch" / "shows" / "99118.json").read_text())["slug"] == (
        "show-99118"
    )
    fetch = site.include_requests("show")
    assert fetch == [[99118]]
    asked = next(p for path, p in site.requests if p.get("include") == "99118")
    assert asked["status"] == "publish"
    assert asked["_fields"] == lezwatch.SHOW_FIELDS  # the same fields as the list fetch


def test_characters_are_reconciled_the_same_way(tmp_path, no_sleep):
    sleep, _ = no_sleep
    site = FakeSite()
    site.add("character", 99041, "2026-09-17T19:10:23")
    site.add("character", 99060, "2026-09-17T19:10:23")
    _cache(tmp_path, "character", 99060)
    outcome, _ = _reconcile(site, tmp_path, sleep, kind="characters")
    assert outcome.refetched == [99041]
    assert _cache_ids(tmp_path, "character") == {99041, 99060}
    assert site.include_requests("character") == [[99041]]


def test_many_missing_ids_are_fetched_a_hundred_to_a_request(tmp_path, no_sleep):
    sleep, _ = no_sleep
    site = FakeSite()
    for i in range(1, 251):
        site.add("show", i, "2026-09-17T19:07:39")
    outcome, _ = _reconcile(site, tmp_path, sleep)
    assert len(outcome.refetched) == 250
    assert [len(batch) for batch in site.include_requests("show")] == [100, 100, 50]
    assert _cache_ids(tmp_path, "show") == set(range(1, 251))


def test_a_cached_record_missing_from_a_lagging_list_survives(tmp_path, no_sleep):
    sleep, _ = no_sleep
    site = FakeSite()
    for i in (1, 2, 3):
        site.add("show", i, "2026-09-17T19:07:39")
    site.list_omits["shows"] = {3}  # the list has not caught up with show 3
    _cache(tmp_path, "show", 1, 2, 3)
    live = [{"uid": 1}, {"uid": 2}]
    # Sabotage landed: the old code removed exactly this record.
    assert lezwatch.find_deleted(tmp_path, kind="shows", live_ids=live) == [3]

    outcome, _ = _reconcile(site, tmp_path, sleep)

    assert outcome.removed == []
    assert outcome.kept == [3]
    assert _cache_ids(tmp_path, "show") == {1, 2, 3}


def test_a_record_that_is_no_longer_published_is_removed(tmp_path, no_sleep):
    sleep, _ = no_sleep
    site = FakeSite()
    site.add("show", 1, "2026-09-17T19:07:39")
    site.add("show", 2, "2026-09-17T19:07:39", status="trash")
    site.add("show", 3, "2026-09-17T19:07:39", status="draft")
    _cache(tmp_path, "show", 1, 2, 3, 4)  # 4 no longer exists at all
    outcome, _ = _reconcile(site, tmp_path, sleep)
    assert outcome.removed == [2, 3, 4]
    assert outcome.kept == []
    assert _cache_ids(tmp_path, "show") == {1}


def test_a_listed_id_that_cannot_be_fetched_fails_the_run_naming_it(tmp_path, no_sleep):
    sleep, _ = no_sleep
    site = FakeSite()
    site.add("show", 1, "2026-09-17T19:07:39")
    site.add("show", 99033, "2026-09-17T19:07:39")
    _cache(tmp_path, "show", 1)
    with _client(site, sleep) as client:
        live = [{"uid": 1}, {"uid": 99033}, {"uid": 99091}, {"uid": 99118}]  # last two: unknown
        with pytest.raises(FetchError) as failure:
            lezwatch.reconcile(client, tmp_path, kind="shows", live_ids=live)
    message = str(failure.value)
    assert "99091" in message and "99118" in message
    assert "99033" not in message  # the one that could be fetched is not blamed
    assert "2 id(s)" in message
    assert 99033 in _cache_ids(tmp_path, "show")  # what could be healed was


def test_a_server_that_ignores_include_is_never_read_as_deleting_everything(tmp_path, no_sleep):
    sleep, _ = no_sleep
    ids = (1, 2, 3, 4)
    site = FakeSite(honors_include=False)
    for i in ids:
        site.add("show", i, "2026-09-17T19:07:39")
    _cache(tmp_path, "show", *ids, 50, 51)  # 50 and 51 are cached but not in the list
    live = [{"uid": i} for i in ids]
    with _client(site, sleep) as client, pytest.raises(FetchError, match="not asked for"):
        lezwatch.reconcile(client, tmp_path, kind="shows", live_ids=live)
    assert _cache_ids(tmp_path, "show") == {*ids, 50, 51}  # nothing was removed

    # Control: the identical cache and list, against a server that honors include.
    honest = FakeSite()
    for i in ids:
        honest.add("show", i, "2026-09-17T19:07:39")
    honest.add("show", 50, "2026-09-17T19:07:39")  # 50 is still published
    with _client(honest, sleep) as client:
        outcome = lezwatch.reconcile(client, tmp_path, kind="shows", live_ids=live)
    assert outcome.kept == [50] and outcome.removed == [51]


def test_a_cache_that_agrees_with_the_list_costs_no_extra_requests(tmp_path, no_sleep):
    """The crawl budget: reconciling is free when nothing is out of step."""
    sleep, _ = no_sleep
    site = FakeSite()
    for i in (1, 2, 3):
        site.add("show", i, "2026-09-17T19:07:39")
    _cache(tmp_path, "show", 1, 2, 3)
    outcome, _ = _reconcile(site, tmp_path, sleep)
    assert (outcome.refetched, outcome.removed, outcome.kept) == ([], [], [])
    assert site.include_requests("show") == []
    assert [path for path, _ in site.requests] == ["/wp-json/lwtv/v1/export/list/shows/"]


# ---- through run_fetch ----------------------------------------------------------


def _world(site_ids: list[int], *, serve: dict[int, dict]):
    """The whole fixture-backed world (tos, taxonomies, actors, TVmaze), with the
    show endpoints replaced: incremental lists are empty ("nothing modified"),
    `include` serves from `serve`, and the export list names `site_ids`."""
    base = build_handler()
    log: list[tuple[str, dict[str, str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path, params = request.url.path, dict(request.url.params)
        if path == "/wp-json/lwtv/v1/export/list/shows/":
            return httpx.Response(200, json=[{"uid": i, "id": f"show-{i}"} for i in site_ids])
        if path == "/wp-json/wp/v2/show" and "include" in params:
            log.append((path, params))
            wanted = {int(i) for i in params["include"].split(",")}
            rows = [serve[i] for i in sorted(wanted) if i in serve]
            return httpx.Response(200, json=rows, headers={"X-WP-Total": str(len(rows))})
        if path == "/wp-json/wp/v2/show" and "modified_after" in params:
            return httpx.Response(200, json=[], headers={"X-WP-Total": "0", "X-WP-TotalPages": "0"})
        return base(request)

    return handler, log


def _fixture_shows() -> dict[int, dict]:
    from .conftest import SHOW_FILES

    shows = [_load(f) for f in SHOW_FILES]
    return {s["id"]: s for s in shows}


def _run_fetch(cache_dir, handler, sleep, *, full: bool = False, log=None):
    def factory(**kwargs):
        return PacedClient(transport=httpx.MockTransport(handler), sleep=sleep, **kwargs)

    return build_mod.run_fetch(
        cache_dir, full=full, log=(log.append if log is not None else (lambda _m: None)),
        client_factory=factory,
    )  # fmt: skip


def test_run_fetch_heals_a_record_the_cache_lost(tmp_path, no_sleep):
    sleep, _ = no_sleep
    shows = _fixture_shows()
    handler, include_log = _world(sorted(shows), serve=shows)
    _run_fetch(tmp_path, handler, sleep, full=True)  # a first, complete mirror
    lost = sorted(shows)[0]
    (tmp_path / "lezwatch" / "shows" / f"{lost}.json").unlink()
    assert lost not in _cache_ids(tmp_path, "show")  # the sabotage: the cache lost a record
    include_log.clear()

    messages: list[str] = []
    _run_fetch(tmp_path, handler, sleep, log=messages)  # the nightly, incremental run

    assert lost in _cache_ids(tmp_path, "show")
    assert [p["include"] for _path, p in include_log] == [str(lost)]
    assert any("1 in the id list but not the cache, fetched by id" in m for m in messages)


def test_run_fetch_without_reconciling_leaves_the_record_lost(tmp_path, no_sleep, monkeypatch):
    """Negative control for the test above: turn reconcile into a no-op and the
    same nightly run passes with the record still missing, which is the bug."""
    sleep, _ = no_sleep
    shows = _fixture_shows()
    handler, _log = _world(sorted(shows), serve=shows)
    _run_fetch(tmp_path, handler, sleep, full=True)
    lost = sorted(shows)[0]
    (tmp_path / "lezwatch" / "shows" / f"{lost}.json").unlink()

    monkeypatch.setattr(lezwatch, "reconcile", lambda *a, **k: lezwatch.Reconciliation([], [], []))
    _run_fetch(tmp_path, handler, sleep)

    assert lost not in _cache_ids(tmp_path, "show")


def test_run_fetch_says_what_it_removed_and_what_it_kept(tmp_path, no_sleep):
    sleep, _ = no_sleep
    shows = _fixture_shows()
    lagging = {**shows, 555: {"id": 555, "slug": "still-published"}}
    handler, _log = _world(sorted(shows), serve=lagging)  # the list omits 555, the site has it
    _run_fetch(tmp_path, handler, sleep, full=True)
    _cache(tmp_path, "show", 555, 556)  # 556: cached, unlisted, and gone from the site

    messages: list[str] = []
    _run_fetch(tmp_path, handler, sleep, log=messages)

    assert _cache_ids(tmp_path, "show") == {*shows, 555}
    assert "shows: 1 removed from cache (no longer published)" in messages
    assert "shows: 1 missing from the id list but still published; kept" in messages


def test_run_fetch_fails_when_a_listed_show_cannot_be_fetched(tmp_path, no_sleep):
    sleep, _ = no_sleep
    shows = _fixture_shows()
    handler, _log = _world([*sorted(shows), 99118], serve=shows)  # 99118: listed, unservable
    with pytest.raises(FetchError, match="99118"):
        _run_fetch(tmp_path, handler, sleep, full=True)


def test_the_cli_reports_a_fetch_failure_plainly(tmp_path, monkeypatch, capsys):
    def boom(cache_dir, *, full, log):
        raise FetchError("shows: 1 id(s) in LezWatch's list are not in the mirror: 99118")

    monkeypatch.setattr(build_mod, "run_fetch", boom)
    assert cli.main(["fetch", "--cache", str(tmp_path / "cache")]) == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("fetch failed: shows: 1 id(s)")
    assert "Traceback" not in captured.err
