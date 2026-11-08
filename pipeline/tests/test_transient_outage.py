"""A transient LezWatch failure does not lose the night, and a lasting one fails plainly.

Run 42466572132 (2026-11-08) lost the night to three read timeouts in about three
and a half minutes on one small request. These tests drive the later retry, the
crawl delay and Retry-After through a fake LezWatch: a real local socket that really
hangs, or httpx.MockTransport with a clock that a recording sleep advances. Nothing
leaves the machine and no test waits for real beyond the socket test's short timeout.

Negative controls: each recovery test has a twin with `later_retry_wait=0` that
fails the same way the night did, so the later retry is what made it pass.
"""

from __future__ import annotations

import re
import threading
import time
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import pairwise
from pathlib import Path

import httpx
import pytest

from qtv_pipeline import build as build_mod
from qtv_pipeline import cli
from qtv_pipeline.http import (
    LEZWATCH_POLICY,
    TVMAZE_POLICY,
    USER_AGENT,
    FetchError,
    HostPolicy,
    PacedClient,
    UpstreamUnavailable,
    _retry_after_seconds,
)

from .conftest import build_handler

HOST = "lezwatchtv.com"
URL = f"https://{HOST}/wp-json/wp/v2/trope"
TROPE_PATH = "/wp-json/wp/v2/trope"


class FakeTime:
    """A clock that only `sleep` moves, plus a log of when each request started."""

    def __init__(self) -> None:
        self.now = 0.0
        self.waits: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.now += seconds


def _scripted(outcomes, fake: FakeTime):
    """Plays `outcomes` in order: an exception is raised, a response is returned.
    Returns the transport and the fake-clock start time of each request."""
    remaining = list(outcomes)
    starts: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        starts.append(fake.now)
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            fake.now += 60.0  # a read timeout takes the whole timeout
            raise outcome
        return outcome

    return httpx.MockTransport(handler), starts


def _client(transport, fake: FakeTime, policy: HostPolicy = LEZWATCH_POLICY) -> PacedClient:
    return PacedClient(
        policies={HOST: policy}, transport=transport, sleep=fake.sleep, clock=fake.clock
    )


def _timeout() -> httpx.ReadTimeout:
    return httpx.ReadTimeout("The read operation timed out")


OK = httpx.Response(200, json=[])
NO_LATER_RETRY = HostPolicy(min_interval=10.0, wait_429=600.0, max_429=3)


# -- the night of 2026-11-08 ------------------------------------------------


def test_three_timeouts_then_a_later_success_saves_the_run():
    fake = FakeTime()
    transport, starts = _scripted([_timeout(), _timeout(), _timeout(), OK], fake)
    with _client(transport, fake) as client:
        assert client.get(URL).status == 200
    assert len(starts) == 4
    assert fake.waits == [5.0, 10.0, 900.0]
    assert client.counters_as_dict()[HOST]["requests"] == 4  # retries stay on the budget


def test_negative_control_without_the_later_retry_the_same_night_fails():
    fake = FakeTime()
    transport, starts = _scripted([_timeout(), _timeout(), _timeout(), OK], fake)
    with _client(transport, fake, NO_LATER_RETRY) as client, pytest.raises(UpstreamUnavailable):
        client.get(URL)
    assert len(starts) == 3  # the fourth answer was there and was never asked for


def test_a_real_socket_that_hangs_then_answers():
    """A real ReadTimeout from a real server, not a raised one, and the real User-Agent."""
    seen: list[str | None] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            seen.append(self.headers.get("User-Agent"))
            if len(seen) <= 3:
                time.sleep(0.5)
                return
            body = b"[]"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    fake = FakeTime()
    policy = HostPolicy(min_interval=0.0, wait_429=1.0, later_retry_wait=900.0)
    try:
        with PacedClient(policies={"127.0.0.1": policy}, sleep=fake.sleep, timeout=0.1) as client:
            fetched = client.get(f"http://127.0.0.1:{server.server_port}/wp-json/wp/v2/trope")
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
    assert fetched.json() == []
    assert seen == [USER_AGENT] * 4
    assert fake.waits == [5.0, 10.0, 900.0]


# -- how much the later retry can cost --------------------------------------


def test_a_lasting_outage_makes_one_extra_request_then_fails_plainly():
    fake = FakeTime()
    transport, starts = _scripted([_timeout()] * 10, fake)
    with (
        _client(transport, fake) as client,
        pytest.raises(UpstreamUnavailable, match=r"after 2 retries and a later retry") as failure,
    ):
        client.get(URL)
    assert len(starts) == 4
    assert isinstance(failure.value.__cause__, httpx.ReadTimeout)


def test_the_later_retry_is_spent_once_a_run():
    fake = FakeTime()
    outcomes = [_timeout(), _timeout(), _timeout(), OK, _timeout(), _timeout(), _timeout(), OK]
    transport, starts = _scripted(outcomes, fake)
    with _client(transport, fake) as client:
        client.get(URL)
        with pytest.raises(UpstreamUnavailable):
            client.get(URL)
    assert len(starts) == 7
    assert fake.waits.count(900.0) == 1


def test_a_later_5xx_is_treated_like_a_timeout():
    fake = FakeTime()
    outcomes = [httpx.Response(503) for _ in range(3)] + [OK]
    transport, starts = _scripted(outcomes, fake)
    with _client(transport, fake) as client:
        assert client.get(URL).status == 200
    assert len(starts) == 4


def test_a_403_gets_no_later_retry():
    fake = FakeTime()
    transport, starts = _scripted([httpx.Response(403), OK], fake)
    with _client(transport, fake) as client, pytest.raises(FetchError, match="403"):
        client.get(URL)
    assert len(starts) == 1 and fake.waits == []


def test_tvmaze_has_no_later_retry():
    """TVmaze failures are per show and kept going past; a 15-minute wait per show
    would be wrong."""
    assert TVMAZE_POLICY.later_retry_wait == 0
    assert LEZWATCH_POLICY.later_retry_wait == 900.0


# -- the crawl delay --------------------------------------------------------


def test_every_request_keeps_the_crawl_delay_through_failures_and_retries():
    fake = FakeTime()
    # Instant 503s: the only thing holding the retries apart is the policy.
    outcomes = [httpx.Response(503), httpx.Response(503), httpx.Response(503), OK, OK, OK]
    transport, starts = _scripted(outcomes, fake)
    with _client(transport, fake) as client:
        for _ in range(3):
            client.get(URL)
    assert len(starts) == 6
    gaps = [b - a for a, b in pairwise(starts)]
    assert min(gaps) >= LEZWATCH_POLICY.min_interval


def test_negative_control_the_gap_check_sees_a_missing_delay():
    """With no pace the same script runs closer than 10 seconds, so the check above
    can fail."""
    fake = FakeTime()
    policy = HostPolicy(min_interval=0.0, wait_429=600.0)
    transport, starts = _scripted([httpx.Response(503), httpx.Response(503), OK, OK], fake)
    with _client(transport, fake, policy) as client:
        client.get(URL)
        client.get(URL)
    gaps = [b - a for a, b in pairwise(starts)]
    assert min(gaps) < LEZWATCH_POLICY.min_interval


# -- Retry-After ------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "retry_after", "expected_wait"),
    [
        (503, "120", 120.0),  # longer than our 5 s: theirs wins
        (503, "1", 5.0),  # shorter than our 5 s: ours wins
        (429, "700", 700.0),
        (429, "30", 600.0),
        (503, "soon", 5.0),  # unreadable: ours
    ],
)
def test_retry_after_only_ever_lengthens_a_wait(status, retry_after, expected_wait):
    fake = FakeTime()
    transport, _starts = _scripted(
        [httpx.Response(status, headers={"Retry-After": retry_after}), OK], fake
    )
    with _client(transport, fake) as client:
        client.get(URL)
    assert fake.waits[0] == expected_wait


@pytest.mark.parametrize("status", [503, 429])
def test_a_retry_after_beyond_the_cap_stops_instead_of_retrying_early(status):
    fake = FakeTime()
    transport, starts = _scripted(
        [httpx.Response(status, headers={"Retry-After": "3600"}), OK], fake
    )
    with (
        _client(transport, fake) as client,
        pytest.raises(UpstreamUnavailable, match="Retry-After 3600s"),
    ):
        client.get(URL)
    assert len(starts) == 1 and fake.waits == []


def test_retry_after_parses_seconds_and_dates():
    assert _retry_after_seconds(None) is None
    assert _retry_after_seconds("nonsense") is None
    assert _retry_after_seconds("90") == 90.0
    assert _retry_after_seconds(formatdate(time.time() - 100, usegmt=True)) == 0.0
    assert 100 < (_retry_after_seconds(formatdate(time.time() + 120, usegmt=True)) or 0) <= 120


# -- the whole run ----------------------------------------------------------


def _fake_lezwatch(failures: int | None, requested: list[tuple[str, str]]):
    """The fixture site, with the first `failures` trope requests timing out
    (None: all of them). Logs each request as (path, query)."""
    inner = build_handler()
    trope_tries = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append((request.url.path, str(request.url.query, "utf-8")))
        if request.url.path == TROPE_PATH:
            trope_tries["n"] += 1
            assert trope_tries["n"] <= 20, "the retries are not bounded"
            if failures is None or trope_tries["n"] <= failures:
                raise _timeout()
        return inner(request)

    return httpx.MockTransport(handler)


def _factory(transport, fake: FakeTime):
    def client_factory(**kwargs):
        return PacedClient(transport=transport, sleep=fake.sleep, clock=fake.clock, **kwargs)

    return client_factory


def test_a_run_that_recovers_repeats_only_the_failed_request(tmp_path):
    clean: list[tuple[str, str]] = []
    build_mod.run_fetch(
        tmp_path / "clean",
        full=True,
        log=lambda _m: None,
        client_factory=_factory(_fake_lezwatch(0, clean), FakeTime()),
    )
    saved: list[tuple[str, str]] = []
    fake = FakeTime()
    build_mod.run_fetch(
        tmp_path / "saved",
        full=True,
        log=lambda _m: None,
        client_factory=_factory(_fake_lezwatch(3, saved), fake),
    )
    trope = next(item for item in clean if item[0] == TROPE_PATH)
    assert saved.count(trope) == 4
    assert [item for item in saved if item != trope] == [item for item in clean if item != trope]
    assert fake.waits.count(900.0) == 1
    out = tmp_path / "out"
    doc = build_mod.run_build(
        tmp_path / "saved", out, git_sha="x", workflow_run_id="1", log=lambda _m: None
    )
    assert doc["shows"]


def test_negative_control_the_run_that_recovers_is_lost_without_the_later_retry(tmp_path):
    def client_factory(**kwargs):
        fake = FakeTime()
        return PacedClient(
            policies={
                HOST: NO_LATER_RETRY,
                "api.tvmaze.com": TVMAZE_POLICY,
                "docs.lezwatchtv.com": NO_LATER_RETRY,
            },
            transport=_fake_lezwatch(3, []),
            sleep=fake.sleep,
            clock=fake.clock,
            **kwargs,
        )

    with pytest.raises(UpstreamUnavailable):
        build_mod.run_fetch(
            tmp_path / "cache", full=True, log=lambda _m: None, client_factory=client_factory
        )


def test_a_permanent_failure_exits_1_and_publishes_nothing(tmp_path, monkeypatch, capsys):
    requested: list[tuple[str, str]] = []
    fake = FakeTime()
    real_run_fetch = build_mod.run_fetch

    def run_fetch(cache_dir, *, full, log):
        return real_run_fetch(
            cache_dir,
            full=full,
            log=log,
            client_factory=_factory(_fake_lezwatch(None, requested), fake),
        )

    monkeypatch.setattr(build_mod, "run_fetch", run_fetch)
    cache, out = tmp_path / "cache", tmp_path / "out"
    out.mkdir()
    yesterday = out / "snapshot.v1.json"
    yesterday.write_text('{"yesterday": true}')

    assert cli.main(["fetch", "--cache", str(cache)]) == 1
    assert "fetch failed: network error" in capsys.readouterr().err
    assert yesterday.read_text() == '{"yesterday": true}'
    assert [p.name for p in out.iterdir()] == ["snapshot.v1.json"]
    assert sum(1 for path, _ in requested if path == TROPE_PATH) == 4
    assert all(path != "/wp-json/wp/v2/show" for path, _ in requested)

    # A build over what the failed fetch left refuses too, and leaves the file alone.
    assert cli.main(["build", "--cache", str(cache), "--out", str(out)]) == 1
    assert yesterday.read_text() == '{"yesterday": true}'
    assert [p.name for p in out.iterdir()] == ["snapshot.v1.json"]


def test_the_workflow_stops_at_a_failed_fetch():
    """Nothing may turn a failed fetch step into a green one ahead of publishing."""
    text = (Path(__file__).parents[2] / ".github" / "workflows" / "snapshot.yml").read_text()
    fetch = text.index('uv run qtv fetch "${args[@]}"')
    assert fetch < text.index("uv run qtv build")
    assert fetch < text.index("gh release upload")
    assert fetch < text.index("actions/upload-pages-artifact")
    assert not re.search(r"^\s*continue-on-error:", text, re.M)
    assert '"${args[@]}" ||' not in text
