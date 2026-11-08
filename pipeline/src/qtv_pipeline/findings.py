"""When in a show queer characters die: the findings page (DECISIONS 0042).

Two halves, kept apart on purpose:

``compute`` reads a snapshot and the TVmaze episode list of each joined show
with a recorded death, and returns aggregate counts only: no character, no
show, no date. Its output is committed as ``pipeline/data/findings_finales.json``
and regenerated only when the owner chooses, so the published claims are
dated and never drift with a nightly build:

    python -m qtv_pipeline.findings compute SNAPSHOT EPISODES_DIR OUT_JSON

``EPISODES_DIR`` holds ``{tvmaze_id}.json`` files, each the body of TVmaze's
``/shows/{id}/episodes?specials=1``. This module never fetches them.

``render_findings``, ``findings_csv`` and ``render_press`` turn that file into
``/findings/finales/``, its CSV and ``/press/``. Every figure on those pages is
formatted from the file here; the templates hold no hand-typed number.

Definitions (stated on the page as well):

- A death event is one date in LezWatch.TV's death-date field for one
  character, in one show whose years for that character include the death's
  year (DECISIONS 0030). A character who later comes back still counts.
- A death is placed in an episode only when TVmaze lists exactly one episode
  that aired on its date, or none that day and exactly one within a day.
  Two or more the same day (a double bill, a season released at once) are
  not placed. Specials are not placed.
- A season finale is the highest-numbered regular episode TVmaze lists for
  that season. A series finale is the last one of the last season, for a
  show TVmaze marks Ended.
- The baseline for a death is the chance that a random regular episode of
  its own show is a season finale (seasons / episodes); the expected share is
  the mean of those over the deaths in a group.
- The role is LezWatch.TV's role for the character in that show: regular,
  recurring or guest.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from qtv_pipeline import show_pages

DEFAULT_FINDINGS_PATH = Path(__file__).resolve().parents[2] / "data" / "findings_finales.json"
FINDINGS_PATH = "findings/finales/index.html"
CSV_PATH = "findings/finales/finales.csv"
PRESS_PATH = "press/index.html"
REPO_ROOT = Path(__file__).resolve().parents[3]
PRESS_ASSETS = (
    # (published file under press/, source in this repository, alt text, width, height)
    (
        "app-icon.png",
        "ios/QueerTVGuide/Assets.xcassets/AppIcon.appiconset/icon-1024.png",
        "The Queer Frame app icon",
        1024,
        1024,
    ),
    (
        "screenshot-search.png",
        "docs/app-store/screenshots/01-browse.png",
        "The app's Search screen, a list of shows",
        1320,
        2868,
    ),
    (
        "screenshot-show.png",
        "docs/app-store/screenshots/02-show-reveal-closed.png",
        "A show screen, with the answer to 'Do any queer characters die?' behind a Reveal button",
        1320,
        2868,
    ),
    (
        "screenshot-privacy.png",
        "docs/app-store/screenshots/05-privacy-and-sources.png",
        "The About screen's privacy section",
        1320,
        2868,
    ),
)
CONTACT_EMAIL = "chelsea@chelseakr.com"
ROLES = ("regular", "recurring", "guest")
ERA_SPLIT = 2010
SEASON_LABELS = {"1": "First season", "2": "Second season", "3+": "Third season or later"}
FORMAT_VERSION = 1


class FindingsError(ValueError):
    """The findings data file is missing a field or is not this format."""


# --- compute ------------------------------------------------------------------


def _regular_episodes(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        e
        for e in episodes
        if e.get("type") == "regular"
        and isinstance(e.get("season"), int)
        and isinstance(e.get("number"), int)
        and e.get("airdate")
    ]


def place(date: str, episodes: list[dict[str, Any]]) -> tuple[int, int] | None:
    """The (season, number) of the one episode a death date names, or None.

    Matching uses every dated episode TVmaze lists (specials too), so a
    special that aired that day blocks a guess; the match counts only when
    it is a regular, numbered episode."""
    dated = [e for e in episodes if e.get("airdate") and e.get("season") is not None]
    day = dt.date.fromisoformat(date)
    same = [e for e in dated if e["airdate"] == date]
    if same:
        hit = same[0] if len(same) == 1 else None
    else:
        near = [e for e in dated if abs((dt.date.fromisoformat(e["airdate"]) - day).days) <= 1]
        hit = near[0] if len(near) == 1 else None
    if hit is None or hit.get("type") != "regular" or not isinstance(hit.get("number"), int):
        return None
    return int(hit["season"]), int(hit["number"])


def death_events(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Every (character, death date, show) under DECISIONS 0030, without names,
    for a death LezWatch.TV counts (0053)."""
    shows = {s["id"]: s for s in doc["shows"]}
    events = []
    for c in doc["characters"]:
        death = c["death"]
        if not death.get("died"):
            continue
        if death.get("counted") is False:
            # A date for a character LezWatch.TV lists as alive (0053).
            continue
        for entry in death["dates"]:
            for link in c["shows"]:
                if str(entry["year"]) in (link.get("years") or []):
                    events.append(
                        {
                            "date": entry["date"],
                            "year": entry["year"],
                            "role": link.get("role"),
                            "show": shows[link["show_id"]],
                        }
                    )
    return events


def _release(show: dict[str, Any]) -> str | None:
    sched = show["schedule"]
    if sched.get("network"):
        return "broadcast"
    if sched.get("web_channel"):
        return "streaming"
    return None


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """The 95% Wilson score interval for k of n."""
    if n == 0:
        raise FindingsError("no deaths in the group")
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def _group() -> dict[str, float]:
    return {"deaths": 0, "in_position": 0, "expected": 0.0}


def _round(groups: dict[str, dict[str, float]]) -> dict[str, dict[str, Any]]:
    return {
        k: {
            "deaths": int(g["deaths"]),
            "in_position": int(g["in_position"]),
            "baseline": round(g["expected"] / g["deaths"], 4) if g["deaths"] else None,
        }
        for k, g in groups.items()
    }


def _placed(ev: dict[str, Any], episodes: dict[int, list[dict[str, Any]]]) -> dict[str, Any] | None:
    """Where one death event falls, or None when it can't be placed."""
    tvid = ev["show"]["schedule"].get("tvmaze_id")
    if not tvid or tvid not in episodes:
        return None
    hit = place(ev["date"], episodes[tvid])
    regular = _regular_episodes(episodes[tvid])
    by_season = Counter(e["season"] for e in regular)
    if hit is None or hit[0] not in by_season:
        return None
    season, number = hit
    in_season = [e["number"] for e in regular if e["season"] == season]
    if number not in in_season:
        return None
    seasons = sorted(by_season)
    last = seasons[-1]
    return {
        "season": season,
        "number": number,
        "finale": number == max(in_season),
        "episodes": len(regular),
        "by_season": by_season,
        "rank": seasons.index(season) + 1,
        "series_finale": season == last
        and number == max(e["number"] for e in regular if e["season"] == last),
    }


def _bucket(rank: int) -> str:
    return "1" if rank == 1 else "2" if rank == 2 else "3+"


def _keys(ev: dict[str, Any]) -> list[str]:
    """The season-finale groups one death counts in."""
    era = f"before {ERA_SPLIT}" if ev["year"] < ERA_SPLIT else f"{ERA_SPLIT} or later"
    release = _release(ev["show"])
    keys = ["all", f"role:{ev['role']}", f"era:{era}"]
    keys += [f"release:{release}"] if release else []
    if ev["role"] == "regular":
        keys.append(f"regular-era:{era}")
        keys += [f"regular-release:{release}"] if release else []
    return keys


def compute(
    doc: dict[str, Any], episodes: dict[int, list[dict[str, Any]]], *, fetched_on: str
) -> dict[str, Any]:
    """The aggregate findings. ``episodes`` maps a TVmaze id to its episode list."""
    events = death_events(doc)
    finale: dict[str, dict[str, float]] = defaultdict(_group)
    order: dict[str, dict[str, float]] = defaultdict(_group)
    series: dict[str, float] = _group()
    per_show: Counter[str] = Counter()
    per_show_regular: Counter[str] = Counter()
    placed_shows: set[str] = set()
    placed = 0
    for ev in events:
        p = _placed(ev, episodes)
        if p is None:
            continue
        show_id = ev["show"]["id"]
        placed += 1
        placed_shows.add(show_id)
        expected = len(p["by_season"]) / p["episodes"]
        for key in _keys(ev):
            g = finale[key]
            g["deaths"] += 1
            g["in_position"] += p["finale"]
            g["expected"] += expected
        per_show[show_id] += p["finale"]
        per_show_regular[show_id] += p["finale"] and ev["role"] == "regular"
        order[_bucket(p["rank"])]["in_position"] += 1
        seasons = sorted(p["by_season"])
        for s, n in p["by_season"].items():
            order[_bucket(seasons.index(s) + 1)]["expected"] += n / p["episodes"]
        if ev["show"]["schedule"].get("status") == "Ended":
            series["deaths"] += 1
            series["in_position"] += p["series_finale"]
            series["expected"] += 1 / p["episodes"]
    for g in order.values():
        g["deaths"] = placed
    regulars = finale["role:regular"]
    lo, hi = wilson(int(regulars["in_position"]), int(regulars["deaths"]))
    return {
        "format": FORMAT_VERSION,
        "snapshot_generated_at": doc["generated_at"],
        "snapshot_content_digest": doc["content_digest"],
        "episodes_fetched_on": fetched_on,
        "death_events": len(events),
        "placed": placed,
        "placed_shows": len(placed_shows),
        "season_finale": _round(dict(finale)),
        "regular_ci95": [round(lo, 4), round(hi, 4)],
        "most_finale_deaths_one_show": max(per_show.values(), default=0),
        "most_regular_finale_deaths_one_show": max(per_show_regular.values(), default=0),
        "season_order": _round({k: order[k] for k in ("1", "2", "3+")}),
        "series_finale": _round({"ended": series})["ended"],
    }


def load_episodes(directory: Path) -> dict[int, list[dict[str, Any]]]:
    return {
        int(p.stem): json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(directory.glob("*.json"))
        if p.stem.isdigit()
    }


# --- the data file ------------------------------------------------------------

_GROUP_KEYS = {"deaths", "in_position", "baseline"}


def load(path: Path = DEFAULT_FINDINGS_PATH) -> dict[str, Any]:
    """The committed findings, checked for shape: only counts and shares."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != FORMAT_VERSION:
        raise FindingsError(f"{path}: not findings format {FORMAT_VERSION}")
    groups = [*data["season_finale"].values(), *data["season_order"].values()]
    groups.append(data["series_finale"])
    for g in groups:
        if set(g) != _GROUP_KEYS:
            raise FindingsError(f"{path}: a group has keys {sorted(g)}")
    for key in ("all", "role:regular", "role:recurring", "role:guest"):
        if key not in data["season_finale"]:
            raise FindingsError(f"{path}: no season_finale group {key!r}")
    return data


# --- formatting ---------------------------------------------------------------


def pct(part: float, whole: float = 1.0) -> str:
    """A whole-number percentage: 50 of 142 -> "35%"."""
    return f"{round(100 * part / whole)}%"


def times(share: float, baseline: float) -> str:
    """How many times the baseline, to one decimal: "4.5"."""
    return f"{share / baseline:.1f}"


def long_date(iso: str) -> str:
    day = dt.date.fromisoformat(iso[:10])
    return f"{day:%B} {day.day}, {day.year}"


def _row(label: str, g: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": label,
        "deaths": g["deaths"],
        "in_position": g["in_position"],
        "share": pct(g["in_position"], g["deaths"]),
        "baseline": pct(g["baseline"]),
    }


def view(data: dict[str, Any]) -> dict[str, Any]:
    """Every figure the pages print, formatted from ``data``."""
    sf = data["season_finale"]
    reg = sf["role:regular"]
    order = data["season_order"]
    series = data["series_finale"]
    split = [
        ("Died before " + str(ERA_SPLIT), f"era:before {ERA_SPLIT}"),
        (f"Died in {ERA_SPLIT} or later", f"era:{ERA_SPLIT} or later"),
        ("Broadcast or cable", "release:broadcast"),
        ("Streaming", "release:streaming"),
    ]
    return {
        "as_of": long_date(data["snapshot_generated_at"]),
        "as_of_iso": data["snapshot_generated_at"][:10],
        "episodes_on": long_date(data["episodes_fetched_on"]),
        "death_events": data["death_events"],
        "placed": data["placed"],
        "placed_shows": data["placed_shows"],
        "regular": {
            **_row("Regulars", reg),
            "times": times(reg["in_position"] / reg["deaths"], reg["baseline"]),
            "ci_level": "95%",
            "ci_low": pct(data["regular_ci95"][0]),
            "ci_high": pct(data["regular_ci95"][1]),
        },
        "guest": _row("Guests", sf["role:guest"]),
        "roles": [
            _row("Regulars", reg),
            _row("Recurring", sf["role:recurring"]),
            _row("Guests", sf["role:guest"]),
            _row("All roles", sf["all"]),
        ],
        "regular_splits": [
            _row(label, sf[f"regular-{key}"]) for label, key in split if f"regular-{key}" in sf
        ],
        "most_one_show": data["most_finale_deaths_one_show"],
        "order": [
            {
                "label": SEASON_LABELS[k],
                "deaths": order[k]["in_position"],
                "share": pct(order[k]["in_position"], order[k]["deaths"]),
                "episodes": pct(order[k]["baseline"]),
            }
            for k in ("1", "2", "3+")
        ],
        "first_season": {
            "share": pct(order["1"]["in_position"], order["1"]["deaths"]),
            "episodes": pct(order["1"]["baseline"]),
        },
        "series": {
            "deaths": series["deaths"],
            "in_position": series["in_position"],
            "share": pct(series["in_position"], series["deaths"]),
            "baseline": pct(series["baseline"]),
            "times": f"{round(series['in_position'] / series['deaths'] / series['baseline'])}",
        },
    }


def findings_csv(data: dict[str, Any], *, licence_url: str) -> str:
    """The aggregate table behind the page, CC BY-SA 4.0, with its credits."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(
        [
            f"# Queer Frame, when queer characters die in a show, as of "
            f"{data['snapshot_generated_at'][:10]}. Adapted from LezWatch.TV "
            "(https://lezwatchtv.com) and TVmaze (https://www.tvmaze.com, CC BY-SA 4.0). "
            f"License: CC BY-SA 4.0 ({licence_url})."
        ]
    )
    w.writerow(["measure", "group", "deaths_placed", "deaths_in_position", "baseline_share"])
    for key, g in data["season_finale"].items():
        w.writerow(["season_finale", key, g["deaths"], g["in_position"], g["baseline"]])
    for key, g in data["season_order"].items():
        w.writerow([f"season_{key}", "all", g["deaths"], g["in_position"], g["baseline"]])
    g = data["series_finale"]
    w.writerow(["series_finale", "ended_shows", g["deaths"], g["in_position"], g["baseline"]])
    return out.getvalue()


# --- the pages ----------------------------------------------------------------


FINDINGS_TITLE = "When queer TV characters die: season finales"


def headline(v: dict[str, Any]) -> str:
    """The page's H1, the Article headline and the press page's headline."""
    return f"{v['regular']['share']} of queer TV regulars who die are killed in a season finale"


def findings_description(v: dict[str, Any]) -> str:
    r = v["regular"]
    return (
        f"{r['share']} of queer TV regulars who die are killed in a season finale, against "
        f"{r['baseline']} of episodes. A dated analysis of LezWatch.TV and TVmaze data."
    )


def render_findings(
    doc: dict[str, Any], data: dict[str, Any], *, base_url: str, app_store_live: bool = False
) -> str:
    base = show_pages._clean_base_url(base_url)
    canonical = f"{base}/findings/finales/"
    crumbs = [(show_pages.SITE_NAME, f"{base}/"), ("Findings", canonical)]
    v = view(data)
    article = {
        "@type": "Article",
        "headline": headline(v),
        "datePublished": v["as_of_iso"],
        "url": canonical,
        "license": doc["licence"]["snapshot"]["url"],
        "isBasedOn": [a["url"] for a in doc["attribution"]],
    }
    return show_pages._ENV.get_template("findings.html.j2").render(
        **show_pages._common(doc, base, app_store_live),
        title=FINDINGS_TITLE,
        description=findings_description(v),
        canonical=canonical,
        crumbs=crumbs,
        breadcrumb=show_pages._structured(show_pages._breadcrumb(crumbs), article),
        v=v,
        headline=headline(v),
        csv_url=f"{base}/{CSV_PATH}",
        lezwatch_url=next(a["url"] for a in doc["attribution"] if a["source"] == "lezwatch"),
        tvmaze_url=next(a["url"] for a in doc["attribution"] if a["source"] == "tvmaze"),
        cc=doc["licence"]["snapshot"],
    )


PRESS_TITLE = "Queer Frame press kit: facts, images and contact"
PRESS_DESCRIPTION = (
    "Facts about Queer Frame, the spoiler-free guide to queer TV: what it is, price, "
    "platform, data sources, the app icon and screenshots, and a press contact."
)


def render_press(
    doc: dict[str, Any],
    data: dict[str, Any],
    *,
    base_url: str,
    app_store_live: bool = False,
    price: str,
    platform: str,
    images: frozenset[str] = frozenset(),
) -> str:
    """The press page. ``images`` names the PRESS_ASSETS files published
    beside it; only those are shown, so no image link is ever broken."""
    base = show_pages._clean_base_url(base_url)
    canonical = f"{base}/press/"
    crumbs = [(show_pages.SITE_NAME, f"{base}/"), ("Press", canonical)]
    return show_pages._ENV.get_template("press.html.j2").render(
        **show_pages._common(doc, base, app_store_live),
        title=PRESS_TITLE,
        description=PRESS_DESCRIPTION,
        canonical=canonical,
        crumbs=crumbs,
        breadcrumb=show_pages._structured(show_pages._breadcrumb(crumbs)),
        v=view(data),
        headline=headline(view(data)),
        findings_url=f"{base}/findings/finales/",
        price=price,
        platform=platform,
        app_store_live=app_store_live,
        contact=CONTACT_EMAIL,
        images=[
            {"src": f"{base}/press/{name}", "alt": alt, "width": w, "height": h}
            for name, _source, alt, w, h in PRESS_ASSETS
            if name in images
        ],
        lezwatch_url=next(a["url"] for a in doc["attribution"] if a["source"] == "lezwatch"),
        tvmaze_url=next(a["url"] for a in doc["attribution"] if a["source"] == "tvmaze"),
    )


def copy_press_assets(press_dir: Path, repo_root: Path = REPO_ROOT) -> frozenset[str]:
    """Copy the icon and screenshots that exist in the repository into
    ``press_dir``; return the names copied."""
    copied = set()
    for name, source, *_ in PRESS_ASSETS:
        src = repo_root / source
        if src.is_file():
            press_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, press_dir / name)
            copied.add(name)
    return frozenset(copied)


def main(argv: list[str]) -> int:
    if len(argv) == 4 and argv[0] == "compute":
        doc = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        episodes = load_episodes(Path(argv[2]))
        fetched = dt.datetime.fromtimestamp(
            max(p.stat().st_mtime for p in Path(argv[2]).glob("*.json")), tz=dt.UTC
        ).date()
        data = compute(doc, episodes, fetched_on=fetched.isoformat())
        Path(argv[3]).write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(view(data), indent=2))
        return 0
    print(
        "usage: python -m qtv_pipeline.findings compute SNAPSHOT EPISODES_DIR OUT_JSON",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
