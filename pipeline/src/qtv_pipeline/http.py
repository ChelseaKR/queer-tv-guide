"""A paced HTTP client: one connection, a minimum interval per host, an
identifying User-Agent, request and byte counters, and a small retry policy.

Every request the pipeline makes goes through here so the crawl budget in
README.md is enforced in one place and reported in one place.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, overload
from urllib.parse import urlsplit

import httpx

from . import __version__

USER_AGENT = f"queer-tv-guide-pipeline/{__version__} (+https://github.com/ChelseaKR/queer-tv-guide)"


class FetchError(RuntimeError):
    """An HTTP exchange that could not be completed within policy. Fatal to the run."""


@dataclass(frozen=True)
class HostPolicy:
    min_interval: float
    """Seconds between the start of consecutive requests to this host."""
    wait_429: float
    """Seconds to wait after a 429 before the first retry."""
    backoff_429: float = 1.0
    """Multiplier applied to wait_429 on each further 429."""
    max_429: int = 3
    wait_5xx: float = 5.0
    max_5xx: int = 2


LEZWATCH_POLICY = HostPolicy(min_interval=10.0, wait_429=600.0, backoff_429=1.0, max_429=3)
"""lezwatchtv.com robots.txt: Crawl-delay: 10. API: 100 requests / 10 min. A 429 means
the 10-minute window is exhausted, so wait a whole window."""

TVMAZE_POLICY = HostPolicy(min_interval=1.0, wait_429=5.0, backoff_429=2.0, max_429=5)
"""api.tvmaze.com: at least 20 calls / 10 s; 'let your client back off for a few seconds
when it receives a 429'."""

DEFAULT_POLICIES: dict[str, HostPolicy] = {
    "lezwatchtv.com": LEZWATCH_POLICY,
    "docs.lezwatchtv.com": LEZWATCH_POLICY,
    "api.tvmaze.com": TVMAZE_POLICY,
}


@dataclass
class HostCounters:
    requests: int = 0
    bytes: int = 0
    last_started: float | None = None

    def as_dict(self) -> dict[str, int]:
        return {"requests": self.requests, "bytes": self.bytes}


@dataclass
class Fetched:
    status: int
    headers: httpx.Headers
    content: bytes
    url: str

    def json(self) -> Any:
        import json

        return json.loads(self.content.decode("utf-8"))

    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


@dataclass
class PacedClient:
    policies: dict[str, HostPolicy] = field(default_factory=lambda: dict(DEFAULT_POLICIES))
    transport: httpx.BaseTransport | None = None
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    timeout: float = 60.0
    log: Callable[[str], None] = lambda _msg: None
    counters: dict[str, HostCounters] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.5"},
            timeout=self.timeout,
            transport=self.transport,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PacedClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- pacing -------------------------------------------------------------

    def _policy_for(self, url: str) -> HostPolicy:
        host = urlsplit(url).hostname or ""
        try:
            return self.policies[host]
        except KeyError:
            raise FetchError(
                f"no crawl policy declared for host {host!r}; refusing {url}"
            ) from None

    def _pace(self, host: str, policy: HostPolicy) -> None:
        c = self.counters.setdefault(host, HostCounters())
        if c.last_started is not None:
            due = c.last_started + policy.min_interval
            now = self.clock()
            if now < due:
                self.sleep(due - now)
        c.last_started = self.clock()

    def _record(self, host: str, content: bytes) -> None:
        c = self.counters.setdefault(host, HostCounters())
        c.requests += 1
        c.bytes += len(content)

    # -- requests -----------------------------------------------------------

    @overload
    def get(
        self, url: str, *, params: dict[str, Any] | None = None, ok_404: Literal[False] = False
    ) -> Fetched: ...

    @overload
    def get(
        self, url: str, *, params: dict[str, Any] | None = None, ok_404: Literal[True]
    ) -> Fetched | None: ...

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        ok_404: bool = False,
    ) -> Fetched | None:
        """GET with pacing and retries.

        Typed by overload: without `ok_404=True` the result is never None, so
        callers need no runtime narrowing (an `assert` would vanish under -O).

        Returns None on a 404 when ok_404 is set (a definitive "not here" from the
        source). Raises FetchError for anything else that is not a 2xx.
        """
        policy = self._policy_for(url)
        host = urlsplit(url).hostname or ""
        n429 = 0
        n5xx = 0
        while True:
            self._pace(host, policy)
            try:
                resp = self._client.get(url, params=params)
            except httpx.HTTPError as exc:
                self._record(host, b"")
                if n5xx < policy.max_5xx:
                    n5xx += 1
                    self.log(f"  network error on {url}: {exc!r}; retry {n5xx}/{policy.max_5xx}")
                    self.sleep(policy.wait_5xx * n5xx)
                    continue
                raise FetchError(f"network error on {url} after {n5xx} retries: {exc!r}") from exc
            self._record(host, resp.content)
            if 200 <= resp.status_code < 300:
                return Fetched(resp.status_code, resp.headers, resp.content, str(resp.url))
            if resp.status_code == 404 and ok_404:
                return None
            if resp.status_code == 429:
                if n429 < policy.max_429:
                    wait = policy.wait_429 * (policy.backoff_429**n429)
                    n429 += 1
                    self.log(
                        f"  429 from {host}; waiting {wait:.0f}s; retry {n429}/{policy.max_429}"
                    )
                    self.sleep(wait)
                    continue
                raise FetchError(f"{host} kept answering 429 after {n429} retries: {url}")
            if 500 <= resp.status_code < 600:
                if n5xx < policy.max_5xx:
                    n5xx += 1
                    self.log(f"  {resp.status_code} from {url}; retry {n5xx}/{policy.max_5xx}")
                    self.sleep(policy.wait_5xx * n5xx)
                    continue
                raise FetchError(f"{resp.status_code} from {url} after {n5xx} retries")
            raise FetchError(f"{resp.status_code} from {url}: {resp.text[:200]!r}")

    def get_json(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        return self.get(url, params=params).json()

    def counters_as_dict(self) -> dict[str, dict[str, int]]:
        return {host: c.as_dict() for host, c in sorted(self.counters.items())}
