"""Affiliate and tracking parameters, stripped from every outbound link.

LezWatch.TV's where-to-watch links are pasted in by its editors, and some
arrive carrying other parties' affiliate tags (an Amazon `tag=` from
DuckDuckGo, from IMDb, from a site we cannot name) or click trackers. The
snapshot publishes them to every reader of the app, so a tag left in would
pay whoever pasted it each time a Queer Frame user taps "Watch on". The
links are stripped, never replaced: the app earns nothing from a link and
adds no tag of its own.

Only the query string changes: scheme, host, path and fragment are kept,
and every parameter not on these lists keeps its exact original bytes (an
Amazon video id, a YouTube `v=`, an iTunes episode `i=` all still work).
`tracking_params` is what the publish gate checks: a published URL with any
listed parameter left in fails the build.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import SplitResult, unquote_plus, urlsplit, urlunsplit

# Anywhere: campaign and click trackers, and referral-reward codes.
_GLOBAL = frozenset(
    {
        "fbclid",
        "gclid",
        "dclid",
        "gbraid",
        "wbraid",
        "msclkid",
        "yclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "_hsenc",
        "_hsmi",
        "irclickid",
        "irgwc",
        "mbsy",
        "mbsy_source",
        "referral_reward_type",
        "campaignid",
        "searchreferral",
        "ftag",
    }
)
_GLOBAL_PREFIXES = ("utm_",)

# Amazon's Associates tags and the link-builder's companions, plus search
# and placement trackers.
_AMAZON = frozenset(
    {
        "tag",
        "linkcode",
        "linkid",
        "ascsubtag",
        "ref",
        "ref_",
        "camp",
        "creative",
        "creativeasin",
        "subscriptionid",
        "token",
        "qid",
        "sr",
    }
)
_AMAZON_PREFIXES = ("pd_rd_", "pf_rd_")

# Apple's affiliate token (`at`), campaign (`ct`), provider token (`pt`) and
# link-origin (`uo`) parameters.
_APPLE = frozenset({"at", "ct", "pt", "uo"})

# YouTube's share trackers.
_YOUTUBE = frozenset({"si", "feature"})


def _host_rules(host: str) -> tuple[frozenset[str], tuple[str, ...]]:
    h = host.lower()
    labels = h.split(".")
    if "amazon" in labels or h.endswith("primevideo.com") or h == "amzn.to":
        return _AMAZON, _AMAZON_PREFIXES
    if h.endswith(".apple.com"):
        return _APPLE, ()
    if h.endswith("youtube.com") or h == "youtu.be":
        return _YOUTUBE, ()
    return frozenset(), ()


def _is_tracking(key: str, host: str) -> bool:
    k = unquote_plus(key).lower()
    names, prefixes = _host_rules(host)
    return k in _GLOBAL or k.startswith(_GLOBAL_PREFIXES) or k in names or k.startswith(prefixes)


def _parts(url: str) -> tuple[SplitResult, list[str]] | None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.query:
        return None
    return parts, [p for p in parts.query.split("&") if p]


def tracking_params(url: str, apple_token: str = "") -> list[str]:
    """The listed affiliate or tracking parameter names still in `url`.

    With `apple_token` set, exactly one `at=<that token>` on an Apple TV or
    iTunes link is the developer's own (DECISIONS 0019) and is not listed;
    any other `at`, or a second one, still is.
    """
    split = _parts(url)
    if split is None:
        return []
    parts, pieces = split
    host = parts.hostname or ""
    found = [p.split("=", 1)[0] for p in pieces if _is_tracking(p.split("=", 1)[0], host)]
    own = f"at={apple_token}"
    if apple_token and host.lower() in APPLE_AFFILIATE_HOSTS and pieces.count(own) == 1:
        found.remove("at")
    return found


def strip_tracking(url: str) -> str:
    """`url` without the listed parameters; everything else byte for byte."""
    split = _parts(url)
    if split is None:
        return url
    parts, pieces = split
    host = parts.hostname or ""
    kept = [p for p in pieces if not _is_tracking(p.split("=", 1)[0], host)]
    if len(kept) == len(pieces):
        return url
    return str(urlunsplit((parts.scheme, parts.netloc, parts.path, "&".join(kept), parts.fragment)))


# Apple Services Performance Partners (DECISIONS 0019): the developer's own
# affiliate token goes on Apple TV and iTunes links only, after every other
# party's has been stripped. One fixed token, the same in every link for
# every reader: no campaign value, nothing per person.
APPLE_AFFILIATE_HOSTS = frozenset({"tv.apple.com", "itunes.apple.com"})
APPLE_TOKEN_RE = re.compile(r"^[A-Za-z0-9]{4,32}$")


def is_valid_apple_token(token: str) -> bool:
    return bool(APPLE_TOKEN_RE.match(token))


def add_apple_token(url: str, token: str) -> str:
    """`url` with `at=<token>` added, if it is an https Apple TV or iTunes link.

    With no token, `url` comes back unchanged: the output is byte for byte
    what it was before this feature.
    """
    if not token:
        return url
    parts = urlsplit(url)
    if parts.scheme != "https" or (parts.hostname or "").lower() not in APPLE_AFFILIATE_HOSTS:
        return url
    query = "&".join(p for p in (parts.query, f"at={token}") if p)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def strip_all(value: Any) -> int:
    """Strips every http(s) URL string inside `value` in place; returns how many changed."""
    changed = 0
    items = (
        value.items()
        if isinstance(value, dict)
        else enumerate(value)
        if isinstance(value, list)
        else ()
    )
    for key, item in list(items):
        if isinstance(item, str):
            clean = strip_tracking(item)
            if clean != item:
                value[key] = clean
                changed += 1
        else:
            changed += strip_all(item)
    return changed


def outbound_urls(value: Any, path: str = "") -> list[tuple[str, str]]:
    """Every http(s) URL string in a document, with where it sits."""
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found += outbound_urls(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            found += outbound_urls(item, f"{path}[{i}]")
    elif isinstance(value, str) and value.startswith(("http://", "https://")):
        found.append((path, value))
    return found
