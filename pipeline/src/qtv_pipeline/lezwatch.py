"""Mirror LezWatch.TV into the cache directory.

Only the data fields the schema needs are requested (`_fields`), no images, no
posts/comments. Incremental fetches pass `modified_after`; the pipeline does
not assume the server honors it (WP REST support for that parameter varies by
version) — an unhonored filter just means every run refetches everything it
would have refetched on a full run, which is slower but never wrong, and the
build's `mode` field in the snapshot says which happened.

The cursor is a hint about what changed; the id list is the authority on what
exists. After every incremental fetch `reconcile` compares the cache with
`export/list/*`: a listed id the cache lacks is fetched by id whatever the
cursor says, and a cached id the list lacks is removed only after the site
confirms it is no longer published.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .http import FetchError, PacedClient

BASE = "https://lezwatchtv.com/wp-json"
PER_PAGE = 100

CURSOR_OVERLAP = timedelta(hours=24)
"""How far before the stored cursor an incremental request looks.

The cursor is the newest `modified_gmt` seen. LezWatch compares `modified_after`
with the site's *local* time, which trails GMT (four hours in September 2026), so
sending the cursor as is skips a record edited within that offset after it, and
skips it for good once a later edit moves the cursor past it. Sending the cursor
minus a whole day is a superset of the intended window for any UTC offset (they
span 26 hours at most, and the site's is a fixed few), and harmless: records are
keyed by id, so a record fetched twice is written once."""

COMPLETENESS_FLOOR_PERCENT = 99
"""The share of the source's own total (`X-WP-Total`) the mirror must hold before a
snapshot is built (README, Build gates, gate 3), and the least an id list may
list. One percent is about 23 shows of 2,275: room for records published between
two requests ten seconds apart, not for a truncated answer."""

CURSOR_FORMAT = "%Y-%m-%dT%H:%M:%S"
"""WordPress's `modified_gmt` format, and the format the cursor is persisted in."""

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


def _parse_cursor(value: str | None) -> datetime | None:
    """The stored cursor as a time, or None when there is none or it does not
    parse. An unreadable cursor means a full fetch: more requests, never fewer
    records."""
    if not value:
        return None
    try:
        return datetime.strptime(value, CURSOR_FORMAT)
    except ValueError:
        return None


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
    stored = None if full else _parse_cursor(cursor.get(cursor_key))
    since = None if stored is None else (stored - CURSOR_OVERLAP).strftime(CURSOR_FORMAT)
    page = 1
    fetched_count = 0
    available: int | None = None
    newest_modified = None if stored is None else stored.strftime(CURSOR_FORMAT)
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


def _uid(item: Any) -> int | None:
    """The integer `uid` of an id-list item, or None when it has none."""
    if not isinstance(item, dict):
        return None
    uid = item.get("uid")
    if isinstance(uid, bool) or not isinstance(uid, int | str):
        return None
    try:
        return int(uid)
    except ValueError:
        return None


def validate_id_list(
    items: Any, *, kind: str, expected_total: int | None = None
) -> list[dict[str, Any]]:
    """The id list as a list of items each carrying a `uid`, or a FetchError.

    The id list decides what is removed, so a malformed answer must stop the run
    rather than read as "nothing exists": one that is not a list, is empty, has an
    item without a numeric `uid` (a renamed key would otherwise make every cached
    record look deleted), or lists fewer than `COMPLETENESS_FLOOR_PERCENT` of the
    collection's own total, which means it was cut short."""
    where = f"lwtv/v1/export/list/{kind}"
    if not isinstance(items, list):
        raise FetchError(f"{where} answered with {type(items).__name__}, not a list of records")
    if not items:
        raise FetchError(f"{where} answered with an empty list; refusing to treat it as no {kind}")
    bad = [item for item in items if _uid(item) is None]
    if bad:
        raise FetchError(
            f"{where}: {len(bad)} of {len(items)} items have no numeric `uid` "
            f"(first: {json.dumps(bad[0], ensure_ascii=False)[:120]}); the list's shape changed"
        )
    if (
        expected_total is not None
        and len(items) * 100 < expected_total * COMPLETENESS_FLOOR_PERCENT
    ):
        raise FetchError(
            f"{where} lists {len(items)} {kind} but the source reports {expected_total} "
            f"(at least {COMPLETENESS_FLOOR_PERCENT}% is required); the list was cut short"
        )
    return items


def fetch_id_list(
    client: PacedClient, cache_dir: Path, *, kind: str, expected_total: int | None = None
) -> list[dict[str, Any]]:
    """`export/list/{shows,characters}/` — ids/slugs/names only, for reconciliation.

    Validated before it is used or saved (`validate_id_list`); a bad answer leaves
    the previously saved list in place. The endpoint is not documented as
    paginated; if the server ever announces X-WP-TotalPages we follow it."""
    paths = _cache_paths(cache_dir)
    items: list[Any] = []
    page = 1
    while True:
        params = {"page": page} if page > 1 else {}
        fetched = client.get(f"{BASE}/lwtv/v1/export/list/{kind}/", params=params)
        batch = fetched.json()
        if not isinstance(batch, list):
            items = batch  # not a list: validate_id_list names it
            break
        items.extend(batch)
        total_pages = int(fetched.headers.get("X-WP-TotalPages", "1") or "1")
        if page >= total_pages or not batch:
            break
        page += 1
    validated = validate_id_list(items, kind=kind, expected_total=expected_total)
    _write_json(paths["ids"] / f"{kind}.json", validated)
    return validated


def find_deleted(
    cache_dir: Path,
    *,
    kind: str,
    live_ids: list[dict[str, Any]],
    expected_total: int | None = None,
) -> list[int]:
    """Cached records whose id is not in the live id list (candidates for removal).

    Raises FetchError for a list that `validate_id_list` refuses, so an empty,
    renamed-key or truncated list can never come back as "everything is deleted"."""
    live = validate_id_list(live_ids, kind=kind, expected_total=expected_total)
    subdir = _cache_paths(cache_dir)["shows" if kind == "shows" else "characters"]
    cached_ids = {int(p.stem) for p in subdir.glob("*.json")}
    live_uids = {uid for item in live if (uid := _uid(item)) is not None}
    return sorted(cached_ids - live_uids)


@dataclass
class Reconciliation:
    """What `reconcile` did to one cache, as ids, so the run can log and tests can assert."""

    refetched: list[int]
    """Listed by LezWatch, absent from the cache: fetched by id."""
    removed: list[int]
    """Cached, absent from the list, and confirmed no longer published: removed."""
    kept: list[int]
    """Cached, absent from the list, but still published (the list lags): kept."""


_KINDS = {
    "shows": ("show", SHOW_FIELDS),
    "characters": ("character", CHARACTER_FIELDS),
}


def _fetch_published(
    client: PacedClient, *, rest_base: str, ids: list[int], fields: str
) -> list[dict[str, Any]]:
    """The published records among `ids`, `PER_PAGE` ids to a request.

    `include` is a core WP REST parameter; combined with `status=publish` it
    answers "which of these are public right now?" in one request per hundred ids,
    and omits (does not 404) an id that is trashed, a draft or gone. A server that
    ignored `include` would answer with unrelated records, and taking "none of my
    ids came back" from that would read a healthy record as deleted, so an answer
    naming any id that was not asked for is refused."""
    found: list[dict[str, Any]] = []
    for start in range(0, len(ids), PER_PAGE):
        batch = ids[start : start + PER_PAGE]
        fetched = client.get(
            f"{BASE}/wp/v2/{rest_base}",
            params={
                "include": ",".join(str(i) for i in batch),
                "per_page": PER_PAGE,
                "status": "publish",
                "_fields": fields,
            },
        )
        records = fetched.json()
        if not isinstance(records, list) or any(
            not isinstance(r, dict) or r.get("id") not in batch for r in records
        ):
            raise FetchError(
                f"wp/v2/{rest_base}?include=... answered with records that were not asked for; "
                "refusing to decide which records still exist from it"
            )
        found.extend(records)
    return found


def _preview(ids: list[int], limit: int = 20) -> str:
    shown = ", ".join(str(i) for i in ids[:limit])
    return f"{shown}, ... ({len(ids)} in all)" if len(ids) > limit else shown


def reconcile(
    client: PacedClient,
    cache_dir: Path,
    *,
    kind: str,
    live_ids: list[dict[str, Any]],
    expected_total: int | None = None,
) -> Reconciliation:
    """Make the cache agree with LezWatch's id list, without trusting the list alone.

    The cursor cannot heal a record the cache lost or never received (it has
    already moved past it), and the list can lag the site by a moment. So:

    1. An id the list has and the cache lacks is fetched by id, whatever the cursor says.
    2. An id the cache has and the list lacks is removed only when the site confirms
       it is not published; if it still is, the list is behind and the record stays.
    3. If a listed id is still not in the cache, the run fails naming the ids: the
       mirror is short, and publishing it would hide that.
    """
    rest_base, fields = _KINDS[kind]
    subdir = _cache_paths(cache_dir)[kind]
    subdir.mkdir(parents=True, exist_ok=True)
    live_ids = validate_id_list(live_ids, kind=kind, expected_total=expected_total)
    live = {uid for item in live_ids if (uid := _uid(item)) is not None}

    missing = sorted(live - {int(p.stem) for p in subdir.glob("*.json")})
    refetched = []
    for record in _fetch_published(client, rest_base=rest_base, ids=missing, fields=fields):
        _write_json(subdir / f"{record['id']}.json", record)
        refetched.append(int(record["id"]))

    candidates = find_deleted(
        cache_dir, kind=kind, live_ids=live_ids, expected_total=expected_total
    )
    published = {
        int(r["id"])
        for r in _fetch_published(client, rest_base=rest_base, ids=candidates, fields="id")
    }
    removed = [i for i in candidates if i not in published]
    for record_id in removed:
        (subdir / f"{record_id}.json").unlink(missing_ok=True)

    unresolved = sorted(live - {int(p.stem) for p in subdir.glob("*.json")})
    if unresolved:
        raise FetchError(
            f"{kind}: {len(unresolved)} id(s) in LezWatch's list are not in the mirror after "
            f"fetching them by id: {_preview(unresolved)}. Nothing is published."
        )
    return Reconciliation(refetched=sorted(refetched), removed=removed, kept=sorted(published))


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
