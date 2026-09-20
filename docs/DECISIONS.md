# Decisions

Numbering: 0001–0004, 0006–0011 and 0013 live here. 0005 and 0012 are
ADRs in `docs/adr/`, so they are skipped here rather than duplicated.

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

