# Roadmap and metrics ledger

The product plan lives in the README, `docs/DECISIONS.md`, `docs/adr/` and the
issue tracker. This file carries the per-repository ledger the portfolio
standards ask for: the metrics table (QUALITY-AND-METRICS-STANDARD), the
optional CI stages (CI-CD §1, CICD-29), the observability tier
(OBSERVABILITY-STANDARD §0, OBS-21), recovery objectives (DG-13) and the
release declaration (REL-01). Values live here; the rigour lives in
`docs/standards/`.

## Metrics

| Metric | Target | Measured by | Gate | Owner |
|--------|--------|-------------|------|-------|
| Pipeline branch coverage [CQ-08] | ≥ 85% (an application, not a published library) | pytest-cov, `make pipeline` | AUTO | Chelsea |
| Pipeline complexity [CQ-05] | ≤ 10 per function | ruff C901 | AUTO | Chelsea |
| Pipeline types [CQ-06] | 0 errors, `mypy --strict` | `make -C pipeline type` | AUTO | Chelsea |
| Lockfile fresh [CQ-09] | `uv lock --check` passes | `make pipeline` | AUTO | Chelsea |
| GuideCore tests | all pass (no coverage floor yet, #20) | `swift test`, `make guidecore` | AUTO | Chelsea |
| Actions SHA-pinned [SEC-25] | 100% | zizmor `unpinned-uses` (waivers for `ci.yml` #11, `snapshot.yml` #12) | AUTO | Chelsea |
| Secrets [SEC-17/18/19] | 0 findings | gitleaks (history and tree), weekly TruffleHog over all tiers | AUTO | Chelsea |
| SAST [SEC-07] | 0 unwaived WARNING/ERROR | semgrep, `make sast` | AUTO | Chelsea |
| Dependency CVEs [SEC-11/13] | 0 known | pip-audit (hashed lock export), osv-scanner (`uv.lock`) | AUTO | Chelsea |
| Workflow SAST [CICD-19] | 0 at medium or above | zizmor, `make workflows` | AUTO | Chelsea |
| `make verify` ≡ CI [CICD-27] | identical targets | `tests/test_ci_parity.py` (pipeline and guidecore pending #11) | AUTO | Chelsea |
| No credentials or personal data in logs [OBS-11] | 0 | semgrep rule `.semgrep/no-sensitive-values-in-logs.yml` | AUTO | Chelsea |
| Snapshot schema-valid [DG-03] | every build | `qtv build` refuses to write an invalid snapshot | AUTO | Chelsea |
| App privacy premise | one host, no third-party code, privacy manifest empty | `SourceTreeGuardTests` | AUTO | Chelsea |
| Native accessibility audit [A11Y] | 0 issues on every screen, largest text size included; a closed "does she die" answer is not in the accessibility tree | `AccessibilityAuditTests` (`performAccessibilityAudit`), `make a11y` in `ci.yml`'s `guidecore` job (#22) | AUTO | Chelsea |
| VoiceOver walkthrough [A11Y-11, A11Y-18] | every primary task, per release | dated `docs/a11y/` record, from [the checklist](a11y/voiceover-walkthrough-checklist.md); not done yet | REVIEW (#22) | Chelsea |
| Threat model [QM-14, RTF-06] | per new external surface | `docs/RESPONSIBLE-TECH-AUDITS.md` §F | REVIEW (#24) | Chelsea |
| DORA delivery signal [QM-11] | reviewed quarterly | portfolio `delivery_metrics.py` | REVIEW | Chelsea |

## CI stages (CI-CD §1, CICD-29)

| Stage | Applies? | Where |
|---|---|---|
| 1–5 format, lint, type, test, security | Applies | `make verify`; `ci.yml` and `security.yml` |
| 6 a11y | Applies | native: the accessibility audit UI tests (#22); HTML: the Pages status page and privacy page (#12, #22) |
| 7 perf | Undecided (#36): the registry scopes PERFORMANCE conservatively as applying; the proposal is N/A, because there is no latency contract and no web frontend, and the app reads one static file | — |
| 8 responsible | Applies | the privacy-premise guards (`SourceTreeGuardTests`), the licence gate (`terms.py`, re-read on every pipeline run) and the `died` never-`false` schema control |

## Observability

- **Pipeline: Tier C.** A batch job run by `snapshot.yml` with no network
  ingress. Its record is the workflow run log (request and byte counts per
  source, no user data) plus `coverage.json` and the Pages status page. OTel
  tracing, metrics, SLOs and health probes: N/A — no long-running service. The
  opt-in `--log-format json` flag Tier C describes is not implemented yet
  (#19).
- **App: no telemetry, by design** (`docs/DECISIONS.md` 0002). No crash
  reporting, analytics, RUM or remote logging; the tier model's OTel and Core
  Web Vitals rows are N/A for that reason. What a user can observe is shown in
  the app: the snapshot's "data as of" time and any refresh failure.
- **No credentials or personal data in logs** (OBS-11, never N/A): the semgrep
  rule above, over Python and Swift.

## Recovery objectives (DG-13)

| Surface | RPO | RTO | How |
|---|---|---|---|
| Published snapshot (GitHub Pages) | 24 h (rebuilt nightly) | about 1 h | dispatch `snapshot.yml`; the mirror cache restores from the `snapshot-latest` release assets. Not exercised yet (#25). |
| Favourites | n/a: on the device only | n/a | the user's own device backup (#25) |

## Releases (REL-01)

Release-producing: the App Store app (`MARKETING_VERSION` in
`ios/Config/Shared.xcconfig`) and the nightly snapshot (versioned by
`schema_version` and `content_digest`; dataset versioning is #12). Nothing has
been released or tagged. The release model is #21. Supported versions are
stated in `SECURITY.md`.
