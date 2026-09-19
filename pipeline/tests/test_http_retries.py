"""The 5xx and network-error retry policy of `PacedClient.get`.

`pipeline/README.md` (crawl budget) promises "retry twice with backoff, then
fail the run". These tests drive that promise through an httpx.MockTransport and
a recording sleep, so no request leaves the process and no test waits.

Each test that expects a retry also asserts the fault really reached the client
(the transport saw the failing attempts), and the retry-count test is
parametrized over `max_5xx`: a policy that stopped honoring it would fail one
of the cases, which is the negative control for the others.
"""

from __future__ import annotations

import httpx
import pytest

from qtv_pipeline.http import FetchError, HostPolicy, PacedClient

URL = "https://api.tvmaze.com/shows/1"
HOST = "api.tvmaze.com"


def _client(transport, sleep, *, max_5xx: int = 2, wait_5xx: float = 5.0) -> PacedClient:
    policy = HostPolicy(
        min_interval=0.0, wait_429=1.0, max_429=1, wait_5xx=wait_5xx, max_5xx=max_5xx
    )
    return PacedClient(policies={HOST: policy}, transport=transport, sleep=sleep)


def _scripted(outcomes):
    """A transport that plays `outcomes` in order: an int is an HTTP status, an
    exception instance is raised. Returns the transport and the attempt log."""
    attempts: list[str] = []
    remaining = list(outcomes)

    def handler(request: httpx.Request) -> httpx.Response:
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            attempts.append(type(outcome).__name__)
            raise outcome
        attempts.append(str(outcome))
        return httpx.Response(outcome, json={"ok": outcome < 300})

    return httpx.MockTransport(handler), attempts


def test_a_5xx_that_recovers_is_retried_with_growing_waits(no_sleep):
    sleep, waits = no_sleep
    transport, attempts = _scripted([503, 502, 200])
    with _client(transport, sleep) as client:
        fetched = client.get(URL)
    assert fetched is not None and fetched.status == 200
    assert attempts == ["503", "502", "200"]  # the faults were really served
    assert waits == [5.0, 10.0]  # wait_5xx * attempt number
    assert client.counters_as_dict()[HOST]["requests"] == 3  # retries count against the budget


def test_a_5xx_that_never_recovers_fails_the_run_after_the_documented_retries(no_sleep):
    sleep, waits = no_sleep
    transport, attempts = _scripted([500, 500, 500])
    with (
        _client(transport, sleep) as client,
        pytest.raises(FetchError, match=r"500 .* after 2 retries"),
    ):
        client.get(URL)
    assert attempts == ["500", "500", "500"]  # one try plus two retries, no more
    assert waits == [5.0, 10.0]


@pytest.mark.parametrize("max_5xx", [0, 1, 2, 3])
def test_the_retry_count_follows_the_policy(no_sleep, max_5xx):
    """Negative control for the two tests above: the count comes from
    `HostPolicy.max_5xx`, not from the mock running out of failures."""
    sleep, waits = no_sleep
    transport, attempts = _scripted([503] * (max_5xx + 1))
    with _client(transport, sleep, max_5xx=max_5xx) as client, pytest.raises(FetchError):
        client.get(URL)
    assert len(attempts) == max_5xx + 1
    assert len(waits) == max_5xx


def test_a_network_error_that_recovers_is_retried(no_sleep):
    sleep, waits = no_sleep
    transport, attempts = _scripted([httpx.ConnectError("boom"), httpx.ReadTimeout("slow"), 200])
    logged: list[str] = []
    client = _client(transport, sleep)
    client.log = logged.append
    with client:
        fetched = client.get(URL)
    assert fetched is not None and fetched.status == 200
    assert attempts == ["ConnectError", "ReadTimeout", "200"]
    assert waits == [5.0, 10.0]
    assert [line for line in logged if "network error" in line] == [
        f"  network error on {URL}: ConnectError('boom'); retry 1/2",
        f"  network error on {URL}: ReadTimeout('slow'); retry 2/2",
    ]
    assert client.counters_as_dict()[HOST]["requests"] == 3


def test_a_network_error_that_never_recovers_fails_the_run(no_sleep):
    sleep, waits = no_sleep
    errors = [httpx.ConnectError("down")] * 3
    transport, attempts = _scripted(errors)
    with (
        _client(transport, sleep) as client,
        pytest.raises(FetchError, match=r"network error .* after 2 retries") as failure,
    ):
        client.get(URL)
    assert attempts == ["ConnectError"] * 3
    assert waits == [5.0, 10.0]
    assert isinstance(failure.value.__cause__, httpx.ConnectError)  # the cause is kept


def test_a_4xx_other_than_404_and_429_is_not_retried(no_sleep):
    sleep, waits = no_sleep
    transport, attempts = _scripted([403])
    with _client(transport, sleep) as client, pytest.raises(FetchError, match="403"):
        client.get(URL)
    assert attempts == ["403"] and waits == []


def test_get_json_decodes_the_body(no_sleep):
    sleep, _ = no_sleep
    transport, _attempts = _scripted([200])
    with _client(transport, sleep) as client:
        assert client.get_json(URL) == {"ok": True}
