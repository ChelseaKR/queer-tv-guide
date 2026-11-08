"""A static web page per show with enough data to answer "does she die in <show>".

Built from the same snapshot the app reads (DECISIONS 0019), on this command:

    python -m qtv_pipeline.show_pages SNAPSHOT_JSON OUT_DIR [--base-url URL]
        [--app-store-live VALUE] [--limit N] [--notice-on-failure]

It writes ``shows/index.html``, ``shows/<slug>/index.html`` for each chosen
show, ``airing/index.html`` (airing_page.py, DECISIONS 0033), ``sitemap.xml``
and ``robots.txt`` into OUT_DIR. Nothing else, and no
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

Words for search (DECISIONS 0024, 0027 and 0045). The title leads with what
people type, the count of listed characters and the show, then asks the
question ("<n> LGBTQ characters in <show>. Do any die? No spoilers", then
shorter forms); the description gives that count and names up to three
listed characters, regulars first, each with the identity the page shows
("Lisa Simpson (bisexual)"), because people search "does <character> die
in <show>" and "is <character> a lesbian", and ends with one fixed
sentence saying whether anyone dies stays hidden until a tap; the
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

The character list (DECISIONS 0035). Outside the answer, each listed
character is one item, regulars first, with a link anchor from the
character's LezWatch slug (``anchors``: stable, unique on the page) and
"played by <actor>" with the actor names LezWatch.TV gives. It never shows a
character's years in the show (a run that ends before the show does gives a
death away), a death date or year, or any cliche or trope. There are no
actor pages.

Character questions (``character_questions``, DECISIONS 0051). After the
sealed answer, one block per listed character, regulars first, asks the
question people type: "Is <character> <label> in <show>?" as a real ``<h3>``,
where the label is the one ``identity`` reads from LezWatch.TV's own gender
and sexuality terms ("a lesbian", "bisexual", "a trans woman", "non-binary"),
or "LGBTQ" when neither term gives one. The answer names both terms as
LezWatch.TV records them, says "LezWatch.TV lists <name> without a stated
orientation" when the sexuality is empty or "Undefined", and never invents a
label. A second ``<h3>``, "Does <character> die in <show>?", points at the
one sealed answer and carries no death status: the answer stays behind the
same reveal as before. Past ``QUESTIONS_VISIBLE`` (8) blocks the rest sit in
a closed ``<details>`` whose summary reads "Show all <n> characters", so the
control works with no script. No FAQPage is added. Nothing in a block reads
a death record.

The next-episode line (``next_episode_line``, DECISIONS 0051). A page whose
show has a TVmaze next episode says, just above the app block, "Next
episode: <date>, per TVmaze", with the calendar day TVmaze gives in the
network's own time zone, or "date to be announced" when TVmaze lists the
episode with no date; with the App Store switch on it adds "Get a reminder
in the app.", which the block under it offers. No next episode, no
schedule, or a date before the snapshot's day: no line at all, never "no
upcoming episodes".

Seasons (``seasons_fact``, DECISIONS 0031). For a show TVmaze lists as Ended, when TVmaze's last season number differs from
LezWatch's season count, the page shows TVmaze's, labeled "per TVmaze".
For a show LezWatch marks on air and TVmaze does not list as Ended, TVmaze's
latest season replaces a lower LezWatch count, as "5 so far, per TVmaze", when
TVmaze's premiere year is within a year of LezWatch's start year (DECISIONS
0048); otherwise LezWatch's count stays. When LezWatch has no count, TVmaze's
latest season fills it ("3 so far" for a show still running). A TVmaze season number of 1900 or more is a year (a
show numbered by year), not a count, and is never used.

Years (``shown_years``, DECISIONS 0049, proposed). TVmaze's premiere year
replaces LezWatch's start year only on an id join, when no character is placed
in the show before it, and when the gap is one year, or 2 to 10 years earlier
with LezWatch's own character years already starting before its start year. A
show TVmaze lists as Ended (on an id join, premiere within a year) never says
"to present": it shows TVmaze's end year when known, else "ended" with no year.
The row says "per TVmaze" when TVmaze supplied any of it.

What a page never says. LezWatch records deaths, not survival
(``schema/README.md``), so a character with no recorded death is "Unknown",
never "No" and never "Lives". A season count, rating or year LezWatch left
blank is "Not recorded", never zero.

Privacy. A page has no script (its one ``<script>`` is schema.org
``application/ld+json`` data, which a browser never runs), no cookie, no
form, no font, no stylesheet link and no request to another host. Every
link to another host is an anchor the visitor chooses to follow. The App
Store link, and Safari's Smart App Banner tag (a ``<meta>``, which fetches
nothing), appear only when the launch switch is on, with the same URL, tag
and price copy as ``app_store.py`` (DECISIONS 0023). With the switch on, the
page's one image is Apple's App Store badge, served from this site
(``app_store.get_app_block``, DECISIONS 0047); off, a page has no image.

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
    BADGE_FILE,
    BADGE_STYLE,
    BANNER,
    PRICE_COPY,
    SwitchError,
    get_app_block,
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
# list, plus the ids below. To widen, add LezWatch ids here (by list), or set
# INDEX_MIN_LISTED to index every built show with at least that many listed
# characters (by rule). Every other show page carries ROBOTS_HOLD and is left
# out of the sitemap.
#
# The first widening batch (DECISIONS 0046): every held-back page that, in
# Search Console's 28 days to 2026-11-07, Google showed at least 5 times, or
# for at least one query it reported, or that earned a click. The counts are
# for that window.
INDEX_EXTRA_IDS: frozenset[int] = frozenset(
    {
        84706,  # will-trent: 63 impressions, 1 click
        98062,  # from: 61 impressions, 1 click
        91890,  # the-mentalist: 49 impressions
        61062,  # the-owl-house: 33 impressions
        90168,  # elsbeth: 22 impressions
        17014,  # swat: 17 impressions
        1432,  # the-vampire-diaries: 15 impressions
        50812,  # for-all-mankind: 12 impressions
        13499,  # the-good-doctor: 11 impressions
        77,  # the-fosters: 10 impressions
        18740,  # the-loud-house: 10 impressions
        82984,  # the-rookie-feds: 10 impressions, 1 click
        32380,  # all-american: 9 impressions
        64744,  # chicago-med: 9 impressions
        72838,  # helluva-boss: 9 impressions
        13266,  # scandal: 9 impressions
        6003,  # the-flash: 9 impressions
        47336,  # why-women-kill: 9 impressions
        32,  # er: 8 impressions
        83773,  # ghosts-us: 8 impressions
        32468,  # manifest: 8 impressions
        39687,  # coroner: 7 impressions
        50486,  # craig-of-the-creek: 7 impressions
        5407,  # holby-city: 7 impressions
        33391,  # legacies: 7 impressions
        62163,  # lovecraft-country: 7 impressions
        1937,  # survivors-remorse: 7 impressions, 1 click
        39604,  # the-dragon-prince: 7 impressions
        2055,  # bones: 6 impressions
        72939,  # new-amsterdam: 6 impressions
        74270,  # q-force: 6 impressions
        58721,  # snowpiercer: 6 impressions, 1 click
        8393,  # the-blacklist: 6 impressions
        12555,  # big-mouth: 5 impressions
        76119,  # one-piece: 5 impressions
        46097,  # the-boys: 5 impressions
        76195,  # the-morning-show: 5 impressions
        94173,  # the-pitt: 5 impressions
        20769,  # 9-1-1: 4 impressions
        151,  # pretty-little-liars: 4 impressions
        1552,  # the-expanse: 4 impressions
        9408,  # father-brown: 3 impressions, 1 click
        1374,  # hollyoaks: 3 impressions
        1420,  # nip-tuck: 3 impressions
        34,  # rookie-blue: 2 impressions
        82556,  # the-brokenwood-mysteries: 2 impressions, 1 click
        4082,  # the-simpsons: 2 impressions
        65982,  # as-five: 1 impression, 1 click
        56,  # chasing-life: 1 impression
        727,  # two-and-a-half-men: 1 impression, 1 click
    }
)
INDEX_MIN_LISTED: int | None = None
ROBOTS_HOLD = "noindex,follow"
# The airing-now page (airing_page.py, DECISIONS 0033), built with the show pages.
AIRING_PATH = "airing/index.html"
# Pages site_index.py always publishes beside the home page, so the sitemap
# always lists them (DECISIONS 0042): the findings page and the press page.
ALWAYS_LISTED = ("findings/finales/", "press/")
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
# A sexuality LezWatch.TV leaves empty or marks "Undefined" is not stated; the
# character block says so instead of a label (DECISIONS 0051).
UNSTATED_SEXUALITIES = frozenset({"Undefined", "Not recorded"})
# Identity labels that are nouns, so the question takes an article ("Is she a
# lesbian"); every other label is an adjective ("Is she bisexual"). A label
# ending in "woman" or "man" is a noun too.
LABEL_NOUNS = frozenset({"lesbian", "hijra", "hermaphrodite", "cogenitor", "fa'afafine"})
# The word for a listed character with no label of its own, the one LezWatch.TV's
# scope allows (DECISIONS 0045).
NO_LABEL_WORD = "LGBTQ"
# Character question blocks shown before the "Show all" control (DECISIONS 0051).
QUESTIONS_VISIBLE = 8
# The hand-picked list (DECISIONS 0021). Resolved from the source tree, so it
# is used by `python -m qtv_pipeline.show_pages` and `make site`; deleting the
# file restores the character-count rule.
DEFAULT_PINNED_PATH = Path(__file__).resolve().parents[2] / "data" / "show_pages_pinned.json"
SITE_NAME = "Queer Frame"
TITLE_MAX = 60
DESCRIPTION_MAX = 155
# Below this a description is padded with ``DESCRIPTION_PAD`` (DECISIONS 0045).
DESCRIPTION_MIN = 120
# The description's last sentence: the same on every page, so it cannot hint.
DESCRIPTION_TAIL = "Whether anyone dies stays hidden until you tap."
DESCRIPTION_PAD = "Names and identities from LezWatch.TV."
# LezWatch slugs are WordPress slugs: lowercase, digits, hyphens, and the
# percent-encoding of non-Latin titles. Anything else would be a path or a
# query to a static host, so the build refuses it.
SLUG = re.compile(r"[a-z0-9%]+(?:-[a-z0-9%]+)*")
# LezWatch terms whose mere presence answers the question (the same slugs
# GuideCore keeps out of its always-visible lists).
DEATH_SPOILER_CLICHES = frozenset({"dead"})
# LezWatch.TV's own status for a character (DECISIONS 0052). Its character
# pages show "Status: Dead" and its show pages count a death only for a
# character carrying the "Dead Queers" cliché; a death date alone leaves the
# status "Alive" (a death the show undid, as Holby City's Bernie Wolfe, or a
# resurrection, as Warrior Nun's Ava Silva). On the 2026-11-07 snapshot 654 of
# the 683 dated deaths carry it.
DEAD_STATUS_CLICHES = frozenset({"dead"})
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
# The TVmaze joins made by an id (LezWatch's stored TVmaze id, its manual
# override, or LezWatch's IMDb id looked up on TVmaze), never by title
# (DECISIONS 0048, 0049).
TVMAZE_ID_JOINS = frozenset({"lwtv_tvmaze_id", "lwtv_tvmaze_id_manual", "imdb_lookup"})
# The largest gap (in years) by which TVmaze's earlier premiere may replace
# LezWatch's start year, and only when LezWatch's own character records
# already place a character in the show before its start year (DECISIONS
# 0049). Home and Away's 10 (1988, not 1998) is the largest such gap on a page.
YEARS_CORROBORATED_GAP = 10

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
    # A death date LezWatch records for a character it lists as alive
    # (DECISIONS 0052). Never a yes.
    listed_alive: bool = False
    # The page's link anchor for this character (``anchors``, DECISIONS 0035).
    anchor: str = ""
    # Actor names exactly as LezWatch.TV lists them; an actor id that did not
    # resolve to a name is left out, never printed as a placeholder.
    actors: tuple[str, ...] = ()
    # The years LezWatch records for the character in this show. Never
    # printed (a run's end can give a death away); only the earliest year
    # across the cast is read, by ``shown_years`` (DECISIONS 0049).
    years: tuple[int, ...] = ()


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
    """The words people search, then the question, longest form that fits
    (DECISIONS 0045). Search Console's queries are mostly "<show> LGBTQ
    characters" and "is <character> gay", so the title leads with the count
    of listed characters and the show; the death question follows, asked the
    same way of every show. No answer in it: the count is of listed
    characters, never of deaths, and nothing here reads a death record."""
    candidates = []
    if count >= 2:
        candidates.append(f"{count} LGBTQ characters in {name}. Do any die? No spoilers")
        candidates.append(f"{count} LGBTQ characters in {name}. Do any die?")
    return fit(
        [
            *candidates,
            f"LGBTQ characters in {name}. Do any die? No spoilers",
            f"LGBTQ characters in {name}, no spoilers",
            f"{name} LGBTQ characters, no spoilers",
            f"{name} LGBTQ characters",
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
    (with ``labels``, each one's identity) and ends with the same sentence on
    every page (``DESCRIPTION_TAIL``). ``names`` is in page order, never by
    death, and ``labels`` is parallel to it (DECISIONS 0024, 0027 and 0045).
    A result under ``DESCRIPTION_MIN`` gets the fixed ``DESCRIPTION_PAD``."""
    names = names or []
    labels = labels if labels is not None else [None] * len(names)
    tail = DESCRIPTION_TAIL
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
    candidates += [f"LGBTQ characters in {name}: does anyone die? {tail}"] * 2
    text = fit(candidates, DESCRIPTION_MAX)
    # Too short for a useful snippet: add a fixed sentence, the same on every
    # page, that says nothing about any death record.
    if len(text) < DESCRIPTION_MIN and len(text) + 1 + len(DESCRIPTION_PAD) <= DESCRIPTION_MAX:
        text = f"{text} {DESCRIPTION_PAD}"
    return text


def _term_name(term: dict[str, Any] | None) -> str:
    return term["name"] if term else NOT_RECORDED


def marked_dead(character: dict[str, Any]) -> bool:
    """Whether LezWatch.TV's own status for the character is Dead: it carries
    one of ``DEAD_STATUS_CLICHES`` (DECISIONS 0052). The marker is already in
    the snapshot (``cliches``), so this costs no request."""
    return any(t["slug"] in DEAD_STATUS_CLICHES for t in character["cliches"])


def _listed_alive_sentence(years: list[int]) -> str:
    """The line for a death date on a character LezWatch.TV lists as alive
    (DECISIONS 0052): what is recorded, and that it is not counted."""
    listed = ", ".join(map(str, years))
    if not years:
        dated = "a death but no date"
    elif len(years) == 1:
        dated = f"a death date ({listed})"
    else:
        dated = f"death dates ({listed})"
    return (
        f"{UNKNOWN}. LezWatch.TV records {dated} for this character but lists the"
        " character as alive, so it is not counted here."
    )


def _death_status(
    death: dict[str, Any],
    other_shows: int,
    show_years: Iterable[str] = (),
    status_dead: bool = True,
) -> tuple[bool, str]:
    """(dies, sentence). Only a recorded death is a yes; everything else is
    Unknown, because LezWatch records deaths, not survival.

    A death date LezWatch records for a character it lists as alive
    (``status_dead`` False, DECISIONS 0052) is not a yes either: LezWatch's own
    pages do not count it, so this page says what is recorded and counts
    nothing.

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
    if not status_dead:
        return False, _listed_alive_sentence(years)
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
    ids = anchors([c for c, _ in pairs])
    for (c, link), anchor in zip(pairs, ids, strict=True):
        others = {lk["show_id"] for lk in c["shows"]} - {show["id"]}
        years_here = [y for lk in c["shows"] if lk["show_id"] == show["id"] for y in lk["years"]]
        status_dead = marked_dead(c)
        dies, status = _death_status(c["death"], len(others), years_here, status_dead)
        recorded = c["death"]["died"] is True and c["death"]["death_known"] is True
        listed_alive = recorded and not status_dead
        elsewhere = not dies and recorded and status_dead
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
                listed_alive=listed_alive,
                anchor=anchor,
                actors=_actor_names(c),
                years=_int_years(years_here),
            )
        )
    return views


# Ids the page's own markup uses; a character anchor never takes one. "answer"
# is the sealed answer, which each "Does <character> die" block links to.
RESERVED_IDS = frozenset({"main", "answer"})


def anchors(characters: list[dict[str, Any]]) -> list[str]:
    """One link anchor per character on a show page, in order (DECISIONS
    0035). It is the character's LezWatch slug, so it stays the same from
    build to build (``#candy-ferocity``). A slug that is not a plain slug, is
    reserved, or repeats one earlier on the page falls back to
    ``character-<LezWatch id>``, then a ``-2``, ``-3`` suffix, so no two are
    alike. Nothing about deaths or years goes into an anchor."""
    used: set[str] = set(RESERVED_IDS)
    out = []
    for c in characters:
        slug = c["slug"]
        base = slug if isinstance(slug, str) and SLUG.fullmatch(slug) and "%" not in slug else ""
        if not base or base in used:
            base = f"character-{c['lwtv_id']}"
        anchor, n = base, 2
        while anchor in used:
            anchor, n = f"{base}-{n}", n + 1
        used.add(anchor)
        out.append(anchor)
    return out


def _actor_names(character: dict[str, Any]) -> tuple[str, ...]:
    names: list[str] = []
    for actor in character["actors"]:
        name = actor["name"]
        if isinstance(name, str) and name.strip() and name.strip() not in names:
            names.append(name.strip())
    return tuple(names)


def played_by(c: CharacterView) -> str | None:
    """ "played by <actor>" from LezWatch.TV's actor names, or None when it
    names no actor (the clause is then left out)."""
    return f"played by {_and_list(list(c.actors))}" if c.actors else None


@dataclass(frozen=True)
class CharacterQuestions:
    """One character's block on a show page (DECISIONS 0051). ``before`` and
    ``after`` are the identity answer around the words "LezWatch.TV", which
    the template links to the character's LezWatch.TV page. Nothing here
    reads a death record; ``death_question`` is only the question."""

    name: str
    source_url: str
    question: str
    before: str
    after: str
    who: str
    death_question: str


def question_label(gender: str, sexuality: str) -> str | None:
    """The label the question asks about, with its article: "a lesbian",
    "bisexual", "a trans woman", "non-binary", from LezWatch.TV's own terms
    through ``identity`` (DECISIONS 0027), so no label is ever invented. A
    parenthetical qualifier ("Non-Binary (Intersex)") is left to the answer,
    which gives the full term. None when neither term gives a label."""
    label = identity(gender, sexuality)
    if label is None:
        return None
    label = " ".join(re.sub(r"\s*\([^)]*\)", "", label).split())
    if not label:
        return None
    if label in LABEL_NOUNS or label.endswith(("woman", "man")):
        return f"a {label}"
    return label


def character_questions(
    show: dict[str, Any], cast: list[CharacterView]
) -> list[CharacterQuestions]:
    """The question blocks, regulars first (``_ranked``, never an order a
    death could affect). The identity answer is "Yes, per LezWatch.TV:
    sexuality <S>, gender <G>." when the question carries a label, or
    "LezWatch.TV lists <name> with the sexuality <S> and the gender <G>."
    when it does not; a sexuality LezWatch.TV leaves empty or "Undefined"
    is said as "without a stated orientation". The role and actors follow,
    as the character list gives them, and a missing one is left out."""
    title = show["title"]
    blocks = []
    for c in _ranked(cast):
        label = question_label(c.gender, c.sexuality)
        before, after = _identity_answer(c, label)
        blocks.append(
            CharacterQuestions(
                name=c.name,
                source_url=c.source_url,
                question=f"Is {c.name} {label or NO_LABEL_WORD} in {title}?",
                before=before,
                after=after,
                who=_who(c),
                death_question=f"Does {c.name} die in {title}?",
            )
        )
    return blocks


def _identity_answer(c: CharacterView, label: str | None) -> tuple[str, str]:
    """The identity answer around the words "LezWatch.TV" (see
    ``character_questions``)."""
    unstated = c.sexuality in UNSTATED_SEXUALITIES
    if label is not None:
        terms = f"gender {c.gender}" if unstated else f"sexuality {c.sexuality}, gender {c.gender}"
        after = f": {terms}."
        if unstated:
            after += f" LezWatch.TV lists {c.name} without a stated orientation."
        return "Yes, per ", after
    if unstated:
        return "", f" lists {c.name} without a stated orientation; gender {c.gender}."
    return "", f" lists {c.name} with the sexuality {c.sexuality} and the gender {c.gender}."


def _who(c: CharacterView) -> str:
    """ "Regular, played by <actor>." from the role and actors the character
    list shows; a missing part is left out, and nothing is a placeholder."""
    parts = [p for p in (c.role if c.role != NOT_RECORDED else None, played_by(c)) if p]
    if not parts:
        return ""
    who = ", ".join(parts)
    return who[0].upper() + who[1:] + "."


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
    alive = sum(1 for c in cast if c.listed_alive)
    if not dead:
        who = "the one listed character" if n == 1 else f"any of the {listed}"
        tail = "It records deaths and nothing else, so this does not say anyone lives."
        if alive:
            # A date is on record, so "no death on record" would be false
            # (DECISIONS 0052); the note below says what is recorded.
            headline = f"{UNKNOWN}. LezWatch.TV does not list {who} as dead. {tail}"
        else:
            headline = (
                f"{UNKNOWN}. LezWatch.TV has no death on record "
                f"{'in this show ' if elsewhere else ''}for {who}. {tail}"
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
    if alive:
        notes.append(
            f"{'One listed character has' if alive == 1 else f'{alive} listed characters have'}"
            f" a recorded death date, but LezWatch.TV lists {'the character' if alive == 1 else 'them'}"
            f" as alive, so {'it is' if alive == 1 else 'they are'} not counted here."
        )
    return Answer(headline, notes)


def _years(years: dict[str, Any]) -> str:
    """The Years row's text for a years record (``shown_years``'s, or
    LezWatch's own). "ended" is said only when a source says the show ended;
    an end year is never invented."""
    start, end = years["start"], years["end"]
    if start is None:
        return NOT_RECORDED
    if end is not None:
        return str(start) if end == start else f"{start} to {end}"
    if years["on_air"] == "yes":
        return f"{start} to present"
    if years["on_air"] == "no":
        return f"{start}, ended (end year not recorded)"
    return f"{start} (end year not recorded)"


def _int_years(values: Iterable[Any]) -> tuple[int, ...]:
    """The plain years among ``values`` (ints or digit strings), sorted."""
    out = set()
    for v in values:
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            out.add(v)
        elif isinstance(v, str) and v.isdigit():
            out.add(int(v))
    return tuple(sorted(out))


def _date_year(value: Any) -> int | None:
    """The year of a TVmaze "YYYY-MM-DD" date, or None."""
    if not isinstance(value, str) or len(value) < 4 or not value[:4].isdigit():
        return None
    return int(value[:4])


def _joined_by_id(show: dict[str, Any]) -> bool:
    """True when TVmaze's record for this show came from an id join
    (``TVMAZE_ID_JOINS``) that no other LezWatch show shares."""
    sched = show["schedule"]
    join = sched.get("join") or {}
    return (
        sched["schedule_known"] is True
        and join.get("matched") is True
        and join.get("method") in TVMAZE_ID_JOINS
    )


def _tvmaze_start(show: dict[str, Any], earliest: int | None) -> int | None:
    """TVmaze's premiere year when DECISIONS 0049 lets it replace LezWatch's
    start year, else None. ``earliest`` is the earliest year LezWatch records
    for any character in this show (``earliest_character_year``).

    The join must be by id and both years known. No character may be placed in
    the show before TVmaze's premiere year (a character cannot appear before a
    show begins). Then TVmaze's year is used when it is one year earlier or
    later (the usual production-year or airdate gap), or when it is 2 to
    ``YEARS_CORROBORATED_GAP`` years earlier and LezWatch's own character
    records already place a character in the show before LezWatch's start
    year. Anything else keeps LezWatch's year."""
    years = show["years"]
    start, end = years["start"], years["end"]
    premiered = _date_year(show["schedule"]["premiered"])
    if (
        not _joined_by_id(show)
        or isinstance(start, bool)
        or not isinstance(start, int)
        or premiered is None
        or premiered == start
    ):
        return None
    if earliest is not None and earliest < premiered:
        return None
    if isinstance(end, int) and premiered > end:
        return None
    gap = start - premiered
    if abs(gap) == 1:
        return premiered
    if 2 <= gap <= YEARS_CORROBORATED_GAP and earliest is not None and earliest < start:
        return premiered
    return None


def earliest_character_year(cast: Iterable[CharacterView]) -> int | None:
    """The earliest year LezWatch records for any listed character in the
    show, or None. Only this one year is read: it says when someone was first
    in the show, never when anyone left or died."""
    return min((y for c in cast for y in c.years), default=None)


def first_character_years(doc: dict[str, Any]) -> dict[str, int]:
    """``earliest_character_year`` for every show at once, by show id (for the
    index, which has no cast lists)."""
    first: dict[str, int] = {}
    for c in doc["characters"]:
        for link in c["shows"]:
            for y in _int_years(link["years"]):
                sid = link["show_id"]
                first[sid] = min(first.get(sid, y), y)
    return first


def shown_years(show: dict[str, Any], earliest: int | None = None) -> tuple[dict[str, Any], bool]:
    """(the years record the page shows, whether TVmaze supplied any of it),
    DECISIONS 0049 (proposed). The record has LezWatch's shape: ``start``,
    ``end`` and ``on_air``.

    - Start: TVmaze's premiere year when ``_tvmaze_start`` allows it,
      otherwise LezWatch's.
    - End: LezWatch's end year when it has one. Otherwise, when TVmaze lists
      the show as Ended and its premiere year is within a year of the start
      year shown, the show is ended: TVmaze's end year when it has one (and it
      is not before the start), else no year. When TVmaze says Ended but its
      premiere year is further off, the two sources disagree, so the page says
      neither "present" nor "ended". Nothing else changes LezWatch's record."""
    years = show["years"]
    start, end, on_air = years["start"], years["end"], years["on_air"]
    tvmaze_start = _tvmaze_start(show, earliest)
    from_tvmaze = tvmaze_start is not None
    if tvmaze_start is not None:
        start = tvmaze_start
    sched = show["schedule"]
    if end is None and sched["schedule_known"] is True and sched["status"] == "Ended":
        premiered = _date_year(sched["premiered"])
        if (
            _joined_by_id(show)
            and isinstance(start, int)
            and premiered is not None
            and abs(premiered - start) <= 1
        ):
            on_air, from_tvmaze = "no", True
            ended = _date_year(sched["ended"])
            if ended is not None and ended >= start:
                end = ended
        else:
            on_air = "unknown"
    return {"start": start, "end": end, "on_air": on_air}, from_tvmaze


def years_fact(show: dict[str, Any], earliest: int | None = None) -> tuple[str, str]:
    """(label, value) for the Years row (DECISIONS 0049, proposed)."""
    years, from_tvmaze = shown_years(show, earliest)
    return ("Years, per TVmaze" if from_tvmaze else "Years"), _years(years)


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


def _same_show_by_year(show: dict[str, Any]) -> bool:
    """True when TVmaze's premiere year is within a year of LezWatch's start
    year (DECISIONS 0048). The join is by id, never by title; this is a second
    check before TVmaze may raise a running show's count, so a join to a
    same-named reboot or original cannot. Either year missing is False."""
    start = show["years"]["start"]
    premiered = show["schedule"]["premiered"]
    if not isinstance(start, int) or not isinstance(premiered, str):
        return False
    head = premiered[:4]
    return head.isdigit() and abs(int(head) - start) <= 1


def _running_count_lags(show: dict[str, Any], recorded: int | None, tvmaze: int | None) -> bool:
    """DECISIONS 0048: a show LezWatch marks on air, that TVmaze does not list
    as Ended, whose LezWatch count is below TVmaze's latest season."""
    return (
        recorded is not None
        and tvmaze is not None
        and tvmaze > recorded
        and show["years"]["on_air"] == "yes"
        and show["schedule"]["status"] != "Ended"
        and _same_show_by_year(show)
    )


def seasons_fact(show: dict[str, Any]) -> tuple[str, str, int | None]:
    """(label, value, count for structured data) for the Seasons row
    (DECISIONS 0031, 0048). For an ended show TVmaze's last season wins when
    the two disagree; for a running show TVmaze's latest season wins only when
    it is higher and the premiere years agree; when LezWatch has no count,
    TVmaze's latest season fills it. Absence stays "Not recorded", never a
    number."""
    recorded = show["seasons"]
    tvmaze = _tvmaze_last_season(show)
    ended = show["schedule"]["status"] == "Ended"
    if tvmaze is not None and (
        recorded is None
        or (ended and tvmaze != recorded)
        or _running_count_lags(show, recorded, tvmaze)
    ):
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


def _facts(
    show: dict[str, Any],
    today: dt.date | None = None,
    cast: Iterable[CharacterView] = (),
) -> list[tuple[str, str]]:
    """The facts rows. With ``today`` (the snapshot's day), a next-episode row
    follows the run status when TVmaze lists one (``next_episode_fact``).
    ``cast`` is read only for the earliest character year (``shown_years``)."""
    sched = show["schedule"]
    seasons_label, seasons, _ = seasons_fact(show)
    upcoming = next_episode_fact(show, today) if today is not None else None
    return [
        years_fact(show, earliest_character_year(cast)),
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
        *([upcoming] if upcoming else []),
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


_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
# LezWatch.TV genres that air so often that a season and episode number mean
# little: the airing page (DECISIONS 0033) and the next-episode row (0037)
# give a soap only its date.
SOAP_GENRES = frozenset({"soap-opera", "telenovela"})
NEXT_EPISODE_LABEL = "Next episode, per TVmaze"


def us_date(day: dt.date) -> str:
    """ "Friday, November 20, 2026": weekday, month spelled out, no ordinal."""
    return f"{_WEEKDAYS[day.weekday()]}, {_MONTHS[day.month - 1]} {day.day}, {day.year}"


def _season_number(value: Any) -> int | None:
    """A season or episode number that counts, or None (not a number, or a
    season numbered by year, ``SEASON_IS_A_YEAR``)."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 1 <= value < SEASON_IS_A_YEAR else None


def _premiere_season(show: dict[str, Any]) -> int | None:
    """The season TVmaze's next episode opens (episode 1 of a numbered
    season), or None: not a premiere, numbers missing, or a soap."""
    sched = show["schedule"]
    if sched["schedule_known"] is not True or not sched["next_episode"]:
        return None
    if any(g["slug"] in SOAP_GENRES for g in show["genres"]):
        return None
    nxt = sched["next_episode"]
    season = _season_number(nxt.get("season"))
    return season if season is not None and _season_number(nxt.get("number")) == 1 else None


def next_episode_fact(show: dict[str, Any], today: dt.date) -> tuple[str, str] | None:
    """(label, value) for the next-episode row (DECISIONS 0037), or None.

    The date is TVmaze's, as a dated fact: "Season 4 premiere, Friday,
    November 20, 2026", "Season 10, episode 4, Thursday, ...", or only the
    date for a soap or when TVmaze gives no usable numbers. No row at all when
    TVmaze has no schedule, lists no next episode, its date is unreadable, or
    the date is before the snapshot's day (a stale listing): "no next episode
    listed" is not a value, so it is never printed as one. Never the episode
    name: one can give a death away ("Dead Air")."""
    sched = show["schedule"]
    if sched["schedule_known"] is not True or not sched["next_episode"]:
        return None
    nxt = sched["next_episode"]
    raw = nxt.get("airdate")
    if not isinstance(raw, str) or _long_date(raw) is None:
        return None
    day = dt.date.fromisoformat(raw)
    if day < today:
        return None
    when = us_date(day)
    premiere = _premiere_season(show)
    if premiere is not None:
        return NEXT_EPISODE_LABEL, f"Season {premiere} premiere, {when}"
    season, number = _season_number(nxt.get("season")), _season_number(nxt.get("number"))
    soap = any(g["slug"] in SOAP_GENRES for g in show["genres"])
    if season is not None and number is not None and not soap:
        return NEXT_EPISODE_LABEL, f"Season {season}, episode {number}, {when}"
    return NEXT_EPISODE_LABEL, when


TO_BE_ANNOUNCED = "date to be announced"


def next_episode_line(show: dict[str, Any], today: dt.date) -> tuple[str, str | None] | None:
    """(what the next-episode line says, the ISO date for its ``<time>`` or
    None), or None for no line (DECISIONS 0051).

    TVmaze's ``airdate`` is the calendar day in the network's own time zone
    (its ``airstamp`` carries the offset), so that day is printed as TVmaze
    gives it, never converted. An episode TVmaze lists with no date reads
    ``TO_BE_ANNOUNCED``: that is TVmaze's own statement, not a guess. No line
    when TVmaze has no schedule or lists no next episode (the Years row says
    when a show has ended, DECISIONS 0049), when the date is unreadable, or
    when it is before the snapshot's day (a stale listing). Never the episode
    name, and never "no upcoming episodes"."""
    sched = show["schedule"]
    if sched["schedule_known"] is not True or not sched["next_episode"]:
        return None
    raw = sched["next_episode"].get("airdate")
    if raw is None or raw == "":
        return TO_BE_ANNOUNCED, None
    if not isinstance(raw, str) or _long_date(raw) is None:
        return None
    day = dt.date.fromisoformat(raw)
    if day < today:
        return None
    return us_date(day), day.isoformat()


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
    premiere = _premiere_season(show)
    if prev_on:
        which = "last" if sched["status"] == "Ended" and not next_on else "most recent"
        text = f"Its {which} episode on TVmaze aired on {prev_on}"
        if isinstance(prev.get("season"), int) and isinstance(prev.get("number"), int):
            text += f" (season {prev['season']}, episode {prev['number']})"
        if not next_on:
            return text + "."
        if premiere is not None:
            return text + f", and the first episode of season {premiere} is listed for {next_on}."
        return text + f", and the next is listed for {next_on}."
    if next_on and premiere is not None:
        return f"TVmaze lists the first episode of season {premiere} for {next_on}."
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
    shown = shown_years(show, earliest_character_year(cast))[0]
    context = [part for part in (_opening_network(show), _opening_years(shown)) if part]
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
    years = shown_years(show, earliest_character_year(cast))[0]
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
        # The one "Get the app" block (DECISIONS 0047), badge by absolute
        # URL: app_store.apply publishes the file at the site root.
        "app_store_block": get_app_block(f"{base_url}/{BADGE_FILE}") if app_store_live else None,
        "app_store_style": BADGE_STYLE,
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
    today = dt.date.fromisoformat(doc["generated_at"][:10])
    return _ENV.get_template("show.html.j2").render(
        **_common(doc, base_url, app_store_live),
        title=show_title(show["title"], len(cast)),
        description=_description(show["title"], cast),
        opening=opening(show, cast),
        canonical=canonical,
        show=show,
        crumbs=crumbs,
        breadcrumb=_structured(_breadcrumb(crumbs), _series(show, canonical, cast)),
        facts=_facts(show, today, cast),
        cast=cast,
        listed=[(c, played_by(c)) for c in _ranked(cast)],
        questions=character_questions(show, cast),
        questions_visible=QUESTIONS_VISIBLE,
        next_episode=next_episode_line(show, today),
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


def _index_entry(s: dict[str, Any], first: dict[str, int] | None = None) -> dict[str, str]:
    years = shown_years(s, (first or {}).get(s["id"]))[0]
    return {"slug": s["slug"], "title": s["title"], "years": _years(years)}


def render_index(
    doc: dict[str, Any],
    shows: list[dict[str, Any]],
    *,
    base_url: str,
    app_store_live: bool = False,
    featured: list[dict[str, Any]] | None = None,
    airing: bool = False,
) -> str:
    """The shows index: the hand-picked shows first (``featured``), then every
    show A to Z under a letter heading, with a list of letters to jump to.
    The structured data lists every show in the published order. ``airing``
    adds the link to the airing-now page (DECISIONS 0033)."""
    canonical = f"{base_url}/shows/"
    crumbs = [(SITE_NAME, f"{base_url}/"), ("Shows", canonical)]
    first = first_character_years(doc)
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
        airing_url=f"{base_url}/airing/" if airing else None,
        featured=[_index_entry(s, first) for s in featured or []],
        groups=[
            {**g, "shows": [_index_entry(s, first) for s in g["shows"]]}
            for g in letter_groups(shows)
        ],
    )


def render_sitemap(
    doc: dict[str, Any],
    shows: list[dict[str, Any]],
    *,
    base_url: str,
    indexed: set[str] | None = None,
    airing: bool = False,
) -> str:
    """The home page (site_index.py, always published) first, the shows
    index, the airing-now page when ``airing`` (DECISIONS 0033), the findings
    and press pages (site_index.py, always published; DECISIONS 0042), then
    each show in ``indexed`` (``indexed_show_ids``; None means every show) in
    the published order."""
    urls = [
        f"{base_url}/",
        f"{base_url}/shows/",
        *([f"{base_url}/airing/"] if airing else []),
        *(f"{base_url}/{path}" for path in ALWAYS_LISTED),
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


def _airing_problems(files: dict[str, str], listed: set[str], base_url: str) -> list[str]:
    """The airing-now page (DECISIONS 0033) is open to search: built means
    listed in the sitemap, with its own canonical URL and no robots tag, and
    not built means not listed."""
    url = f"{base_url}/airing/"
    text = files.get(AIRING_PATH)
    if text is None:
        return (
            [f"the sitemap lists {url}, which is not a page of this build"] if url in listed else []
        )
    problems = [] if url in listed else [f"the sitemap does not list {url}"]
    probe = _HeadProbe()
    probe.feed(text)
    if probe.canonical != url:
        problems.append(f"{AIRING_PATH}: canonical is {probe.canonical!r}, not {url!r}")
    if probe.robots:
        problems.append(f"{AIRING_PATH}: in the sitemap but tagged {probe.robots}")
    return problems


def index_problems(files: dict[str, str], *, base_url: str) -> list[str]:
    """Every way the sitemap and the robots tags of ``files`` disagree; empty
    when they agree (DECISIONS 0028).

    A show page or the shows index whose canonical URL is in the sitemap must
    carry no robots tag; one that is not in the sitemap must carry exactly
    ``ROBOTS_HOLD``. Every show URL in the sitemap must be a page in
    ``files``, and the home page and the shows index must be listed. The
    airing-now page (DECISIONS 0033), when built, must be listed and carry
    no robots tag, and the sitemap must not list it when it is not built."""
    locs = _sitemap_locs(files["sitemap.xml"])
    listed = set(locs)
    problems: list[str] = []
    if len(listed) != len(locs):
        problems.append("the sitemap lists a URL twice")
    for required in (
        f"{base_url}/",
        f"{base_url}/shows/",
        *(f"{base_url}/{path}" for path in ALWAYS_LISTED),
    ):
        if required not in listed:
            problems.append(f"the sitemap does not list {required}")
    problems += _airing_problems(files, listed, base_url)
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
    airing: bool = True,
) -> dict[str, str]:
    """Every file of the site, as ``{relative path: text}``; writes nothing.
    ``airing`` builds the airing-now page (DECISIONS 0033) and links to it."""
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
            airing=airing,
        )
    }
    if airing:
        # Imported here: airing_page builds on this module's helpers.
        from qtv_pipeline import airing_page

        files[AIRING_PATH] = airing_page.render_airing(
            doc,
            base_url=base,
            built={s["id"]: f"{base}/shows/{s['slug']}/" for s in shows},
            app_store_live=app_store_live,
        )
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
    files["sitemap.xml"] = render_sitemap(doc, shows, base_url=base, indexed=indexed, airing=airing)
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
    from qtv_pipeline import airing_page

    built = {s["id"]: f"/shows/{s['slug']}/" for s in shows}
    for line in airing_page.plan_airing(doc, built).notes:
        print(line)
    print(f"show_pages: wrote {len(files)} files to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
