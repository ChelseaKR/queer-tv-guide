# Snapshot contract

`snapshot.v1.json` is the JSON Schema (draft 2020-12) for the one file the app
reads. The pipeline validates every build against it before publishing; the app
should validate `schema_version == "1"` and otherwise trust the shape.

Owned by `pipeline/`. Changes that remove or rename a field, tighten a type, or
change an enum bump the major version to a new file (`snapshot.v2.json`);
additive changes (new optional fields) do not. The app lane builds against this
file, not against the pipeline's Python.

## Where the file is published

One static URL, refreshed nightly (see `.github/workflows/snapshot.yml`):

```
https://chelseakr.github.io/queer-tv-guide/snapshot.v1.json
https://chelseakr.github.io/queer-tv-guide/snapshot.v1.json.sha256
```

GitHub Pages was chosen while the repository was private, when Release assets
needed a token to download, and it stays the app's one URL. The same bytes are
also attached to the rolling GitHub Release `snapshot-latest` (useful for
`gh release download` during development and as a history of checksums).

The app makes one conditional GET of the file with `If-None-Match` against the
stored ETag (`ios/GuideCore/Sources/GuideCore/SnapshotRefresher.swift`). If the
server returns 304 Not Modified, the cached copy is kept. That is the app's only
network call.

## Reading the model

### Identity

- `show.id` is `lwtv:show:<post id>`, `character.id` is `lwtv:character:<post id>`.
  LezWatch's WordPress post ids are the stable key; slugs and titles change.
- `character.shows[].show_id` and `show.similar_show_ids[]` only reference ids
  that exist in the same snapshot.

### Absence is explicit (the rule the app must respect)

| Situation | What the snapshot says | What the app must render |
|---|---|---|
| LezWatch records a death | `death.died: true`, `death_known: true`, `dates` non-empty | "Dies (2026)" |
| LezWatch records no death | `death.died: null`, `death_known: false`, `dates: []` | "Not recorded" — never "survives" or "no" |
| TVmaze matched, nothing scheduled | `schedule.schedule_known: true`, `next_episode: null` | "No upcoming episode" |
| TVmaze not matched, or its show is also matched to another LezWatch show | `schedule.schedule_known: false`, everything else in `schedule` null | "Schedule unknown" |
| LezWatch has no watch link | `watch_links: []` | Nothing; never a guessed service |
| Rating not given | `ratings.quality: null` (LezWatch stores 0 for unrated; the pipeline maps 0 → null) | "Unrated" |
| Gender/sexuality not recorded | `gender: null` | "Not recorded" |
| Season count not filled in | `seasons: null` (LezWatch stores 0; the pipeline maps 0 → null) | "Seasons not recorded" — never "0 seasons" |
| Finish year blank | `years.end: null`; read `years.on_air` (`yes`/`no`/`unknown`) | Don't infer "ongoing" from a blank |

`died` is constrained by the schema to `true` or `null`; `false` is a schema
violation and the build fails. LezWatch records deaths, not survival.

### A death date is not always a counted death (`death.counted`, DECISIONS 0053)

LezWatch keeps death dates and, separately, a status it shows as "Status:
Dead" or "Status: Alive" (the `dead` cliche) and counts on its show pages. When
`died` is true the pipeline also writes `counted`: true if the character
carries the marker, false if LezWatch records a date but lists the character as
alive (Holby City's Bernie Wolfe, Warrior Nun's Ava Silva, Sara Lance, Nora
West-Allen). `died` and `dates` do not change; episode placement (0041) still
uses the dates. The field is optional and additive; absent (older files, or no
recorded death) means "not computed", and a reader keeps its old reading.

| Situation | What the snapshot says | What the app must render |
|---|---|---|
| Date recorded, character marked dead | `died: true`, `counted: true` | "Dies (2019)" |
| Date recorded, character listed as alive | `died: true`, `counted: false` | "LezWatch.TV records a death date (2019) for this character but lists the character as alive, so it is not counted here" |
| Date recorded, field absent (old file) | `died: true`, no `counted` | as before: "Dies (2019)" |

### The LezWatch ↔ TVmaze join

Documented by LezWatch itself: its "Next Episode" feature passes a TVmaze id (or
IMDb id) to TVmaze. The pipeline tries, in order:

1. `lezshows_tvmaze_id_manual` (an editor override) → `GET /shows/{id}`
2. `lezshows_tvmaze_id` (LezWatch's stored id) → `GET /shows/{id}`
3. `lezshows_imdb` → `GET /lookup/shows?imdb={id}` (TVmaze 301s to the show)

`schedule.join.method` records which one matched (or `none`). A show with
`lezshows_tvmaze_ignore` set is not joined and is counted as
`coverage.tvmaze.misses.ignored_by_source`. The miss rate is in
`coverage.tvmaze` on every build and printed by the pipeline.

A join is by id, and nothing proves the TVmaze show is the one LezWatch means.
When two or more LezWatch shows resolve to the same TVmaze show, at most one of
them is right and the pipeline cannot tell which, so none of them gets that
schedule: each has `schedule_known: false` (the app says "Schedule unknown") and
is counted as `coverage.tvmaze.misses.shared_tvmaze_id`. Each such TVmaze show is
listed in `coverage.tvmaze.shared_tvmaze_ids` as `{tvmaze_id, show_ids}`, for a
person to review and fix at the source. Both fields were added after the first
v1 files, so a reader treats their absence as "not checked", not as zero.

### Where a death falls in a show (added after the first v1 files)

DECISIONS 0041. Each `death.dates[]` entry may carry `placements`: one per show
the death counts for under DECISIONS 0030, matched by air date to TVmaze's
episode list for that show.

| `precision` | What it says | What the app may say |
|---|---|---|
| `episode` | `season` and one number in `episodes` | "season 2, episode 7" |
| `episode_pair` | two episodes aired that day | "season 2, episode 7 or 8"; never pick one |
| `special` | a TVmaze special; `airdate` set, `episodes` null | "a special that aired <date>" |
| `season` | `season` only (often a season released at once) | "in season 2"; inside that season, "may be before or after" |
| `unplaced` | `reason` says why; `season` null | that a death is recorded but cannot be placed; never "0" or "none" |
| `other_show` | a crossover date that lands on an episode of another of the character's shows | not counted for this show |

`show_id` is null only when the date counts for none of the character's shows.
A date says only that the character died at some point; LezWatch.TV records no
date for a return, so never read a placement as "still dead".

`show.episode_counts` lists numbered regular episodes per season (specials not
counted), for a season-and-episode picker. It is null when this build has no
episode list for the show (only joined shows with a recorded death are
fetched); null never means zero episodes. `coverage.placements` counts the
death events by precision and reason, and carries the placebo control the
build gates on.

A reader treats any of these fields' absence as "not computed".

### Attribution and license

`attribution[]` holds one entry per source with display text, link, license
name/URL, the terms URL and the date the terms were read. The app must show all
of it on an attribution screen reachable from the main navigation, and must link
every show and character to its `source_url` (LezWatch asks for a link back;
TVmaze's CC BY-SA attribution is satisfied by linking to TVmaze URLs, which
`schedule.tvmaze_url` and each `episode.url` provide).

`licence.snapshot` is `CC-BY-SA-4.0`: the snapshot file is a database that
incorporates TVmaze data, so ShareAlike attaches to the file. It does not attach
to the app code. `licence.notice` is the plain-language version the app shows
verbatim. Details in `docs/LICENSES-AND-ATTRIBUTION.md`.

The field names `licence`, `licence_name` and `licence_url` keep their British
spelling on purpose: they are part of the published v1 contract, and renaming
them would break every reader of an existing file.

### Coverage

`coverage` carries two numbers for everything: fetched vs available per source,
joined vs total for TVmaze with misses broken down by reason, and present vs
absent per field. The app may surface these on the attribution screen ("2,272 of
2,272 shows; 1,9xx with a schedule").

### Determinism

`content_digest` is the SHA-256 of the canonical JSON (sorted keys, no
whitespace, UTF-8) of the document with `generated_at`, `build.run`, and the
per-source `fetched_at`/`requests`/`bytes`/`mode` removed. Two builds over the
same mirror produce the same digest. `snapshot.v1.json.sha256` is the digest of
the file bytes, for transport integrity.

### Sizes

Measured on the first full mirror (2026-09-13): 2,272 shows, 7,375
characters, 12.5 MB. Text fields (`summary`, `notes.*`,
`ratings.worth_it_details`) are the bulk.

## Validating locally

```
cd pipeline && uv run qtv validate path/to/snapshot.v1.json
```
