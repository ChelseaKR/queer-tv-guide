"""A paced HTTP client: one connection, a minimum interval per host, an
identifying User-Agent, request and byte counters, and a small retry policy.

Every request the pipeline makes goes through here so the crawl budget in
README.md is enforced in one place and reported in one place.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any, Literal, overload
from urllib.parse import urlsplit

import httpx

from . import __version__

USER_AGENT = f"queer-tv-guide-pipeline/{__version__} (+https://github.com/ChelseaKR/queer-tv-guide)"


class FetchError(RuntimeError):
    """An HTTP exchange that could not be completed within policy. Fatal to the run."""


class UpstreamUnavailable(FetchError):
    """The host kept failing in a way that says "try again later", not "this is wrong":
    5xx, a network error, or 429, each after the policy's retries. A caller that can
    keep what it already has for one record may catch this; anything else stays a
    plain FetchError (a 403 or a 400 means the request or the policy is wrong)."""


def _retry_after_seconds(value: str | None) -> float | None:
    """A Retry-After header (delta-seconds or an HTTP date) as seconds from now, or
    None when it is absent or unreadable. A date in the past is 0."""
    if value is None:
        return None
    value = value.strip()
    if value.isdecimal():
        return float(value)
    try:
        return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
    except ValueError:
        return None


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
    later_retry_wait: float = 0.0
    """Seconds to wait before one more try of a request that used up max_5xx, at most
    once per run per host. 0 means never: the failure goes straight to the caller."""
    max_retry_after: float = 900.0
    """The longest Retry-After this client waits out. Asked to wait longer, it stops
    instead of retrying early."""


LEZWATCH_POLICY = HostPolicy(
    min_interval=10.0, wait_429=600.0, backoff_429=1.0, max_429=3, later_retry_wait=900.0
)
"""lezwatchtv.com robots.txt: Crawl-delay: 10. API: 100 requests / 10 min. A 429 means
the 10-minute window is exhausted, so wait a whole window. Three tries inside four
minutes all fail if the site is slow for those minutes (2026-11-08), so one failed
request gets one more try 15 minutes later, once a run (DECISIONS 0054)."""

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
    later_retry_used: bool = False

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

    # -- retries ------------------------------------------------------------

    def _wait_429(
        self, host: str, policy: HostPolicy, url: str, n429: int, ra: float | None
    ) -> None:
        """Wait out a 429 before the next try, or raise when the policy is spent."""
        if n429 >= policy.max_429:
            raise UpstreamUnavailable(f"{host} kept answering 429 after {n429} retries: {url}")
        self._refuse_long_retry_after(url, policy, ra)
        wait = max(policy.wait_429 * (policy.backoff_429**n429), ra or 0.0)
        self.log(f"  429 from {host}; waiting {wait:.0f}s; retry {n429 + 1}/{policy.max_429}")
        self.sleep(wait)

    def _refuse_long_retry_after(self, url: str, policy: HostPolicy, ra: float | None) -> None:
        if ra is not None and ra > policy.max_retry_after:
            raise UpstreamUnavailable(
                f"{url} asked for Retry-After {ra:.0f}s, over the "
                f"{policy.max_retry_after:.0f}s this run waits; not retrying sooner"
            )

    def _wait_transient(
        self,
        host: str,
        policy: HostPolicy,
        n5xx: int,
        *,
        url: str,
        label: str,
        detail: str = "",
        ra: float | None = None,
    ) -> int:
        """Wait out a 5xx or network error before the next try and return the new
        retry count, or raise when the policy is spent."""
        self._refuse_long_retry_after(url, policy, ra)
        if n5xx < policy.max_5xx:
            n5xx += 1
            self.log(f"  {label}{detail}; retry {n5xx}/{policy.max_5xx}")
            self.sleep(max(policy.wait_5xx * n5xx, ra or 0.0))
            return n5xx
        counters = self.counters.setdefault(host, HostCounters())
        if policy.later_retry_wait > 0 and not counters.later_retry_used:
            counters.later_retry_used = True
            wait = max(policy.later_retry_wait, ra or 0.0)
            self.log(f"  {label}{detail}; one later retry for this run in {wait:.0f}s")
            self.sleep(wait)
            return n5xx
        later = " and a later retry" if policy.later_retry_wait > 0 else ""
        raise UpstreamUnavailable(f"{label} after {n5xx} retries{later}{detail}")

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
                try:
                    n5xx = self._wait_transient(
                        host,
                        policy,
                        n5xx,
                        url=url,
                        label=f"network error on {url}",
                        detail=f": {exc!r}",
                    )
                except UpstreamUnavailable as spent:
                    raise spent from exc
                continue
            self._record(host, resp.content)
            if 200 <= resp.status_code < 300:
                return Fetched(resp.status_code, resp.headers, resp.content, str(resp.url))
            if resp.status_code == 404 and ok_404:
                return None
            retry_after = _retry_after_seconds(resp.headers.get("Retry-After"))
            if resp.status_code == 429:
                self._wait_429(host, policy, url, n429, retry_after)
                n429 += 1
                continue
            if 500 <= resp.status_code < 600:
                n5xx = self._wait_transient(
                    host,
                    policy,
                    n5xx,
                    url=url,
                    label=f"{resp.status_code} from {url}",
                    ra=retry_after,
                )
                continue
            raise FetchError(f"{resp.status_code} from {url}: {resp.text[:200]!r}")

    def get_json(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        return self.get(url, params=params).json()

    def counters_as_dict(self) -> dict[str, dict[str, int]]:
        return {host: c.as_dict() for host, c in sorted(self.counters.items())}
