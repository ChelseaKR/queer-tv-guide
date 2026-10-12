# Decisions

Numbering: 0001–0004, 0006–0011, 0013, 0015 and 0018 live here. 0005, 0012 and
0014 are ADRs in `docs/adr/`, so they are skipped here rather than
duplicated.

## 0001 — Native SwiftUI, not a web shell (2026-09-13)

**Decision.** The app is native SwiftUI over a bundled snapshot. No web view,
no JavaScript runtime, no Capacitor.

**Why.** The product's only differentiator that nobody else in this niche
delivers honestly is that "Data Not Collected" is literally true ([moved to private strategy notes]). A native app
with zero third-party SDKs and one plain GET for snapshot refresh is the
simplest thing that makes that claim auditable. It also answers App Review's
4.2 / 4.3(b) "repackaged website" risk directly — the research's top review
risk — because there is no website to repackage.

**Cost.** Chelsea's day-to-day stack is TypeScript and Python; Swift is a
second language for maintenance. Mitigated by keeping the app thin: all data
shaping lives in `pipeline/` (Python), the app renders a contract.

**Reversible.** Yes, while the app is small.

## 0002 — Data posture: none (2026-09-13)

Per DATA-GOVERNANCE-STANDARD §4a the declared analytics posture is **"none"**.
No analytics, no crash reporting, no telemetry, no accounts. Snapshot refresh
is a GET of a static file from infrastructure Chelsea controls with access
logging minimized and documented in the privacy notice. This is a per-product
choice; the portfolio's other products made the opposite one the same day.

## 0003 — Paid up front, one price (2026-09-13, provisional)

One-time purchase at the App Store, no IAP, no subscription: no StoreKit code,
no receipt validation, nothing to phone home about. [moved to private strategy notes]

## 0004 — Name: undecided

Owner's call. Do not use "Signal". **Resolved by 0006.**


## 0006 — Name: Queer Frame (2026-09-17)

**Decision.** The product is called **Queer Frame**. It is the home-screen
name (`CFBundleDisplayName`), the in-app name (`AppIdentity.displayName`),
the App Store name, and the name on the privacy and support pages.

**Not renamed.** The repository (`queer-tv-guide`), the bundle identifier
(`com.chelseakr.queertvguide`), `PRODUCT_NAME`, the Xcode targets and the
snapshot URL keep their working names. None of them is shown to a user,
and a bundle identifier cannot change once an app is registered. Resolves
0004. Never "Signal".

**Trademark screen (2026-10-02): no conflict found.** The official USPTO
trademark search (`https://tmsearch.uspto.gov/`, a word search typed into
the search box), the US App Store search API, and the Justia, uspto.report
and Trademarkia mirrors found no "QUEER FRAME" mark and no app by that
name. The nearest marks were QUEER EYE (live, classes 41 and 25, Scout
Productions) and the dead QUEER TV and QUEER TELEVISION. This is a screen,
not legal advice; an attorney's clearance search is the standard next step
for certainty.

## 0007 — The snapshot stays on GitHub Pages (2026-09-17)

**Decision.** `https://chelseakr.github.io/queer-tv-guide/snapshot.v1.json`
stays the app's one fetch URL.

**What users are told.** GitHub serves the data file and, by GitHub's own
documentation, logs the IP address of every request "for security
purposes". The privacy policy says so plainly, as does the About screen.
It also says the app itself collects nothing. The developer never receives
that log.

**Supersedes** the clause in 0002 that the file would come "from
infrastructure Chelsea controls with access logging minimized". The rest of
0002 (posture "none") stands. The App Store privacy label stays "Data Not
Collected": the developer collects nothing, and GitHub is a host, not a
partner whose code is in the app.

## 0008 — Ask LezWatch.TV in writing before shipping (2026-09-17)

**Superseded by 0013.** The request was never sent.

**Decision.** The app does not ship until LezWatch.TV gives written OK for
its use.

**Why.** Their terms grant free reuse of the data, but the same page scopes
the service to "any API based services to display data on your own site". A
paid iPhone app is not obviously "your own site". App Review 5.2.2 requires
being "specifically permitted", so the owner chose to ask rather than rely on
a reading.

**How.** The request is drafted in [moved to private strategy notes],
addressed to `contact@lezwatchtv.com` (from their Contact Us page). The owner
sends it; nothing in this repository sends mail. When they reply, save the
reply (dated) beside the draft and update the LezWatch row of
`docs/LICENSES-AND-ATTRIBUTION.md`.

This is a deliberate exception to that document's "nobody is contacted to
ask" rule, for this one question. The nightly mirror and the published
CC BY-SA snapshot continue as before, and the email tells LezWatch.TV about
both.

## 0009 — iPhone only (2026-09-17)

**Decision.** The app targets iPhone only (`TARGETED_DEVICE_FAMILY = 1`), not
iPad.

**Consequences.**
- App Store Connect no longer requires 13-inch iPad screenshots.
- iPads can still run the app in iPhone compatibility mode, and App Review
  may test it there (guideline 2.4.1), so it must still work at that size.
- The iPad-only orientation key is gone.

## 0010 — Support URL: a support page on the same Pages site (2026-09-17)

**Decision.** The App Store Support URL is
`https://chelseakr.github.io/queer-tv-guide/support.html`, published from
`docs/site/support.html` by the nightly workflow alongside `privacy.html`. It
uses the same host, so no new party is involved, and it is linked from the
About screen.

**Still owed.** A contact method on the page. Apple expects the Support URL
to offer "an easy way to contact you", and the page says one will be added
before release.

## 0011 — Price: $4.99, one-time (2026-09-17)

**Decision.** One-time purchase at **$4.99** (US), no IAP, no subscription.
[moved to private strategy notes] The Apple
Small Business Program rate (15%) applies.

## 0013 — Ship on LezWatch.TV's published terms, with full attribution (2026-09-17)

**Decision.** Queer Frame launches on LezWatch.TV's published terms of use
("You are welcome to use, reuse, and extend the data here for no fees … We
do ask you link back to us, or note us by name"), with every credit those
terms and TVmaze's CC BY-SA 4.0 ask for. **Supersedes 0008.** The permission
email drafted under 0008 was not sent, by owner decision, and nobody was
contacted.

**What "full attribution" means, and where each piece is checked:**
- Every show and character screen links to its LezWatch.TV page
  ("View on LezWatch.TV").
- The About screen names both sources with links, links each source's
  license or terms, and says "LezWatch.TV and TVmaze do not endorse this
  app".
- Wherever TVmaze data shows (a show's next episode, the Favorites list),
  a TVmaze link and the CC BY-SA 4.0 license link show with it.
- The published snapshot carries its CC BY-SA 4.0 license, notice and source
  credits, and so does its Pages index.

The full audit is in `docs/LICENSES-AND-ATTRIBUTION.md` ("Attribution
audit"). Removing a credit fails `swift test` or the pipeline tests (both
run in CI) and the UI tests.

**Risk accepted.** The terms scope themselves to "any API based services to
display data on your own site", and a paid app is arguably not that.
App Review 5.2.2 may ask for authorization. The answer is the dated terms
snapshot, the attribution, and the App Review note in `docs/APP-STORE.md`.

## 0015 — First App Store release: 1.0.0, United States only, 13+ (2026-10-02)

**Decision** (owner, 2026-10-02):
- **Version 1.0.0.** `MARKETING_VERSION` is 1.0.0 in
  `ios/Config/Shared.xcconfig`, the only place it is set, and the build
  number stays 1. `CHANGELOG.md` has a `## [1.0.0] - TBD` section that the
  release commit dates; the release workflow refuses it while it says TBD,
  and `make appstore` requires a section for the app's version.
- **Storefronts: the United States only**, so no Digital Services Act
  trader declaration.
- **Age rating: the draft answers in `docs/APP-STORE-LISTING.md` are
  confirmed**, expected to compute 13+.
- **Price confirmed:** $4.99, paid up front, no in-app purchase (0003,
  0011).
- **Support contact:** the support page lists `chelsea@chelseakr.com`
  (resolves the "still owed" line in 0010).

**Still open:** a trademark screen for "Queer Frame" (the owner's).
Update 2026-10-02: done, no conflict found (0006).

## 0018 — A native Android app with parity to iOS (proposed, 2026-10-12)

**Status: proposed.** The owner asked on 2026-10-12 for an Android app with
full parity with the iOS app. The code is on `feat/android-app`; the Play
listing, signing and the Data safety form are the owner's (no Play Console
action has been taken).

**Decision.** Queer Frame for Android is native Kotlin, Jetpack Compose and
Material 3, in `android/`, not a web shell (as 0001 for iOS). Package name
`com.chelseakr.queertvguide`, the iOS bundle id's stem (0006). Version 1.0.0
(code 1), as iOS. It reads the same snapshot from the same one URL (0007)
under the same contract (`schema/`), bundles the same published file, and
makes the same single conditional GET.

**Parity is tested, not asserted.** `android/core` ports GuideCore's data
layer (decoder rules, search and filters, every absence's wording, the
reminder planner, the widget's lines, the favorites backup format).
`ios/GuideCore/Tests/Fixtures/parity.golden.json` records GuideCore's output
for the shared test fixture in five time zones and at several clocks;
GuideCore's `ParityGoldenTests` fails if GuideCore changes it, and
`android/core`'s `ParityGoldenTest` fails if Kotlin says anything
different: the same reminders at the same instants with the same words, and
the same next-episode sentence in the viewer's time zone. An on-device test
repeats the date checks with Android's own formats. A backup file is the
same bytes on both platforms, so favorites move between them.

**Features.** Everything on main plus the `feat/ios-parity-fg` work: search
and filters (including "No recorded deaths"), show and character pages with
the closed "does she die" reveal, favorites with backup and restore, local
reminders (WorkManager and local notifications; no server push), the Up
Next home-screen widget (Glance), About with both sources' attribution and
the "do not endorse" line, refresh states with Try again, a five-page
first-run pager, `queerframe://show/<id>` links, a tablet list-detail
layout, haptics, TalkBack, font scale and contrast-checked colors, and a
"Rate Queer Frame" row that opens the Play listing.

**Privacy (0002 stands).** No analytics, crash reporting, ads, accounts or
Play services SDK; the only libraries are AndroidX and Kotlin's.
`SourceGuardTest` holds the tree to one network call site, one host, three
permissions (internet, network state, notifications) and no tracking
library. Favorites, the first-run flag and the reminder switch move only in
a device-to-device transfer, never to cloud backup. The Data safety answer
is "No data collected" and "No data shared"; GitHub's request log (0007) is
stated in the privacy policy as on iOS.

**Distribution.** Paid on Google Play at the US price equivalent of $4.99,
no in-app purchase, no ads, United States only (0011, 0015).

**Not included.** Play's In-App Review prompt waits on 0017: if the owner
accepts the iOS rating prompt, the same `ReviewPromptPolicy` can be ported;
until then the About row is the only ask. Android App Links (verified
https links) wait on the owner deciding on universal links.

**CI.** The `android` job runs `make android` on Linux on every run; the
emulator tests run locally (`make -C android instrumented`).

