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
   privacy manifest) and the pipeline's licence gate.

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
