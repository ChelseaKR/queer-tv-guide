"""Cache records -> snapshot records.

This is where every absence rule lives. If a source did not record something,
the output says so explicitly (null, an empty list, a *_known flag) rather
than a value that looks real. Nothing here invents a link, a rating, or a
death.
"""

from __future__ import annotations

import html
import re
from typing import Any

from . import fields

_TAG_RE = re.compile(r"<[^>]+>")
_LI_RE = re.compile(r"(?is)<li[^>]*>")
_BLOCK_END_RE = re.compile(r"(?is)</(li|p|div|ul|ol)>")
_WS_RE = re.compile(r"[ \t]+")
_BLANKLINES_RE = re.compile(r"\n{3,}")


def html_to_text(raw: str | None) -> str | None:
    """Minimal HTML->text for LezWatch's own short, simply-marked-up fields
    (lists of <li>, <strong>, <p>). Not a general HTML sanitizer."""
    if not raw:
        return None
    text = _LI_RE.sub("\n- ", raw)
    text = _BLOCK_END_RE.sub("\n", text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text)
    text = _BLANKLINES_RE.sub("\n\n", text)
    text = text.strip()
    return text or None


def _rating_int(value: Any) -> int | None:
    """LezWatch stores 0 for an unrated field; the schema's 1-5 range makes
    0 and "not rated" the same fact, so both become null."""
    n = fields.int_or_none(value)
    if n is None or n == 0:
        return None
    return n


def _to_z(modified_gmt: str) -> str:
    return modified_gmt if modified_gmt.endswith("Z") else modified_gmt + "Z"


def _terms_from_ids(
    ids: list[int] | None, taxonomy: dict[int, dict[str, Any]]
) -> list[dict[str, str]]:
    out = []
    for term_id in ids or []:
        ref = fields.term_ref(fields.int_or_none(term_id), taxonomy)
        if ref is not None:
            out.append(ref)
    return out


def _watch_links(waystowatch: Any) -> list[dict[str, str]]:
    if not isinstance(waystowatch, list):
        return []
    out = []
    for item in waystowatch:
        url = (item or {}).get("url") if isinstance(item, dict) else None
        url = fields.nonempty_str(url)
        if not url:
            continue
        from urllib.parse import urlsplit

        host = urlsplit(url).hostname or ""
        out.append({"url": url, "host": host})
    return out


def _alternate_names(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    if isinstance(raw, list):
        out = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                name = item.get("name") or item.get("title") or item.get("value")
                if isinstance(name, str) and name.strip():
                    out.append(name.strip())
        return out
    return []

_IMDB_RE = re.compile(r"^tt\d+$")


def normalize_show(
    raw: dict[str, Any], taxonomies: dict[str, dict[int, dict[str, Any]]]
) -> dict[str, Any]:
    lwtv_id = int(raw["id"])
    imdb = fields.nonempty_str(fields.acf(raw, "lezshows_imdb"))
    if imdb and not _IMDB_RE.match(imdb):
        imdb = None

    tvmaze_ignore = fields.acf(raw, "lezshows_tvmaze_ignore") is True

    format_ids = raw.get("format") or []
    format_term = (
        fields.term_ref(fields.int_or_none(format_ids[0]), taxonomies["formats"])
        if format_ids
        else None
    )

    on_air_raw = fields.meta_str(raw, "lezshows_on_air")
    on_air = {"yes": "yes", "no": "no"}.get((on_air_raw or "").lower(), "unknown")

    show = {
        "id": f"lwtv:show:{lwtv_id}",
        "lwtv_id": lwtv_id,
        "slug": raw["slug"],
        "title": html.unescape((raw.get("title") or {}).get("rendered", "")),
        "alternate_names": _alternate_names(fields.acf(raw, "lezshows_show_names")),
        "source_url": raw["link"],
        "summary": fields.nonempty_str(fields.acf(raw, "excerpt")),
        "years": {
            "start": fields.int_or_none(fields.acf(raw, "lezshows_airdates_start")),
            "end": fields.int_or_none(fields.acf(raw, "lezshows_airdates_finish")),
            "on_air": on_air,
        },
        "seasons": fields.int_or_none(fields.acf(raw, "lezshows_seasons")),
        "format": format_term,
        "networks": _terms_from_ids(raw.get("station"), taxonomies["stations"]),
        "countries": _terms_from_ids(raw.get("country"), taxonomies["countries"]),
        "genres": _terms_from_ids(raw.get("genre"), taxonomies["genres"]),
        "tropes": _terms_from_ids(raw.get("trope"), taxonomies["tropes"]),
        "triggers": _terms_from_ids(raw.get("trigger"), taxonomies["triggers"]),
        "intersections": _terms_from_ids(raw.get("intersection"), taxonomies["intersections"]),
        "stars": _terms_from_ids(raw.get("star"), taxonomies["stars"]),
        "ratings": {
            "worth_it": fields.nonempty_str(fields.acf(raw, "lezshows_worthit_rating")),
            "worth_it_details": fields.nonempty_str(fields.acf(raw, "lezshows_worthit_details")),
            "quality": _rating_int(fields.acf(raw, "lezshows_quality_rating")),
            "realness": _rating_int(fields.acf(raw, "lezshows_realness_rating")),
            "screentime": _rating_int(fields.acf(raw, "lezshows_screentime_rating")),
            "score": (
                float(fields.meta_str(raw, "lezshows_the_score"))
                if fields.meta_str(raw, "lezshows_the_score")
                else None
            ),
            "show_we_love": bool(fields.acf(raw, "lezshows_worthit_show_we_love")),
        },
        "counts": {
            # patched with real numbers once characters are grouped by show (build.py)
            "characters": 0,
            "deaths": 0,
            "characters_source_reported": fields.meta_int(raw, "lezshows_char_count"),
            "deaths_source_reported": fields.meta_int(raw, "lezshows_dead_count"),
        },
        "external_ids": {
            "imdb": imdb,
            "tmdb": fields.meta_str(raw, "lezshows_tmdb_id"),
            "tvmaze": fields.meta_int(raw, "lezshows_tvmaze_id"),
        },
        "watch_links": _watch_links(fields.acf(raw, "lezshows_waystowatch")),
        # filtered to real ids that exist in the snapshot by build.py
        "similar_show_ids": [
            f"lwtv:show:{sid}" for sid in (fields.acf(raw, "lezshows_similar_shows") or [])
        ],
        "notes": {
            "plot": fields.nonempty_str(fields.acf(raw, "lezshows_plots")),
            "queer_episodes": html_to_text(fields.acf(raw, "lezshows_episodes")),
        },
        "schedule": None,  # filled in by normalize_schedule in build.py
        "source_modified_at": _to_z(raw["modified_gmt"]),
        "_join_ignored_by_source": tvmaze_ignore,
    }
    return show


def normalize_character(
    raw: dict[str, Any],
    taxonomies: dict[str, dict[int, dict[str, Any]]],
    actor_names: dict[int, str],
) -> dict[str, Any]:
    lwtv_id = int(raw["id"])

    gender_ids = raw.get("gender") or []
    gender = (
        fields.term_ref(fields.int_or_none(gender_ids[0]), taxonomies["genders"])
        if gender_ids
        else None
    )
    sexuality_ids = raw.get("sexuality") or []
    sexuality = (
        fields.term_ref(fields.int_or_none(sexuality_ids[0]), taxonomies["sexualities"])
        if sexuality_ids
        else None
    )
    romantic_ids = raw.get("romantic") or []
    romantic = (
        fields.term_ref(fields.int_or_none(romantic_ids[0]), taxonomies["romantic"])
        if romantic_ids
        else None
    )

    actors = []
    for actor_id in fields.acf(raw, "lezchars_actor") or []:
        aid = fields.int_or_none(actor_id)
        if aid is None:
            continue
        actors.append({"lwtv_id": aid, "slug": None, "name": actor_names.get(aid)})

    shows = []
    for entry in fields.acf(raw, "lezchars_show_group") or []:
        show_id = fields.int_or_none((entry or {}).get("show"))
        if show_id is None:
            continue
        shows.append(
            {
                "show_id": f"lwtv:show:{show_id}",
                "role": fields.nonempty_str((entry or {}).get("type")),
                "years": [str(y) for y in (entry.get("appears") or [])],
            }
        )

    death = _normalize_death(fields.acf(raw, "lezchars_death_year"))

    return {
        "id": f"lwtv:character:{lwtv_id}",
        "lwtv_id": lwtv_id,
        "slug": raw["slug"],
        "name": html.unescape((raw.get("title") or {}).get("rendered", "")),
        "source_url": raw["link"],
        "gender": gender,
        "sexuality": sexuality,
        "romantic": romantic,
        "cliches": _terms_from_ids(raw.get("cliche"), taxonomies["cliches"]),
        "actors": actors,
        "shows": shows,  # filtered to real show ids by build.py
        "death": death,
        "source_modified_at": _to_z(raw["modified_gmt"]),
    }


def _normalize_death(raw_entries: Any) -> dict[str, Any]:
    if not isinstance(raw_entries, list) or not raw_entries:
        return {"died": None, "death_known": False, "dates": [], "years": []}

    dates = []
    for entry in raw_entries:
        raw_date = (
            fields.nonempty_str((entry or {}).get("date")) if isinstance(entry, dict) else None
        )
        parsed = None
        year = None
        if raw_date and re.match(r"^\d{8}$", raw_date):
            parsed = f"{raw_date[0:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            year = int(raw_date[0:4])
        elif raw_date and re.match(r"^\d{4}$", raw_date):
            year = int(raw_date)
        dates.append({"date": parsed, "year": year, "raw": raw_date or ""})

    if not dates:
        # LezWatch recorded a death entry with no usable date; still a death.
        return {"died": True, "death_known": True, "dates": [], "years": []}

    years = sorted({d["year"] for d in dates if d["year"] is not None})
    return {"died": True, "death_known": True, "dates": dates, "years": years}


def normalize_schedule(
    join: dict[str, Any] | None, tvmaze_show: dict[str, Any] | None
) -> dict[str, Any]:
    method = (join or {}).get("method", "none")
    matched = bool((join or {}).get("matched"))

    empty = {
        "schedule_known": False,
        "join": {"method": method, "matched": False},
        "tvmaze_id": None,
        "tvmaze_url": None,
        "status": None,
        "premiered": None,
        "ended": None,
        "network": None,
        "web_channel": None,
        "next_episode": None,
        "previous_episode": None,
    }
    if not matched or tvmaze_show is None:
        return empty

    embedded = tvmaze_show.get("_embedded") or {}
    return {
        "schedule_known": True,
        "join": {"method": method, "matched": True},
        "tvmaze_id": int(tvmaze_show["id"]),
        "tvmaze_url": tvmaze_show.get("url"),
        "status": tvmaze_show.get("status"),
        "premiered": tvmaze_show.get("premiered"),
        "ended": tvmaze_show.get("ended"),
        "network": _channel(tvmaze_show.get("network")),
        "web_channel": _channel(tvmaze_show.get("webChannel")),
        "next_episode": _episode(embedded.get("nextepisode")),
        "previous_episode": _episode(embedded.get("previousepisode")),
    }


def _channel(obj: dict[str, Any] | None) -> dict[str, Any] | None:
    if not obj:
        return None
    return {"name": obj.get("name") or "", "country_code": (obj.get("country") or {}).get("code")}


def _episode(ep: dict[str, Any] | None) -> dict[str, Any] | None:
    if not ep:
        return None
    return {
        "tvmaze_id": int(ep["id"]),
        "season": ep.get("season"),
        "number": ep.get("number"),
        "name": fields.nonempty_str(ep.get("name")),
        "airdate": fields.nonempty_str(ep.get("airdate")),
        "airtime": fields.nonempty_str(ep.get("airtime")),
        "airstamp": fields.nonempty_str(ep.get("airstamp")),
        "runtime": ep.get("runtime"),
        "url": ep["url"],
    }


def strip_internal(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if not k.startswith("_")}
