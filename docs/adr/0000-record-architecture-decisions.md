# 0000. Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-09-17
- **Deciders:** Chelsea Kelly-Reif (owner)

## Context

DOCUMENTATION-STANDARD §3 asks every repository past `Spec` status for an ADR
log: `docs/adr/NNNN-kebab-title.md`, MADR format, numbered, append-only.

This repository already records decisions in `docs/DECISIONS.md`: numbered
entries such as 0001 (native SwiftUI), 0002 (data posture "none") and 0004
(name). Code and docs cite them ("DECISIONS 0004"), and product and launch
decisions keep being added there.

## Decision

- **One number sequence across both places.** A decision is numbered once,
  whether it is written as an entry in `docs/DECISIONS.md` or as a file here.
  Before taking a number, check both, and take the next one unused in either.
  A number is never reused.
- **Where a decision goes.** Product and launch decisions can stay in
  `docs/DECISIONS.md`. Engineering, standards and guardrail decisions (a
  platform or dependency, a CI exception, a security or privacy boundary, a
  quality threshold, declaring a standard N/A) get a file here, from
  `docs/adr/template.md`.
- **Nothing is renumbered or moved.** Existing citations stay valid.
- **Status** is exactly one of `Proposed`, `Accepted`, `Superseded by NNNN`,
  `Deprecated`. An accepted decision is never edited except to mark it
  superseded; a change is a new, later decision.

## Consequences

- "Decision 0005" means exactly one thing in this repository, wherever it is
  written down.
- Two places to look instead of one. The README's Standards Conformance
  section points at both.
- Note on 0002: it cites DATA-GOVERNANCE-STANDARD §4a / DG-20, which are
  proposed in portfolio-standards#168 and are not in the pinned v2.0.0 copy.
  The decision stands on its own; the citation becomes accurate when that
  standard is released and re-vendored.
