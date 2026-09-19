"""Orchestration: `qtv fetch` mirrors the sources into the cache (network);
`qtv build` turns the cache into snapshot.v1.json (offline, deterministic).
Keeping them separate means build can be re-run, tested, and validated without
ever touching the network, and a network failure during fetch cannot produce
a partial snapshot: build simply refuses to run without a completed fetch.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jsonschema

from . import __version__, fields, lezwatch, normalize, terms, tvmaze
from . import coverage as coverage_mod
from . import digest as digest_mod
from . import license as license_mod
from .http import HostCounters, PacedClient


class BuildError(RuntimeError):
    """The mirror is missing, incomplete, or fails validation. Nothing is published."""


RUN_META_PATH = "run.json"

MAX_SHRINK_PERCENT = 2
"""The most the shows or the characters may fall, against the snapshot this build
replaces, before the build refuses (README, Build gates, gate 6). LezWatch's
catalog only grows in ordinary weeks; two percent is about 45 shows or 147
characters gone in one night, which is a fault far more often than an edit.
`--allow-shrink` is the deliberate override."""


def _now_z() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run_fetch(
    cache_dir: Path,
    *,
    full: bool = False,
    log: Callable[[str], None] = print,
    client_factory: Callable[..., PacedClient] = PacedClient,
) -> dict[str, Any]:
    """Network phase. Raises on any unrecovered fetch error or a terms change --
    both are fatal to the run, per the crawl-budget and license-gate rules.

    `client_factory` exists so tests can inject a PacedClient wired to an
    httpx.MockTransport and a no-op sleep, without any network dependency and
    without a production code path branching on "are we under test"."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    started_at = _now_z()

    with client_factory(log=log) as client:
        terms.check_lezwatch_terms(client)
        log("license gate: LezWatch ToS still grants reuse")

        taxonomies = lezwatch.fetch_taxonomies(client, cache_dir)
        n_terms = sum(len(v) for v in taxonomies.values())
        log(f"taxonomies: {n_terms} terms in {len(taxonomies)} lists")

        shows_available = lezwatch.fetch_available_count(client, "show")
        shows_result, _ = lezwatch.fetch_shows(client, cache_dir, full=full)
        log(f"shows: {shows_result.fetched} fetched this run ({shows_available} available)")

        chars_available = lezwatch.fetch_available_count(client, "character")
        chars_result, _ = lezwatch.fetch_characters(client, cache_dir, full=full)
        log(f"characters: {chars_result.fetched} fetched this run ({chars_available} available)")

        actor_names = lezwatch.fetch_actor_names(client, cache_dir)
        log(f"actors: {len(actor_names)} names")

        for kind, total in (("shows", shows_available), ("characters", chars_available)):
            id_list = lezwatch.fetch_id_list(client, cache_dir, kind=kind, expected_total=total)
            outcome = lezwatch.reconcile(
                client, cache_dir, kind=kind, live_ids=id_list, expected_total=total
            )
            if outcome.refetched:
                log(
                    f"{kind}: {len(outcome.refetched)} in the id list but not the cache, fetched by id"
                )
            if outcome.removed:
                log(f"{kind}: {len(outcome.removed)} removed from cache (no longer published)")
            if outcome.kept:
                log(
                    f"{kind}: {len(outcome.kept)} missing from the id list but still published; kept"
                )

        shows_raw = lezwatch.load_shows(cache_dir)
        joins = tvmaze.sync_shows(client, cache_dir, shows_raw, full=full)
        matched = sum(1 for j in joins.values() if j.get("matched"))
        log(f"tvmaze: {matched}/{len(joins)} shows joined this run")

        counters = client.counters_as_dict()

    finished_at = _now_z()
    lw = counters.get("lezwatchtv.com", HostCounters().as_dict())
    tv = counters.get("api.tvmaze.com", HostCounters().as_dict())
    run_meta = {
        "mode": "full" if full else "incremental",
        "started_at": started_at,
        "finished_at": finished_at,
        "lezwatch": {
            "requests": lw["requests"],
            "bytes": lw["bytes"],
            "available": {
                "shows": shows_available,
                "characters": chars_available,
                "actors": None,
            },
        },
        "tvmaze": {"requests": tv["requests"], "bytes": tv["bytes"]},
    }
    (cache_dir / RUN_META_PATH).write_text(json.dumps(run_meta, indent=1, sort_keys=True))
    log(
        f"requests: lezwatch={lw['requests']} ({lw['bytes']} bytes), "
        f"tvmaze={tv['requests']} ({tv['bytes']} bytes)"
    )
    return run_meta


def _find_schema_path() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "schema" / "snapshot.v1.json",  # repo-root/schema (normal checkout)
        Path.cwd().parent / "schema" / "snapshot.v1.json",  # cwd == pipeline/
        Path.cwd() / "schema" / "snapshot.v1.json",  # cwd == repo root
    ]
    for c in candidates:
        if c.exists():
            return c
    raise BuildError(
        f"schema/snapshot.v1.json not found near any of: {[str(c) for c in candidates]}"
    )


def run_build(
    cache_dir: Path,
    out_dir: Path,
    *,
    git_sha: str | None = None,
    workflow_run_id: str | None = None,
    schema_path: Path | None = None,
    previous_path: Path | None = None,
    allow_shrink: bool = False,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Offline phase. No network calls. Refuses to write anything if the cache
    is missing, empty or short of the source's total, the assembled snapshot
    fails schema validation, or it is much smaller than `previous_path`."""
    run_meta_path = cache_dir / RUN_META_PATH
    if not run_meta_path.exists():
        raise BuildError(f"{run_meta_path} missing; run `qtv fetch` before `qtv build`")
    run_meta = json.loads(run_meta_path.read_text())

    taxonomies_raw = lezwatch.load_taxonomies(cache_dir)
    taxonomies_by_key = {
        key: fields.terms_by_id(terms_list) for key, terms_list in taxonomies_raw.items()
    }

    shows_raw = lezwatch.load_shows(cache_dir)
    chars_raw = lezwatch.load_characters(cache_dir)
    actor_names = lezwatch.load_actor_names(cache_dir)
    joins = tvmaze.load_joins(cache_dir)

    if not shows_raw:
        raise BuildError("no shows in cache; refusing to publish an empty snapshot")
    if not chars_raw:
        raise BuildError("no characters in cache; refusing to publish an empty snapshot")
    _check_completeness(run_meta["lezwatch"]["available"], len(shows_raw), len(chars_raw))

    shows = [normalize.normalize_show(raw, taxonomies_by_key) for raw in shows_raw]
    characters = [
        normalize.normalize_character(raw, taxonomies_by_key, actor_names) for raw in chars_raw
    ]

    _attach_schedules(shows, joins, cache_dir)
    show_ids = _drop_dangling_references(shows, characters)
    _count_characters_per_show(shows, characters)

    tvmaze_cov = coverage_mod.tvmaze_coverage(shows)
    clean_shows = [normalize.strip_internal(s) for s in shows]
    field_cov = coverage_mod.field_presence(clean_shows, characters)

    lw_available = run_meta["lezwatch"]["available"]
    coverage = {
        "lezwatch": {
            "shows": {"available": lw_available["shows"], "fetched": len(shows)},
            "characters": {"available": lw_available["characters"], "fetched": len(characters)},
            "actors": {"available": lw_available["actors"], "fetched": len(actor_names)},
        },
        "tvmaze": tvmaze_cov,
        "fields": field_cov,
    }

    taxonomies_block = {
        key: [
            {
                "lwtv_id": int(t["id"]),
                "slug": t["slug"],
                "name": t["name"],
                "count": t.get("count"),
            }
            for t in terms_list
        ]
        for key, terms_list in taxonomies_raw.items()
    }

    doc: dict[str, Any] = {
        "schema_version": "1",
        "generated_at": _now_z(),
        "content_digest": "sha256:" + "0" * 64,  # placeholder, replaced below
        "build": {
            "pipeline_version": __version__,
            "run": {"git_sha": git_sha, "workflow_run_id": workflow_run_id},
        },
        # "licence" is a published v1 field name: spelling kept for existing readers.
        "licence": {"snapshot": license_mod.SNAPSHOT_LICENSE, "notice": license_mod.LICENSE_NOTICE},
        "attribution": license_mod.ATTRIBUTION,
        "sources": {
            "lezwatch": {
                "name": "LezWatch.TV",
                "base_url": "https://lezwatchtv.com/wp-json/",
                "fetched_at": run_meta["finished_at"],
                "requests": run_meta["lezwatch"]["requests"],
                "bytes": run_meta["lezwatch"]["bytes"],
                "mode": run_meta["mode"],
            },
            "tvmaze": {
                "name": "TVmaze",
                "base_url": "https://api.tvmaze.com/",
                "fetched_at": run_meta["finished_at"],
                "requests": run_meta["tvmaze"]["requests"],
                "bytes": run_meta["tvmaze"]["bytes"],
                "mode": run_meta["mode"],
            },
        },
        "coverage": coverage,
        "taxonomies": taxonomies_block,
        "shows": sorted(clean_shows, key=lambda s: s["lwtv_id"]),
        "characters": sorted(characters, key=lambda c: c["lwtv_id"]),
    }
    doc["content_digest"] = digest_mod.content_digest(doc)

    _validate(doc, schema_path or _find_schema_path(), show_ids)
    _check_no_shrink(doc, previous_path, allow_shrink=allow_shrink, log=log)
    _write_outputs(doc, coverage, out_dir, log)
    return doc


def _check_completeness(available: dict[str, int | None], shows: int, characters: int) -> None:
    """Gate 3: the mirror holds at least `COMPLETENESS_FLOOR_PERCENT` of what the
    source says it has. Checked offline from the totals the fetch recorded, so a
    snapshot short of its own source is never built. A total the source did not
    give cannot be checked, and an unchecked mirror is not published."""
    for kind, held in (("shows", shows), ("characters", characters)):
        total = available.get(kind)
        if total is None:
            raise BuildError(
                f"cannot check mirror completeness: LezWatch reported no total for {kind}"
            )
        if held * 100 < total * lezwatch.COMPLETENESS_FLOOR_PERCENT:
            raise BuildError(
                f"mirror completeness: {held} of the {total} {kind} LezWatch reports are "
                f"cached ({100 * held / total:.1f}%); at least "
                f"{lezwatch.COMPLETENESS_FLOOR_PERCENT}% is required. Nothing is published; "
                "the last good snapshot stays."
            )


def _check_no_shrink(
    doc: dict[str, Any],
    previous_path: Path | None,
    *,
    allow_shrink: bool,
    log: Callable[[str], None],
) -> None:
    """Gate 6: the new snapshot has not lost more than `MAX_SHRINK_PERCENT` of its
    shows or characters against the one it replaces. Skipped, loudly, when there
    is no previous file to compare with."""
    if previous_path is None:
        log("shrink gate SKIPPED: no previous snapshot was supplied to compare with")
        return
    try:
        previous = json.loads(previous_path.read_text())
        before = {kind: len(previous[kind]) for kind in ("shows", "characters")}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise BuildError(
            f"cannot compare with the previous snapshot {previous_path}: {exc!r}"
        ) from exc
    for kind, old in before.items():
        new = len(doc[kind])
        # A shrink is new below (100 - MAX_SHRINK_PERCENT)% of old, in integers.
        if new * 100 >= old * (100 - MAX_SHRINK_PERCENT):
            continue
        fell = f"{kind}: {old} in the previous snapshot, {new} now ({100 * (old - new) / old:.1f}% fewer)"
        if allow_shrink:
            log(f"shrink gate OVERRIDDEN by --allow-shrink: {fell}")
            continue
        raise BuildError(
            f"the snapshot shrank more than {MAX_SHRINK_PERCENT}%: {fell}. Nothing is "
            "published. If the removal is real, build with --allow-shrink."
        )
    log(
        f"shrink gate: shows {before['shows']} -> {len(doc['shows'])}, "
        f"characters {before['characters']} -> {len(doc['characters'])}"
    )


def _attach_schedules(
    shows: list[dict[str, Any]], joins: dict[str, dict[str, Any]], cache_dir: Path
) -> None:
    """Give every show its TVmaze schedule block (unknown when not joined)."""
    for show in shows:
        join = joins.get(str(show["lwtv_id"]))
        tvmaze_show = None
        if join and join.get("matched") and join.get("tvmaze_id") is not None:
            tvmaze_show = tvmaze.load_tvmaze_show(cache_dir, join["tvmaze_id"])
        show["schedule"] = normalize.normalize_schedule(join, tvmaze_show)


def _drop_dangling_references(
    shows: list[dict[str, Any]], characters: list[dict[str, Any]]
) -> set[str]:
    """Remove similar-show and character-show links to shows not in this
    snapshot, and return the ids that are."""
    show_ids = {s["id"] for s in shows}
    for show in shows:
        show["similar_show_ids"] = [sid for sid in show["similar_show_ids"] if sid in show_ids]
    for char in characters:
        char["shows"] = [s for s in char["shows"] if s["show_id"] in show_ids]
    return show_ids


def _count_characters_per_show(
    shows: list[dict[str, Any]], characters: list[dict[str, Any]]
) -> None:
    """Patch each show's character and recorded-death counts."""
    per_show_chars: dict[str, list[dict[str, Any]]] = {}
    for char in characters:
        for s in char["shows"]:
            per_show_chars.setdefault(s["show_id"], []).append(char)
    for show in shows:
        here = per_show_chars.get(show["id"], [])
        show["counts"]["characters"] = len(here)
        show["counts"]["deaths"] = sum(1 for c in here if c["death"]["death_known"])


def _validate(doc: dict[str, Any], schema_path: Path, show_ids: set[str]) -> None:
    """Refuse a document that fails the schema or references a missing show."""
    schema = json.loads(schema_path.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        raise BuildError(
            f"snapshot fails schema validation ({len(errors)} error(s)); first: "
            f"{'/'.join(str(p) for p in first.path)}: {first.message}"
        )

    dangling = [sid for s in doc["shows"] for sid in s["similar_show_ids"] if sid not in show_ids]
    if dangling:
        raise BuildError(f"referential integrity: {len(dangling)} similar_show_ids not in snapshot")


def _write_outputs(
    doc: dict[str, Any], coverage: dict[str, Any], out_dir: Path, log: Callable[[str], None]
) -> None:
    """Write the snapshot, its checksum line and the coverage report."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "snapshot.v1.json"
    raw = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False).encode("utf-8")
    out_path.write_bytes(raw)
    checksum_line = digest_mod.file_digest(raw) + "  snapshot.v1.json\n"
    (out_dir / "snapshot.v1.json.sha256").write_text(checksum_line)
    coverage_path = out_dir / "coverage.json"
    coverage_path.write_text(json.dumps(coverage, indent=1, sort_keys=True))

    for line in coverage_mod.summary_lines(coverage):
        log(line)
    log(f"wrote {out_path} ({len(raw)} bytes), content_digest={doc['content_digest']}")
