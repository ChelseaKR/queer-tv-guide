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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from . import fields
from .http import PacedClient

BASE = "https://api.tvmaze.com"

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
    return json.loads(path.read_text())


def _save_joins(cache_dir: Path, joins: dict[str, dict[str, Any]]) -> None:
    path = _joins_path(cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(joins, indent=1, sort_keys=True, ensure_ascii=False))


def _recently_updated_ids(client: PacedClient, *, since: str = "week") -> set[int]:
    fetched = client.get(f"{BASE}/updates/shows", params={"since": since})
    assert fetched is not None
    data = fetched.json()
    return {int(k) for k in data.keys()} if isinstance(data, dict) else set()


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


def sync_shows(
    client: PacedClient,
    cache_dir: Path,
    shows: list[dict[str, Any]],
    *,
    full: bool = False,
) -> dict[str, dict[str, Any]]:
    """Fetch/refresh TVmaze data for every LezWatch show that needs it.

    Returns the updated joins map (lwtv show id -> join record), also
    persisted to cache/tvmaze/joins.json. TVmaze show bodies are cached at
    cache/tvmaze/shows/{tvmaze_id}.json.
    """
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

        result: dict[str, Any] | None = None
        method: JoinMethod = "none"
        reason = "not_found"
        for method, key in candidates:
            try:
                if method == "imdb_lookup":
                    result = _lookup_by_imdb(client, key)
                else:
                    result = _fetch_show(client, int(key))
            except ValueError:
                result = None
            if result is not None:
                reason = "ok"
                break
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
    return joins


def load_tvmaze_show(cache_dir: Path, tvmaze_id: int) -> dict[str, Any] | None:
    path = _cache_dir(cache_dir) / f"{tvmaze_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())
