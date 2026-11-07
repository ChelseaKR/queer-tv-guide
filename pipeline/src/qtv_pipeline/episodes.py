"""TVmaze episode lists, and where in a show each recorded death falls (DECISIONS 0041).

LezWatch.TV records a full calendar date for each death, and that date is the
day the episode aired (measured 2026-11-06: 86% of death dates land exactly on
a TVmaze air date for the show; shifted by 3 to 10 days, 3-5% do). Matching
the date to the show's TVmaze episode list places the death in a season and,
usually, an episode. That is the data an app needs to answer "has anyone died
so far?" for a viewer partway through a show. This module only produces the
data; nothing here renders it.

What is fetched: `/shows/{id}/episodes?specials=1` for each joined show with a
recorded death, through the same paced client as every other TVmaze request.
Only `season`, `number`, `airdate` and `type` are kept, in the cache and in
memory. No names, summaries or images: images may carry other rights and
summaries add spoiler risk.

The rules, in the order they are tried (each death date, each show it falls
in under DECISIONS 0030):

1. Regular episodes aired that exact day. One: that episode. Two from one
   season: "episode 7 or 8" (a double bill). Three or more from one season:
   the season only (a season released at once; never "episode 1"). From two
   seasons: not placed.
2. Only specials aired that day. One: that special, by its air date.
3. Regular episodes within a day either side (time zones). One: that
   episode. Several from one season: the season.
4. Regular episodes within a week either side, all from one season: the season.
5. The date falls inside exactly one season's first-to-last air dates: the season.
6. Otherwise not placed, with the reason (before the first episode, after the
   last, between seasons).

A date that falls in two or more shows (a crossover) is kept only in the show
where it lands on an episode, when exactly one show places it at the episode
level; the others say `other_show`.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from . import fields
from .http import PacedClient, UpstreamUnavailable
from .tvmaze import BASE, TvmazeDegraded, degraded_limit

KEPT_FIELDS = ("season", "number", "airdate", "type")
"""The only episode fields kept, in the cache and in the snapshot's derived data."""

ENDED_STATUSES = ("Ended", "Canceled", "To Be Determined")
"""Same as `tvmaze._needs_refresh`: a show in one of these is refreshed only when
TVmaze's `/updates/shows` says it changed."""

NEAR_DAYS = 1
"""A death date one day off an air date still names the episode (time zones)."""

WEEK_DAYS = 7
"""Within a week of a season's episodes, the death is in that season."""

CONTROL_SHIFT_DAYS = 3
"""The placebo control moves every death date this many days later."""

CONTROL_MAX_RATE = 0.10
"""The share of shifted dates that may still be placed at the episode level before
the build refuses. Measured 2026-11-06: about 4% of shifted dates, against 86% of
real ones. A matcher that matches everything would place nearly all of them."""

CONTROL_MIN_EVENTS = 50
"""Below this many death events with an episode list the control is too noisy to
judge, and it is reported but not enforced."""

Precision = Literal["episode", "episode_pair", "special", "season", "unplaced", "other_show"]

EPISODE_LEVEL: frozenset[str] = frozenset({"episode", "episode_pair", "special"})


@dataclass(frozen=True)
class Episode:
    season: int
    number: int | None
    airdate: dt.date
    regular: bool


def slim(raw: Any) -> list[dict[str, Any]]:
    """TVmaze's episode list cut down to `KEPT_FIELDS`."""
    if not isinstance(raw, list):
        return []
    return [{key: item.get(key) for key in KEPT_FIELDS} for item in raw if isinstance(item, dict)]


def _date(value: Any) -> dt.date | None:
    text = fields.nonempty_str(value)
    if text is None:
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return None


def parse(slimmed: Iterable[dict[str, Any]]) -> list[Episode]:
    """Episodes that have a season and an air date. A regular episode has a number;
    anything else (TVmaze's specials, or a regular episode TVmaze has not numbered)
    is matched only as a special."""
    out = []
    for item in slimmed:
        season = fields.int_or_none(item.get("season"))
        airdate = _date(item.get("airdate"))
        if season is None or airdate is None:
            continue
        number = fields.int_or_none(item.get("number"))
        regular = item.get("type", "regular") == "regular" and number is not None
        out.append(Episode(season, number if regular else None, airdate, regular))
    return out


def episode_counts(slimmed: Iterable[dict[str, Any]]) -> list[dict[str, int]]:
    """Numbered regular episodes per season, whether aired yet or not, for a
    season-and-episode picker. Specials are not counted."""
    seen: dict[int, set[int]] = {}
    for item in slimmed:
        season = fields.int_or_none(item.get("season"))
        number = fields.int_or_none(item.get("number"))
        if season is None or number is None or item.get("type", "regular") != "regular":
            continue
        seen.setdefault(season, set()).add(number)
    return [{"season": s, "episodes": len(nums)} for s, nums in sorted(seen.items())]


# -- placement ---------------------------------------------------------------


def _placement(
    precision: Precision,
    reason: str,
    *,
    season: int | None = None,
    episodes: list[int] | None = None,
    airdate: dt.date | None = None,
) -> dict[str, Any]:
    return {
        "precision": precision,
        "reason": reason,
        "season": season,
        "episodes": episodes,
        "airdate": airdate.isoformat() if airdate else None,
    }


def _one_season(eps: Sequence[Episode]) -> int | None:
    seasons = {e.season for e in eps}
    return seasons.pop() if len(seasons) == 1 else None


def _numbers(eps: Sequence[Episode]) -> list[int]:
    return sorted(e.number for e in eps if e.number is not None)


def _same_day(death: dt.date, episodes: Sequence[Episode]) -> dict[str, Any] | None:
    """Rules 1 and 2: something aired that exact day."""
    same = [e for e in episodes if e.airdate == death]
    same_regular = [e for e in same if e.regular]
    if same_regular:
        season = _one_season(same_regular)
        if season is None:
            return _placement("unplaced", "several_seasons_same_day")
        numbers = _numbers(same_regular)
        if len(same_regular) == 1:
            return _placement("episode", "exact_date", season=season, episodes=numbers)
        if len(same_regular) == 2:
            return _placement("episode_pair", "double_bill", season=season, episodes=numbers)
        return _placement("season", "season_drop", season=season)
    if not same:
        return None
    season = _one_season(same)
    if len(same) == 1:
        return _placement("special", "special_same_day", season=season, airdate=death)
    if season is not None:
        return _placement("season", "specials_same_day", season=season)
    return _placement("unplaced", "several_seasons_same_day")


def _nearby(death: dt.date, regular: Sequence[Episode]) -> dict[str, Any] | None:
    """Rules 3 and 4: regular episodes within a day, then within a week."""
    for days, one, several in (
        (NEAR_DAYS, "one_day_off", "one_day_off_several"),
        (WEEK_DAYS, None, "within_a_week"),
    ):
        near = [e for e in regular if abs((e.airdate - death).days) <= days]
        if not near:
            continue
        season = _one_season(near)
        if one is not None and len(near) == 1:
            return _placement("episode", one, season=season, episodes=_numbers(near))
        if season is not None:
            return _placement("season", several, season=season)
        return _placement("unplaced", "near_several_seasons")
    return None


def _by_span(death: dt.date, regular: Sequence[Episode]) -> dict[str, Any]:
    """Rules 5 and 6: inside one season's air dates, or why not."""
    spans: dict[int, tuple[dt.date, dt.date]] = {}
    for e in regular:
        lo, hi = spans.get(e.season, (e.airdate, e.airdate))
        spans[e.season] = (min(lo, e.airdate), max(hi, e.airdate))
    inside = [s for s, (lo, hi) in spans.items() if lo <= death <= hi]
    if len(inside) == 1:
        return _placement("season", "inside_season_span", season=inside[0])
    if inside:
        return _placement("unplaced", "overlapping_seasons")
    if death < min(lo for lo, _ in spans.values()):
        return _placement("unplaced", "before_first_episode")
    if death > max(hi for _, hi in spans.values()):
        return _placement("unplaced", "after_last_episode")
    return _placement("unplaced", "between_seasons")


def place(death: dt.date, episodes: Sequence[Episode]) -> dict[str, Any]:
    """Where `death` falls in a show with these episodes (the module docstring's rules).
    The result has no `show_id`; the caller adds it."""
    same_day = _same_day(death, episodes)
    if same_day is not None:
        return same_day
    regular = [e for e in episodes if e.regular]
    if not regular:
        return _placement("unplaced", "no_dated_episodes")
    return _nearby(death, regular) or _by_span(death, regular)


Matcher = Callable[[dt.date, Sequence[Episode]], dict[str, Any]]


def _show_order(show_id: str) -> int:
    return int(show_id.rsplit(":", 1)[-1])


def place_date(
    entry: dict[str, Any],
    character_shows: list[dict[str, Any]],
    episodes_by_show: dict[str, list[Episode] | None],
    *,
    matcher: Matcher = place,
) -> list[dict[str, Any]]:
    """Placements for one recorded death date (`death.dates[i]`) of one character.

    `episodes_by_show` maps a show id to its episode list, or None when the show
    has no usable TVmaze join or its list could not be fetched; a show missing
    from the map is treated the same way."""
    year = entry.get("year")
    date = _date(entry.get("date"))
    if year is None:
        return [{"show_id": None, **_placement("unplaced", "date_not_recorded")}]
    shows = sorted(
        {s["show_id"] for s in character_shows if str(year) in (s.get("years") or [])},
        key=_show_order,
    )
    if not shows:
        # DECISIONS 0030: the death year is in none of the character's shows.
        return [{"show_id": None, **_placement("unplaced", "no_show_in_death_year")}]
    out = []
    for show_id in shows:
        if date is None:
            placed = _placement("unplaced", "year_only")
        elif show_id not in episodes_by_show:
            placed = _placement("unplaced", "no_tvmaze_join")
        elif episodes_by_show[show_id] is None:
            placed = _placement("unplaced", "episodes_unavailable")
        else:
            placed = matcher(date, episodes_by_show[show_id] or [])
        out.append({"show_id": show_id, **placed})
    hits = [p for p in out if p["precision"] in EPISODE_LEVEL]
    if len(out) > 1 and len(hits) == 1:
        # A crossover: the date lands on an episode of only one of the shows.
        out = [
            p
            if p is hits[0]
            else {
                "show_id": p["show_id"],
                **_placement("other_show", "crossover_matched_other_show"),
            }
            for p in out
        ]
    return out


def place_all(
    characters: list[dict[str, Any]],
    episodes_by_show: dict[str, list[Episode] | None],
    *,
    matcher: Matcher = place,
) -> None:
    """Give every recorded death date its `placements`, in place."""
    for character in characters:
        for entry in character["death"]["dates"]:
            entry["placements"] = place_date(
                entry, character["shows"], episodes_by_show, matcher=matcher
            )


# -- the placebo control and the coverage numbers ----------------------------


def shifted_control(
    characters: list[dict[str, Any]],
    episodes_by_show: dict[str, list[Episode] | None],
    *,
    shift_days: int = CONTROL_SHIFT_DAYS,
    matcher: Matcher = place,
) -> dict[str, Any]:
    """Run the matcher on every death date that falls in a show with an episode list,
    once as recorded and once moved `shift_days` later, and report the share placed
    at the episode level each time. A real date should land on its episode; a
    shifted one should not. A rate is null (not 0) when no date could be tried."""
    eligible = real_hits = shifted_hits = 0
    for character in characters:
        for entry in character["death"]["dates"]:
            date = _date(entry.get("date"))
            year = entry.get("year")
            if date is None or year is None:
                continue
            for link in character["shows"]:
                eps = episodes_by_show.get(link["show_id"])
                if not eps or str(year) not in (link.get("years") or []):
                    continue
                eligible += 1
                real_hits += matcher(date, eps)["precision"] in EPISODE_LEVEL
                shifted = date + dt.timedelta(days=shift_days)
                shifted_hits += matcher(shifted, eps)["precision"] in EPISODE_LEVEL
    return {
        "shift_days": shift_days,
        "eligible": eligible,
        "episode_level_rate": round(real_hits / eligible, 4) if eligible else None,
        "shifted_episode_level_rate": round(shifted_hits / eligible, 4) if eligible else None,
        "max_shifted_rate": CONTROL_MAX_RATE,
        "enforced": eligible >= CONTROL_MIN_EVENTS,
    }


def control_problem(control: dict[str, Any]) -> str | None:
    """Why the build must refuse, or None. Only an enforced control can fail."""
    rate = control["shifted_episode_level_rate"]
    if not control["enforced"] or rate is None or rate < control["max_shifted_rate"]:
        return None
    return (
        f"placebo control: {100 * rate:.1f}% of death dates moved {control['shift_days']} days "
        f"still land on an episode (limit {100 * control['max_shifted_rate']:.0f}%, "
        f"{control['eligible']} dates). The matcher is matching too much; nothing is published."
    )


def coverage(
    characters: list[dict[str, Any]],
    *,
    lists_wanted: int,
    lists_cached: int,
    control: dict[str, Any],
) -> dict[str, Any]:
    """Counts of death events (character x date x show) by precision and by reason."""
    placements = [
        p for c in characters for entry in c["death"]["dates"] for p in entry["placements"]
    ]
    by_precision = Counter(p["precision"] for p in placements)
    return {
        "death_events": len(placements),
        "by_precision": {
            key: by_precision.get(key, 0)
            for key in ("episode", "episode_pair", "special", "season", "unplaced", "other_show")
        },
        "by_reason": dict(sorted(Counter(p["reason"] for p in placements).items())),
        "episode_lists": {"wanted": lists_wanted, "cached": lists_cached},
        "shifted_control": control,
    }


def summary_lines(block: dict[str, Any]) -> list[str]:
    total = block["death_events"]
    if not total:
        return ["death placement: no recorded death events"]
    p = block["by_precision"]
    episode = p["episode"] + p["episode_pair"] + p["special"]
    lines = [
        f"death placement: {episode}/{total} death events at the episode level "
        f"({100 * episode / total:.1f}%), {p['season']} season only, "
        f"{p['unplaced']} not placed, {p['other_show']} placed in another show",
        f"  episode lists: {block['episode_lists']['cached']}/"
        f"{block['episode_lists']['wanted']} wanted shows cached",
    ]
    control = block["shifted_control"]
    if control["eligible"]:
        lines.append(
            f"  placebo control: {100 * control['episode_level_rate']:.1f}% of real dates and "
            f"{100 * control['shifted_episode_level_rate']:.1f}% of dates moved "
            f"{control['shift_days']} days land on an episode ({control['eligible']} dates)"
        )
    return lines


# -- fetch and cache ---------------------------------------------------------


@dataclass
class EpisodeSyncReport:
    wanted: int = 0
    attempted: int = 0
    degraded: list[int] = field(default_factory=list)


def cache_path(cache_dir: Path, tvmaze_id: int) -> Path:
    return cache_dir / "tvmaze" / "episodes" / f"{tvmaze_id}.json"


def load(cache_dir: Path, tvmaze_id: int) -> list[dict[str, Any]] | None:
    path = cache_path(cache_dir, tvmaze_id)
    if not path.exists():
        return None
    data: list[dict[str, Any]] = json.loads(path.read_text())
    return data


def shows_with_a_death(characters_raw: list[dict[str, Any]]) -> set[str]:
    """LezWatch show ids (as strings, the joins map's keys) of every show listed for
    a character with a recorded death. Only these need an episode list."""
    out: set[str] = set()
    for raw in characters_raw:
        deaths = fields.acf(raw, "lezchars_death_year")
        if not isinstance(deaths, list) or not deaths:
            continue
        for entry in fields.acf(raw, "lezchars_show_group") or []:
            show_id = fields.int_or_none((entry or {}).get("show"))
            if show_id is not None:
                out.add(str(show_id))
    return out


def sync_episodes(
    client: PacedClient,
    cache_dir: Path,
    joins: dict[str, dict[str, Any]],
    wanted_show_ids: set[str],
    *,
    full: bool = False,
    recently_updated: set[int] | None = None,
    report: EpisodeSyncReport | None = None,
) -> EpisodeSyncReport:
    """Fetch the episode list of each joined TVmaze show in `wanted_show_ids`.

    Refreshed like the show records: always on a full run or when nothing is
    cached; otherwise when the show is still running or TVmaze lists it in
    `/updates/shows`. When TVmaze keeps failing for one show, its cached list is
    kept (or it stays without one, which the snapshot says as
    `episodes_unavailable`), and the run fails only past `degraded_limit`."""
    report = report if report is not None else EpisodeSyncReport()
    targets: dict[int, str | None] = {}
    for lwtv_id in sorted(wanted_show_ids, key=int):
        join = joins.get(lwtv_id) or {}
        if join.get("matched") and join.get("tvmaze_id") is not None:
            targets[int(join["tvmaze_id"])] = join.get("status")
    report.wanted = len(targets)
    if recently_updated is None and not full:
        fetched = client.get(f"{BASE}/updates/shows", params={"since": "week"})
        data = fetched.json()
        recently_updated = {int(k) for k in data} if isinstance(data, dict) else set()
    updated = recently_updated or set()

    for tvmaze_id, status in sorted(targets.items()):
        path = cache_path(cache_dir, tvmaze_id)
        stale = full or not path.exists() or status not in ENDED_STATUSES or tvmaze_id in updated
        if not stale:
            continue
        report.attempted += 1
        try:
            got = client.get(
                f"{BASE}/shows/{tvmaze_id}/episodes", params={"specials": "1"}, ok_404=True
            )
        except UpstreamUnavailable as exc:
            client.log(f"  tvmaze episodes unavailable for {tvmaze_id}; keeping the cache: {exc}")
            report.degraded.append(tvmaze_id)
            if len(report.degraded) > degraded_limit(len(targets)):
                break
            continue
        if got is None:
            # TVmaze says the show is not there: drop any old list rather than keep
            # placing deaths against episodes it no longer lists.
            path.unlink(missing_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(slim(got.json()), indent=0, sort_keys=True))

    if len(report.degraded) > degraded_limit(report.attempted):
        raise TvmazeDegraded(
            f"TVmaze episode lists failed for {len(report.degraded)} of {report.attempted} "
            f"shows (limit {degraded_limit(report.attempted)}); not treating this as a healthy run"
        )
    return report
