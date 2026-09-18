# Queer Frame

(Repository and bundle id keep the working name `queer-tv-guide`; DECISIONS 0006.)

A no-account, no-telemetry iOS guide to queer TV: *does she die, is it worth
it, where to watch, when's the next episode.*

**Status:** In build. Not yet on the App Store; private repository.

Chosen on 2026-09-13 from [moved to private strategy notes]. The
product's premise is that the App Store label **"Data Not Collected"** is
literally true: no accounts, no analytics, no third-party SDKs, favourites kept
on the device. That is a per-product choice, recorded as the analytics posture
"none" in `docs/DECISIONS.md` 0002. (The portfolio control it cites, DG-20 in
DATA-GOVERNANCE-STANDARD §4a, is proposed in portfolio-standards#168 and is not
yet in a released standard; the pinned v2.0.0 copy in `docs/standards/` has no
§4a.)

## Quickstart

```sh
# Every merge-blocking gate, run the way CI runs it.
# Needs uv, git and curl; the Swift lane needs macOS with Xcode.
make verify

# The Python pipeline alone: lint, types, the offline test suite, a wheel build.
make -C pipeline verify

# The app's logic package, then the app with its unit and UI tests in the simulator.
# (Both first fetch the published snapshot the app bundles, checksum-verified.)
make -C ios package-test
make -C ios test
```

Building a real snapshot contacts LezWatch.TV and TVmaze, at the pace their
terms allow; see `pipeline/README.md` before running `qtv fetch`.

## Standards Conformance

Held to the portfolio standards pinned in `docs/standards/` (v2.0.0). Every
gap row names the open issue that tracks it. `docs/ROADMAP.md` carries the
per-control ledger, `docs/capabilities.md` what the project may claim, and
decisions live in `docs/DECISIONS.md` and `docs/adr/` (one number sequence,
`docs/adr/0000`).

| Standard | State |
|----------|-------|
| Responsible-Tech Framework | Applies — gap tracked in #24 (audits drafted in `docs/RESPONSIBLE-TECH-AUDITS.md`; owner sign-offs pending) |
| Code Quality | Applies — gap tracked in #20 |
| Security & Supply-Chain | Applies — gap tracked in #19 |
| CI/CD | Applies — gap tracked in #18 |
| Release & Versioning | Applies — gap tracked in #21 (release-producing: the App Store app and the nightly snapshot; nothing released yet) |
| Observability | Applies — gap tracked in #19 (pipeline: Tier C; the app emits no telemetry by design, DECISIONS 0002; the no-credentials-in-logs gate, OBS-11, is part of #19) |
| Performance | Applies — gap tracked in #36 (scoped conservatively by the portfolio registry; the only hosted route is a static data file and a one-page index, so an N/A is proposed there) |
| Accessibility | Applies — gap tracked in #22 (native app: automated audit, human VoiceOver walkthrough pending; HTML: Pages and privacy pages) |
| Internationalization | Applies — gap tracked in #23 (English-only today, by design) |
| AI Evaluation | N/A — no model, prompt or retrieval component; the product uses no LLM |
| Documentation | Applies — gap tracked in #26 |
| Quality & Metrics | Applies — `DEFINITION_OF_DONE.md`, the PR checklist, and the metrics ledger in `docs/ROADMAP.md` |
| AI Development Measurement | Applies — no per-repository gate; delivery and quality-debt metrics come from the portfolio's `delivery_metrics.py` and are never used as gates |
| Incident Response | Applies — gap tracked in #27 (no incidents to date) |
| Data Governance | Applies — gap tracked in #25 (L1 public data; actor sexuality and gender are never stored) |

CITATION.cff covers the published snapshot dataset (CC BY-SA 4.0). The code
itself has no licence yet: that is an owner decision.


## Shape

- `pipeline/` — Python. Mirrors LezWatch.TV (characters, shows, deaths,
  worth-it/quality, tropes, where-to-watch links) and TVmaze (episode schedule)
  into a versioned, attributed, offline-usable snapshot. Publishes it as a
  static artifact. Never touches a user.
- `schema/` — the snapshot contract the app consumes. Owned by the pipeline;
  versioned.
- `ios/` — SwiftUI. Reads the bundled snapshot; refreshes it with one plain GET
  of a static file; stores favourites locally; links out to watch, never plays.
- `docs/` — research, decisions, licences and attributions, the App Store
  checklist.

## Not yet cleared to ship

A support contact method on the support page (`TODO(owner)`, DECISIONS
0010). `make -C ios presubmit-check` fails until it is added, and CI warns.
The rest of the submission checklist is `docs/APP-STORE.md` "Before
submission". Data use is settled: the app ships on LezWatch.TV's published
terms with full attribution (DECISIONS 0013). The name is **Queer Frame**
(DECISIONS 0006). Never "Signal", which collides with Signal Messenger.
