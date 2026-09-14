"""Small helpers for reading LezWatch's WP REST records.

ACF (Advanced Custom Fields) values come through typed on `record["acf"]`.
The same data is often *also* exposed on `record["meta"]` in WP's native
single-element-array meta format (e.g. `{"lezshows_tvmaze_id": ["33320"]}`),
and a few fields (tvmaze id, tmdb id, on-air flag) are meta-only. These
helpers read acf first and fall back to meta, and normalise "not set" to
None/empty consistently so absence never silently becomes 0, "", or false.
"""

from __future__ import annotations

from typing import Any


def acf(record: dict[str, Any], key: str, default: Any = None) -> Any:
    return (record.get("acf") or {}).get(key, default)


def meta_str(record: dict[str, Any], key: str) -> str | None:
    values = (record.get("meta") or {}).get(key)
    if not values:
        return None
    value = values[0] if isinstance(values, list) else values
    value = str(value).strip()
    return value or None


def meta_int(record: dict[str, Any], key: str) -> int | None:
    value = meta_str(record, key)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def nonempty_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def int_or_none(value: Any) -> int | None:
    if value is None or value == "" or value is False:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def term_ref(term_id: int | None, terms_by_id: dict[int, dict[str, Any]]) -> dict[str, str] | None:
    if term_id is None:
        return None
    term = terms_by_id.get(term_id)
    if term is None:
        return None
    return {"slug": term["slug"], "name": term["name"]}


def terms_by_id(term_list: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(t["id"]): t for t in term_list}
