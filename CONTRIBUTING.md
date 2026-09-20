# Contributing

One maintainer, public repository. These notes are for her, for future
collaborators, and for the coding agents that work here.

## The one local gate

```sh
make verify
```

It runs every merge-blocking check CI runs, as the same commands (the root
`Makefile`): the pipeline's lock check, lint, format, types, tests with the
85% branch-coverage floor and wheel build; GuideCore's Swift tests; the
repository policy tests; workflow SAST (zizmor); secret scanning (gitleaks,
history and tree); SAST (semgrep); and dependency CVE scans (pip-audit,
osv-scanner). If `make verify` passes locally, CI should too; if it does not,
that is a bug in one of them.

Install the pre-commit hooks once per clone for faster feedback (gitleaks on
the staged diff, ruff on pipeline files, mypy before a push):

```sh
pre-commit install --hook-type pre-commit --hook-type pre-push
```

## Pull requests

- Every change goes through a pull request into `main`; no direct pushes.
- The PR template carries the Definition of Done (`DEFINITION_OF_DONE.md`).
  Tick what applies, and say why for what does not.
- Commit subjects are lowercase conventional commits (`fix(pipeline): …`,
  `docs: …`). Stage files by name; never `git add -A`.
- Update `CHANGELOG.md` under `[Unreleased]` in the same PR as a user-visible
  change.
- A decision that is expensive to reverse (a data source, a license, a
  platform, a guardrail, declaring a standard N/A) gets an ADR in
  `docs/adr/` (see `docs/adr/0000-record-architecture-decisions.md`).

## Standards

This repository is held to the portfolio standards pinned in `docs/standards/`
(read those, not a memory of them). The README's **Standards Conformance**
table says which apply and which gaps are open, each linked to its issue.
Never edit `docs/standards/` by hand: it is a verbatim copy of a release, and
`tests/test_vendored_standards.py` fails on any edit.

## Product guardrails (do not cross)

- No accounts, analytics, crash reporting, telemetry or third-party SDKs in
  the app (`docs/DECISIONS.md` 0002). The app talks to one host.
- Licenses before bytes: a data source is used only after its terms have been
  read, quoted and snapshotted (`docs/LICENSES-AND-ATTRIBUTION.md`). Nobody
  contacts the sources.
- A death LezWatch has not recorded is shown as not recorded, never as "no".
- The product name is Queer Frame (`docs/DECISIONS.md` 0006); never use "Signal".
