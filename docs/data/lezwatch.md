# Data card: LezWatch.TV

DATA-GOVERNANCE-STANDARD §1 (DG-01). The licence analysis, quotations and the
attribution text live in `docs/LICENSES-AND-ATTRIBUTION.md`; this card does not
repeat them.

| Field | Value |
|---|---|
| Source | LezWatch.TV REST API, `https://lezwatchtv.com/wp-json/`: `wp/v2/show`, `wp/v2/character` (fields trimmed), the twelve `lez_*` taxonomies, `lwtv/v1/export/raw/actors/`, `lwtv/v1/export/list/{shows,characters}/`, and `/tos/` for the licence gate. A volunteer-run database of queer female, non-binary and transgender characters on TV. |
| License | LezWatch.TV Terms of Use: free reuse, attribution requested, no formal open licence, so no SPDX identifier. Read and snapshotted on 2026-09-13 (`docs/terms-snapshots/2026-09-13/`). The pipeline re-reads the grant on every run and stops if it is gone (`pipeline/src/qtv_pipeline/terms.py`). The derived snapshot is published under CC-BY-SA-4.0, which LezWatch.TV's terms allow. |
| Fetch/refresh cadence | Nightly, `snapshot.yml` at 09:17 UTC. Incremental from a `modified_gmt` cursor with 24 hours of overlap; a full mirror on the first run or with `--full`. Paced at one request per 10 seconds (the robots.txt `Crawl-delay`). |
| Staleness SLA | 48 hours: two missed nightly runs. The app shows every snapshot's "data as of" time and its age, and past 48 hours (or when the age cannot be known) it says the data is out of date, above the content (`DataFreshness`). `freshness.yml` checks the published file every 6 hours: older than 30 hours (a missed nightly run) or a failed nightly run opens a SEV3 `incident` issue, and older than 48 hours makes it SEV2 (`scripts/check_snapshot_freshness.py`, #25). |
| Fetch timestamp | `sources.lezwatch.fetched_at` (UTC, when the fetch run finished) on every snapshot; `source_modified_at` (LezWatch's own `modified_gmt`) on every show and character. |
| Tier | **L1**, public reference data. Gender, sexuality and death data describe **fictional characters**. The only data about **real people** is actor names, which appear in public screen credits. |
| Sensitive fields not taken | LezWatch's actor export also carries each actor's sexuality, gender, birth and death dates, and social links. The pipeline keeps names only; `pipeline/tests/test_data_minimisation.py` plants values in every other field and proves none reaches the cache or the snapshot. Stored, those fields would be **L3** (they could out a real person). |
| Known limitations | The mirror must reach 99% of `X-WP-Total` or the build fails; the snapshot's `coverage` block reports fetched versus available. LezWatch stores 0 for "not filled in" (ratings, seasons), which the pipeline maps to null. Deaths are recorded per character, not per show. No images and no editorial posts are taken. |
| Retention | L1 (DG-06): kept while useful. If LezWatch.TV withdraws or changes its terms, the licence gate stops publication at once, and the published copy is removed within 30 days. |
| Dataset version | `schema_version` "1" plus a `content_digest` over the canonical document. There is no dataset version and the published file is overwritten nightly (#12). |
