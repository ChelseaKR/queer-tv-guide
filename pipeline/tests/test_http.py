from __future__ import annotations

import httpx
import pytest

from qtv_pipeline.http import DEFAULT_POLICIES, USER_AGENT, FetchError, HostPolicy, PacedClient


def test_user_agent_names_the_repo():
    assert "queer-tv-guide" in USER_AGENT
    assert "github.com/ChelseaKR/queer-tv-guide" in USER_AGENT


def test_unknown_host_refused(no_sleep):
    sleep, _ = no_sleep
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={}))
    with PacedClient(transport=transport, sleep=sleep) as client:
        with pytest.raises(FetchError, match="no crawl policy declared"):
            client.get("https://example.com/whatever")


def test_pacing_waits_the_full_interval():
    """Fake clock: two requests to the same host must be spaced by
    policy.min_interval, proving the pacer enforces it rather than just
    sleeping a fixed constant."""
    clock = {"t": 0.0}
    waited: list[float] = []

    def fake_clock() -> float:
        return clock["t"]

    def fake_sleep(seconds: float) -> None:
        waited.append(seconds)
        clock["t"] += seconds

    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"ok": True}))
    client = PacedClient(
        policies={"lezwatchtv.com": HostPolicy(min_interval=10.0, wait_429=600.0)},
        transport=transport,
        sleep=fake_sleep,
        clock=fake_clock,
    )
    with client:
        client.get("https://lezwatchtv.com/wp-json/lwtv/v1/stats/")
        clock["t"] += 1.0  # only 1s elapsed "naturally"
        client.get("https://lezwatchtv.com/wp-json/lwtv/v1/stats/")

    assert waited == [9.0]  # had to wait 9 more seconds to reach the 10s interval


def test_429_backs_off_and_then_succeeds(no_sleep):
    sleep, calls = no_sleep
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(429, text="slow down")
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = PacedClient(
        policies={"api.tvmaze.com": HostPolicy(min_interval=0.0, wait_429=5.0, backoff_429=2.0, max_429=5)},
        transport=transport,
        sleep=sleep,
    )
    with client:
        fetched = client.get("https://api.tvmaze.com/shows/1")
    assert fetched is not None and fetched.status == 200
    assert calls == [5.0, 10.0]  # backoff_429 doubling


def test_429_exhausted_raises(no_sleep):
    sleep, _ = no_sleep
    transport = httpx.MockTransport(lambda req: httpx.Response(429, text="no"))
    client = PacedClient(
        policies={"api.tvmaze.com": HostPolicy(min_interval=0.0, wait_429=1.0, max_429=2)},
        transport=transport,
        sleep=sleep,
    )
    with client, pytest.raises(FetchError, match="429"):
        client.get("https://api.tvmaze.com/shows/1")


def test_404_with_ok_404_returns_none(no_sleep):
    sleep, _ = no_sleep
    transport = httpx.MockTransport(lambda req: httpx.Response(404, json={"message": "no"}))
    client = PacedClient(policies=dict(DEFAULT_POLICIES), transport=transport, sleep=sleep)
    with client:
        assert client.get("https://api.tvmaze.com/shows/404", ok_404=True) is None


def test_404_without_ok_404_raises(no_sleep):
    sleep, _ = no_sleep
    transport = httpx.MockTransport(lambda req: httpx.Response(404, json={"message": "no"}))
    client = PacedClient(policies=dict(DEFAULT_POLICIES), transport=transport, sleep=sleep)
    with client, pytest.raises(FetchError, match="404"):
        client.get("https://api.tvmaze.com/shows/404")


def test_counters_track_requests_and_bytes(no_sleep):
    sleep, _ = no_sleep
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"a": 1}))
    client = PacedClient(policies=dict(DEFAULT_POLICIES), transport=transport, sleep=sleep)
    with client:
        client.get("https://api.tvmaze.com/shows/1")
        client.get("https://api.tvmaze.com/shows/2")
    counters = client.counters_as_dict()
    assert counters["api.tvmaze.com"]["requests"] == 2
    assert counters["api.tvmaze.com"]["bytes"] > 0
