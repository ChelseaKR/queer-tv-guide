"""Two numbers, everywhere. Computed from the final normalized snapshot data
plus the raw fetch counts, and printed on every build (never only written to
a file nobody reads)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# dotted field path -> getter(show_or_character) -> True (present) / False (absent) /
# None (n/a, skip)
_FIELD_GETTERS_SHOW: dict[str, Any] = {
    "shows.watch_links": lambda s: len(s["watch_links"]) > 0,
    "shows.ratings.worth_it": lambda s: s["ratings"]["worth_it"] is not None,
    "shows.ratings.quality": lambda s: s["ratings"]["quality"] is not None,
    "shows.external_ids.imdb": lambda s: s["external_ids"]["imdb"] is not None,
    "shows.years.end": lambda s: s["years"]["end"] is not None,
    "shows.seasons": lambda s: s["seasons"] is not None,
    "shows.schedule.schedule_known": lambda s: s["schedule"]["schedule_known"],
    "shows.schedule.next_episode": lambda s: s["schedule"]["next_episode"] is not None,
    "shows.networks": lambda s: len(s["networks"]) > 0,
    "shows.tropes": lambda s: len(s["tropes"]) > 0,
}

_FIELD_GETTERS_CHARACTER: dict[str, Any] = {
    "characters.death": lambda c: c["death"]["death_known"],
    "characters.gender": lambda c: c["gender"] is not None,
    "characters.sexuality": lambda c: c["sexuality"] is not None,
    "characters.romantic": lambda c: c["romantic"] is not None,
    "characters.actors": lambda c: (
        len(c["actors"]) > 0 and all(a["name"] is not None for a in c["actors"])
    ),
}


@dataclass
class FetchedVsAvailable:
    available: int | None
    fetched: int

    def as_dict(self) -> dict[str, int | None]:
        return {"available": self.available, "fetched": self.fetched}


def field_presence(
    shows: list[dict[str, Any]], characters: list[dict[str, Any]]
) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for path, getter in _FIELD_GETTERS_SHOW.items():
        present = sum(1 for s in shows if getter(s))
        out[path] = {"present": present, "absent": len(shows) - present}
    for path, getter in _FIELD_GETTERS_CHARACTER.items():
        present = sum(1 for c in characters if getter(c))
        out[path] = {"present": present, "absent": len(characters) - present}
    return out


def tvmaze_coverage(shows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(shows)
    with_key = sum(1 for s in shows if s["schedule"]["join"]["method"] != "none")
    joined = sum(1 for s in shows if s["schedule"]["schedule_known"])
    no_key = sum(
        1
        for s in shows
        if s["schedule"]["join"]["method"] == "none" and not s["_join_ignored_by_source"]
    )
    ignored = sum(1 for s in shows if s["_join_ignored_by_source"])
    claimants: dict[int, list[str]] = {}
    for s in shows:
        shared_id = s.get("_shared_tvmaze_id")
        if shared_id is not None:
            claimants.setdefault(shared_id, []).append(s["id"])
    shared = sum(len(ids) for ids in claimants.values())
    not_found = sum(
        1
        for s in shows
        if s["schedule"]["join"]["method"] != "none"
        and not s["schedule"]["schedule_known"]
        and s.get("_shared_tvmaze_id") is None
    )
    other = total - joined - no_key - ignored - not_found - shared
    return {
        "shows_total": total,
        "with_join_key": with_key,
        "joined": joined,
        "join_rate": round(joined / total, 4) if total else 0.0,
        "misses": {
            "no_key": no_key,
            "ignored_by_source": ignored,
            "not_found": not_found,
            "shared_tvmaze_id": shared,
            "other": max(other, 0),
        },
        "shared_tvmaze_ids": [
            {"tvmaze_id": tvmaze_id, "show_ids": sorted(ids, key=_show_id_order)}
            for tvmaze_id, ids in sorted(claimants.items())
        ],
    }


def _show_id_order(show_id: str) -> int:
    """`lwtv:show:1992` sorts before `lwtv:show:10010`: by number, not text."""
    return int(show_id.rsplit(":", 1)[-1])


def summary_lines(coverage: dict[str, Any]) -> list[str]:
    """The human-readable form printed to stdout on every build."""
    lines = ["coverage report", "================"]
    lw = coverage["lezwatch"]
    for kind in ("shows", "characters", "actors"):
        av = lw[kind]["available"]
        fe = lw[kind]["fetched"]
        pct = f" ({100 * fe / av:.1f}%)" if av else ""
        av_display = av if av is not None else "?"
        lines.append(f"lezwatch {kind}: {fe} fetched / {av_display} available{pct}")
    tv = coverage["tvmaze"]
    lines.append(
        f"tvmaze join: {tv['joined']}/{tv['shows_total']} shows "
        f"({100 * tv['join_rate']:.1f}%); "
        f"misses -- no_key={tv['misses']['no_key']} "
        f"ignored_by_source={tv['misses']['ignored_by_source']} "
        f"not_found={tv['misses']['not_found']} "
        f"shared_tvmaze_id={tv['misses'].get('shared_tvmaze_id', 0)} "
        f"other={tv['misses']['other']}"
    )
    for entry in tv.get("shared_tvmaze_ids", []):
        lines.append(
            f"  tvmaze {entry['tvmaze_id']} claimed by {', '.join(entry['show_ids'])}; "
            "schedule unknown for each"
        )
    lines.append("fields present / absent:")
    for path, counts in coverage["fields"].items():
        total = counts["present"] + counts["absent"]
        pct = f"{100 * counts['present'] / total:.1f}%" if total else "n/a"
        lines.append(f"  {path}: {counts['present']}/{total} present ({pct})")
    return lines
