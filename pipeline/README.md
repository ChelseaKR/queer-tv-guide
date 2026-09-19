# pipeline

Mirrors LezWatch.TV and TVmaze into `snapshot.v1.json` (contract:
`../schema/`). Python 3.12, `uv`. There are no users here: nothing in this
directory ever sees a person, and the only network calls are to the two
sources.

```
cd pipeline
uv sync --all-groups
uv run qtv terms-check                      # 1 request: the LezWatch ToS still grants reuse
uv run qtv fetch --cache .cache             # incremental mirror (full on first run)
uv run qtv build --cache .cache --out out   # normalize, validate, digest, coverage report
uv run qtv validate out/snapshot.v1.json
uv run pytest
```

`make verify` checks that `uv.lock` matches `pyproject.toml`, then runs ruff
(lint and format), `mypy --strict`, the offline test suite with its 85% branch
coverage floor (the end-to-end tests build a snapshot from fixtures), and a
wheel build. The root `make verify` runs it as `make pipeline`.

## Crawl budget (declared before the first mirror)

| | LezWatch.TV | TVmaze |
|---|---|---|
| Published limit | 100 requests / IP / 10 min | ≥ 20 calls / 10 s / IP |
| robots.txt | `Crawl-delay: 10` (`User-agent: *`) | none on `api.tvmaze.com` (404) |
| Pace | 1 request / 10 s, one connection | 1 request / s, one connection |
| On 429 | wait the 10-minute window, retry (max 3) | back off 5 s, doubling, retry (max 5) |
| On 5xx / network error | retry twice with backoff, then **fail the run** | same |
| User-Agent | `queer-tv-guide-pipeline/<version> (+https://github.com/ChelseaKR/queer-tv-guide)` | same |
| Full mirror | ~120 requests, ~20 min, ~10 MB | ~2,000 requests, ~35 min, ~4 MB |
| Nightly incremental (measured) | 23 requests | 670–676 requests |

Every run prints requests and bytes per host and writes them into
`sources.*` in the snapshot.
The nightly figures above come from the per-host request counters in the
[September 18 run](https://github.com/ChelseaKR/queer-tv-guide/actions/runs/35371523231)
(23 LezWatch, 670 TVmaze) and the
[September 19 run](https://github.com/ChelseaKR/queer-tv-guide/actions/runs/35434596786)
(23 LezWatch, 676 TVmaze). At one TVmaze request per second, 676 requests take
about 11 minutes. Recheck these figures when pipeline changes alter the run.

What is fetched, and only this:

- LezWatch: `wp/v2/show` and `wp/v2/character` with `_fields` trimmed to the
  data fields; the twelve `lez_*` taxonomies; `lwtv/v1/export/raw/actors/`
  (names only); `lwtv/v1/export/list/{shows,characters}/` (ids, to detect
  deletions); `/tos/` (the license gate). No images, no posts, no comments.
- TVmaze: `/shows/{id}?embed[]=nextepisode&embed[]=previousepisode` per joined
  show; `/lookup/shows?imdb=` as a fallback join; `/updates/shows` to decide
  what to refresh. No images, no summaries, no cast.

## Incremental fetch and the cursor

`cache/lezwatch/cursor.json` holds the newest `modified_gmt` seen per post
type. The next run asks `modified_after=<cursor minus 24 h>`; the overlap is
harmless because records are keyed by id. Deletions are detected by comparing
the cached ids with `export/list/*` (one request each). A `--full` run ignores
the cursor.

TVmaze is refreshed for a show when it has never been fetched, when its cached
status is not `Ended`, or when `/updates/shows` reports a newer `updated`
stamp than the cached record.

The cache directory is the mirror. In CI it is restored from and saved to the
rolling release as `mirror-cache.tar.gz`, so a nightly run is incremental and a
lost cache costs one full mirror, nothing else.

## Build gates (any one fails the run; nothing is published)

1. The LezWatch ToS still contains the sentence "You are welcome to use,
   reuse, and extend the data here for no fees." (`terms.py`).
2. Every source fetch completed: no request ended in an unrecovered error.
3. Mirror completeness: cached shows and characters ≥ 99 % of the source's
   `X-WP-Total`, and ≥ 1 of each.
4. The snapshot validates against `schema/snapshot.v1.json` (which forbids
   `died: false`).
5. Referential integrity: every `show_id` a character or show references
   exists in the snapshot.

The join rate to TVmaze is reported, not gated: it is a property of the sources.
Measured on the first full mirror (2026-09-13): 1,800/2,272 shows joined
(79.2%); misses were 37 with no join key at all and 435 where LezWatch's
stored/manual TVmaze id or IMDb id did not resolve on TVmaze (`not_found`) --
LezWatch's own docs describe hand-fixing exactly this class of mismatch via a
"TVmaze Names" override, which this pipeline does not yet search by show name
as a fourth fallback; that is the natural next improvement to the join rate.

## Publishing

`.github/workflows/snapshot.yml` runs nightly and on dispatch. It restores the
mirror, fetches incrementally, builds, and then:

1. uploads `snapshot.v1.json`, `snapshot.v1.json.sha256`, `coverage.json` and
   `mirror-cache.tar.gz` to the rolling release **`snapshot-latest`**
   (`gh release upload --clobber`), and
2. deploys `snapshot.v1.json`, its `.sha256`, and an `index.html` carrying the
   attribution and license notice to **GitHub Pages**.

Why both. Pages gives the app one plain static URL with an ETag, chosen while
the repository was private (a release asset on a private repository needs a
token to download), and publishing the file openly is also what CC BY-SA's
ShareAlike asks for (`docs/LICENSES-AND-ATTRIBUTION.md`). The
release keeps the cache and gives the app lane `gh release download` during
development. A rolling tag rather than dated tags because the app needs one
URL that never changes and dated releases would pile up 365 a year; the
deployment history on the Pages environment is the audit trail.

The one URL:

```
https://chelseakr.github.io/queer-tv-guide/snapshot.v1.json
```

## Absence discipline

- Character with no recorded death: `died: null`, `death_known: false`. Never
  `false`; the schema rejects it.
- Show with no watch link: `watch_links: []`. Never a guessed link.
- TVmaze not joined: `schedule_known: false` and every schedule field null.
  Joined with nothing scheduled: `schedule_known: true`, `next_episode: null`.
- Rating 0 in LezWatch means unrated and becomes `null`.
- Season count 0 in LezWatch means never filled in and becomes `null`.
- Prose fields (`summary`, `notes.plot`, `notes.queer_episodes`,
  `ratings.worth_it_details`) are HTML stripped to plain text: tags dropped,
  entities decoded, list items as `- ` lines. An inline `<img>` has no text,
  so no image URL reaches the snapshot.
- A failed fetch is a failed run. The previous snapshot stays current.

## Layout

```
src/qtv_pipeline/
  http.py       paced client: one connection, min interval per host, UA, counters, backoff
  terms.py      the LezWatch ToS gate
  lezwatch.py   mirror LezWatch into the cache (incremental, cursor, deletions)
  tvmaze.py     join and mirror TVmaze into the cache
  normalize.py  cache records -> snapshot records (all the absence rules)
  build.py      assemble, digest, validate, write
  coverage.py   two numbers everywhere, printed on every build
  cli.py        qtv
tests/          offline, httpx.MockTransport; negative controls assert the sabotage landed
```
