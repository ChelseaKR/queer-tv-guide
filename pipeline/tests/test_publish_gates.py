"""What the nightly run refuses to publish.

Three gates, each with the fault injected and its effect asserted first:

- The id list decides what is removed from the mirror, so an empty, renamed-key,
  truncated or non-list answer stops the run and removes nothing. The old
  `find_deleted` read all four as "delete these cached records"; each test
  recomputes that old outcome to show the fault it injects is a dangerous one.
- Gate 3, mirror completeness: the cache holds at least 99% of the source's
  `X-WP-Total`, and a total the source did not give is not waved through.
- The shrink gate: a snapshot that lost more than 2% of its shows or characters
  against the one it replaces is refused, unless `--allow-shrink` says it is meant.

Offline: httpx.MockTransport, the fixture-backed world of conftest.py, and a
recording sleep.
"""

from __future__ import annotations

import json

import httpx
import pytest

from qtv_pipeline import build as build_mod
from qtv_pipeline import cli, lezwatch
from qtv_pipeline.http import FetchError, PacedClient

from .conftest import build_handler


def _client(handler, sleep) -> PacedClient:
    return PacedClient(transport=httpx.MockTransport(handler), sleep=sleep)


def _cache_shows(cache_dir, ids) -> None:
    subdir = cache_dir / "lezwatch" / "shows"
    subdir.mkdir(parents=True, exist_ok=True)
    for i in ids:
        (subdir / f"{i}.json").write_text(json.dumps({"id": i}))


def _cached(cache_dir) -> set[int]:
    return {int(p.stem) for p in (cache_dir / "lezwatch" / "shows").glob("*.json")}


def _old_find_deleted(cached: set[int], answer) -> list[int]:
    """The behavior this replaces: a non-list became [], and any item without
    `uid` was skipped, so whatever was not recognized counted as deleted."""
    items = answer if isinstance(answer, list) else []
    live = {int(i["uid"]) for i in items if isinstance(i, dict) and "uid" in i}
    return sorted(cached - live)


# ---- the id list ----------------------------------------------------------------

# (answer, message the run stops with, what the old find_deleted made of it)
BAD_ANSWERS = [
    pytest.param(
        {"code": "rest_forbidden", "message": "no"}, "not a list", [1, 2, 3], id="an-error-object"
    ),
    pytest.param("maintenance", "not a list", [1, 2, 3], id="a-string"),
    pytest.param([], "empty list", [1, 2, 3], id="empty"),
    pytest.param(
        [{"id": 1}, {"id": 2}, {"id": 3}], "no numeric `uid`", [1, 2, 3], id="renamed-key"
    ),
    pytest.param([{"uid": 1}, {"name": "x"}], "1 of 2 items", [2, 3], id="one-item-without-uid"),
    pytest.param([{"uid": "abc"}], "no numeric `uid`", "crash", id="non-numeric-uid"),
    pytest.param([{"uid": None}], "no numeric `uid`", "crash", id="null-uid"),
]


def _assert_the_old_code_mishandled(answer, expected) -> None:
    """The fault landed: the old find_deleted either marked cached records deleted
    or crashed with an unexplained error on this answer."""
    if expected == "crash":
        with pytest.raises((ValueError, TypeError)):
            _old_find_deleted({1, 2, 3}, answer)
    else:
        assert _old_find_deleted({1, 2, 3}, answer) == expected


@pytest.mark.parametrize(("answer", "message", "old"), BAD_ANSWERS)
def test_a_malformed_id_list_stops_the_run_and_removes_nothing(
    tmp_path, no_sleep, answer, message, old
):
    sleep, _ = no_sleep
    _cache_shows(tmp_path, [1, 2, 3])
    ids_file = tmp_path / "lezwatch" / "ids" / "shows.json"
    ids_file.parent.mkdir(parents=True)
    ids_file.write_text('[{"uid": 1}, {"uid": 2}, {"uid": 3}]')  # the last good list

    _assert_the_old_code_mishandled(answer, old)

    def handler(request):
        return httpx.Response(200, json=answer)

    with _client(handler, sleep) as client, pytest.raises(FetchError, match=message):
        lezwatch.fetch_id_list(client, tmp_path, kind="shows")

    assert _cached(tmp_path) == {1, 2, 3}
    assert ids_file.read_text() == '[{"uid": 1}, {"uid": 2}, {"uid": 3}]'  # not overwritten


@pytest.mark.parametrize(("answer", "message", "old"), BAD_ANSWERS)
def test_find_deleted_and_reconcile_refuse_the_same_answers(
    tmp_path, no_sleep, answer, message, old
):
    sleep, _ = no_sleep
    _cache_shows(tmp_path, [1, 2, 3])
    _assert_the_old_code_mishandled(answer, old)
    with pytest.raises(FetchError, match=message):
        lezwatch.find_deleted(tmp_path, kind="shows", live_ids=answer)

    def no_requests(request):
        raise AssertionError("reconcile must refuse before it asks the site anything")

    with _client(no_requests, sleep) as client, pytest.raises(FetchError, match=message):
        lezwatch.reconcile(client, tmp_path, kind="shows", live_ids=answer)
    assert _cached(tmp_path) == {1, 2, 3}


def test_a_healthy_id_list_is_accepted_and_saved(tmp_path, no_sleep):
    """Control for the refusals above: the same call with a well-formed answer
    (uids as numbers or numeric strings) succeeds and is saved."""
    sleep, _ = no_sleep
    good = [{"uid": 1, "id": "show-1"}, {"uid": "2", "id": "show-2"}]
    with _client(lambda request: httpx.Response(200, json=good), sleep) as client:
        items = lezwatch.fetch_id_list(client, tmp_path, kind="shows")
    assert items == good
    assert json.loads((tmp_path / "lezwatch" / "ids" / "shows.json").read_text()) == good
    _cache_shows(tmp_path, [1, 2, 3])
    assert lezwatch.find_deleted(tmp_path, kind="shows", live_ids=good) == [3]


def test_a_truncated_id_list_is_refused_against_the_sources_total(tmp_path, no_sleep):
    sleep, _ = no_sleep
    _cache_shows(tmp_path, range(1, 201))
    truncated = [{"uid": i} for i in range(1, 151)]  # 150 of the 200 the source reports
    # The fault landed: 50 records would have been removed on this answer alone.
    assert len(_old_find_deleted(set(range(1, 201)), truncated)) == 50

    with (
        _client(lambda request: httpx.Response(200, json=truncated), sleep) as client,
        pytest.raises(FetchError, match=r"lists 150 shows but the source reports 200"),
    ):
        lezwatch.fetch_id_list(client, tmp_path, kind="shows", expected_total=200)
    with pytest.raises(FetchError, match="cut short"):
        lezwatch.find_deleted(tmp_path, kind="shows", live_ids=truncated, expected_total=200)
    assert len(_cached(tmp_path)) == 200

    # Control: without the total there is nothing to measure the list against, so
    # the total is what caught it.
    assert len(lezwatch.find_deleted(tmp_path, kind="shows", live_ids=truncated)) == 50


@pytest.mark.parametrize(("listed", "accepted"), [(198, True), (197, False), (200, True)])
def test_the_id_list_floor_is_ninety_nine_percent(listed, accepted):
    items = [{"uid": i} for i in range(listed)]
    if accepted:
        assert lezwatch.validate_id_list(items, kind="shows", expected_total=200) == items
    else:
        with pytest.raises(FetchError, match="cut short"):
            lezwatch.validate_id_list(items, kind="shows", expected_total=200)


def test_an_id_list_announced_over_two_pages_is_read_to_the_end(tmp_path, no_sleep):
    sleep, _ = no_sleep
    pages = {"1": [{"uid": 1}, {"uid": 2}], "2": [{"uid": 3}]}
    seen: list[str] = []

    def handler(request):
        page = request.url.params.get("page", "1")
        seen.append(page)
        return httpx.Response(200, json=pages[page], headers={"X-WP-TotalPages": "2"})

    with _client(handler, sleep) as client:
        items = lezwatch.fetch_id_list(client, tmp_path, kind="shows", expected_total=3)
    assert seen == ["1", "2"]
    assert [i["uid"] for i in items] == [1, 2, 3]


def test_run_fetch_stops_on_a_renamed_key_and_keeps_the_mirror(tmp_path, no_sleep):
    sleep, _ = no_sleep
    base = build_handler()

    def handler(request):
        if request.url.path == "/wp-json/lwtv/v1/export/list/shows/":
            return httpx.Response(200, json=[{"id": 25206}, {"id": 30001}])  # `uid` renamed
        return base(request)

    def factory(**kwargs):
        return PacedClient(transport=httpx.MockTransport(handler), sleep=sleep, **kwargs)

    # A first run against the honest world builds the mirror ...
    build_mod.run_fetch(tmp_path, full=True, log=lambda _m: None, client_factory=_honest(sleep))
    before = _cached(tmp_path)
    assert len(before) == 5
    # ... and the second, against a list with the key renamed, refuses and removes nothing.
    with pytest.raises(FetchError, match="no numeric `uid`"):
        build_mod.run_fetch(tmp_path, full=True, log=lambda _m: None, client_factory=factory)
    assert _cached(tmp_path) == before


def _honest(sleep):
    def factory(**kwargs):
        return PacedClient(transport=httpx.MockTransport(build_handler()), sleep=sleep, **kwargs)

    return factory


# ---- gate 3: mirror completeness ------------------------------------------------


@pytest.mark.parametrize(
    ("total", "held", "passes"),
    [(100, 100, True), (100, 99, True), (100, 98, False), (2275, 2253, True), (2275, 2252, False)],
)
def test_completeness_floor_is_ninety_nine_percent_of_the_source_total(total, held, passes):
    available = {"shows": total, "characters": total}
    if passes:
        build_mod._check_completeness(available, held, held)
        return
    with pytest.raises(build_mod.BuildError, match=f"{held} of the {total} shows"):
        build_mod._check_completeness(available, held, total)
    with pytest.raises(build_mod.BuildError, match=f"{held} of the {total} characters"):
        build_mod._check_completeness(available, total, held)


def test_a_total_the_source_did_not_give_is_not_waved_through():
    with pytest.raises(build_mod.BuildError, match="reported no total for shows"):
        build_mod._check_completeness({"shows": None, "characters": 5}, 5, 5)


@pytest.fixture
def mirror(tmp_path, no_sleep):
    """A complete mirror of the fixture world: 5 shows and 2 characters."""
    sleep, _ = no_sleep
    cache = tmp_path / "cache"
    build_mod.run_fetch(cache, full=True, log=lambda _m: None, client_factory=_honest(sleep))
    return cache


def _set_available(cache, **available) -> None:
    path = cache / "run.json"
    meta = json.loads(path.read_text())
    meta["lezwatch"]["available"].update(available)
    path.write_text(json.dumps(meta))


def test_a_mirror_short_of_the_source_total_builds_nothing(tmp_path, mirror):
    out = tmp_path / "out"
    _set_available(mirror, shows=10)  # the source has 10 shows; the mirror holds 5
    assert json.loads((mirror / "run.json").read_text())["lezwatch"]["available"]["shows"] == 10
    with pytest.raises(build_mod.BuildError) as failure:
        build_mod.run_build(mirror, out, log=lambda _m: None)
    assert "5 of the 10 shows LezWatch reports are cached (50.0%)" in str(failure.value)
    assert "at least 99% is required" in str(failure.value)
    assert not out.exists()  # nothing was written


def test_the_same_mirror_builds_when_it_is_complete(tmp_path, mirror):
    """Control for the test above: nothing but the recorded total differs."""
    doc = build_mod.run_build(mirror, tmp_path / "out", log=lambda _m: None)
    assert len(doc["shows"]) == 5 and len(doc["characters"]) == 2


def test_a_mirror_with_no_recorded_total_builds_nothing(tmp_path, mirror):
    _set_available(mirror, characters=None)
    with pytest.raises(build_mod.BuildError, match="reported no total for characters"):
        build_mod.run_build(mirror, tmp_path / "out", log=lambda _m: None)
    assert not (tmp_path / "out").exists()


# ---- the shrink gate ------------------------------------------------------------


def _previous(tmp_path, shows: int, characters: int):
    path = tmp_path / "previous.json"
    path.write_text(json.dumps({"shows": [{}] * shows, "characters": [{}] * characters}))
    return path


def _doc(shows: int, characters: int) -> dict:
    return {"shows": [{}] * shows, "characters": [{}] * characters}


@pytest.mark.parametrize(("new", "passes"), [(100, True), (98, True), (97, False), (0, False)])
def test_shrink_floor_is_two_percent(tmp_path, new, passes):
    previous = _previous(tmp_path, 100, 100)
    lines: list[str] = []
    if passes:
        build_mod._check_no_shrink(_doc(new, 100), previous, allow_shrink=False, log=lines.append)
        assert lines[-1].startswith("shrink gate: shows 100 ->")
        return
    with pytest.raises(build_mod.BuildError, match=rf"shows: 100 in the previous.*{new} now"):
        build_mod._check_no_shrink(_doc(new, 100), previous, allow_shrink=False, log=lines.append)


def test_growth_is_never_a_shrink(tmp_path):
    lines: list[str] = []
    build_mod._check_no_shrink(
        _doc(150, 300), _previous(tmp_path, 100, 100), allow_shrink=False, log=lines.append
    )
    assert lines[-1] == "shrink gate: shows 100 -> 150, characters 100 -> 300"


def test_a_snapshot_that_shrank_is_refused_and_nothing_is_written(tmp_path, mirror):
    out = tmp_path / "out"
    previous = _previous(tmp_path, 10, 2)  # the published one had 10 shows; this build has 5
    with pytest.raises(build_mod.BuildError) as failure:
        build_mod.run_build(mirror, out, previous_path=previous, log=lambda _m: None)
    assert "shows: 10 in the previous snapshot, 5 now (50.0% fewer)" in str(failure.value)
    assert "--allow-shrink" in str(failure.value)
    assert not out.exists()

    # Control: the same build against a previous snapshot of the same size goes through.
    doc = build_mod.run_build(
        mirror, out, previous_path=_previous(tmp_path, 5, 2), log=lambda _m: None
    )
    assert len(doc["shows"]) == 5 and (out / "snapshot.v1.json").exists()


def test_allow_shrink_publishes_a_deliberate_removal_and_says_so(tmp_path, mirror):
    lines: list[str] = []
    build_mod.run_build(
        mirror,
        tmp_path / "out",
        previous_path=_previous(tmp_path, 10, 2),
        allow_shrink=True,
        log=lines.append,
    )
    assert any(
        line.startswith("shrink gate OVERRIDDEN by --allow-shrink: shows: 10 in the previous")
        for line in lines
    )
    assert (tmp_path / "out" / "snapshot.v1.json").exists()


def test_no_previous_snapshot_skips_the_gate_loudly(tmp_path, mirror):
    lines: list[str] = []
    build_mod.run_build(mirror, tmp_path / "out", log=lines.append)
    assert "shrink gate SKIPPED: no previous snapshot was supplied to compare with" in lines


@pytest.mark.parametrize(
    "content",
    ["not json", '{"shows": []}', '{"shows": 3, "characters": 4}', "[]"],
    ids=["not-json", "no-characters-key", "counts-not-lists", "not-an-object"],
)
def test_an_unreadable_previous_snapshot_is_an_error_not_a_pass(tmp_path, mirror, content):
    previous = tmp_path / "previous.json"
    previous.write_text(content)
    with pytest.raises(build_mod.BuildError, match="cannot compare with the previous snapshot"):
        build_mod.run_build(mirror, tmp_path / "out", previous_path=previous, log=lambda _m: None)
    assert not (tmp_path / "out").exists()


def test_a_missing_previous_file_is_an_error_not_a_pass(tmp_path, mirror):
    with pytest.raises(build_mod.BuildError, match="cannot compare with the previous snapshot"):
        build_mod.run_build(
            mirror, tmp_path / "out", previous_path=tmp_path / "nope.json", log=lambda _m: None
        )


def test_the_cli_takes_previous_and_allow_shrink(tmp_path, mirror, capsys):
    out = tmp_path / "out"
    previous = str(_previous(tmp_path, 10, 2))
    args = ["build", "--cache", str(mirror), "--out", str(out), "--previous", previous]
    assert cli.main(args) == 1
    assert "the snapshot shrank more than 2%" in capsys.readouterr().err
    assert not out.exists()

    assert cli.main([*args, "--allow-shrink"]) == 0
    assert (out / "snapshot.v1.json").exists()
