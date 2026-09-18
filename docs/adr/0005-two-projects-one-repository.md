# 0005. Two projects in one repository; Python config stays in pipeline/

- **Status:** Proposed
- **Date:** 2026-09-17
- **Deciders:** Chelsea Kelly-Reif (owner)

## Context

The repository holds two projects that ship together: `pipeline/`, a Python
package that builds the snapshot, and `ios/`, the SwiftUI app and its
`GuideCore` Swift package. `schema/` is the contract between them.

CODE-QUALITY-STANDARD §4 asks for exactly one root `pyproject.toml`
(CQ-25), `tests/` at the repository root (CQ-24), and forbids
monorepo-style nesting unless an ADR declares it (CQ-26). CI-CD-STANDARD §9
allows either hoisting a nested project's config to the root or exposing
the nested project through a root Makefile.

Hoisting `pipeline/pyproject.toml` and `uv.lock` to the root would put
Python packaging config above an iOS app that has nothing to do with it,
and would make every `uv` command operate on a root that is mostly Swift.

## Decision

- Keep the two projects in their own directories, each with its own build
  files: `pipeline/pyproject.toml` + `pipeline/uv.lock` for Python (the only
  Python project, so still exactly one Python config), and
  `ios/project.yml` + `ios/GuideCore/Package.swift` for Swift.
- Expose both from the root through the root `Makefile`: `make pipeline` and
  `make guidecore` are part of `make verify`, which is what CI runs.
- `pipeline/tests/` holds the pipeline's tests. The root `tests/` holds only
  repository-level policy tests (workflows, CI parity, vendored standards,
  scanner configuration).
- The pipeline's code-quality floors (ruff rule set and complexity 10, mypy
  `--strict`, pytest strict flags, 85% branch coverage, `uv lock --check`)
  are declared in `pipeline/pyproject.toml` and enforced by
  `pipeline/Makefile verify`.

## Consequences

- The portfolio's `conformance_check.py` reads Python controls only from a
  root `pyproject.toml`, so it does not score this repository's coverage
  floor, lockfile or Python version pin. Those controls are still enforced,
  by `make pipeline`; this ADR is the record of where to find them.
- A second Python project, or a move of GuideCore's logic into Python,
  would reopen this decision.
- Numbered in the one sequence shared with `docs/DECISIONS.md`
  (`docs/adr/0000`): 0001–0004 are recorded there.
