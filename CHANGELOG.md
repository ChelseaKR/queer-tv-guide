# Changelog

All notable changes to this project are recorded here, in the
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) format. The
project will use [Semantic Versioning](https://semver.org/) for the app
(`MARKETING_VERSION`) and the pipeline (`pipeline/pyproject.toml`); the
snapshot contract versions itself separately (`schema/snapshot.v1.json`).

Nothing has been released yet. Entries describe what a user of the app, or a
consumer of the published snapshot, would notice.

## [Unreleased]

### Added

- A nightly pipeline mirrors LezWatch.TV (shows, characters, deaths, tropes,
  where-to-watch links) and TVmaze (episode schedules) into one attributed,
  schema-validated snapshot file, published at a single static URL, with a
  coverage report of what each source did and did not provide (#1).
- The iOS app: search and browse with filters, show and character screens,
  "does she die?" behind a tap-to-reveal, favourites kept only on the device,
  and a data-as-of footer. It works offline from the bundled snapshot and
  refreshes with one HTTPS request (#2).
- A placeholder app icon (#3, #5).
- A pinned copy of the portfolio standards (v2.0.0) in `docs/standards/` (#7).
- "Do any queer characters die?" on every show, behind the same closed-by-default
  reveal as the character answer. It is never "nobody dies", and it shows both
  numbers where LezWatch.TV's own tally disagrees with its character records (#15).
- A privacy policy page and an in-app link to it; iPad orientations; the
  export-compliance declaration (#17).
- Every show and character screen links to its LezWatch.TV page. A show's
  next episode and the Favourites list credit TVmaze with a link and its
  CC BY-SA 4.0 licence. About states that neither source endorses the app.
  The snapshot's Pages index shows the licence and every source credit with
  links.
- The app says how old its data is ("Data as of … (5 hours ago)"). Once the
  data is more than 48 hours old, or its age cannot be known because it is
  dated later than the device's clock, Search and Favourites open with a
  plain warning that it is out of date (#25).
- Favourites can be backed up without an account: the … menu on Favourites
  exports a JSON file through the share sheet and imports one you pick.
  Import checks the file and skips shows or characters that are not in the
  data, saying how many (#25).
- A staleness alarm for the published snapshot: `freshness.yml` checks it
  every 6 hours and opens an `incident` issue when it is more than 30 hours
  old, past the 48-hour SLA, unreadable, or the last nightly run failed
  (#25).
- A short first-run screen, skippable at once, on how spoilers stay closed,
  what "Not recorded" means, where the data comes from (LezWatch.TV and
  TVmaze, neither endorsing the app) and what the app does not collect.
  About opens it again.
- A Share button on every show, which hands its LezWatch.TV page (with any
  query or fragment removed) to the system share sheet.
- Pull to refresh on Favourites and About, as on Search, and light haptics
  when a star is toggled or a reveal is opened.
- Search filters for where to watch (particular sites), tropes and trigger
  warnings, on one filter screen that counts the shows they leave. Tropes
  that give away a death are never offered as a filter.

### Changed

- VoiceOver reads a show's years, seasons and networks as one stop, in words
  ("1995 to 2001") rather than punctuation, and each show's and character's
  name is a heading. With Reduce Motion on, the app's own animations are
  dropped. The accessibility audit now covers Search, its results, the
  character screen, Favourites and About at the largest text size too.
- Search no longer needs punctuation or word order: "greys anatomy" finds
  Grey’s Anatomy and "xena warrior" finds Xena: Warrior Princess (both found
  nothing before). Results are worked out off the main thread, and an empty
  result says whether the filters caused it, with a button to clear them.
- A show's worth-it explanation is collapsed behind "Why? (may contain
  spoilers)", because 61 of them name a death outright.
- The app ships the real published snapshot, checksum-verified, instead of the
  test fixture, and loads it off the main thread (#10).
- Trope tags that give away a death ("Dead Queers", "Bury Your Queers") no
  longer appear above the reveal (#15).
- The App Store checklist now requires swapping the test fixture for the real
  snapshot before any archive (#4).

### Fixed

- VoiceOver now reads a show's network in search results, which it had been
  skipping (#6).
- Text and accent colours meet 4.5:1 contrast. Empty states and show rows no
  longer clip or truncate at large Dynamic Type sizes. VoiceOver moves to an
  answer when it is revealed. A next-episode date that has passed says so
  instead of posing as upcoming (#15).
- Show and character descriptions no longer contain HTML tags or entities;
  a season count LezWatch never filled in reads "not recorded" instead of
  "0 seasons" (#8).
- The saved copy of LezWatch.TV's robots.txt, kept as licence evidence,
  matches the bytes as fetched again, and CI checks every saved terms page
  against its recorded checksum (#9).
- An unrecorded death now reads "Not recorded. …" on the character and show
  screens. It used to open with "No death is recorded", and a VoiceOver user
  who moved on after the first word heard "No". Section headings on About,
  and text scrolling toward the tab bar, now meet 4.5:1 contrast, and the
  About rows scale with Dynamic Type (#22, #28).
