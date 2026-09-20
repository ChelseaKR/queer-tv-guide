# Responsible-tech audits: queer-tv-guide (working name)

Instantiates `docs/standards/RESPONSIBLE-TECH-FRAMEWORK.md` (pinned v2.0.0).
**Drafted 2026-09-17; not yet signed off.** Each audit below records findings
and a checklist. Its REVIEW-GATE is the owner's dated sign-off, which is
pending for every audit (#24). Nothing here is a completed review until that
line is filled in.

## Applicability

The repository is registered as a privacy-first, local-first tool: a native
app that works offline over a bundled public dataset, plus the pipeline that
builds the dataset.

- A Ethics: applies
- B Bias and representation: applies. The product describes LGBTQ+
  representation using a volunteer database's own labels.
- C Privacy: applies (the DPIA-lite is below)
- D Transparency: applies
- E Accessibility: applies. Native app and two HTML pages; see #22.
- F Security: applies (threat model below; ASVS declaration in §F)
- AI-EVAL: N/A. There is no model, prompt, retrieval or LLM anywhere in the
  product or the pipeline.
- I18N: applies, deferred to a second UI language (`docs/I18N.md`, #23)

## A. Ethics

**Stakeholders.** Users (people looking for queer TV, some not out); the
fictional characters' portrayal; **real actors**, named in credits;
LezWatch.TV's volunteers, whose work is the data; TVmaze.

**Worst plausible misuse.** Treating "this actor played a queer character" as
a statement about the actor, or using the dataset to target them. The snapshot
carries actor names only, never an actor's own sexuality or gender. The app
never infers anything about an actor.

**Worst plausible failures.**
- A wrong "does she die" answer: a spoiler, or false reassurance. Unrecorded
  deaths are `null` and read "not recorded", never "no".
- Outing a real person through the data. LezWatch's actor export includes
  actors' sexuality and gender; the pipeline drops it (test in #31).
- The app quietly sending data somewhere. There is one host and no SDKs,
  enforced by `SourceTreeGuardTests`.

**Non-goals (this is not):** a streaming app; a social product (no accounts,
reviews, comments or sharing of lists); a recommender that learns from
behavior; a source of claims about real people; a complete record of all
queer TV. The source covers queer women, non-binary and transgender
characters, and the app should say so.

**Kill switch / rollback.** Disable `snapshot.yml` to stop publishing; the
app keeps its last good copy and shows its date. Remove the app from sale in
App Store Connect. A published snapshot can be replaced by re-running the
workflow from a known-good commit.

| Check | Gate | Where |
|---|---|---|
| No telemetry, one host, no third-party code | AUTO | `ios/GuideCore/Tests/GuideCoreTests/SourceTreeGuardTests.swift` |
| `died` is never `false` | AUTO | `schema/snapshot.v1.json`, `pipeline/tests/test_build_end_to_end.py` |
| Actor personal fields never stored | AUTO | `pipeline/tests/test_data_minimization.py` (#31) |
| Source terms still grant reuse, checked every run | AUTO | `pipeline/src/qtv_pipeline/terms.py` |
| Consequence scan and non-goals signed off (RTF-01) | REVIEW | this section; **pending (#24)** |

## B. Bias and representation

- **Whose words.** Gender, sexuality, romantic orientation, tropes and
  "worth it" ratings are LezWatch.TV's volunteer editorial labels, shown as
  theirs and attributed. The app does not relabel or rank people.
- **Coverage skew.** The source catalogs queer women, non-binary and trans
  characters. Queer men are largely out of scope. Coverage leans towards
  English-language, US and UK television. The TVmaze join works for about 79%
  of shows (1,800 of 2,272 in the first full mirror), so schedules are
  missing unevenly. The app must describe itself by what it covers.
- **Framing of death.** "Bury Your Queers" is a real pattern the data records.
  Death information and death-revealing trope tags sit behind a closed-by-default
  reveal (#15). An unrecorded death is never presented as survival.
- **Erasure risk.** A show or character missing from the source is simply
  absent. The About screen shows fetched-versus-available counts.

| Check | Gate | Where |
|---|---|---|
| Death-revealing tags filtered from visible lists | AUTO | `ios/GuideCore/Tests/GuideCoreTests/PresentationTests.swift` |
| Coverage reported per run | AUTO | `coverage` block in the snapshot; `pipeline/src/qtv_pipeline/coverage.py` |
| Representational-harm review signed off (RTF-03) | REVIEW | this section; **pending (#24)** |

## C. Privacy (DPIA-lite)

- **Personal data processed by the developer: none.** No accounts, analytics,
  crash reporting or identifiers (`docs/DECISIONS.md` 0002). The data tier is
  L1 (public reference data; `docs/data/`, #31).
- **The one request.** Opening the app, or pulling to refresh, sends one HTTPS
  GET for the snapshot to GitHub Pages. GitHub logs the IP address under its
  own policy; the developer never receives it. `docs/site/privacy.html` says
  so.
- **On the device.** Favorites are stored in `UserDefaults`, never synced by
  the app, and covered by iOS data protection when the device is locked.
- **Open question for the owner: a shared device.** For someone not out,
  having this app, or its favorites list, visible to someone else on the same
  phone is itself a disclosure. The app has no lock and no quick way to clear
  favorites. Nothing the developer collects is at risk here; this is about
  the user's own device. Decide whether to add a "clear favorites" control
  and say something in the FAQ. Also decide whether this makes the app a
  "privacy-sensitive tool" under SECURITY §2, which would add its hardened
  controls.
- **Retention:** nothing retained by the developer. Snapshot data: L1,
  indefinite, removed within 30 days of a source withdrawing permission.

| Check | Gate | Where |
|---|---|---|
| Privacy manifest declares nothing collected, no tracking | AUTO | `SourceTreeGuardTests` |
| Privacy policy states the one request and GitHub's logs | REVIEW | `docs/site/privacy.html` |
| DPIA-lite signed off (RTF-04) | REVIEW | this section; **pending (#24)** |

## D. Transparency

- Every source is credited, with license links, on the About screen, and
  each show screen ends with an attribution footer that links to the
  sources.
- The data's age is on every screen ("data as of"). A next-episode date that
  has passed says so.
- Absence is explicit throughout: "not recorded", "schedule unknown",
  "unrated", never a default that reads as a fact.
- What the project may claim is in `docs/capabilities.md` (#29). No AI is used,
  so there is no model card.

| Check | Gate | Where |
|---|---|---|
| Attribution text carried in every snapshot from one source | AUTO | `pipeline/src/qtv_pipeline/license.py` feeds `attribution` and `licence`; the schema requires both |
| That text still matches `docs/LICENSES-AND-ATTRIBUTION.md` | REVIEW | no test compares them yet |
| Honesty-of-framing review signed off (RTF-05) | REVIEW | this section and `docs/capabilities.md`; **pending (#24)** |

## E. Accessibility

Findings and gaps are tracked in #22: the automated audit test is not on
`main` or in CI, and no human VoiceOver walkthrough has been done. No
conformance claim is made.

## F. Security

**Declarations (SECURITY-AND-SUPPLY-CHAIN-STANDARD §8, SEC-01, SEC-40):**

1. **ASVS level: N/A (no auth/authz/ingress surface).** The app has no
   accounts and no server; it is a client that makes one HTTPS GET. The
   pipeline runs in Actions with no network ingress. Supply-chain and scanning
   controls still apply in full.
2. **Container scanning: N/A (no Dockerfile).**
3. **SBOM + signing: pending the release model (#21).** The repository is
   release-producing (the app and the nightly snapshot), so this is owed, not
   N/A.
4. **Secret-management policy.** The repository stores no Actions secrets or
   variables (checked 2026-09-17). Workflows use only the per-run
   `GITHUB_TOKEN`, with job-scoped permissions. Apple signing identities and
   App Store Connect credentials live in the owner's keychain and Xcode, never
   in the repository or CI. Any future secret is scoped to one job, recorded
   here with its rotation date, rotated at least yearly, and revoked per
   INCIDENT-RESPONSE-STANDARD §4 on exposure.
5. **VEX:** none needed. No unfixable HIGH or CRITICAL dependency CVE (pip-audit
   and osv-scanner report none, #13).

**Threat model (STRIDE-lite).**

| Asset / flow | Threat | Mitigation | Residual |
|---|---|---|---|
| Published snapshot | Tampering through a compromised workflow or action | SHA-pinned actions, job-scoped writes, zizmor, CODEOWNERS on `.github/` (#13) | The app trusts whatever GitHub Pages serves over HTTPS. The snapshot is not signed, and the app does not verify provenance. A compromised account or deploy would be believed. |
| Snapshot content from the sources | Script or markup injection into prose | Prose stripped to plain text in the pipeline (#8); the app renders SwiftUI `Text`, with no web view | Misleading but well-formed data from a source. |
| The refresh request | Interception | HTTPS to one host, ephemeral session, no cookies | GitHub Pages availability. |
| Repository | A committed secret | gitleaks pre-commit, in CI over history and tree, and weekly TruffleHog over all tiers (#13, #16) | None known. |
| Pipeline dependencies | A vulnerable package | `uv.lock` hashes, pip-audit and osv-scanner on every PR and weekly | Zero-days. |
| The app's supply chain | A third-party SDK | None allowed; `SourceTreeGuardTests` fails on a remote package | None. |

| Check | Gate | Where |
|---|---|---|
| Workflow SAST, SAST, secret scan, SCA | AUTO | `make verify`, `security.yml` (#13) |
| Threat model and residual-risk register signed off (RTF-06) | REVIEW | this section; **pending (#24)** |

## Sign-off

| Audit | Reviewer | Date |
|---|---|---|
| A Ethics | — pending — | |
| B Bias and representation | — pending — | |
| C Privacy | — pending — | |
| D Transparency | — pending — | |
| F Security | — pending — | |
