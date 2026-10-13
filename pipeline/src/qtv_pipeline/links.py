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

from typing import Any
from urllib.parse import unquote_plus, urlsplit, urlunsplit

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


def _parts(url: str) -> tuple[Any, list[str]] | None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.query:
        return None
    return parts, [p for p in parts.query.split("&") if p]


def tracking_params(url: str) -> list[str]:
    """The listed affiliate or tracking parameter names still in `url`."""
    split = _parts(url)
    if split is None:
        return []
    parts, pieces = split
    host = parts.hostname or ""
    return [p.split("=", 1)[0] for p in pieces if _is_tracking(p.split("=", 1)[0], host)]


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
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "&".join(kept), parts.fragment))


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
