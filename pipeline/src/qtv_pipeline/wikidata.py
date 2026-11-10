"""Other titles and unknown season counts from Wikidata (DECISIONS 0055).

Wikidata is a third mirror with one difference from the other two: nothing in
the run depends on it. `qtv wikidata` runs as its own step, between `qtv fetch`
and `qtv build`, and always exits 0 in the workflow. It reads QLever, never
Wikimedia's `/sparql` or `/w/api.php`, which robots.txt disallows. It replaces
the cached file only after a complete read that looks whole, so an outage, a
429 or a cut-short answer leaves the last known file exactly as it was. `qtv
build` reads that file, or the committed one when the cache has none, and
contacts nothing.

A value is used only when the item's LezWatch.TV id (P7107) names this show and
the TVmaze id (P8600) or IMDb id (P345) the show already carries leads to that
same item and no other. A season count never replaces LezWatch.TV's or
TVmaze's, and a count TVmaze disagrees with is not used. No death field is read
from Wikidata, ever.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .http import FetchError, HostPolicy, PacedClient, UpstreamUnavailable
from .normalize import SEASON_IS_A_YEAR, tvmaze_last_season

HOST = "qlever.dev"
ENDPOINT = f"https://{HOST}/api/wikidata"

POLICY = HostPolicy(
    min_interval=10.0,
    wait_429=60.0,
    backoff_429=2.0,
    max_429=2,
    wait_5xx=15.0,
    max_5xx=1,
    max_retry_after=120.0,
)
"""QLever publishes no rate limit and has no robots.txt. Ten seconds between three
small queries, and little patience: a read that fails is tried again the next night,
so this step never holds up the night's snapshot. There is no later retry."""

CACHE_PATH = "wikidata/items.json"
SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "wikidata_items.json"
REJECTS_PATH = Path(__file__).resolve().parents[2] / "data" / "wikidata_title_rejects.json"
REFRESH_AFTER = dt.timedelta(days=7)
MIN_KEPT_PERCENT = 90
"""A read holding fewer items than this share of the last known file is treated as a
failed read: an answer cut short must not take values away."""

_PREFIXES = (
    "PREFIX wdt: <http://www.wikidata.org/prop/direct/> "
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
    "PREFIX skos: <http://www.w3.org/2004/02/skos/core#> "
)
QUERY_FACTS = (
    _PREFIXES + "SELECT ?item ?lezwatch ?tvmaze ?imdb ?seasons ?class ?language ?title WHERE { "
    "?item wdt:P7107 ?lezwatch . "
    "OPTIONAL { ?item wdt:P8600 ?tvmaze } "
    "OPTIONAL { ?item wdt:P345 ?imdb } "
    "OPTIONAL { ?item wdt:P2437 ?seasons } "
    "OPTIONAL { ?item wdt:P31 ?class } "
    "OPTIONAL { ?item wdt:P364 ?l . ?l wdt:P424 ?language } "
    "OPTIONAL { ?item wdt:P1476 ?title } }"
)
QUERY_LABELS = (
    _PREFIXES + "SELECT ?item ?label WHERE { "
    '{ ?item wdt:P7107 ?x . ?item rdfs:label ?label . FILTER(LANG(?label) IN ("en", "mul")) } '
    "UNION { ?item wdt:P7107 ?x . ?item wdt:P364 ?l . ?l wdt:P424 ?code . "
    "?item rdfs:label ?label . FILTER(LANG(?label) = STR(?code)) } }"
)
QUERY_ALIASES = (
    _PREFIXES + "SELECT ?item ?alias WHERE { ?item wdt:P7107 ?x . ?item skos:altLabel ?alias . "
    'FILTER(LANG(?alias) IN ("en", "mul")) }'
)

ENGLISH = frozenset({"en", "mul"})
# P31 classes that say the item is not the show itself.
NOT_A_SHOW_FOR_TITLES = frozenset({"Q21191270", "Q196600"})  # episode, media franchise
NOT_A_SHOW_FOR_SEASONS = NOT_A_SHOW_FOR_TITLES | frozenset(
    {"Q3464665", "Q11424", "Q506240"}  # one season of a series, film, television film
)

MAX_TITLE_LENGTH = 90
MIN_COMPACT_LENGTH = 3
MAX_ABBREVIATION_LENGTH = 6
MIN_SHARED_PREFIX = 4
MIN_LATIN_PERCENT = 80
MIN_ONE_WORD_ALIAS = 8
_STOP_WORDS = frozenset({"the", "a", "an", "of", "and", "in", "to", "my", "on", "for", "at"})
_QUALIFIER_WORDS = frozenset(
    {"live", "action", "reboot", "revival", "remake", "cgi", "classic", "extras", "anime"}
    | {"adaptation", "version", "original", "tv", "television"}
)
_APOSTROPHES = frozenset("'\u2019\u2018\u02bc`\u00b4")
_TRAILING_PARENTHESES = re.compile(r"[(\uff08][^()\uff08\uff09]*[)\uff09]\s*$")
_YEAR = re.compile(r"^(19|20)\d\d$")
_FETCHED_AT = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
_QID = re.compile(r"^Q\d+$")
_COUNTERS = ("requests", "bytes")
_SERIES_WORDS = re.compile(
    r"\b(?:(?:tv|television|web|animated|anime)\s+series|miniseries|mini-series|serie"
    r"|(?:the|la)\s+series)\b",
    re.IGNORECASE,
)
_PART_OF_A_SHOW = frozenset(
    {"season", "seasons", "episode", "episodes", "pilot", "saison", "temporada", "staffel"}
)
_SPOILER_WORDS = frozenset(
    {"die", "dies", "died", "dead", "death", "deaths", "kill", "kills", "killed", "killing"}
    | {"funeral", "finale", "ending", "widow", "widowed", "muerte", "morte", "mort", "tod"}
)


class WikidataReadError(ValueError):
    """An answer that is not what the query asks for. The read counts as failed."""


@dataclass(frozen=True)
class Candidate:
    name: str
    source: str
    language: str


def fold(text: str) -> str:
    """The app's search folding (SearchIndex.fold): case, width and diacritics
    folded, "&" read as "and", apostrophes dropped, other punctuation a space."""
    decomposed = unicodedata.normalize("NFKD", text).casefold()
    out: list[str] = []
    for ch in decomposed:
        if unicodedata.combining(ch) or ch in _APOSTROPHES:
            continue
        if ch == "&":
            out.append(" and ")
        else:
            out.append(ch if ch.isalnum() else " ")
    return " ".join("".join(out).split())


def _extra_words(folded: str, folded_title: str) -> set[str]:
    """The words of a candidate the title does not have, ignoring a bare year."""
    title_words = set(folded_title.split())
    return {w for w in folded.split() if w not in title_words and not _YEAR.match(w)}


def _looks_abbreviated(text: str) -> bool:
    compact = [ch for ch in text if ch.isalnum()]
    return len(compact) <= MAX_ABBREVIATION_LENGTH and sum(1 for ch in compact if ch.isupper()) >= 2


def _shares_a_word(folded: str, folded_title: str) -> bool:
    """A word of real content in common with the title, or one that starts the other
    ("Sense Eight" and "Sense8", "Black List" and "The Blacklist")."""
    title_words = [w for w in folded_title.split() if w not in _STOP_WORDS]
    words = [w for w in folded.split() if w not in _STOP_WORDS]
    return any(
        a == b
        or (min(len(a), len(b)) >= MIN_SHARED_PREFIX and (a.startswith(b) or b.startswith(a)))
        for a in words
        for b in title_words
    )


def _mostly_latin(text: str) -> bool:
    letters = [ch for ch in text if ch.isalpha()]
    latin = sum(1 for ch in letters if "LATIN" in unicodedata.name(ch, ""))
    return bool(letters) and latin * 100 >= len(letters) * MIN_LATIN_PERCENT


def title_rejection(candidate: str, title: str) -> str | None:
    """Why a candidate is not an other title for a show with this title, or None
    when it is one. Rules come from reading every candidate (DECISIONS 0055)."""
    folded, folded_title = fold(candidate), fold(title)
    compact = folded.replace(" ", "")
    extra = _extra_words(folded, folded_title)
    checks: tuple[tuple[bool, str], ...] = (
        (len(compact) < MIN_COMPACT_LENGTH or len(candidate) > MAX_TITLE_LENGTH, "unusable"),
        ("://" in candidate, "unusable"),
        (compact == folded_title.replace(" ", ""), "same_as_title"),
        (not extra, "adds_nothing"),
        (bool(_TRAILING_PARENTHESES.search(candidate.strip())), "disambiguated"),
        (bool(_SERIES_WORDS.search(candidate)), "disambiguated"),
        (extra <= _QUALIFIER_WORDS, "disambiguated"),
        (_looks_abbreviated(candidate), "abbreviation"),
        (bool(extra & _PART_OF_A_SHOW), "part_of_a_show"),
        (bool(extra & _SPOILER_WORDS), "spoiler_word"),
    )
    return next((reason for failed, reason in checks if failed), None)


def english_candidate_rejection(
    candidate: Candidate, item: dict[str, Any], title: str
) -> str | None:
    """Rules for an English label or alias. Editors' aliases are the dirtiest field
    Wikidata has: working titles, fan names, a character, an episode, plain vandalism.
    On an English-language show a name with no word in common with the title is more
    often one of those than a title, so it goes, with some real ones. On a show in
    another language an English name usually is a translation or a romanization, so
    only a bare word that could be anything goes."""
    folded, folded_title = fold(candidate.name), fold(title)
    if not _mostly_latin(candidate.name):
        return "not_latin_script"
    one_word = len(folded.split()) == 1
    languages = item["languages"]
    if not languages or "en" in languages:
        if one_word or not _shares_a_word(folded, folded_title):
            return "no_word_in_common"
    elif candidate.source == "alias" and one_word and len(folded) < MIN_ONE_WORD_ALIAS:
        return "short_alias"
    return None


# -- reading ---------------------------------------------------------------


# -- reading ----------------------------------------------------------------


def _bindings(client: PacedClient, query: str) -> list[dict[str, Any]]:
    answer = client.get_json(ENDPOINT, params={"query": query})
    try:
        rows = answer["results"]["bindings"]
    except (KeyError, TypeError) as exc:
        raise WikidataReadError(f"no result rows in the answer: {exc!r}") from exc
    if not isinstance(rows, list) or not rows:
        raise WikidataReadError("the answer holds no rows")
    return rows


def _qid(row: dict[str, Any]) -> str:
    return str(row["item"]["value"]).rsplit("/", 1)[-1]


def _empty_item() -> dict[str, Any]:
    return {
        "lezwatch": [],
        "tvmaze": [],
        "imdb": [],
        "seasons": [],
        "classes": [],
        "languages": [],
        "titles": [],
        "labels": [],
        "aliases": [],
    }


def _add(item: dict[str, Any], key: str, value: Any) -> None:
    if value not in item[key]:
        item[key].append(value)


def _add_facts(item: dict[str, Any], row: dict[str, Any]) -> None:
    for key, column in (
        ("lezwatch", "lezwatch"),
        ("tvmaze", "tvmaze"),
        ("imdb", "imdb"),
        ("seasons", "seasons"),
        ("languages", "language"),
    ):
        if column in row:
            _add(item, key, row[column]["value"])
    if "class" in row:
        _add(item, "classes", str(row["class"]["value"]).rsplit("/", 1)[-1])
    if "title" in row:
        _add(item, "titles", [row["title"].get("xml:lang", ""), row["title"]["value"]])


def _sorted_items(items: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        qid: {key: sorted(values) for key, values in item.items()}
        for qid, item in sorted(items.items())
    }


def read_items(client: PacedClient) -> dict[str, dict[str, Any]]:
    """Every item with a LezWatch.TV id, with only the fields this rule reads. All
    three queries must succeed; anything else raises and nothing is kept."""
    items: dict[str, dict[str, Any]] = {}
    try:
        for row in _bindings(client, QUERY_FACTS):
            _add_facts(items.setdefault(_qid(row), _empty_item()), row)
        for row in _bindings(client, QUERY_LABELS):
            if _qid(row) in items:
                value = [row["label"].get("xml:lang", ""), row["label"]["value"]]
                _add(items[_qid(row)], "labels", value)
        for row in _bindings(client, QUERY_ALIASES):
            if _qid(row) in items:
                value = [row["alias"].get("xml:lang", ""), row["alias"]["value"]]
                _add(items[_qid(row)], "aliases", value)
    except (KeyError, TypeError, AttributeError) as exc:
        raise WikidataReadError(f"an answer row is not the expected shape: {exc!r}") from exc
    return _sorted_items(items)


def _valid_item(item: Any) -> bool:
    if not isinstance(item, dict) or not set(_empty_item()) <= set(item):
        return False
    pairs = ("labels", "aliases", "titles")
    plain = set(_empty_item()) - set(pairs)
    return all(
        isinstance(item[key], list) and all(isinstance(v, str) for v in item[key]) for key in plain
    ) and all(
        isinstance(item[key], list)
        and all(
            isinstance(v, list) and len(v) == 2 and all(isinstance(x, str) for x in v)
            for v in item[key]
        )
        for key in pairs
    )


def _valid_mirror(data: Any) -> bool:
    """Everything `attach` and the schema rely on, so that a damaged file reads as no
    file rather than failing the build."""
    if not isinstance(data, dict) or not isinstance(data.get("items"), dict) or not data["items"]:
        return False
    if not _FETCHED_AT.match(str(data.get("fetched_at"))):
        return False
    if not all(isinstance(data.get(key, 0), int) and data.get(key, 0) >= 0 for key in _COUNTERS):
        return False
    return all(_QID.match(qid) and _valid_item(item) for qid, item in data["items"].items())


def _read_mirror_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if _valid_mirror(data) else None


def load_mirror(cache_dir: Path, *, seed: Path | None = None) -> dict[str, Any] | None:
    """The last known read: the cached file, else the committed one. None only when
    neither can be read, and then every value is simply absent."""
    return _read_mirror_file(cache_dir / CACHE_PATH) or _read_mirror_file(seed or SEED_PATH)


def _is_fresh(mirror: dict[str, Any] | None, now: dt.datetime) -> bool:
    if mirror is None:
        return False
    try:
        fetched = dt.datetime.fromisoformat(str(mirror["fetched_at"]).replace("Z", "+00:00"))
    except ValueError:
        return False
    return now - fetched < REFRESH_AFTER


def _write_atomically(path: Path, data: dict[str, Any]) -> None:
    """Replace the file in one step: a run killed here leaves the old file whole."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(render_mirror(data), encoding="utf-8")
    os.replace(temporary, path)


def render_mirror(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=0, sort_keys=True) + "\n"


@dataclass(frozen=True)
class RefreshResult:
    outcome: str
    """"refreshed", "fresh" (read recently, no request made) or "kept" (read failed)."""
    detail: str = ""


def refresh(
    cache_dir: Path,
    *,
    force: bool = False,
    now: dt.datetime | None = None,
    seed: Path | None = None,
    log: Callable[[str], None] = print,
    client_factory: Callable[..., PacedClient] = PacedClient,
) -> RefreshResult:
    """Read Wikidata when the last read is a week old and keep it only if it is
    whole. A read that fails changes nothing on disk and raises nothing."""
    moment = now or dt.datetime.now(dt.UTC)
    known = load_mirror(cache_dir, seed=seed)
    if not force and _is_fresh(_read_mirror_file(cache_dir / CACHE_PATH), moment):
        log("wikidata: read within the last week; no request made")
        return RefreshResult("fresh")
    with client_factory(log=log, policies={HOST: POLICY}) as client:
        try:
            items = read_items(client)
        except (FetchError, UpstreamUnavailable, ValueError) as exc:
            return _kept(f"read failed: {exc}", log)
        counters = client.counters_as_dict().get(HOST, {"requests": 0, "bytes": 0})
    if known is not None and len(items) * 100 < len(known["items"]) * MIN_KEPT_PERCENT:
        return _kept(f"{len(items)} items, against {len(known['items'])} last known", log)
    _write_atomically(
        cache_dir / CACHE_PATH,
        {
            "endpoint": ENDPOINT,
            "fetched_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "items": items,
            "requests": counters["requests"],
            "bytes": counters["bytes"],
        },
    )
    log(f"wikidata: {len(items)} items read in {counters['requests']} requests")
    return RefreshResult("refreshed")


def _kept(detail: str, log: Callable[[str], None]) -> RefreshResult:
    log(f"::notice::Wikidata not refreshed, last known values stay ({detail})")
    return RefreshResult("kept", detail)


# -- choosing values --------------------------------------------------------


def candidates(item: dict[str, Any]) -> list[Candidate]:
    """The item's English label and aliases and, for a show in one language other
    than English, its title in that language. Labels in other languages are how
    other markets translate a title, and those are not names this app's users know."""
    found = [Candidate(v, "label", lang) for lang, v in item["labels"] if lang in ENGLISH]
    found += [Candidate(v, "alias", lang) for lang, v in item["aliases"] if lang in ENGLISH]
    languages = item["languages"]
    if len(languages) == 1 and languages[0] not in ENGLISH:
        native = languages[0]
        found += [Candidate(v, "label", lang) for lang, v in item["labels"] if lang == native]
        found += [Candidate(v, "title", lang) for lang, v in item["titles"] if lang == native]
    return found


def season_count(item: dict[str, Any]) -> int | None:
    """P2437 when it is one whole number below a year and the item is a show, else
    None. Two different values are a disagreement, so neither is used."""
    if NOT_A_SHOW_FOR_SEASONS & set(item["classes"]):
        return None
    try:
        values = {float(v) for v in item["seasons"]}
    except (TypeError, ValueError):
        return None
    if len(values) != 1:
        return None
    value = values.pop()
    if not value.is_integer() or not 1 <= value < SEASON_IS_A_YEAR:
        return None
    return int(value)


def _index(items: dict[str, dict[str, Any]], key: str) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for qid, item in items.items():
        for value in item[key]:
            found.setdefault(str(value), set()).add(qid)
    return found


@dataclass(frozen=True)
class _Indexes:
    lezwatch: dict[str, set[str]]
    tvmaze: dict[str, set[str]]
    imdb: dict[str, set[str]]


def agreed_item(show: dict[str, Any], indexes: _Indexes) -> tuple[str | None, list[str], str]:
    """(item id, what matched, how it went): the one item the show's LezWatch.TV id
    and its TVmaze or IMDb id all name. Two ids that disagree give no item."""
    named = indexes.lezwatch.get(show["slug"], set())
    if not named:
        return None, [], "no_lezwatch_id"
    tvmaze_id = show["schedule"].get("tvmaze_id") or show["external_ids"].get("tvmaze")
    by_tvmaze = indexes.tvmaze.get(str(tvmaze_id), set()) if tvmaze_id is not None else set()
    by_imdb = indexes.imdb.get(show["external_ids"].get("imdb") or "", set())
    joined = by_tvmaze | by_imdb
    if not joined:
        return None, [], "no_second_id"
    if len(named) != 1 or joined != named:
        return None, [], "ids_conflict"
    matched = ["lezwatch"]
    matched += [name for name, hit in (("tvmaze", by_tvmaze), ("imdb", by_imdb)) if hit]
    return next(iter(named)), matched, "agreed"


def _accepted_titles(
    show: dict[str, Any],
    qid: str,
    item: dict[str, Any],
    rejects: dict[str, list[str]],
    tally: Counter[str],
) -> list[Candidate]:
    if NOT_A_SHOW_FOR_TITLES & set(item["classes"]):
        tally["not_a_show"] += len(candidates(item))
        return []
    kept: dict[str, Candidate] = {}
    for candidate in candidates(item):
        reason = title_rejection(candidate.name, show["title"])
        if not reason and candidate.language in ENGLISH:
            reason = english_candidate_rejection(candidate, item, show["title"])
        if not reason and candidate.name in rejects.get(qid, ()):
            reason = "rejected_by_hand"
        if reason:
            tally[reason] += 1
        else:
            tally["passed_rules"] += 1
            kept.setdefault(fold(candidate.name), candidate)
    return list(kept.values())


def _without_collisions(
    chosen: dict[str, list[Candidate]],
    shows: Iterable[dict[str, Any]],
    tally: Counter[str],
) -> dict[str, list[Candidate]]:
    """Drop a title that is another show's title, or that two shows both claim:
    search would then send someone to a show that may not be the one they mean."""
    titles: dict[str, set[str]] = {}
    for show in shows:
        titles.setdefault(fold(show["title"]), set()).add(show["id"])
    claims = Counter(fold(c.name) for names in chosen.values() for c in names)
    out: dict[str, list[Candidate]] = {}
    for show_id, names in chosen.items():
        kept = []
        for candidate in names:
            folded = fold(candidate.name)
            if titles.get(folded, set()) - {show_id}:
                tally["another_shows_title"] += 1
            elif claims[folded] > 1:
                tally["claimed_by_two_shows"] += 1
            else:
                kept.append(candidate)
        if kept:
            out[show_id] = kept
    return out


def _fits_the_run(count: int, years: dict[str, Any], this_year: int) -> bool:
    """A count with no second source must fit in the years LezWatch.TV records, give
    or take a year. Guiding Light's 72 counts its radio years, and Tales of the City's
    3 counts later miniseries LezWatch.TV lists on their own. No start year: no check
    is possible, so no value."""
    start = years.get("start")
    if start is None:
        return False
    return bool(count <= (years.get("end") or this_year) - start + 2)


def _season_fill(
    show: dict[str, Any], item: dict[str, Any], tally: Counter[str], this_year: int
) -> int | None:
    """Wikidata's count when LezWatch.TV has none and TVmaze has none or the same.
    A different TVmaze count is a disagreement, and it stays as it is."""
    if show["seasons"] is not None:
        return None
    count = season_count(item)
    if count is None:
        return None
    theirs = tvmaze_last_season(show)
    if theirs == count:
        tally["seasons_agree_with_tvmaze"] += 1
        return count
    if theirs is not None:
        tally["seasons_disagree_with_tvmaze"] += 1
        return None
    if not _fits_the_run(count, show["years"], this_year):
        tally["seasons_longer_than_the_run"] += 1
        return None
    tally["seasons_no_tvmaze"] += 1
    return count


def _block(
    qid: str,
    matched: list[str],
    read_on: str,
    titles: list[Candidate],
    seasons: int | None,
) -> dict[str, Any]:
    block: dict[str, Any] = {"item": qid, "matched_by": matched, "read_on": read_on}
    if titles:
        block["alternate_names"] = [
            {"name": c.name, "source": c.source, "language": c.language} for c in titles
        ]
    if seasons is not None:
        block["seasons"] = seasons
    return block


def load_rejects(path: Path | None = None) -> dict[str, list[str]]:
    """Names read by hand and found wrong, by item. Unreadable means none: the rules
    above still apply."""
    try:
        data = json.loads((path or REJECTS_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def attach(
    shows: list[dict[str, Any]],
    mirror: dict[str, Any] | None,
    *,
    rejects: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Add the agreed values to `shows` and return the counts for the coverage
    report. With no mirror nothing changes: absent stays absent."""
    tally: Counter[str] = Counter()
    if mirror is None:
        return {}
    items = mirror["items"]
    rejects = load_rejects() if rejects is None else rejects
    indexes = _Indexes(_index(items, "lezwatch"), _index(items, "tvmaze"), _index(items, "imdb"))
    agreed: dict[str, tuple[str, list[str]]] = {}
    chosen: dict[str, list[Candidate]] = {}
    for show in shows:
        qid, matched, how = agreed_item(show, indexes)
        tally[how] += 1
        if qid is not None:
            agreed[show["id"]] = (qid, matched)
            chosen[show["id"]] = _accepted_titles(show, qid, items[qid], rejects, tally)
    final = _without_collisions(chosen, shows, tally)
    read_on = str(mirror["fetched_at"])[:10]
    this_year = int(read_on[:4])
    for show in shows:
        if show["id"] not in agreed:
            continue
        qid, matched = agreed[show["id"]]
        titles = final.get(show["id"], [])
        seasons = _season_fill(show, items[qid], tally, this_year)
        if not titles and seasons is None:
            continue
        have = {fold(name) for name in show["alternate_names"]}
        titles = [c for c in titles if fold(c.name) not in have]
        show["alternate_names"] = show["alternate_names"] + [c.name for c in titles]
        if seasons is not None:
            show["seasons"] = seasons
        show["wikidata"] = _block(qid, matched, read_on, titles, seasons)
    return _coverage(mirror, shows, tally)


def _coverage(
    mirror: dict[str, Any], shows: list[dict[str, Any]], tally: Counter[str]
) -> dict[str, Any]:
    blocks = [s["wikidata"] for s in shows if "wikidata" in s]
    with_titles = [b for b in blocks if b.get("alternate_names")]
    return {
        "read_on": str(mirror["fetched_at"])[:10],
        "items": len(mirror["items"]),
        "agreed": tally["agreed"],
        "no_lezwatch_id": tally["no_lezwatch_id"],
        "no_second_id": tally["no_second_id"],
        "ids_conflict": tally["ids_conflict"],
        "titles_added": sum(len(b["alternate_names"]) for b in with_titles),
        "shows_with_titles": len(with_titles),
        "seasons_filled": sum(1 for b in blocks if "seasons" in b),
        "seasons_no_tvmaze": tally["seasons_no_tvmaze"],
        "seasons_agree_with_tvmaze": tally["seasons_agree_with_tvmaze"],
        "seasons_disagree_with_tvmaze": tally["seasons_disagree_with_tvmaze"],
        "seasons_longer_than_the_run": tally["seasons_longer_than_the_run"],
        "titles_rejected": {
            reason: count
            for reason, count in sorted(tally.items())
            if reason
            in {
                "unusable",
                "not_latin_script",
                "no_word_in_common",
                "short_alias",
                "rejected_by_hand",
                "same_as_title",
                "adds_nothing",
                "disambiguated",
                "abbreviation",
                "part_of_a_show",
                "spoiler_word",
                "not_a_show",
                "another_shows_title",
                "claimed_by_two_shows",
            }
        },
    }


def source_run(mirror: dict[str, Any] | None) -> dict[str, Any] | None:
    """The snapshot's `sources.wikidata`: the last good read, which may be days old."""
    if mirror is None:
        return None
    return {
        "name": "Wikidata (through QLever)",
        "base_url": f"https://{HOST}/",
        "fetched_at": mirror["fetched_at"],
        "requests": int(mirror.get("requests", 0)),
        "bytes": int(mirror.get("bytes", 0)),
        "mode": "full",
    }
