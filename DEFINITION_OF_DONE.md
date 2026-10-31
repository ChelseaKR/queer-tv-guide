# Definition of Done

A change is done when every line below that applies is true. The PR template
repeats the review lines as a checklist. Reviewed quarterly; changes to this
file go through a pull request like any other (CODEOWNERS routes it to the
owner). Source: QUALITY-AND-METRICS-STANDARD, "Definition of Done".

## AUTO (merge-blocking, `make verify` and CI)

1. Format and lint: ruff (pipeline, root Python), zero findings.
2. Types: `mypy --strict` on the pipeline, zero errors.
3. Tests: pipeline suite with at least 85% branch coverage; GuideCore's Swift
   tests; the repository policy tests.
4. Security: gitleaks, semgrep, pip-audit, osv-scanner; zizmor on workflows;
   SHA-pinned actions.
5. Guardrails: the app's source-tree guards (one host, no third-party code,
   privacy manifest), the pipeline's license gate, and Greenlight's App Store
   preflight over the app and widget targets (`make greenlight`).

## REVIEW (the author confirms in the PR)

- The change is linked to an issue or states what it is for.
- `CHANGELOG.md` `[Unreleased]` is updated for anything a user or snapshot
  consumer would notice.
- Docs that describe the change are updated in the same PR.
- A decision that is expensive to reverse has an ADR (`docs/adr/`).
- A snapshot schema change has a migration note and bumps the schema version
  where the contract requires it (`schema/README.md`).
- A UI change keeps VoiceOver labels, Dynamic Type and Reduce Motion working.
- A new external surface (a host, an SDK, a data source) has a threat-model
  note, and a new data source has its terms read and snapshotted first.
- The ISO 25010 quality characteristic the change serves is named.

## RELEASE (before an App Store submission)

- The App Store checklist in `docs/APP-STORE.md` is complete.
- A dated VoiceOver walkthrough exists for this version (#22).
- The CHANGELOG section for the version is written and dated.
- Rollback is known: the previous build stays available in App Store Connect,
  and the previous snapshot can be republished.
- The significant-change check below is done.

### Significant change (app-store age-assurance laws)

Texas SB 2420, Utah 13-76, Louisiana R.S. 51:1771 and Alabama HB 161
require the developer to notify the app stores, and let parents of minors
approve, before a "significant change". A release is a significant change
if its Terms or privacy policy change does any of: adds a category of
personal data collected, stored or shared; adds in-app purchases or ads
(Utah and Alabama: where none existed); changes the age rating or the
content descriptors behind it. In Texas and Louisiana a material change to
functionality or user experience also counts.
`SignificantChange.states(for:)` in `ios/AgeAssurance` encodes this. When a
release is one:

- notify the stores before release: App Store Connect (age rating and
  release notes) and, once the Android app is on Google Play, the Play
  Console Age Signals page;
- present the platform flow on the release's first launch with
  `SignificantUpdatePresenter.present(updateDescription:requirements:from:)`
  (PermissionKit's parent request, or Apple's adult acknowledgment, as
  `requiredRegulatoryFeatures` says);
- keep the age rating honest and stable: the rating is set once in App Store
  Connect, and a later change is itself a significant change.
