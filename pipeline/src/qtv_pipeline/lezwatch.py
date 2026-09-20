"""Mirror LezWatch.TV into the cache directory.

Only the data fields the schema needs are requested (`_fields`), no images, no
posts/comments. Incremental fetches pass `modified_after`; the pipeline does
not assume the server honors it (WP REST support for that parameter varies by
version) — an unhonored filter just means every run refetches everything it
would have refetched on a full run, which is slower but never wrong, and the
build's `mode` field in the snapshot says which happened.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .http import PacedClient

BASE = "https://lezwatchtv.com/wp-json"
PER_PAGE = 100

# (WP taxonomy slug, REST base / top-level field name, schema key in taxonomies{})
TAXONOMIES: list[tuple[str, str, str]] = [
    ("lez_tropes", "trope", "tropes"),
    ("lez_cliches", "cliche", "cliches"),
    ("lez_gender", "gender", "genders"),
    ("lez_sexuality", "sexuality", "sexualities"),
    ("lez_romantic", "romantic", "romantic"),
    ("lez_stations", "station", "stations"),
    ("lez_genres", "genre", "genres"),
    ("lez_country", "country", "countries"),
    ("lez_formats", "format", "formats"),
    ("lez_triggers", "trigger", "triggers"),
    ("lez_intersections", "intersection", "intersections"),
    ("lez_stars", "star", "stars"),
]

SHOW_FIELDS = (
    "id,slug,link,modified_gmt,status,title,acf,meta,"
    "station,trope,genre,country,star,trigger,intersection,format"
)
CHARACTER_FIELDS = "id,slug,link,modified_gmt,status,title,acf,cliche,gender,sexuality,romantic"


@dataclass
class MirrorResult:
    fetched: int
    available: int | None
    deleted_ids: list[int]


def _cache_paths(cache_dir: Path) -> dict[str, Path]:
    root = cache_dir / "lezwatch"
    return {
        "root": root,
        "shows": root / "shows",
        "characters": root / "characters",
        "taxonomies": root / "taxonomies",
        "cursor": root / "cursor.json",
        "actors": root / "actors.json",
        "ids": root / "ids",
    }


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False))


def fetch_available_count(client: PacedClient, rest_base: str) -> int | None:
    """One cheap request (per_page=1) just to read the true X-WP-Total for the
    whole collection -- a filtered (modified_after) list request's X-WP-Total
    reflects the filter, not the site total, so this is separate."""
    fetched = client.get(
        f"{BASE}/wp/v2/{rest_base}",
        params={"per_page": 1, "status": "publish", "_fields": "id"},
    )
    total = fetched.headers.get("X-WP-Total")
    return int(total) if total is not None else None


def fetch_taxonomies(client: PacedClient, cache_dir: Path) -> dict[str, list[dict[str, Any]]]:
    paths = _cache_paths(cache_dir)
    out: dict[str, list[dict[str, Any]]] = {}
    for _wp_slug, rest_base, schema_key in TAXONOMIES:
        terms: list[dict[str, Any]] = []
        page = 1
        while True:
            fetched = client.get(
                f"{BASE}/wp/v2/{rest_base}",
                params={"per_page": PER_PAGE, "page": page, "_fields": "id,slug,name,count"},
            )
            batch = fetched.json()
            if not batch:
                break
            terms.extend(batch)
            total_pages = int(fetched.headers.get("X-WP-TotalPages", "1") or "1")
            if page >= total_pages:
                break
            page += 1
        _write_json(paths["taxonomies"] / f"{rest_base}.json", terms)
        out[schema_key] = terms
    return out


def _post_type_cursor_key(post_type: str) -> str:
    return post_type


def _list_posts(
    client: PacedClient,
    *,
    rest_base: str,
    fields: str,
    cache_subdir: Path,
    cursor: dict[str, str],
    cursor_key: str,
    full: bool,
) -> MirrorResult:
    cache_subdir.mkdir(parents=True, exist_ok=True)
    since = None if full else cursor.get(cursor_key)
    page = 1
    fetched_count = 0
    available: int | None = None
    newest_modified = since
    while True:
        params: dict[str, Any] = {
            "per_page": PER_PAGE,
            "page": page,
            "orderby": "modified",
            "order": "asc",
            "status": "publish",
            "_fields": fields,
        }
        if since:
            params["modified_after"] = since
        fetched = client.get(f"{BASE}/wp/v2/{rest_base}", params=params)
        if available is None:
            total = fetched.headers.get("X-WP-Total")
            available = int(total) if total is not None else None
        batch = fetched.json()
        if not batch:
            break
        for record in batch:
            _write_json(cache_subdir / f"{record['id']}.json", record)
            fetched_count += 1
            mod = record.get("modified_gmt")
            if mod and (newest_modified is None or mod > newest_modified):
                newest_modified = mod
        total_pages = int(fetched.headers.get("X-WP-TotalPages", "1") or "1")
        if page >= total_pages:
            break
        page += 1
    if newest_modified:
        cursor[cursor_key] = newest_modified
    return MirrorResult(fetched=fetched_count, available=available, deleted_ids=[])


def fetch_shows(
    client: PacedClient, cache_dir: Path, *, full: bool = False
) -> tuple[MirrorResult, dict[str, str]]:
    paths = _cache_paths(cache_dir)
    cursor = _read_json(paths["cursor"], {})
    result = _list_posts(
        client,
        rest_base="show",
        fields=SHOW_FIELDS,
        cache_subdir=paths["shows"],
        cursor=cursor,
        cursor_key="shows",
        full=full,
    )
    _write_json(paths["cursor"], cursor)
    return result, cursor


def fetch_characters(
    client: PacedClient, cache_dir: Path, *, full: bool = False
) -> tuple[MirrorResult, dict[str, str]]:
    paths = _cache_paths(cache_dir)
    cursor = _read_json(paths["cursor"], {})
    result = _list_posts(
        client,
        rest_base="character",
        fields=CHARACTER_FIELDS,
        cache_subdir=paths["characters"],
        cursor=cursor,
        cursor_key="characters",
        full=full,
    )
    _write_json(paths["cursor"], cursor)
    return result, cursor


def fetch_actor_names(client: PacedClient, cache_dir: Path) -> dict[int, str]:
    """`export/raw/actors/` — names only, no images/bio/links we don't use.

    The endpoint is not documented as paginated; if the server does add
    X-WP-TotalPages we follow it, otherwise a single response is treated as
    complete (the docs describe it as "an entire set of data").
    """
    paths = _cache_paths(cache_dir)
    names: dict[int, str] = {}
    page = 1
    while True:
        params = {"page": page} if page > 1 else {}
        fetched = client.get(f"{BASE}/lwtv/v1/export/raw/actors/", params=params)
        batch = fetched.json()
        if not isinstance(batch, list) or not batch:
            break
        for actor in batch:
            uid = actor.get("uid")
            if uid is not None:
                names[int(uid)] = actor.get("name") or ""
        total_pages = int(fetched.headers.get("X-WP-TotalPages", "1") or "1")
        if page >= total_pages:
            break
        page += 1
    _write_json(paths["actors"], {str(k): v for k, v in names.items()})
    return names


def fetch_id_list(client: PacedClient, cache_dir: Path, *, kind: str) -> list[dict[str, Any]]:
    """`export/list/{shows,characters}/` — ids/slugs/names only, for deletion detection."""
    paths = _cache_paths(cache_dir)
    fetched = client.get(f"{BASE}/lwtv/v1/export/list/{kind}/")
    items = fetched.json()
    if not isinstance(items, list):
        items = []
    _write_json(paths["ids"] / f"{kind}.json", items)
    return items


def find_deleted(cache_dir: Path, *, kind: str, live_ids: list[dict[str, Any]]) -> list[int]:
    """Cached records whose id no longer appears in the live id list."""
    subdir = _cache_paths(cache_dir)["shows" if kind == "shows" else "characters"]
    cached_ids = {int(p.stem) for p in subdir.glob("*.json")}
    live_uids = {int(item["uid"]) for item in live_ids if "uid" in item}
    return sorted(cached_ids - live_uids)


def load_taxonomies(cache_dir: Path) -> dict[str, list[dict[str, Any]]]:
    paths = _cache_paths(cache_dir)
    out: dict[str, list[dict[str, Any]]] = {}
    for _wp_slug, rest_base, schema_key in TAXONOMIES:
        out[schema_key] = _read_json(paths["taxonomies"] / f"{rest_base}.json", [])
    return out


def load_shows(cache_dir: Path) -> list[dict[str, Any]]:
    paths = _cache_paths(cache_dir)
    return [
        json.loads(p.read_text())
        for p in sorted(paths["shows"].glob("*.json"), key=lambda p: int(p.stem))
    ]


def load_characters(cache_dir: Path) -> list[dict[str, Any]]:
    paths = _cache_paths(cache_dir)
    return [
        json.loads(p.read_text())
        for p in sorted(paths["characters"].glob("*.json"), key=lambda p: int(p.stem))
    ]


def load_actor_names(cache_dir: Path) -> dict[int, str]:
    paths = _cache_paths(cache_dir)
    raw = _read_json(paths["actors"], {})
    return {int(k): v for k, v in raw.items()}


def cache_paths(cache_dir: Path) -> dict[str, Path]:
    return _cache_paths(cache_dir)
