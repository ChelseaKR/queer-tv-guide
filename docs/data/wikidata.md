# Data card: Wikidata

DATA-GOVERNANCE-STANDARD §1 (DG-01). The license analysis lives in
`docs/LICENSES-AND-ATTRIBUTION.md`, and the rule for which values are used in
DECISIONS 0055; this card does not repeat them.

| Field | Value |
|---|---|
| Source | Wikidata, through QLever's public endpoint `https://qlever.dev/api/wikidata`: every item with a LezWatch.TV show id (P7107), with its TVmaze id, IMDb id, season count, type, language, English label and aliases, and label and title in its own language. |
| License | CC0-1.0 (Wikidata's licensing page, read and snapshotted on 2026-11-08). Inside the CC-BY-SA-4.0 snapshot it adds no condition. |
| Fetch/refresh cadence | At most weekly, in its own workflow step after the LezWatch.TV and TVmaze fetch. Three queries, one request per 10 seconds. A failed read is tried again the next night. |
| Staleness SLA | None of its own. A failed read leaves the last known values in place, and the committed copy is the floor. `sources.wikidata.fetched_at` shows the age. No alarm: an old alternate title does no harm, and the file's own 48-hour alarm is about LezWatch.TV and TVmaze. |
| Fetch timestamp | `sources.wikidata.fetched_at` (UTC), and `read_on` on each `show.wikidata`. |
| Tier | **L1**, public reference data: other titles of TV shows and season counts. No personal data, no cast, no images, no deaths. |
| Known limitations | Editors can change it, and a weekly read takes those edits without a person reading them; the rules and the rejected list catch known shapes of junk, not all of them. Only shows with two ids agreeing get values (about 1,910 of 2,290), so web series are mostly left out. QLever's base dump can lag Wikidata by weeks. A real alternate title with no word in common with an English-language show's title is rejected along with the junk. |
| Retention | L1 (DG-06): kept while useful. CC0 sets no removal duty. A wrong value is removed by naming it in `pipeline/data/wikidata_title_rejects.json` or by fixing it on Wikidata. |
| Dataset version | As for LezWatch.TV: `schema_version` plus `content_digest`; dataset versioning is #12. |
