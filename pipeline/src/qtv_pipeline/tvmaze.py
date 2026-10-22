"""Join LezWatch shows to TVmaze and mirror the schedule.

The join key, in the order the pipeline tries it (documented in
schema/README.md and mirrored here in `JoinMethod`):

1. `lezshows_tvmaze_id_manual` (acf) — an editor override on LezWatch.
2. `lezshows_tvmaze_id` (meta) — LezWatch's own stored id, set by their
   "Next Episode" feature (docs.lezwatchtv.com/style-guide/shows/tvmaze-integration/).
3. `lezshows_imdb` (acf) — looked up via `/lookup/shows?imdb=`.

A show with `lezshows_tvmaze_ignore` set is never joined (LezWatch itself has
marked the match unreliable) and is counted separately from a genuine miss.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from . import fields
from .http import FetchError, PacedClient, UpstreamUnavailable

BASE = "https://api.tvmaze.com"

DEGRADED_FRACTION = 0.05
"""The share of the shows a run asked TVmaze about that may fail before the run fails.
One bad answer must not cost the nightly snapshot (a 502 on one show did, 2026-10-21);
a TVmaze outage must still stop the run rather than publish a mirror that stopped
refreshing. 5% of a nightly run (about 650 shows asked about, so about 30) is far above the
occasional 502 and far below an outage."""

DEGRADED_FLOOR = 2
"""Never fewer than this many may fail, so a small incremental run is not brittle."""


class TvmazeDegraded(FetchError):
    """Too many shows could not be refreshed from TVmaze to call the run healthy."""


@dataclass
class SyncReport:
    """What the sync did, for the run's output. `degraded` holds LezWatch show ids whose
    TVmaze refresh failed after retries; each keeps what the cache already had (or
    stays unjoined, which the snapshot renders as schedule unknown)."""

    attempted: int = 0
    degraded: list[str] = field(default_factory=list)


def degraded_limit(attempted: int) -> int:
    return max(DEGRADED_FLOOR, int(DEGRADED_FRACTION * attempted))


JoinMethod = Literal["lwtv_tvmaze_id_manual", "lwtv_tvmaze_id", "imdb_lookup", "none"]


@dataclass
class JoinAttempt:
    method: JoinMethod
    matched: bool
    tvmaze_id: int | None
    ignored_by_source: bool
    reason: Literal["ok", "no_key", "ignored_by_source", "not_found", "other"]


def _candidates(show: dict[str, Any]) -> list[tuple[JoinMethod, str]]:
    out: list[tuple[JoinMethod, str]] = []
    manual = fields.nonempty_str(fields.acf(show, "lezshows_tvmaze_id_manual"))
    if manual:
        out.append(("lwtv_tvmaze_id_manual", manual))
    stored = fields.meta_str(show, "lezshows_tvmaze_id")
    if stored:
        out.append(("lwtv_tvmaze_id", stored))
    imdb = fields.nonempty_str(fields.acf(show, "lezshows_imdb"))
    if imdb:
        out.append(("imdb_lookup", imdb))
    return out


def _cache_dir(cache_dir: Path) -> Path:
    d = cache_dir / "tvmaze" / "shows"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _joins_path(cache_dir: Path) -> Path:
    return cache_dir / "tvmaze" / "joins.json"


def load_joins(cache_dir: Path) -> dict[str, dict[str, Any]]:
    path = _joins_path(cache_dir)
    if not path.exists():
        return {}
    joins: dict[str, dict[str, Any]] = json.loads(path.read_text())
    return joins


def _save_joins(cache_dir: Path, joins: dict[str, dict[str, Any]]) -> None:
    path = _joins_path(cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(joins, indent=1, sort_keys=True, ensure_ascii=False))


def _recently_updated_ids(client: PacedClient, *, since: str = "week") -> set[int]:
    fetched = client.get(f"{BASE}/updates/shows", params={"since": since})
    data = fetched.json()
    return {int(k) for k in data} if isinstance(data, dict) else set()


def _needs_refresh(cached: dict[str, Any] | None, recently_updated: set[int]) -> bool:
    if cached is None or not cached.get("matched"):
        return True
    status = cached.get("status")
    if status not in ("Ended", "Canceled", "To Be Determined"):
        return True
    tvmaze_id = cached.get("tvmaze_id")
    return tvmaze_id in recently_updated


def _fetch_show(client: PacedClient, tvmaze_id: int) -> dict[str, Any] | None:
    fetched = client.get(
        f"{BASE}/shows/{tvmaze_id}",
        params={"embed[]": ["nextepisode", "previousepisode"]},
        ok_404=True,
    )
    return fetched.json() if fetched is not None else None


def _lookup_by_imdb(client: PacedClient, imdb_id: str) -> dict[str, Any] | None:
    fetched = client.get(f"{BASE}/lookup/shows", params={"imdb": imdb_id}, ok_404=True)
    if fetched is None:
        return None
    show = fetched.json()
    # /lookup/shows redirects to /shows/{id}, which has no embedded episodes yet.
    return _fetch_show(client, int(show["id"]))


def _resolve(
    client: PacedClient, lwtv_id: str, candidates: list[tuple[JoinMethod, str]]
) -> tuple[dict[str, Any] | None, JoinMethod, bool]:
    """Try each join key in order. Returns (body or None, the method that decided it,
    whether TVmaze was unavailable). A key that is not an integer id is a miss."""
    result: dict[str, Any] | None = None
    method: JoinMethod = "none"
    for method, key in candidates:
        try:
            if method == "imdb_lookup":
                result = _lookup_by_imdb(client, key)
            else:
                result = _fetch_show(client, int(key))
        except ValueError:
            result = None
        except UpstreamUnavailable as exc:
            client.log(f"  tvmaze unavailable for lwtv show {lwtv_id}; keeping the cache: {exc}")
            return None, method, True
        if result is not None:
            break
    return result, method, False


def sync_shows(
    client: PacedClient,
    cache_dir: Path,
    shows: list[dict[str, Any]],
    *,
    full: bool = False,
    report: SyncReport | None = None,
) -> dict[str, dict[str, Any]]:
    """Fetch/refresh TVmaze data for every LezWatch show that needs it.

    Returns the updated joins map (lwtv show id -> join record), also
    persisted to cache/tvmaze/joins.json. TVmaze show bodies are cached at
    cache/tvmaze/shows/{tvmaze_id}.json.

    When TVmaze keeps failing for one show (5xx, network error or 429 after the
    client's retries), that show's cached join and cached body are left exactly as
    they were, so the snapshot keeps its last known TVmaze fields; a show with
    nothing cached gets no join record at all and the snapshot says its schedule is
    unknown. Nothing is written that claims "not found". The show is counted in
    `report.degraded`, and the sync raises `TvmazeDegraded` (after saving) only when
    more than `degraded_limit` of the shows it asked about failed.
    """
    report = report if report is not None else SyncReport()
    shows_dir = _cache_dir(cache_dir)
    joins = load_joins(cache_dir)
    recently_updated: set[int] = set() if full else _recently_updated_ids(client)

    for show in shows:
        lwtv_id = str(show["id"])
        if fields.acf(show, "lezshows_tvmaze_ignore") is True:
            joins[lwtv_id] = {
                "method": "none",
                "matched": False,
                "tvmaze_id": None,
                "status": None,
                "reason": "ignored_by_source",
            }
            continue

        cached = joins.get(lwtv_id)
        if not full and not _needs_refresh(cached, recently_updated):
            continue

        candidates = _candidates(show)
        if not candidates:
            joins[lwtv_id] = {
                "method": "none",
                "matched": False,
                "tvmaze_id": None,
                "status": None,
                "reason": "no_key",
            }
            continue

        report.attempted += 1
        result, method, unavailable = _resolve(client, lwtv_id, candidates)
        if unavailable:
            # Leave joins[lwtv_id] and the cached body untouched. Never write
            # "not_found": TVmaze did not say that.
            report.degraded.append(lwtv_id)
            if len(report.degraded) > degraded_limit(len(shows)):
                break  # a ceiling no run can be under: stop hammering an outage
            continue
        reason = "ok" if result is not None else "not_found"
        if result is None:
            joins[lwtv_id] = {
                "method": method,
                "matched": False,
                "tvmaze_id": None,
                "status": None,
                "reason": reason,
            }
            continue

        tvmaze_id = int(result["id"])
        (shows_dir / f"{tvmaze_id}.json").write_text(
            json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False)
        )
        joins[lwtv_id] = {
            "method": method,
            "matched": True,
            "tvmaze_id": tvmaze_id,
            "status": result.get("status"),
            "reason": "ok",
        }

    _save_joins(cache_dir, joins)
    if len(report.degraded) > degraded_limit(report.attempted):
        raise TvmazeDegraded(
            f"TVmaze failed for {len(report.degraded)} of {report.attempted} shows "
            f"(limit {degraded_limit(report.attempted)}); not treating this as a healthy run"
        )
    return joins


def load_tvmaze_show(cache_dir: Path, tvmaze_id: int) -> dict[str, Any] | None:
    path = _cache_dir(cache_dir) / f"{tvmaze_id}.json"
    if not path.exists():
        return None
    show: dict[str, Any] = json.loads(path.read_text())
    return show
