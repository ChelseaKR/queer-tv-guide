"""One page of queer TV with a new episode coming up: ``/airing/`` (DECISIONS 0033).

``show_pages.render_site`` builds it beside the show pages, from the same
snapshot and nothing else: no request to LezWatch.TV, TVmaze or any other
host. It is in the sitemap and open to search (one URL, not a family of
templates, so 0028's hold does not apply), and the home page and the shows
index link to it.

Which shows (``plan_airing``):

- LezWatch.TV marks the show on air (``years.on_air == "yes"``), and its
  LezWatch end year, when it has one, is not before the episode's year.
  TVmaze sometimes lists a revival LezWatch.TV has not caught up with (Law &
  Order: LezWatch.TV ends it in 2010, TVmaze lists the 2022 revival, the
  issue #52 pattern); those are left out and named in the build log.
- TVmaze has a schedule for it (``schedule_known``) and lists a next
  episode dated from the snapshot's date through the end of the month
  ``WINDOW_MONTHS`` months later (built 2026-11-05: through March 31, 2027).
  The window rolls with each nightly build.

How they are grouped: season premieres (episode 1 of a numbered season)
first, then other new episodes, then soaps and telenovelas (LezWatch.TV's
genres ``SOAP_GENRES``) under their own heading, since they air so often
that "next episode" means little. Each group is in date order, then A to Z.

What a line says: the title (linked to its show page when one is built,
otherwise to LezWatch.TV), the network, the date and, when TVmaze gives
both numbers, the season and episode, and how many queer characters
LezWatch.TV lists. A soap's line gives only the date.

What it never says. No episode name: one can give a death away ("Dead
Air"). No character at all, so no character's years: a character whose
years reach the new season would tell you she survived. No trope, no death
record, no death count, and no order a death could change. A test swaps
every death record and asserts not a byte changes.

Absence. A show with no TVmaze date is not on the page, and one sentence
says that this does not mean it is not coming back. A missing network,
season or episode number, or character count shortens the line; it is never
printed as a placeholder. A build in which no show has a TVmaze schedule at
all says the schedules are missing from this build, never "nothing airs".

The app. While the App Store switch is off, one sentence says the iPhone app
(new-episode reminders, the Up Next widget) is not on the App Store yet,
with no link. On, the shared "Get the iPhone app" block
(``app_store.get_app_block``, DECISIONS 0047) links to the plain App Store
URL in ``app_store.py``, with no campaign or tracking parameter. The page has no analytics and no
script, like every other page.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from qtv_pipeline.show_pages import (
    _ENV,
    SITE_NAME,
    SOAP_GENRES,
    TITLE_MAX,
    _breadcrumb,
    _common,
    _listed_characters,
    _long_date,
    _opening_network,
    _structured,
    fit,
    sort_title,
    us_date,
)

# The window ends on the last day of the month this many months after the
# snapshot's month (November 2026 -> March 31, 2027).
WINDOW_MONTHS = 4
DESCRIPTION_MAX = 155
_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


@dataclass(frozen=True)
class Airing:
    title: str
    url: str
    # True when ``url`` is the show's page on this site, False when it is
    # LezWatch.TV's page for it (no page is built here).
    own_page: bool
    network: str | None
    airdate: str  # ISO date, for <time datetime>
    when: str  # "Friday, November 20, 2026"
    kind: str  # "premiere", "episode" or "soap"
    season: int | None
    number: int | None
    listed: int


@dataclass(frozen=True)
class Plan:
    start: dt.date
    end: dt.date
    premieres: list[Airing]
    episodes: list[Airing]
    soaps: list[Airing]
    schedules_known: bool
    notes: list[str]

    @property
    def total(self) -> int:
        return len(self.premieres) + len(self.episodes) + len(self.soaps)


def window_end(start: dt.date, months: int = WINDOW_MONTHS) -> dt.date:
    """The last day of the month ``months`` after ``start``'s month."""
    index = start.year * 12 + start.month - 1 + months + 1  # the month after the last
    first_after = dt.date(index // 12, index % 12 + 1, 1)
    return first_after - dt.timedelta(days=1)


def month_year(day: dt.date) -> str:
    return f"{_MONTHS[day.month - 1]} {day.year}"


def _airdate(show: dict[str, Any]) -> dt.date | None:
    sched = show["schedule"]
    if sched["schedule_known"] is not True or not sched["next_episode"]:
        return None
    value = sched["next_episode"].get("airdate")
    if not isinstance(value, str) or _long_date(value) is None:
        return None
    return dt.date.fromisoformat(value)


def _number(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _log_text(value: Any) -> str:
    return " ".join(str(value).split())


def plan_airing(doc: dict[str, Any], built: dict[str, str], *, months: int = WINDOW_MONTHS) -> Plan:
    """The shows on the page, grouped and ordered. ``built`` maps a show id
    to the URL of its page on this site, for the shows that have one."""
    start = dt.date.fromisoformat(doc["generated_at"][:10])
    end = window_end(start, months)
    listed = _listed_characters(doc)
    groups: dict[str, list[Airing]] = {"premiere": [], "episode": [], "soap": []}
    notes: list[str] = []
    for show in doc["shows"]:
        day = _airdate(show)
        if day is None or not start <= day <= end:
            continue
        years = show["years"]
        label = f"{_log_text(show['title'])} (id {_log_text(show['lwtv_id'])})"
        if years["on_air"] != "yes":
            notes.append(
                f"airing: left out {label}: TVmaze lists an episode on {day}, "
                "but LezWatch.TV does not mark the show on air"
            )
            continue
        if isinstance(years["end"], int) and years["end"] < day.year:
            notes.append(
                f"airing: left out {label}: TVmaze lists an episode on {day}, "
                f"but LezWatch.TV ends the show in {years['end']}"
            )
            continue
        episode = show["schedule"]["next_episode"]
        season, number = _number(episode.get("season")), _number(episode.get("number"))
        soap = any(g["slug"] in SOAP_GENRES for g in show["genres"])
        kind = "soap" if soap else ("premiere" if season and number == 1 else "episode")
        own = show["id"] in built
        numbered = bool(season and number) and kind != "soap"
        groups[kind].append(
            Airing(
                title=show["title"],
                url=built[show["id"]] if own else show["source_url"],
                own_page=own,
                network=_opening_network(show),
                airdate=day.isoformat(),
                when=us_date(day),
                kind=kind,
                season=season if numbered else None,
                number=number if numbered else None,
                listed=listed.get(show["id"], 0),
            )
        )
    for items in groups.values():
        items.sort(key=lambda a: (a.airdate, sort_title(a.title), a.url))
    known = any(s["schedule"]["schedule_known"] is True for s in doc["shows"])
    plan = Plan(start, end, groups["premiere"], groups["episode"], groups["soap"], known, notes)
    notes.append(
        f"airing: {plan.total} shows with a new episode through {end}: "
        f"{len(plan.premieres)} season premieres, {len(plan.episodes)} other shows, "
        f"{len(plan.soaps)} soaps and telenovelas"
    )
    return plan


def airing_title(end: dt.date) -> str:
    return fit(
        [
            f"Queer TV airing now: new episodes through {month_year(end)}",
            f"Queer TV airing now, through {month_year(end)}",
            "Queer TV airing now",
        ],
        TITLE_MAX,
    )


def airing_description(plan: Plan) -> str:
    through = month_year(plan.end)
    premieres = len(plan.premieres)
    tail = "No spoilers."
    shows, have = ("One TV show", "has") if plan.total == 1 else (f"{plan.total} TV shows", "have")
    which = (
        "a season premiere"
        if plan.total == 1
        else f"{premieres} of them {'a season premiere' if premieres == 1 else 'season premieres'}"
    )
    candidates = []
    if plan.total and premieres:
        candidates.append(
            f"{shows} with queer women, non-binary and trans characters {have} new "
            f"episodes coming through {through}, {which}. {tail}"
        )
    if plan.total:
        candidates.append(
            f"{shows} with queer characters {have} new episodes coming through "
            f"{through}. Dates from TVmaze, characters from LezWatch.TV. {tail}"
        )
    candidates.append(
        f"Queer TV with new episodes coming through {through}. Dates from TVmaze, "
        f"characters from LezWatch.TV. {tail}"
    )
    return fit(candidates, DESCRIPTION_MAX)


def render_airing(
    doc: dict[str, Any],
    *,
    base_url: str,
    built: dict[str, str],
    app_store_live: bool = False,
    plan: Plan | None = None,
) -> str:
    """The page, from ``plan`` (``plan_airing`` when not given)."""
    plan = plan or plan_airing(doc, built)
    canonical = f"{base_url}/airing/"
    crumbs = [(SITE_NAME, f"{base_url}/"), ("Airing now", canonical)]
    every = [*plan.premieres, *plan.episodes, *plan.soaps]
    listing = {
        "@type": "ItemList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i,
                "item": {"@type": "TVSeries", "name": a.title, "url": a.url},
            }
            for i, a in enumerate(every, start=1)
        ],
    }
    tvmaze = next(a for a in doc["attribution"] if a["source"] == "tvmaze")
    return _ENV.get_template("airing.html.j2").render(
        **_common(doc, base_url, app_store_live),
        title=airing_title(plan.end),
        description=airing_description(plan),
        canonical=canonical,
        crumbs=crumbs,
        breadcrumb=_structured(_breadcrumb(crumbs), listing),
        plan=plan,
        start_text=us_date(plan.start),
        end_text=us_date(plan.end),
        through=month_year(plan.end),
        tvmaze_url=tvmaze["url"],
    )
