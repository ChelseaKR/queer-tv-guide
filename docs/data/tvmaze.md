# Data card: TVmaze

DATA-GOVERNANCE-STANDARD §1 (DG-01). The licence analysis and the attribution
text live in `docs/LICENSES-AND-ATTRIBUTION.md`; this card does not repeat
them.

| Field | Value |
|---|---|
| Source | TVmaze API, `https://api.tvmaze.com/`: `/shows/{id}` with the next and previous episode embedded, per joined show; `/lookup/shows?imdb=` as a fallback join; `/updates/shows` to decide what to refresh. |
| License | CC-BY-SA-4.0 (TVmaze's API page, read and snapshotted on 2026-09-13). Share-alike attaches to the published snapshot, which is released under CC-BY-SA-4.0 for that reason; the app's code is not Adapted Material. |
| Fetch/refresh cadence | Nightly with the LezWatch.TV run. A show is refreshed when never fetched, when its cached status is not `Ended`, or when `/updates/shows` reports a newer stamp. Paced at one request per second. |
| Staleness SLA | 48 hours, as for LezWatch.TV, with the same alarm and the same in-app warning (one snapshot carries both sources). The app shows the "data as of" time, and a next-episode date that has already passed reads as passed, not upcoming. |
| Fetch timestamp | `sources.tvmaze.fetched_at` (UTC) on every snapshot. |
| Tier | **L1**, public reference data: network, status, premiere and end dates, and the next and previous episode (number, name, air date and time, runtime, URL). No personal data, no cast, no images, no summaries. |
| Known limitations | The join is through LezWatch.TV's stored TVmaze or IMDb id. The first full mirror (2026-09-13) joined 1,800 of 2,272 shows (79.2%); `coverage.tvmaze` reports every run's join rate and the reasons for each miss. A show that did not join says "schedule unknown", never "no upcoming episode". |
| Retention | L1 (DG-06): kept while useful; removed within 30 days if TVmaze withdraws the data. |
| Dataset version | As for LezWatch.TV: `schema_version` plus `content_digest`; dataset versioning is #12. |
