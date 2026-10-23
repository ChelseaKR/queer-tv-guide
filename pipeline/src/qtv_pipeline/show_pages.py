"""A static web page for each of the most-listed shows: "does she die in <show>".

Built from the same snapshot the app reads (DECISIONS 0019), on this command:

    python -m qtv_pipeline.show_pages SNAPSHOT_JSON OUT_DIR [--base-url URL]
        [--app-store-live VALUE] [--limit N] [--notice-on-failure]

It writes ``shows/index.html``, ``shows/<slug>/index.html`` for each chosen
show, ``sitemap.xml`` and ``robots.txt`` into OUT_DIR. Nothing else, and no
page reads anything but the snapshot. Every file is rendered before the
first is written, so a build that fails leaves OUT_DIR as it was.

``--notice-on-failure`` is for the nightly workflow, where these pages must
never block the snapshot from publishing: any problem at all prints a
``::notice::`` line, writes nothing and exits 0. (The workflow policy forbids
``continue-on-error``, so the generator carries the rule.) Without the flag a
problem exits 1, as before.

Which shows (``select_shows``). The rule is "most listed characters": a show
is ranked by how many characters this snapshot lists for it (the length of
its ``characters`` entries, not LezWatch's own tally), most first, and ties
go to the lower LezWatch id so a rebuild picks the same shows. The first 50
are built. Shows with no listed character are never built: they have nothing
to answer from. Episode counts are not in the snapshot, so "most episodes"
is not a usable rule.

What a page may say. The answer to "does she die" is the one thing a visitor
did not ask to be told. It sits inside a native ``<details>`` element that is
closed when the page loads, and nowhere else: not in the title, the
description, the structured data, a heading, the facts or the list of
characters. LezWatch's death-revealing terms (the cliche ``dead`` and the
trope ``dead-queers``) and its trigger warnings stay in that element too.

What a page never says. LezWatch records deaths, not survival
(``schema/README.md``), so a character with no recorded death is "Unknown",
never "No" and never "Lives". A season count, rating or year LezWatch left
blank is "Not recorded", never zero.

Privacy. A page has no script (its one ``<script>`` is schema.org
``application/ld+json`` data, which a browser never runs), no cookie, no
form, no image, no font, no stylesheet link and no request to any host. Every
link to another host is an anchor the visitor chooses to follow. The App
Store link appears only when the launch switch is on, as in ``app_store.py``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jinja2

from qtv_pipeline.app_store import APP_STORE_URL, SwitchError, live_or_false

# The site's own domain (DECISIONS 0020). Pages serves the project path with a
# 301 to it, so every canonical URL, internal link, breadcrumb item and
# sitemap entry names this host and no github.io address.
DEFAULT_BASE_URL = "https://queerframe.app"
DEFAULT_LIMIT = 50
SITE_NAME = "Queer Frame"
TITLE_MAX = 60
DESCRIPTION_MAX = 155
# LezWatch slugs are WordPress slugs: lowercase, digits, hyphens, and the
# percent-encoding of non-Latin titles. Anything else would be a path or a
# query to a static host, so the build refuses it.
SLUG = re.compile(r"[a-z0-9%]+(?:-[a-z0-9%]+)*")
# LezWatch terms whose mere presence answers the question (the same slugs
# GuideCore keeps out of its always-visible lists).
DEATH_SPOILER_CLICHES = frozenset({"dead"})
DEATH_SPOILER_TROPES = frozenset({"dead-queers"})
UNKNOWN = "Unknown"
NOT_RECORDED = "Not recorded"

_ENV = jinja2.Environment(
    loader=jinja2.PackageLoader("qtv_pipeline", "templates"),
    autoescape=True,
    undefined=jinja2.StrictUndefined,
    keep_trailing_newline=True,
)


class ShowPagesError(ValueError):
    """The snapshot or an option cannot produce a safe site."""


@dataclass(frozen=True)
class CharacterView:
    name: str
    source_url: str
    role: str
    gender: str
    sexuality: str
    dies: bool
    status: str


@dataclass(frozen=True)
class Answer:
    headline: str
    notes: list[str]


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def select_shows(doc: dict[str, Any], limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """The shows to build: most listed characters first, ties by LezWatch id."""
    listed: dict[str, int] = {}
    for character in doc["characters"]:
        for link in character["shows"]:
            listed[link["show_id"]] = listed.get(link["show_id"], 0) + 1
    ranked = sorted(
        (s for s in doc["shows"] if listed.get(s["id"], 0) > 0),
        key=lambda s: (-listed[s["id"]], s["lwtv_id"]),
    )
    chosen = ranked[:limit]
    slugs = [s["slug"] for s in chosen]
    bad = [s for s in slugs if not SLUG.fullmatch(s)]
    if bad:
        raise ShowPagesError(f"unsafe slug(s) for a path: {bad}")
    if len(set(slugs)) != len(slugs):
        raise ShowPagesError("two chosen shows share a slug")
    return chosen


def fit(candidates: list[str], limit: int) -> str:
    """The first candidate within ``limit`` characters; the last is clipped."""
    for text in candidates:
        if len(text) <= limit:
            return text
    return candidates[-1][: limit - 1].rstrip() + "…"


def show_title(name: str) -> str:
    return fit(
        [
            f"Does she die in {name}? Spoiler-safe answer | {SITE_NAME}",
            f"Does she die in {name}? Spoiler-safe answer",
            f"Does she die in {name}?",
            f"Does she die in {name}?",
        ],
        TITLE_MAX,
    )


def show_description(name: str) -> str:
    return fit(
        [
            f"Does she die in {name}? The queer characters LezWatch.TV lists, "
            "with the full answer hidden until you open it.",
            f"Does she die in {name}? The full answer is hidden until you open it.",
            f"Does she die in {name}? The full answer is hidden until you open it.",
        ],
        DESCRIPTION_MAX,
    )


def _term_name(term: dict[str, Any] | None) -> str:
    return term["name"] if term else NOT_RECORDED


def _death_status(death: dict[str, Any], other_shows: int) -> tuple[bool, str]:
    """(dies, sentence). Only a recorded death is a yes; everything else is
    Unknown, because LezWatch records deaths, not survival."""
    if death["death_known"] is not True or death["died"] is not True:
        return False, f"{UNKNOWN}. LezWatch.TV has not recorded a death."
    years = sorted(death["years"])
    if not years:
        text = "Dies (year not recorded)."
    elif len(years) > 1:
        text = f"Dies more than once ({', '.join(map(str, years))})."
    else:
        text = f"Dies ({years[0]})."
    if other_shows:
        text += " The record belongs to the character, not to one show, so it does not say whether it happens in this one."
    return True, text


def _characters(doc: dict[str, Any], show: dict[str, Any]) -> list[CharacterView]:
    views = []
    for c in sorted(doc["characters"], key=lambda c: c["lwtv_id"]):
        link = next((x for x in c["shows"] if x["show_id"] == show["id"]), None)
        if link is None:
            continue
        dies, status = _death_status(c["death"], len(c["shows"]) - 1)
        views.append(
            CharacterView(
                name=c["name"],
                source_url=c["source_url"],
                role=(link["role"] or NOT_RECORDED).capitalize(),
                gender=_term_name(c["gender"]),
                sexuality=_term_name(c["sexuality"]),
                dies=dies,
                status=status,
            )
        )
    return views


def _answer(show: dict[str, Any], cast: list[CharacterView]) -> Answer:
    notes: list[str] = []
    dead = [c.name for c in cast if c.dies]
    reported = show["counts"]["deaths_source_reported"]
    if reported is not None and reported != len(dead):
        notes.append(
            f"LezWatch.TV's own tally for this show is {reported} "
            f"{_plural(reported, 'death', 'deaths')}; its character records list {len(dead)}."
        )
    notes += [
        f"LezWatch.TV tags this show “{t['name']}”."
        for t in show["tropes"]
        if t["slug"] in DEATH_SPOILER_TROPES
    ]
    n = len(cast)
    listed = f"{n} listed {_plural(n, 'character', 'characters')}"
    if not dead:
        headline = (
            f"{UNKNOWN}. LezWatch.TV has no death on record for "
            f"{'the one listed character' if n == 1 else f'any of the {listed}'}. "
            "It records deaths and nothing else, so this does not say anyone lives."
        )
    else:
        headline = (
            f"Yes. {len(dead)} of {listed} {_plural(len(dead), 'dies', 'die')}: {', '.join(dead)}."
        )
        if len(dead) < n:
            notes.append(
                f"For the other {n - len(dead)}, the answer is {UNKNOWN.lower()}: "
                "LezWatch.TV records deaths, not survival."
            )
    return Answer(headline, notes)


def _years(years: dict[str, Any]) -> str:
    start, end = years["start"], years["end"]
    if start is None:
        return NOT_RECORDED
    if end is not None:
        return str(start) if end == start else f"{start} to {end}"
    return f"{start} to present" if years["on_air"] == "yes" else f"{start} (end year not recorded)"


def _facts(show: dict[str, Any]) -> list[tuple[str, str]]:
    sched = show["schedule"]
    seasons = show["seasons"]
    channel = (
        ", ".join(n["name"] for n in show["networks"])
        or (sched["network"] or sched["web_channel"] or {}).get("name")
        or NOT_RECORDED
    )
    return [
        ("Years", _years(show["years"])),
        ("Seasons", NOT_RECORDED if seasons is None else str(seasons)),
        ("Format", _term_name(show["format"])),
        ("Network", channel),
        ("Country", ", ".join(c["name"] for c in show["countries"]) or NOT_RECORDED),
        ("Genres", ", ".join(g["name"] for g in show["genres"]) or NOT_RECORDED),
        ("Worth it, per LezWatch.TV", show["ratings"]["worth_it"] or "Not rated"),
        (
            "Run status, per TVmaze",
            sched["status"] if sched["schedule_known"] and sched["status"] else UNKNOWN,
        ),
    ]


def _breadcrumb(items: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": url}
            for i, (name, url) in enumerate(items, start=1)
        ],
    }


def _common(doc: dict[str, Any], base_url: str, app_store_live: bool) -> dict[str, Any]:
    return {
        "site_name": SITE_NAME,
        "base_url": base_url,
        "licence": doc["licence"],
        "attribution": doc["attribution"],
        "generated_on": doc["generated_at"][:10],
        "app_store_url": APP_STORE_URL if app_store_live else None,
    }


def render_show(
    doc: dict[str, Any], show: dict[str, Any], *, base_url: str, app_store_live: bool = False
) -> str:
    cast = _characters(doc, show)
    canonical = f"{base_url}/shows/{show['slug']}/"
    crumbs = [
        (SITE_NAME, f"{base_url}/"),
        ("Shows", f"{base_url}/shows/"),
        (show["title"], canonical),
    ]
    return _ENV.get_template("show.html.j2").render(
        **_common(doc, base_url, app_store_live),
        title=show_title(show["title"]),
        description=show_description(show["title"]),
        canonical=canonical,
        show=show,
        crumbs=crumbs,
        breadcrumb=_breadcrumb(crumbs),
        facts=_facts(show),
        cast=cast,
        answer=_answer(show, cast),
        tvmaze_url=show["schedule"]["tvmaze_url"],
    )


def render_index(
    doc: dict[str, Any],
    shows: list[dict[str, Any]],
    *,
    base_url: str,
    app_store_live: bool = False,
) -> str:
    canonical = f"{base_url}/shows/"
    crumbs = [(SITE_NAME, f"{base_url}/"), ("Shows", canonical)]
    return _ENV.get_template("index.html.j2").render(
        **_common(doc, base_url, app_store_live),
        title=fit(
            [f"Does she die? Queer TV shows, spoiler-safe | {SITE_NAME}", "Does she die?"], 60
        ),
        description=fit(
            [
                "Does she die in your show? Pick a show with queer characters; the full "
                "answer stays hidden until you open it.",
                "Does she die in your show? The full answer stays hidden until you open it.",
            ],
            DESCRIPTION_MAX,
        ),
        canonical=canonical,
        crumbs=crumbs,
        breadcrumb=_breadcrumb(crumbs),
        shows=[
            {"slug": s["slug"], "title": s["title"], "years": _years(s["years"])} for s in shows
        ],
    )


def render_sitemap(doc: dict[str, Any], shows: list[dict[str, Any]], *, base_url: str) -> str:
    urls = [f"{base_url}/shows/", *(f"{base_url}/shows/{s['slug']}/" for s in shows)]
    return _ENV.get_template("sitemap.xml.j2").render(urls=urls, lastmod=doc["generated_at"][:10])


def _clean_base_url(value: str) -> str:
    base = value.rstrip("/")
    if not base.startswith("https://") or any(c in base for c in "?# \"'<>"):
        raise ShowPagesError(f"base URL must be a plain https:// URL, got {value!r}")
    return base


def render_robots(*, base_url: str) -> str:
    """Everything may be crawled, and the sitemap is named."""
    return f"User-agent: *\nAllow: /\n\nSitemap: {base_url}/sitemap.xml\n"


def render_site(
    doc: dict[str, Any],
    *,
    base_url: str = DEFAULT_BASE_URL,
    app_store_live: bool = False,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, str]:
    """Every file of the site, as ``{relative path: text}``; writes nothing."""
    base = _clean_base_url(base_url)
    if not isinstance(doc, dict):
        raise ShowPagesError("the snapshot file is not a JSON object")
    # Fail before rendering if the file is not a snapshot this module understands.
    dt.date.fromisoformat(doc["generated_at"][:10])
    shows = select_shows(doc, limit)
    if not shows:
        raise ShowPagesError("no show has a listed character; nothing to build")
    files = {
        "shows/index.html": render_index(doc, shows, base_url=base, app_store_live=app_store_live)
    }
    for show in shows:
        files[f"shows/{show['slug']}/index.html"] = render_show(
            doc, show, base_url=base, app_store_live=app_store_live
        )
    files["sitemap.xml"] = render_sitemap(doc, shows, base_url=base)
    files["robots.txt"] = render_robots(base_url=base)
    return files


def build_site(
    doc: dict[str, Any],
    out_dir: Path,
    *,
    base_url: str = DEFAULT_BASE_URL,
    app_store_live: bool = False,
    limit: int = DEFAULT_LIMIT,
) -> list[Path]:
    """Write the pages, the sitemap and robots.txt under ``out_dir``; return the files.

    All of it is rendered first. If a write then fails, the files and
    directories this call made are removed again, so a half-built site never
    reaches the Pages artifact.
    """
    files = render_site(doc, base_url=base_url, app_store_live=app_store_live, limit=limit)
    written: list[Path] = []
    made_dirs: list[Path] = []
    try:
        for relative, text in files.items():
            path = out_dir / relative
            # Ancestors under out_dir that do not exist yet, outermost first.
            missing = [d for d in path.parents if out_dir in d.parents or d == out_dir]
            made_dirs.extend(d for d in reversed(missing) if not d.exists())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            written.append(path)
    except OSError:
        for path in written:
            path.unlink(missing_ok=True)
        for directory in reversed(made_dirs):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        raise
    return written


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m qtv_pipeline.show_pages")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--app-store-live", default="false")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--notice-on-failure", action="store_true")
    args = parser.parse_args(argv)
    try:
        doc = json.loads(args.snapshot.read_text(encoding="utf-8"))
        files = build_site(
            doc,
            args.out_dir,
            base_url=args.base_url,
            app_store_live=live_or_false(args.app_store_live),
            limit=args.limit,
        )
    except Exception as exc:  # the soft mode must hold for any problem
        if args.notice_on_failure:
            why = " ".join(f"{type(exc).__name__}: {exc}".split())
            print(
                "::notice title=show pages skipped::The per-show pages were not built "
                f"and the snapshot is published without them: {why}"
            )
            return 0
        if not isinstance(exc, (ShowPagesError, SwitchError, OSError, ValueError, KeyError)):
            raise
        print(f"show_pages: refused: {exc}", file=sys.stderr)
        return 1
    print(f"show_pages: wrote {len(files)} files to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
