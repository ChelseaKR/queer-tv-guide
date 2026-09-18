# 0012. GuideCore's tests run on macOS for pull requests that touch them

- **Status:** Proposed
- **Date:** 2026-09-17
- **Deciders:** Chelsea Kelly-Reif (owner)

## Context

CI-CD-STANDARD §11b forbids macOS runners (billed at 10x the Linux rate) on
per-push and pull-request CI. It allows them on a nightly schedule "if a
platform genuinely needs coverage".

GuideCore holds all of the app's logic: decoding, search, presentation (the
"does she die" wording), favourites and the refresh client. It uses Apple's
Foundation networking types. On Linux they live in `FoundationNetworking` and
behave differently. Measured on 2026-09-17: `swift test` in the
`swift:6.1-noble` image fails to compile (`URLSession`, `URLRequest` and
`URLSessionConfiguration` are unavailable). Porting would mean `#if
canImport(FoundationNetworking)` branches in shipping code and a URLProtocol
test double that behaves differently on each platform. The tests would then
pass on a platform the app never runs on.

A nightly-only run would let a change to the app's logic merge untested.

## Decision

- `ci.yml`'s `guidecore` job stays on macOS for pull requests.
- It runs only when a pull request touches `ios/`, `schema/`, the root
  `Makefile` or `ci.yml`. A `changes` job on Linux decides, and the rule
  fails closed: `guidecore` is skipped only on a clean "false", so a failed,
  cancelled or skipped `changes` job runs the tests.
- Every push to `main` and every manual dispatch runs it.
- `tests/test_workflow_policy.py` allows a macOS job on pull-request CI only
  when it is listed with this ADR and is scope-gated in that way.

## Consequences

- Pipeline-only and docs-only pull requests spend no macOS minutes.
- When `guidecore` is skipped it reports "skipped", which a required status
  check accepts. The fail-closed condition is what keeps that from becoming
  a way to skip the tests on a pull request that does touch the app.
- Revisit if GuideCore stops needing Apple networking types, or if the Actions
  budget rather than correctness becomes the binding constraint.
- Amended 2026-09-18 (#22, #28): the same job now also runs `make a11y`,
  the accessibility audit UI tests, in the iOS simulator. The scope rule is
  unchanged. The job moved from `macos-14` to `macos-26`: the audit's
  results depend on the iOS version, the test was proven on Xcode 26.6 with
  iOS 26.5, and the macOS 14 image is deprecated. A pull request that
  touches the app now uses more macOS minutes: the audit tests take about
  3 minutes locally, plus the simulator build. Reverting means
  dropping that one step and the `a11y` verify target, and moving the audit
  to a nightly schedule. A regression would then merge and fail a day
  later.
- Numbered 0012 in the one sequence shared with `docs/DECISIONS.md`
  (`docs/adr/0000`): 0005 is `docs/adr/0005`, and 0006–0011 are the launch
  decisions proposed in #33.
