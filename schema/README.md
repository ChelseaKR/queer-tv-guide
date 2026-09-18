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

The app fetches `snapshot.v1.json.sha256` first (~100 bytes), compares it with
the digest of the bundled/cached snapshot, and only then fetches the file. That
is the app's only network call.

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
| TVmaze not matched | `schedule.schedule_known: false`, everything else in `schedule` null | "Schedule unknown" |
| LezWatch has no watch link | `watch_links: []` | Nothing; never a guessed service |
| Rating not given | `ratings.quality: null` (LezWatch stores 0 for unrated; the pipeline maps 0 → null) | "Unrated" |
| Gender/sexuality not recorded | `gender: null` | "Not recorded" |
| Season count not filled in | `seasons: null` (LezWatch stores 0; the pipeline maps 0 → null) | "Seasons not recorded" — never "0 seasons" |
| Finish year blank | `years.end: null`; read `years.on_air` (`yes`/`no`/`unknown`) | Don't infer "ongoing" from a blank |

`died` is constrained by the schema to `true` or `null`; `false` is a schema
violation and the build fails. LezWatch records deaths, not survival.

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

### Attribution and licence

`attribution[]` holds one entry per source with display text, link, licence
name/URL, the terms URL and the date the terms were read. The app must show all
of it on an attribution screen reachable from the main navigation, and must link
every show and character to its `source_url` (LezWatch asks for a link back;
TVmaze's CC BY-SA attribution is satisfied by linking to TVmaze URLs, which
`schedule.tvmaze_url` and each `episode.url` provide).

`licence.snapshot` is `CC-BY-SA-4.0`: the snapshot file is a database that
incorporates TVmaze data, so ShareAlike attaches to the file. It does not attach
to the app code. `licence.notice` is the plain-language version the app shows
verbatim. Details in `docs/LICENSES-AND-ATTRIBUTION.md`.

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
