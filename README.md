# queer-tv-guide (working name)

A no-account, no-telemetry iOS guide to queer TV: *does she die, is it worth
it, where to watch, when's the next episode.*

Chosen on 2026-09-13 from [moved to private strategy notes]. The
product's premise is that the App Store label **"Data Not Collected"** is
literally true: no accounts, no analytics, no third-party SDKs, favourites kept
on the device. That is a per-product choice under the portfolio's Data
Governance standard §4a (DG-20: the declared posture is "none").

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

## Not yet decided

The name. "Signal" (the research's placeholder) collides with Signal Messenger
and is not used anywhere here.
