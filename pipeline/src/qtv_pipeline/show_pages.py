"""A static web page per show with enough data to answer "does she die in <show>".

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

Which shows (``select_shows``, DECISIONS 0021 and 0025), in this order:

1. The hand-picked list, when the file ``data/show_pages_pinned.json`` exists
   (``load_pinned`` validates it): up to 50 entries, in the file's order. An
   entry whose LezWatch id is not in the snapshot, or whose show lists no
   character there, is skipped and named in the build log
   (``plan_selection``).
2. Every other show that meets the inclusion rule (``qualifies``): at least
   ``MIN_LISTED`` (5) characters listed in this snapshot (the length of its
   ``characters`` entries, not LezWatch's own tally) and a TVmaze match (a
   TVmaze page URL). Most listed characters first; ties go to the lower
   LezWatch id so a rebuild picks the same shows.
3. Only if that makes fewer than ``PAGE_FLOOR`` (50) pages: the most-listed
   remaining shows, same order, up to 50. On the real data this never runs;
   it keeps a thin snapshot from shrinking the site below the 50 pages that
   were first published.

At most ``DEFAULT_LIMIT`` pages are built (``--limit``); a cut is logged.
A chosen show whose slug is not a safe path segment, or repeats the slug of
a show earlier in that order, gets no page and no link, and is named in the
build log; the rest are built. A slug that carries percent-encoding (a
non-Latin title) is written to disk decoded (``slug_dir``), because the
static host decodes the URL before it looks for the file; its URLs keep the
encoded form. A pinned show left out this way, or more than
``SKIP_MAX_SHARE`` (5%) of the chosen shows left out, refuses the build.
Shows with no listed character are never built, pinned or not: they have
nothing to answer from. Episode counts are not in the snapshot, so "most
episodes" is not a usable rule.

Which pages search engines may index (``indexed_show_ids``, DECISIONS
0028). Every chosen show gets a page, and every page stays linked from the
shows index and its neighbors, but only the hand-picked list (or, with no
list, the first ``PINNED_MAX`` pages in the published order) is in the
sitemap. Every other show page carries ``<meta name="robots"
content="noindex,follow">``: search engines may follow its links but are
asked not to show it. The list or rule in ``INDEX_EXTRA_IDS`` and
``INDEX_MIN_LISTED`` widens the indexed set. That one function decides
both the sitemap and the robots tag, and ``index_problems`` refuses a build
in which they disagree.

Words for search (DECISIONS 0024 and 0027). The title asks the question
people type, with the count of listed characters when it fits ("Do any of
the <n> queer characters in <show> die?", then the 0024 forms with
"Spoiler-free"); the description gives that count and names up to three
listed characters, regulars first, each with the identity the page shows
("Lisa Simpson (bisexual)"), because people search "does <character> die
in <show>" and "is <character> a lesbian", and says who dies is behind the
spoiler warning; the
characters heading says "Queer women, non-binary and trans characters in
<show>", because that is what LezWatch.TV covers; one fixed sentence on every
page names the bury-your-gays trope and another says that cisgender gay and
bisexual men are not listed. None of these depends on any
death record, so none of them can answer the question. The one structured
data block holds a BreadcrumbList and a schema.org TVSeries (name, page,
LezWatch.TV and TVmaze pages, years, seasons, genres, countries and the
characters' names). There is no FAQPage: its answer would be the spoiler.

The opening (``opening``, DECISIONS 0029). A page's first paragraph is a
sentence only that show can have: the number of listed characters, the
network and years, two names (regulars first) and, from TVmaze, when the most
recent episode aired and when the next is listed. It uses no death record and
no episode name, and a fact the snapshot lacks is left out of the sentence,
never printed as a placeholder.

What a page may say. The answer to "does she die" is the one thing a visitor
did not ask to be told. It sits inside a native ``<details>`` element that is
closed when the page loads, and nowhere else: not in the title, the
description, the structured data, a heading, the facts or the list of
characters. LezWatch's death-revealing terms (the cliche ``dead`` and the
trope ``dead-queers``) stay in that element too. LezWatch's trigger-warning
level (``low``, ``medium`` or ``high``, which says how intense a show is and
nothing about who dies) is a facts row; any other trigger term is never
printed (DECISIONS 0031).

Seasons (``seasons_fact``, DECISIONS 0031). For a show TVmaze lists as Ended, when TVmaze's last season number differs from
LezWatch's season count, the page shows TVmaze's, labeled "per TVmaze".
When LezWatch has no count, TVmaze's latest season fills it ("3 so far" for
a show still running). A TVmaze season number of 1900 or more is a year (a
show numbered by year), not a count, and is never used.

What a page never says. LezWatch records deaths, not survival
(``schema/README.md``), so a character with no recorded death is "Unknown",
never "No" and never "Lives". A season count, rating or year LezWatch left
blank is "Not recorded", never zero.

Privacy. A page has no script (its one ``<script>`` is schema.org
``application/ld+json`` data, which a browser never runs), no cookie, no
form, no image, no font, no stylesheet link and no request to any host. Every
link to another host is an anchor the visitor chooses to follow. The App
Store link, and Safari's Smart App Banner tag (a ``<meta>``, which fetches
nothing), appear only when the launch switch is on, with the same URL, tag
and price copy as ``app_store.py`` (DECISIONS 0023).

While the switch is off, a show page says in one fixed sentence that
Queer Frame is also an iPhone app that is not on the App Store yet, with no
link (there is no listing to link to).

Links between pages. Each show page links to the shows before and after it
in the published order (the order of the shows index and the sitemap,
wrapping at the ends) and to the shows index, so every page is reachable
from two others as well as from the index. It also links to up to four
similar shows (``related``): LezWatch.TV's own similar shows that have a
page, then the pages sharing the most genres. Tropes are never used, since
LezWatch's death trope would make "similar" a hint. The link text is the
show's title and nothing else.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import unicodedata
import urllib.parse
from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import jinja2

from qtv_pipeline.app_store import (
    APP_STORE_URL,
    BANNER,
    PRICE_COPY,
    SwitchError,
    live_or_false,
)

# The site's own domain (DECISIONS 0020). Pages serves the project path with a
# 301 to it, so every canonical URL, internal link, breadcrumb item and
# sitemap entry names this host and no github.io address.
DEFAULT_BASE_URL = "https://queerframe.app"
# The most pages one build writes (DECISIONS 0025). The rule picks about 350
# today; the cap keeps a surprise in LezWatch's data from multiplying the
# site, and stays far below a sitemap file's 50,000-URL limit.
DEFAULT_LIMIT = 600
SITEMAP_MAX_URLS = 50_000
# The hand-picked list's size (DECISIONS 0021).
PINNED_MAX = 50
# The inclusion rule (DECISIONS 0025): this many listed characters, and a
# TVmaze match.
MIN_LISTED = 5
# Fewer pages than this and the most-listed shows fill the gap (see above).
PAGE_FLOOR = 50
# Which show pages search engines may index (DECISIONS 0028): the hand-picked
# list, and nothing else until the widen criterion there is met. To widen, add
# LezWatch ids here (by list), or set INDEX_MIN_LISTED to index every built
# show with at least that many listed characters (by rule). Every other show
# page carries ROBOTS_HOLD and is left out of the sitemap.
INDEX_EXTRA_IDS: frozenset[int] = frozenset()
INDEX_MIN_LISTED: int | None = None
ROBOTS_HOLD = "noindex,follow"
RELATED_LIMIT = 4
# A chosen show whose slug is unsafe or repeated is left out and logged; more
# than this share of them left out refuses the build (``_drop_bad_slugs``).
SKIP_MAX_SHARE = 0.05
# Character names in a description, at most; regulars first (``_roles_first``).
DESCRIPTION_NAMES = 3
# Character names in the page's opening sentence (``opening``, DECISIONS 0029).
OPENING_NAMES = 2
ROLE_ORDER = {"regular": 0, "recurring": 1, "guest": 2}
# The description's identity labels (``identity``, DECISIONS 0027).
LESBIAN_SEXUALITIES = frozenset({"Homosexual", "Lesbian"})
LESBIAN_GENDERS = frozenset({"Cisgender", "Cisgender Woman", "Trans Woman"})
SEXUALITY_LABELS = frozenset(
    {
        "Bisexual",
        "Pansexual",
        "Queer",
        "Asexual",
        "Demisexual",
        "Fluid",
        "Questioning",
        "Non-Monosexual",
    }
)
NO_GENDER_LABEL = frozenset({"Unknown", "Not recorded"})
# The hand-picked list (DECISIONS 0021). Resolved from the source tree, so it
# is used by `python -m qtv_pipeline.show_pages` and `make site`; deleting the
# file restores the character-count rule.
DEFAULT_PINNED_PATH = Path(__file__).resolve().parents[2] / "data" / "show_pages_pinned.json"
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
# LezWatch's trigger-warning levels (DECISIONS 0031). They rate how intense
# a show is and name no event, so the level is a facts row. Any other
# trigger term is never printed outside the answer.
TRIGGER_LEVELS = {"low": "Low", "medium": "Medium", "high": "High"}
# A TVmaze season number this large is a year (soaps and anime numbered by
# year, "2011"), not a season count (DECISIONS 0031).
SEASON_IS_A_YEAR = 1900

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
    # A death LezWatch records for the character that this show's years do
    # not place in this show (DECISIONS 0030). Never a yes.
    elsewhere: bool = False


@dataclass(frozen=True)
class Answer:
    headline: str
    notes: list[str]


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


@dataclass(frozen=True)
class Pin:
    lezwatch_id: int
    slug: str
    title: str
    reason: str


def _pin_from_entry(path: Path, n: int, entry: Any) -> Pin:
    if not isinstance(entry, dict):
        raise ShowPagesError(f"{path}: entry {n} is not an object")
    ident = entry.get("lezwatch_id")
    if isinstance(ident, bool) or not isinstance(ident, int):
        raise ShowPagesError(f"{path}: entry {n} has no integer lezwatch_id")
    texts: dict[str, str] = {}
    missing = []
    for key in ("slug", "title", "reason"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            texts[key] = value
        else:
            missing.append(key)
    if missing:
        raise ShowPagesError(f"{path}: entry {n} (id {ident}) has no {', '.join(missing)}")
    return Pin(ident, texts["slug"], texts["title"], texts["reason"])


def load_pinned(path: Path) -> list[Pin] | None:
    """The pinned list in file order, or None when the file does not exist.

    A file that exists but is wrong is an error, never a silent fall back to
    the other rule: more than 50 entries (``PINNED_MAX``), a repeated id or slug, an id
    that is not an integer, or a missing slug, title or reason."""
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = raw["shows"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ShowPagesError(f"{path}: not a pinned list: {exc!r}") from exc
    if not isinstance(raw.get("how_chosen"), str) or not raw["how_chosen"].strip():
        raise ShowPagesError(f"{path}: how_chosen must say how the list was chosen")
    if not isinstance(entries, list) or len(entries) > PINNED_MAX:
        raise ShowPagesError(f"{path}: at most {PINNED_MAX} shows may be pinned")
    pins = [_pin_from_entry(path, n, entry) for n, entry in enumerate(entries, 1)]
    ids = [p.lezwatch_id for p in pins]
    slugs = [p.slug for p in pins]
    if len(set(ids)) != len(ids):
        raise ShowPagesError(
            f"{path}: repeated lezwatch_id: {sorted({i for i in ids if ids.count(i) > 1})}"
        )
    if len(set(slugs)) != len(slugs):
        raise ShowPagesError(
            f"{path}: repeated slug: {sorted({x for x in slugs if slugs.count(x) > 1})}"
        )
    return pins


def _listed_characters(doc: dict[str, Any]) -> dict[str, int]:
    listed: dict[str, int] = {}
    for character in doc["characters"]:
        for link in character["shows"]:
            listed[link["show_id"]] = listed.get(link["show_id"], 0) + 1
    return listed


def qualifies(show: dict[str, Any], listed: dict[str, int]) -> bool:
    """The inclusion rule (DECISIONS 0025): at least ``MIN_LISTED`` listed
    characters, so the answer, the character list and the description have
    substance, and a TVmaze match, so the run status, network and TVmaze
    credit are real. Nothing about deaths goes into it."""
    return listed.get(show["id"], 0) >= MIN_LISTED and bool(show["schedule"]["tvmaze_url"])


RULE = (
    f"every show with at least {MIN_LISTED} listed characters and a TVmaze match, "
    "most listed first, then lower LezWatch id"
)


def plan_selection(
    doc: dict[str, Any], limit: int = DEFAULT_LIMIT, pinned: list[Pin] | None = None
) -> tuple[list[dict[str, Any]], list[str]]:
    """The shows to build, in order, and one log line per thing worth saying.

    Pinned shows first, in the list's order; a pin that is not in the snapshot
    or lists no character is skipped and named. Then every show that
    ``qualifies``; then, below ``PAGE_FLOOR`` pages, the most-listed others.
    Most listed characters first in both, ties by lower LezWatch id. At most
    ``limit`` in all."""
    listed = _listed_characters(doc)
    ranked = sorted(
        (s for s in doc["shows"] if listed.get(s["id"], 0) > 0),
        key=lambda s: (-listed[s["id"]], s["lwtv_id"]),
    )
    notes: list[str] = []
    chosen: list[dict[str, Any]] = []
    if pinned is None:
        notes.append(f"show_pages: selection rule: {RULE}")
    else:
        by_id = {s["lwtv_id"]: s for s in doc["shows"]}
        for pin in pinned[:limit]:
            show = by_id.get(pin.lezwatch_id)
            if show is None:
                notes.append(
                    f"show_pages: pinned list: skipped {pin.title} (id {pin.lezwatch_id}): "
                    "not in the snapshot"
                )
            elif listed.get(show["id"], 0) == 0:
                notes.append(
                    f"show_pages: pinned list: skipped {pin.title} (id {pin.lezwatch_id}): "
                    "the snapshot lists no character for it"
                )
            else:
                chosen.append(show)
        notes.insert(
            0,
            f"show_pages: selection rule: pinned list ({len(chosen)} of {len(pinned)} built), "
            f"then {RULE}",
        )
    pinned_count = len(chosen)
    taken = {s["id"] for s in chosen}
    by_rule = [s for s in ranked if s["id"] not in taken and qualifies(s, listed)]
    chosen += by_rule
    taken.update(s["id"] for s in by_rule)
    floor = min(PAGE_FLOOR, limit)
    filled = [s for s in ranked if s["id"] not in taken][: max(floor - len(chosen), 0)]
    if filled:
        notes.append(
            f"show_pages: only {len(chosen)} shows are pinned or meet the rule; "
            f"{len(filled)} more with the most listed characters make up {floor} pages"
        )
    chosen += filled
    if len(chosen) > limit:
        notes.append(
            f"show_pages: the limit of {limit} pages cut {len(chosen) - limit} "
            "shows with the fewest listed characters"
        )
        chosen = chosen[:limit]
    pinned_ids = {s["id"] for s in chosen[:pinned_count]}
    chosen, skipped = _drop_bad_slugs(chosen, pinned_ids)
    notes += skipped
    built = {s["id"] for s in chosen}
    notes.append(
        f"show_pages: {len(chosen)} pages: {min(pinned_count, len(chosen))} pinned, "
        f"{sum(s['id'] in built for s in by_rule)} by the rule, "
        f"{sum(s['id'] in built for s in filled)} to reach the floor"
        + (f", {len(skipped)} skipped" if skipped else "")
    )
    return chosen, notes


def _log_text(value: Any) -> str:
    """``value`` on one line for the build log: snapshot text is untrusted, and
    a line break in it could start a workflow command."""
    return " ".join(str(value).split())


def slug_dir(slug: str) -> str | None:
    """The directory name a show's page is written under, or None when the
    slug cannot be one.

    The URL keeps the slug as LezWatch publishes it, percent-encoding and
    all (``/shows/the-air-%e0%b9%80.../``). The static host decodes a
    request's path before it looks for the file, so the page must live under
    the decoded name; a directory named with a literal ``%e0`` answers only
    a double-encoded URL, and the published one gets a 404. A slug whose
    decoded form is not valid UTF-8, or holds a separator, a second level of
    encoding, a dot segment, white space or a control character, gets no
    page."""
    if not SLUG.fullmatch(slug):
        return None
    try:
        decoded = urllib.parse.unquote(slug, errors="strict")
    except UnicodeDecodeError:
        return None
    if decoded in {".", ".."} or any(
        ch in "/\\%?#" or ch.isspace() or not ch.isprintable() for ch in decoded
    ):
        return None
    return decoded


def _drop_bad_slugs(
    chosen: list[dict[str, Any]], pinned_ids: set[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """The chosen shows without any whose slug cannot be a page, and one log
    line per show left out.

    A slug that is not a safe path segment (``SLUG``) is never built. Of two
    shows with the same slug the first in the published order (pins first)
    is kept and the later one left out. A left-out show is also absent from
    the index, the sitemap and every link, since all of them are made from
    the list returned here.

    Two cases still refuse the whole build: a pinned show left out (the
    hand-picked pages must never quietly disappear), and more than
    ``SKIP_MAX_SHARE`` of the chosen shows left out (a change in the data's
    shape, not one bad record)."""
    kept: list[dict[str, Any]] = []
    notes: list[str] = []
    lost_pins: list[str] = []
    seen: set[str] = set()
    for show in chosen:
        slug = show["slug"]
        if not isinstance(slug, str) or slug_dir(slug) is None:
            why = "unsafe slug for a path"
        elif slug in seen:
            why = "another show earlier in the order has the same slug"
        else:
            seen.add(slug)
            kept.append(show)
            continue
        label = (
            f"{_log_text(show['title'])} (id {_log_text(show['lwtv_id'])}, "
            f"slug {_log_text(repr(slug))})"
        )
        notes.append(f"show_pages: skipped {label}: {why}")
        if show["id"] in pinned_ids:
            lost_pins.append(f"{label}: {why}")
    if lost_pins:
        raise ShowPagesError(
            f"a pinned show cannot be built, refusing the build: {'; '.join(lost_pins)}"
        )
    dropped = len(chosen) - len(kept)
    if dropped > len(chosen) * SKIP_MAX_SHARE:
        raise ShowPagesError(
            f"{dropped} of {len(chosen)} chosen shows have an unsafe or repeated slug, "
            f"more than {SKIP_MAX_SHARE:.0%}; refusing the build: "
            + "; ".join(n.removeprefix("show_pages: skipped ") for n in notes)
        )
    return kept, notes


def select_shows(
    doc: dict[str, Any], limit: int = DEFAULT_LIMIT, pinned: list[Pin] | None = None
) -> list[dict[str, Any]]:
    """The shows to build, in order (see the module docstring)."""
    return plan_selection(doc, limit, pinned)[0]


def indexed_show_ids(
    shows: list[dict[str, Any]],
    pinned: list[Pin] | None,
    listed: dict[str, int],
    *,
    extra_ids: frozenset[int] | None = None,
    min_listed: int | None = None,
) -> set[str]:
    """The ids of the built shows that search engines may index (DECISIONS
    0028). The one place that decides it: the sitemap lists exactly these,
    and every other show page carries ``ROBOTS_HOLD``.

    With a pinned list, the pinned shows that were built. Without one, the
    first ``PINNED_MAX`` pages in the published order (the 0019 rule's 50).
    Then, to widen: any built show whose LezWatch id is in ``extra_ids``
    (default ``INDEX_EXTRA_IDS``), and, when ``min_listed`` (default
    ``INDEX_MIN_LISTED``) is set, every built show with at least that many
    listed characters. Nothing about deaths goes into it."""
    extra = INDEX_EXTRA_IDS if extra_ids is None else extra_ids
    floor = INDEX_MIN_LISTED if min_listed is None else min_listed
    if pinned is None:
        ids = {s["id"] for s in shows[:PINNED_MAX]}
    else:
        pinned_ids = {p.lezwatch_id for p in pinned}
        ids = {s["id"] for s in shows if s["lwtv_id"] in pinned_ids}
    ids |= {s["id"] for s in shows if s["lwtv_id"] in extra}
    if floor is not None:
        ids |= {s["id"] for s in shows if listed.get(s["id"], 0) >= floor}
    return ids


def fit(candidates: list[str], limit: int) -> str:
    """The first candidate within ``limit`` characters; the last is clipped."""
    for text in candidates:
        if len(text) <= limit:
            return text
    return candidates[-1][: limit - 1].rstrip() + "…"


def show_title(name: str, count: int = 0) -> str:
    """The question people search, longest form that fits, with the number of
    listed characters when there are several (DECISIONS 0027). No answer in
    it: the count is of listed characters, never of deaths."""
    candidates = []
    if count >= 2:
        candidates.append(f"Do any of the {count} queer characters in {name} die?")
    return fit(
        [
            *candidates,
            f"Do any queer characters die in {name}? Spoiler-free",
            f"Do queer characters die in {name}? Spoiler-free",
            f"Does she die in {name}? Spoiler-free",
            f"Does she die in {name}?",
        ],
        TITLE_MAX,
    )


def _and_list(names: list[str]) -> str:
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def identity(gender: str, sexuality: str) -> str | None:
    """A short label for a character in the description, from the two terms
    the page already shows, so a search like "is <character> a lesbian" is
    answered in the snippet (DECISIONS 0027). LezWatch.TV catalogs queer
    women and non-binary characters, and its scope is trusted: "Homosexual"
    or "Lesbian" with a gender term of "Cisgender", or one ending in "Woman"
    ("Cisgender Woman", "Trans Woman"), is "lesbian". With any other gender
    term ("Non-Binary", "Genderqueer", "Agender", "Trans Man") it is never
    "lesbian"; the gender term is the label instead. Other named
    sexualities ("Bisexual", "Queer", "Pansexual") are used as given,
    lowercased. Otherwise the gender term is the label when it is not
    cisgender or unknown ("trans woman", "non-binary", "trans man"). Never
    "gay", and None when neither term gives a label. Nothing about deaths."""
    if sexuality in LESBIAN_SEXUALITIES and (gender in LESBIAN_GENDERS or gender.endswith("Woman")):
        return "lesbian"
    if sexuality in SEXUALITY_LABELS:
        return sexuality.lower()
    if not gender.startswith("Cisgender") and gender not in NO_GENDER_LABEL:
        return gender.lower()
    return None


def _labelled(name: str, label: str | None) -> str:
    return f"{name} ({label})" if label else name


def show_description(
    name: str,
    names: list[str] | None = None,
    count: int = 0,
    labels: list[str | None] | None = None,
) -> str:
    """Says how many characters LezWatch.TV lists, names up to three of them
    (with ``labels``, each one's identity) and says who dies is behind the
    spoiler warning. ``names`` is in page order, never by death, and
    ``labels`` is parallel to it (DECISIONS 0024 and 0027)."""
    names = names or []
    labels = labels if labels is not None else [None] * len(names)
    tail = "Who dies, if anyone, is behind a spoiler warning."
    who = "one LGBTQ character" if count == 1 else f"{count} LGBTQ characters"
    who_first = who[0].upper() + who[1:]
    # Labelled names first (they answer "is <character> a lesbian"), then
    # bare names, so a long show title still gets some names in.
    shortlists = [
        [_labelled(n, lab) for n, lab in zip(names[:k], labels[:k], strict=True)]
        for k in range(min(DESCRIPTION_NAMES, len(names)), 0, -1)
    ] + [names[:k] for k in range(min(DESCRIPTION_NAMES, len(names)), 0, -1)]
    candidates = []
    for named in shortlists:
        listed = _and_list(named)
        if count > len(named):
            candidates.append(f"LezWatch.TV lists {who} in {name}, including {listed}. {tail}")
            candidates.append(f"{who_first} in {name}, including {listed}. {tail}")
        else:
            candidates.append(f"LezWatch.TV lists {who} in {name}: {listed}. {tail}")
            candidates.append(f"{who_first} in {name}: {listed}. {tail}")
    if count:
        candidates.append(f"LezWatch.TV lists {who} in {name}. {tail}")
    candidates += [f"Do any queer characters die in {name}? {tail}"] * 2
    return fit(candidates, DESCRIPTION_MAX)


def _term_name(term: dict[str, Any] | None) -> str:
    return term["name"] if term else NOT_RECORDED


def _death_status(
    death: dict[str, Any], other_shows: int, show_years: Iterable[str] = ()
) -> tuple[bool, str]:
    """(dies, sentence). Only a recorded death is a yes; everything else is
    Unknown, because LezWatch records deaths, not survival.

    LezWatch records a death on the character, not on a show (DECISIONS
    0030). For a character linked to more than one show, the death counts for
    this show only when a death year is one of the character's years in this
    show (``show_years``, the link's years). Otherwise the snapshot cannot
    place the death in this show, so the answer here is Unknown, never a
    guess either way."""
    if death["death_known"] is not True or death["died"] is not True:
        return False, f"{UNKNOWN}. LezWatch.TV has not recorded a death."
    years = sorted(death["years"])
    listed = ", ".join(map(str, years))
    if not years:
        text = "Dies (year not recorded)."
    elif len(years) > 1:
        text = f"Dies more than once ({listed})."
    else:
        text = f"Dies ({years[0]})."
    if not other_shows:
        return True, text
    here = {str(y) for y in show_years}
    matched = [str(y) for y in years if str(y) in here]
    if matched:
        verb = "is" if len(matched) == 1 else "are"
        text += (
            " The record belongs to the character, not to one show; it is counted here"
            f" because {_and_list(matched)} {verb} among this character's years in this show."
        )
        return True, text
    if not years:
        return False, (
            f"{UNKNOWN}. LezWatch.TV records a death for this character but no year,"
            " so it cannot say whether it happens in this show."
        )
    if not here:
        return False, (
            f"{UNKNOWN}. LezWatch.TV records a death for this character ({listed}) but not"
            " the character's years in this show, so it cannot say whether it happens here."
        )
    return False, (
        f"{UNKNOWN}. LezWatch.TV records a death for this character ({listed}), but not in"
        " a year the character appears in this show. It may happen in another show."
    )


def cast_index(doc: dict[str, Any]) -> dict[str, list[tuple[dict[str, Any], dict[str, Any]]]]:
    """(character, its link to the show) per show id, characters in LezWatch
    id order. Built once per site so hundreds of pages do not each re-sort
    every character."""
    index: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for c in sorted(doc["characters"], key=lambda c: c["lwtv_id"]):
        seen: set[str] = set()
        for link in c["shows"]:
            if link["show_id"] not in seen:  # the first link to a show, as before
                seen.add(link["show_id"])
                index.setdefault(link["show_id"], []).append((c, link))
    return index


def _characters(
    doc: dict[str, Any],
    show: dict[str, Any],
    index: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] | None = None,
) -> list[CharacterView]:
    views = []
    pairs = (index if index is not None else cast_index(doc)).get(show["id"], [])
    for c, link in pairs:
        others = {lk["show_id"] for lk in c["shows"]} - {show["id"]}
        years_here = [y for lk in c["shows"] if lk["show_id"] == show["id"] for y in lk["years"]]
        dies, status = _death_status(c["death"], len(others), years_here)
        elsewhere = not dies and c["death"]["died"] is True and c["death"]["death_known"] is True
        views.append(
            CharacterView(
                name=c["name"],
                source_url=c["source_url"],
                role=(link["role"] or NOT_RECORDED).capitalize(),
                gender=_term_name(c["gender"]),
                sexuality=_term_name(c["sexuality"]),
                dies=dies,
                status=status,
                elsewhere=elsewhere,
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
    elsewhere = sum(1 for c in cast if c.elsewhere)
    if not dead:
        headline = (
            f"{UNKNOWN}. LezWatch.TV has no death on record "
            f"{'in this show ' if elsewhere else ''}for "
            f"{'the one listed character' if n == 1 else f'any of the {listed}'}. "
            "It records deaths and nothing else, so this does not say anyone lives."
        )
    else:
        headline = (
            f"Yes. {len(dead)} of {listed} {_plural(len(dead), 'dies', 'die')}: {', '.join(dead)}."
        )
        if len(dead) < n:
            # The fixed line under the notes says why (show.html.j2).
            notes.append(f"For the other {n - len(dead)}, the answer is {UNKNOWN.lower()}.")
    if elsewhere:
        notes.append(
            f"{'One listed character has' if elsewhere == 1 else f'{elsewhere} listed characters have'}"
            " a recorded death that LezWatch.TV does not place in this show, so"
            f" {'it is' if elsewhere == 1 else 'they are'} not counted here."
        )
    return Answer(headline, notes)


def _years(years: dict[str, Any]) -> str:
    start, end = years["start"], years["end"]
    if start is None:
        return NOT_RECORDED
    if end is not None:
        return str(start) if end == start else f"{start} to {end}"
    return f"{start} to present" if years["on_air"] == "yes" else f"{start} (end year not recorded)"


def _tvmaze_last_season(show: dict[str, Any]) -> int | None:
    """TVmaze's latest aired season number, or None when TVmaze has none or
    numbers this show's seasons by year."""
    sched = show["schedule"]
    if sched["schedule_known"] is not True:
        return None
    season = (sched["previous_episode"] or {}).get("season")
    if isinstance(season, bool) or not isinstance(season, int):
        return None
    return season if 1 <= season < SEASON_IS_A_YEAR else None


def seasons_fact(show: dict[str, Any]) -> tuple[str, str, int | None]:
    """(label, value, count for structured data) for the Seasons row
    (DECISIONS 0031). For an ended show TVmaze's last season wins when the
    two disagree; when LezWatch has no count, TVmaze's latest season fills
    it. Absence stays "Not recorded", never a number."""
    recorded = show["seasons"]
    tvmaze = _tvmaze_last_season(show)
    ended = show["schedule"]["status"] == "Ended"
    if tvmaze is not None and (recorded is None or (ended and tvmaze != recorded)):
        return "Seasons, per TVmaze", str(tvmaze) if ended else f"{tvmaze} so far", tvmaze
    if recorded is None:
        return "Seasons", NOT_RECORDED, None
    return "Seasons", str(recorded), recorded


def _tvmaze_channel(show: dict[str, Any]) -> str | None:
    sched = show["schedule"]
    if sched["schedule_known"] is not True:
        return None
    return (sched["network"] or sched["web_channel"] or {}).get("name") or None


def network_fact(show: dict[str, Any]) -> tuple[str, str]:
    """(label, value) for the Network row: LezWatch's stations, then
    TVmaze's network or web channel."""
    sched = show["schedule"]
    channel = (
        ", ".join(n["name"] for n in show["networks"])
        or (sched["network"] or sched["web_channel"] or {}).get("name")
        or NOT_RECORDED
    )
    return "Network", channel


def trigger_level(show: dict[str, Any]) -> str:
    """LezWatch's trigger-warning level, "Not rated" when none is recorded.
    A term that is not one of the three levels is not printed (it could name
    an event); the row then points to LezWatch.TV."""
    slugs = [t["slug"] for t in show["triggers"]]
    if not slugs:
        return "Not rated"
    if len(slugs) == 1 and slugs[0] in TRIGGER_LEVELS:
        return TRIGGER_LEVELS[slugs[0]]
    return "See LezWatch.TV"


def _facts(show: dict[str, Any]) -> list[tuple[str, str]]:
    sched = show["schedule"]
    seasons_label, seasons, _ = seasons_fact(show)
    return [
        ("Years", _years(show["years"])),
        (seasons_label, seasons),
        ("Format", _term_name(show["format"])),
        network_fact(show),
        ("Country", ", ".join(c["name"] for c in show["countries"]) or NOT_RECORDED),
        ("Genres", ", ".join(g["name"] for g in show["genres"]) or NOT_RECORDED),
        ("Worth it, per LezWatch.TV", show["ratings"]["worth_it"] or "Not rated"),
        ("Trigger warning, per LezWatch.TV", trigger_level(show)),
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


def _ranked(cast: list[CharacterView]) -> list[CharacterView]:
    """Regulars first, then recurring, then guests; the page's own order
    within each. Nothing about deaths goes into the order."""
    ranked = sorted(enumerate(cast), key=lambda ic: (ROLE_ORDER.get(ic[1].role.lower(), 3), ic[0]))
    return [c for _, c in ranked]


def _roles_first(cast: list[CharacterView]) -> list[str]:
    return [c.name for c in _ranked(cast)]


def _description(name: str, cast: list[CharacterView]) -> str:
    ranked = _ranked(cast)
    return show_description(
        name,
        [c.name for c in ranked],
        len(cast),
        [identity(c.gender, c.sexuality) for c in ranked],
    )


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


def _long_date(value: Any) -> str | None:
    """ "March 8, 2009" from an ISO date, or None when there is no readable
    date (never a placeholder)."""
    if not isinstance(value, str):
        return None
    try:
        day = dt.date.fromisoformat(value)
    except ValueError:
        return None
    return f"{_MONTHS[day.month - 1]} {day.day}, {day.year}"


def _opening_years(years: dict[str, Any]) -> str | None:
    start, end = years["start"], years["end"]
    if start is None:
        return None
    if end is not None:
        return str(start) if end == start else f"{start} to {end}"
    return f"{start} to present" if years["on_air"] == "yes" else f"from {start}"


def _opening_network(show: dict[str, Any]) -> str | None:
    names = [n["name"] for n in show["networks"] if n.get("name")]
    if names:
        return _and_list(names)
    return _tvmaze_channel(show)


def _opening_episodes(show: dict[str, Any]) -> str | None:
    """The TVmaze sentence: when the most recent episode aired (season and
    number when both are known) and when the next is listed. Episode names
    are left out: one can give away a death ("Dead Air")."""
    sched = show["schedule"]
    if sched["schedule_known"] is not True:
        return None
    prev, nxt = sched["previous_episode"] or {}, sched["next_episode"] or {}
    prev_on, next_on = _long_date(prev.get("airdate")), _long_date(nxt.get("airdate"))
    if prev_on:
        which = "last" if sched["status"] == "Ended" and not next_on else "most recent"
        text = f"Its {which} episode on TVmaze aired on {prev_on}"
        if isinstance(prev.get("season"), int) and isinstance(prev.get("number"), int):
            text += f" (season {prev['season']}, episode {prev['number']})"
        return text + (f", and the next is listed for {next_on}." if next_on else ".")
    if next_on:
        return f"TVmaze lists its next episode for {next_on}."
    return None


def opening(show: dict[str, Any], cast: list[CharacterView]) -> str:
    """The page's first sentence, which only this show can have: how many
    characters LezWatch.TV lists, the network and years, up to
    ``OPENING_NAMES`` names (regulars first, never in an order a death could
    affect), then the TVmaze episode dates. Built only from facts that cannot
    answer the question: no death, death count, death year or trope, and no
    episode name. A fact the snapshot lacks is left out, never printed as
    "Unknown" or "Not recorded" (the facts list says that)."""
    n = len(cast)
    who = "one queer character" if n == 1 else f"{n} queer characters"
    context = [part for part in (_opening_network(show), _opening_years(show["years"])) if part]
    # A semicolon keeps a list of networks apart from the years.
    joiner = "; " if any("," in part for part in context) else ", "
    where = show["title"] + (f" ({joiner.join(context)})" if context else "")
    names = [c.name for c in _ranked(cast)][:OPENING_NAMES]
    if not names:
        first = f"LezWatch.TV lists {who} in {where}."
    elif n > len(names):
        first = f"LezWatch.TV lists {who} in {where}, including {_and_list(names)}."
    else:
        first = f"LezWatch.TV lists {who} in {where}: {_and_list(names)}."
    episodes = _opening_episodes(show)
    return f"{first} {episodes}" if episodes else first


def _series(show: dict[str, Any], canonical: str, cast: list[CharacterView]) -> dict[str, Any]:
    """schema.org TVSeries from snapshot facts only; nothing about deaths."""
    series: dict[str, Any] = {
        "@type": "TVSeries",
        "name": show["title"],
        "url": canonical,
        "sameAs": [u for u in (show["source_url"], show["schedule"]["tvmaze_url"]) if u],
    }
    years = show["years"]
    if years["start"] is not None:
        series["startDate"] = str(years["start"])
    if years["end"] is not None:
        series["endDate"] = str(years["end"])
    seasons = seasons_fact(show)[2]
    if seasons is not None:
        series["numberOfSeasons"] = seasons
    if show["genres"]:
        series["genre"] = [g["name"] for g in show["genres"]]
    if show["countries"]:
        series["countryOfOrigin"] = [
            {"@type": "Country", "name": c["name"]} for c in show["countries"]
        ]
    if cast:
        series["character"] = [{"@type": "Person", "name": c.name} for c in cast]
    return series


def _structured(crumbs: dict[str, Any], *more: dict[str, Any]) -> dict[str, Any]:
    """One JSON-LD block: the breadcrumb, then anything else, as a @graph."""
    graph = [{k: v for k, v in crumbs.items() if k != "@context"}, *more]
    return {"@context": "https://schema.org", "@graph": graph}


def _common(doc: dict[str, Any], base_url: str, app_store_live: bool) -> dict[str, Any]:
    return {
        "site_name": SITE_NAME,
        "base_url": base_url,
        "licence": doc["licence"],
        "attribution": doc["attribution"],
        "generated_on": doc["generated_at"][:10],
        "app_store_url": APP_STORE_URL if app_store_live else None,
        "app_store_banner": BANNER if app_store_live else None,
        "app_store_copy": PRICE_COPY,
    }


def neighbors(shows: list[dict[str, Any]], index: int) -> list[dict[str, Any]]:
    """The shows before and after ``shows[index]`` in the published order,
    wrapping at the ends; never the show itself and never one twice."""
    n = len(shows)
    if n < 2:
        return []
    before, after = shows[(index - 1) % n], shows[(index + 1) % n]
    return [before] if before is after else [before, after]


def related(shows: list[dict[str, Any]], index: int) -> list[dict[str, Any]]:
    """Up to RELATED_LIMIT other built shows like ``shows[index]``: LezWatch.TV's
    own similar shows first (its order), then those sharing the most genres
    (ties in published order). Never the show itself, its two neighbors (they
    are linked already) or a show sharing nothing. Tropes are not used: the
    death trope would turn "similar" into a hint."""
    me = shows[index]
    skip = {me["id"], *(s["id"] for s in neighbors(shows, index))}
    position = {s["id"]: i for i, s in enumerate(shows)}
    picked: list[dict[str, Any]] = []
    for sid in me["similar_show_ids"]:
        if sid in position and sid not in skip and shows[position[sid]] not in picked:
            picked.append(shows[position[sid]])
    mine = {g["slug"] for g in me["genres"]}
    shared = {s["id"]: len(mine & {g["slug"] for g in s["genres"]}) for s in shows}
    by_genre = sorted(
        (s for s in shows if s["id"] not in skip and s not in picked and shared[s["id"]]),
        key=lambda s: (-shared[s["id"]], position[s["id"]]),
    )
    return (picked + by_genre)[:RELATED_LIMIT]


def render_show(
    doc: dict[str, Any],
    show: dict[str, Any],
    *,
    base_url: str,
    app_store_live: bool = False,
    others: list[dict[str, Any]] | None = None,
    similar: list[dict[str, Any]] | None = None,
    total: int = 1,
    index: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] | None = None,
    indexed: bool = True,
) -> str:
    """One show's page. ``indexed`` False adds the ``ROBOTS_HOLD`` tag
    (DECISIONS 0028); nothing else on the page changes."""
    cast = _characters(doc, show, index)
    canonical = f"{base_url}/shows/{show['slug']}/"
    crumbs = [
        (SITE_NAME, f"{base_url}/"),
        ("Shows", f"{base_url}/shows/"),
        (show["title"], canonical),
    ]
    return _ENV.get_template("show.html.j2").render(
        **_common(doc, base_url, app_store_live),
        title=show_title(show["title"], len(cast)),
        description=_description(show["title"], cast),
        opening=opening(show, cast),
        canonical=canonical,
        show=show,
        crumbs=crumbs,
        breadcrumb=_structured(_breadcrumb(crumbs), _series(show, canonical, cast)),
        facts=_facts(show),
        cast=cast,
        answer=_answer(show, cast),
        tvmaze_url=show["schedule"]["tvmaze_url"],
        others=[
            {"title": s["title"], "url": f"{base_url}/shows/{s['slug']}/"} for s in others or []
        ],
        similar=[
            {"title": s["title"], "url": f"{base_url}/shows/{s['slug']}/"} for s in similar or []
        ],
        total=total,
        robots=None if indexed else ROBOTS_HOLD,
    )


_ARTICLES = ("the ", "a ", "an ")


def sort_title(title: str) -> str:
    """The title as the A to Z index files it: case and accents folded, and
    a leading English article dropped ("The L Word" files under L)."""
    folded = "".join(
        ch for ch in unicodedata.normalize("NFKD", title) if not unicodedata.combining(ch)
    ).casefold()
    for article in _ARTICLES:
        if folded.startswith(article) and len(folded) > len(article):
            return folded[len(article) :]
    return folded


def letter_groups(shows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The shows in A to Z order, one group per first letter. A title that
    starts with anything but A to Z (a digit, a symbol, a non-Latin script)
    goes under "#", first."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for s in sorted(shows, key=lambda s: (sort_title(s["title"]), s["lwtv_id"])):
        first = sort_title(s["title"])[:1]
        letter = first.upper() if "a" <= first <= "z" else "#"
        groups.setdefault(letter, []).append(s)
    return [
        {
            "label": letter,
            "heading": "# (numbers, symbols and other scripts)" if letter == "#" else letter,
            "anchor": "letter-" + ("other" if letter == "#" else letter.lower()),
            "shows": groups[letter],
        }
        for letter in sorted(groups, key=lambda x: (x != "#", x))
    ]


def _index_entry(s: dict[str, Any]) -> dict[str, str]:
    return {"slug": s["slug"], "title": s["title"], "years": _years(s["years"])}


def render_index(
    doc: dict[str, Any],
    shows: list[dict[str, Any]],
    *,
    base_url: str,
    app_store_live: bool = False,
    featured: list[dict[str, Any]] | None = None,
) -> str:
    """The shows index: the hand-picked shows first (``featured``), then every
    show A to Z under a letter heading, with a list of letters to jump to.
    The structured data lists every show in the published order."""
    canonical = f"{base_url}/shows/"
    crumbs = [(SITE_NAME, f"{base_url}/"), ("Shows", canonical)]
    return _ENV.get_template("index.html.j2").render(
        **_common(doc, base_url, app_store_live),
        title=fit(
            [
                f"Do queer characters die? {len(shows)} TV shows, spoiler-free",
                "Does she die? Queer TV shows, spoiler-free",
            ],
            TITLE_MAX,
        ),
        description=fit(
            [
                "Does she die in your show? Check for the bury-your-gays trope before you "
                "watch: LGBTQ characters in each show, with the answer hidden until you open it.",
                "Does she die in your show? The full answer stays hidden until you open it.",
            ],
            DESCRIPTION_MAX,
        ),
        canonical=canonical,
        crumbs=crumbs,
        breadcrumb=_structured(
            _breadcrumb(crumbs),
            {
                "@type": "ItemList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": i,
                        "name": s["title"],
                        "url": f"{base_url}/shows/{s['slug']}/",
                    }
                    for i, s in enumerate(shows, start=1)
                ],
            },
        ),
        total=len(shows),
        featured=[_index_entry(s) for s in featured or []],
        groups=[
            {**g, "shows": [_index_entry(s) for s in g["shows"]]} for g in letter_groups(shows)
        ],
    )


def render_sitemap(
    doc: dict[str, Any],
    shows: list[dict[str, Any]],
    *,
    base_url: str,
    indexed: set[str] | None = None,
) -> str:
    """The home page (site_index.py, always published) first, the shows
    index, then each show in ``indexed`` (``indexed_show_ids``; None means
    every show) in the published order."""
    urls = [
        f"{base_url}/",
        f"{base_url}/shows/",
        *(f"{base_url}/shows/{s['slug']}/" for s in shows if indexed is None or s["id"] in indexed),
    ]
    if len(urls) > SITEMAP_MAX_URLS:
        raise ShowPagesError(
            f"{len(urls)} URLs is more than one sitemap file may list ({SITEMAP_MAX_URLS})"
        )
    return _ENV.get_template("sitemap.xml.j2").render(urls=urls, lastmod=doc["generated_at"][:10])


class _HeadProbe(HTMLParser):
    """A page's canonical URL and robots tag, read with html.parser."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canonical: str | None = None
        self.robots: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href")
        elif tag == "meta" and (a.get("name") or "").lower() == "robots":
            self.robots.append(a.get("content") or "")


def _sitemap_locs(xml: str) -> list[str]:
    locs: list[str] = []
    for part in xml.split("<loc>")[1:]:
        locs.append(html.unescape(part.split("</loc>", 1)[0]))
    return locs


def index_problems(files: dict[str, str], *, base_url: str) -> list[str]:
    """Every way the sitemap and the robots tags of ``files`` disagree; empty
    when they agree (DECISIONS 0028).

    A show page or the shows index whose canonical URL is in the sitemap must
    carry no robots tag; one that is not in the sitemap must carry exactly
    ``ROBOTS_HOLD``. Every show URL in the sitemap must be a page in
    ``files``, and the home page and the shows index must be listed."""
    locs = _sitemap_locs(files["sitemap.xml"])
    listed = set(locs)
    problems: list[str] = []
    if len(listed) != len(locs):
        problems.append("the sitemap lists a URL twice")
    for required in (f"{base_url}/", f"{base_url}/shows/"):
        if required not in listed:
            problems.append(f"the sitemap does not list {required}")
    pages: set[str] = set()
    for path, text in sorted(files.items()):
        if not (path.startswith("shows/") and path.endswith("/index.html")):
            continue
        probe = _HeadProbe()
        probe.feed(text)
        url = probe.canonical
        if not url:
            problems.append(f"{path}: no canonical URL")
            continue
        pages.add(url)
        if url in listed and probe.robots:
            problems.append(f"{path}: in the sitemap but tagged {probe.robots}")
        elif url not in listed and probe.robots != [ROBOTS_HOLD]:
            problems.append(
                f"{path}: left out of the sitemap but its robots tags are {probe.robots}, "
                f"not [{ROBOTS_HOLD!r}]"
            )
    problems += [
        f"the sitemap lists {u}, which is not a page of this build"
        for u in locs
        if u.startswith(f"{base_url}/shows/") and u not in pages
    ]
    return problems


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
    pinned: list[Pin] | None = None,
) -> dict[str, str]:
    """Every file of the site, as ``{relative path: text}``; writes nothing."""
    base = _clean_base_url(base_url)
    if not isinstance(doc, dict):
        raise ShowPagesError("the snapshot file is not a JSON object")
    # Fail before rendering if the file is not a snapshot this module understands.
    dt.date.fromisoformat(doc["generated_at"][:10])
    shows = select_shows(doc, limit, pinned)
    if not shows:
        raise ShowPagesError("no show has a listed character; nothing to build")
    pinned_ids = {p.lezwatch_id for p in pinned or []}
    indexed = indexed_show_ids(shows, pinned, _listed_characters(doc))
    files = {
        "shows/index.html": render_index(
            doc,
            shows,
            base_url=base,
            app_store_live=app_store_live,
            featured=[s for s in shows if s["lwtv_id"] in pinned_ids],
        )
    }
    index = cast_index(doc)
    for i, show in enumerate(shows):
        # Decoded on disk, encoded in every URL (``slug_dir``). _drop_bad_slugs
        # has already left out any show whose slug has no directory name.
        files[f"shows/{slug_dir(show['slug'])}/index.html"] = render_show(
            doc,
            show,
            base_url=base,
            app_store_live=app_store_live,
            others=neighbors(shows, i),
            similar=related(shows, i),
            total=len(shows),
            index=index,
            indexed=show["id"] in indexed,
        )
    files["sitemap.xml"] = render_sitemap(doc, shows, base_url=base, indexed=indexed)
    files["robots.txt"] = render_robots(base_url=base)
    problems = index_problems(files, base_url=base)
    if problems:
        raise ShowPagesError(
            "the sitemap and the robots tags disagree, refusing the build: " + "; ".join(problems)
        )
    return files


def build_site(
    doc: dict[str, Any],
    out_dir: Path,
    *,
    base_url: str = DEFAULT_BASE_URL,
    app_store_live: bool = False,
    limit: int = DEFAULT_LIMIT,
    pinned: list[Pin] | None = None,
) -> list[Path]:
    """Write the pages, the sitemap and robots.txt under ``out_dir``; return the files.

    All of it is rendered first. If a write then fails, the files and
    directories this call made are removed again, so a half-built site never
    reaches the Pages artifact.
    """
    files = render_site(
        doc, base_url=base_url, app_store_live=app_store_live, limit=limit, pinned=pinned
    )
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
    parser.add_argument("--pinned", type=Path, default=DEFAULT_PINNED_PATH)
    parser.add_argument("--no-pinned", action="store_true")
    args = parser.parse_args(argv)
    try:
        doc = json.loads(args.snapshot.read_text(encoding="utf-8"))
        pinned = None if args.no_pinned else load_pinned(args.pinned)
        files = build_site(
            doc,
            args.out_dir,
            base_url=args.base_url,
            app_store_live=live_or_false(args.app_store_live),
            limit=args.limit,
            pinned=pinned,
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
    shows, notes = plan_selection(doc, args.limit, pinned)
    for line in notes:
        print(line)
    held = len(shows) - len(indexed_show_ids(shows, pinned, _listed_characters(doc)))
    print(
        f"show_pages: {len(shows) - held} show pages in the sitemap, "
        f"{held} held back with {ROBOTS_HOLD} (DECISIONS 0028)"
    )
    print(f"show_pages: wrote {len(files)} files to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
