# App Store listing, review notes, and the path to TestFlight

Everything here is a draft for the owner to approve, edit, or reject — nothing
in this file has been submitted anywhere. `ios/` has no App Store Connect
access and this session did not attempt any.

## 1. Listing draft

| Field | Draft | Source |
|---|---|---|
| Name | **TBD** (DECISIONS 0004). Placeholder used throughout the code: `AppIdentity.displayName` in `ios/QueerTVGuide/App/AppIdentity.swift`. Never "Signal" — collides with the messaging app. | DECISIONS 0004 |
| Subtitle | "Does she die? Is it worth it?" (29 characters, fits the 30-char subtitle limit) | research §6 rank 1 |
| Category | Entertainment (primary); no secondary category needed | — |
| Price | One-time purchase, no IAP, no subscription. [moved to private strategy notes] | DECISIONS 0003 |
| Age rating | **12+** if declared at all — draft answer below | research §3.1 (Sapphic Signal's own rating), §7 |
| Privacy label | **"Data Not Collected"** for every category — this is the product's whole premise and is literally true for this build (see §3) | DECISIONS 0002, research §4.3 |

### Description (draft)

> A no-account, no-telemetry guide to queer TV. Search a show and see: is it
> worth watching, does a queer character die (you choose when to find out),
> what the tropes are, and where to stream it. Browse "no recorded deaths,"
> filter by rating, favourite what you're following — all stored only on
> this device. Data is a nightly, attributed mirror of LezWatch.TV and
> TVmaze; the app works offline and tells you exactly how current its data
> is. No account. No analytics. No ads. No third-party SDKs. The only thing
> this app ever asks for is the data file itself.

### Keywords (draft, adult branches excluded per research §7 / 1.1.4)

`queer tv, lesbian tv, sapphic, lgbtq shows, bury your gays, where to watch,
queer characters, tv tracker, does she die, lgbtq representation`

Deliberately excluded: any keyword from TMDB's `lesbian-fetish` /
`queer-porn` / `lesbian-rape` branches (research §3.1, §7) — this app doesn't
use TMDB at all (it's LezWatch + TVmaze only, research §6 rank 1), and none
of those terms describe this product regardless.

### Age rating questionnaire (draft answers)

Apple's current age-rating flow is a set of content-frequency questions
(none/infrequent/frequent), not free text. Draft answers, all **"None"**
unless noted:

- Sexual content or nudity: **None.** The app discusses relationships and
  queer identity (explicitly permitted per research §7's read of 1.1.1) but
  shows no sexual content and carries no user-generated content of any kind.
- Mature/suggestive themes: **Infrequent/Mild** — some shows' `triggers`
  field surfaces things like "Violence" from the source data; the app
  states these as content notes, not depicts them.
- Violence: **Infrequent/Mild**, same basis.
- Horror/fear themes: **None.**
- Gambling, alcohol/drugs, profanity: **None** (not in the data model at
  all).
- Unrestricted web access: **No** — the app never opens a browser in-app; it
  hands URLs to the system via `openURL`, which is not "web access" in
  Apple's sense (no `WKWebView`, no `SFSafariViewController` — enforced by
  `SourceTreeGuardTests.testNoOtherNetworkOrWebPrimitives`).
- Expected result: **12+**, matching Sapphic Signal's own rating (research
  §3.1) and comfortably below Groove/qcal/QLIST's 17+/18+.

### Screenshots plan (not produced this session — no device/App Store Connect access)

1. Search screen with a few bundled shows visible and the filter menu open.
2. A show detail screen: worth-it/quality, where-to-watch links, next
   episode.
3. A character detail screen with the spoiler reveal control **shown
   closed** (never a screenshot with a death spoiler already revealed).
4. Favourites screen.
5. About & Privacy screen, since "Data Not Collected" being checkable is the
   product's differentiator (research §4.3) — this screen is evidence, not
   boilerplate.

All five map onto existing screens (§4 below); none require new UI.

## 2. Privacy label

"Data Not Collected" for every category Apple's privacy label asks about.
This is true of the build in this PR:

- No account, ever (`AppModel` never asks for identity; `FavouritesStore` is
  local `UserDefaults`, never synced).
- No analytics, no crash reporter, no third-party SDK of any kind — enforced
  by `SourceTreeGuardTests.testNoRemotePackagesOrPods` and
  `testImportsAreSystemOrOurs` (only `Foundation`/`SwiftUI`/`Observation`/
  `UIKit`/our own modules/`XCTest` may be imported anywhere in `ios/`).
- Exactly one network call exists in the whole app: a conditional GET of the
  published snapshot file, no cookies, no credentials, no custom headers
  beyond `Accept`/`If-None-Match` — enforced by
  `SnapshotRefresherTests.testConfigurationHasNoCookiesNoCacheNoCredentials`
  and `.testExactlyOneRequestPerRefreshAndNoCookieHeader`, and by
  `SourceTreeGuardTests.testOnlyTheSnapshotHostAppearsInSource` (no host
  other than the snapshot host appears anywhere in `ios/`).
- `PrivacyInfo.xcprivacy` declares `NSPrivacyTracking = false`, an empty
  `NSPrivacyTrackingDomains`, an empty `NSPrivacyCollectedDataTypes`, and
  only the required-reason API entries the code actually uses (UserDefaults,
  reason `CA92.1`) — checked against the real source by
  `SourceTreeGuardTests.testPrivacyManifestDeclaresExactlyTheRequiredReasonAPIsUsed`,
  which fails if the code starts using an API category the manifest doesn't
  declare, or the manifest claims one the code doesn't use.

## 3. App Review clauses (research §7) and how this build satisfies each

Quotes are from research §7, itself quoting
https://developer.apple.com/app-store/review/guidelines/ (fetched
2026-09-13).

- **5.2.2 Third-party terms.** *"If your app uses, accesses, monetizes
  access to, or displays content from a third-party service, ensure that
  you are specifically permitted to do so under the service's terms of
  use."* LezWatch.TV's published terms are free-reuse with a link-back
  request (schema/README.md, research §2.2); the app links every show and
  character back to its `source_url` (`ShowDetailView`/`CharacterDetailView`
  headers use the show/character page URL from the snapshot) and shows the
  attribution text and licence on the About screen
  (`AboutView`/`Snapshot.attribution`). Owner action: attach the ToS text and
  a TVmaze attribution screenshot to the App Review notes (§5 below).
- **4.2 Minimum functionality / 4.2.2 "not primarily a collection of
  links."** *"Your app should include features, content, and UI that
  elevate it beyond a repackaged website."* This app bundles the dataset
  offline, adds a spoiler-gated death reveal LezWatch's own site doesn't
  gate, adds filters (worth-it, no-recorded-deaths, has-a-watch-link) and
  local favourites, and works with no network at all after first launch.
  The where-to-watch links are one section of a multi-section detail screen,
  not the whole app.
- **4.3(b) Spam / "indistinguishable from what's already widely
  available."** Sapphic Signal exists in this niche (research §3.1). The
  distinctions research §6 names — offline-first, deaths/tropes/worth-it
  data, no account, no analytics, a privacy label that's actually true
  ([moved to private strategy notes]) — are all visible on screen one: the About screen states
  the posture in the app's own words, and the Search screen's filters
  surface the deaths/tropes data Sapphic Signal doesn't have.
- **1.1.1 / 1.1.4 Content.** *"Overtly sexual or pornographic material"* is
  banned; discussing sexual orientation is explicitly permitted. This app's
  entire data model is LezWatch + TVmaze (research §6 rank 1) — it never
  touches TMDB's `lesbian-fetish`/`queer-porn`/`lesbian-rape` keyword
  branches research §7 flags, because it doesn't use TMDB at all. Keywords
  above exclude them regardless.
- **1.2 User-generated content.** None shipped: no comments, ratings,
  reviews, or submissions anywhere in the app (confirmed by reading every
  screen in `ios/QueerTVGuide/Views`). Favourites are a private, local list,
  not content anyone else sees.
- **5.1.1 Data collection / no login.** *"If your app doesn't include
  significant account-based features, let people use it without a login."*
  There is no login anywhere in this app — no screen asks for identity of
  any kind. The privacy policy link is still required even for "Data Not
  Collected" (owner action: publish one; the About screen's posture text can
  be the policy's substance).
- **5.1.2 / App Tracking Transparency.** No SDK exists to prompt for, and
  none is added (DECISIONS 0002; enforced by the import/host guard tests
  above). A plain outbound link to a streaming service is not "tracking" per
  Apple's own definition (research §7).
- **3.1.1 In-app purchase.** *"Apps may not use their own mechanisms to
  unlock content."* This app has nothing to unlock — no StoreKit code at
  all (DECISIONS 0003: paid up front, one non-consumable purchase at the
  App Store level, not an in-app mechanism). Owner action: configure the
  paid-app price tier in App Store Connect; no code change is needed.
- **5.2.3 Audio/video.** *"Never play or download from the services
  linked."* Where-to-watch links open via `openURL` (`ShowDetailView`) —
  the system hands off to Safari/the target app. There is no video player,
  no embedded web view, and no download of any media anywhere in `ios/`
  (`SourceTreeGuardTests.testNoOtherNetworkOrWebPrimitives` bans
  `WKWebView`/`SFSafariViewController` as well as lower-level networking
  primitives).
- **2.3.1 Metadata / Notes for Review.** Draft review note (owner to paste
  into App Store Connect): *"This app makes exactly one network request: an
  HTTPS GET of a static JSON file published by [snapshot URL], sent when the
  app opens or the user pulls to refresh, to check for a newer dataset
  (conditional on an ETag; a 304 response means no data transfers). No
  accounts, no analytics, no third-party SDKs, no tracking. The bundled
  snapshot lets the app work fully offline from first launch. Data is a
  nightly mirror of LezWatch.TV (https://lezwatchtv.com/) and TVmaze
  (https://www.tvmaze.com/), attributed on the About screen, per each
  source's published reuse terms."*
- **Storefront availability.** Research §8 could not verify country-level
  restriction history for LGBTQ content on the App Store this session.
  Owner decision, not a code question: research §7 suggests limiting the
  first release to storefronts where the content is uncontroversial rather
  than treating this as a review risk to engineer around.

## 4. Screens this build ships (2 of 2 planned before this PR / 5 total)

The brief's five screens, all present in `ios/QueerTVGuide/Views`:

1. **Search** (`SearchView.swift`) — search across shows and characters,
   worth-it/no-recorded-deaths/has-a-watch-link filters, pull to refresh.
2. **Show detail** (`ShowDetailView.swift`) — worth-it/quality/realness/
   screentime, tropes, trigger warnings, characters, where-to-watch as
   `openURL` links, next episode (schedule-known vs schedule-unknown
   distinguished), plot notes behind a spoiler disclosure, attribution
   footer with `generated_at`.
3. **Character detail** (`CharacterDetailView.swift`) — identity fields,
   "does she die" behind `SpoilerReveal` (closed by default), shows the
   character appears in.
4. **Favourites** (`FavouritesView.swift`) — local list, swipe to remove,
   empty state explains the local-only posture.
5. **About & Privacy** (`AboutView.swift`) — the posture statement, every
   `attribution` entry from the snapshot, the licence notice, coverage
   numbers, and the current snapshot's `generated_at`/origin.

## 5. Owner steps to a TestFlight build

Everything through "Archive" runs with no App Store Connect access, which
this session doesn't have. Steps that touch Apple's servers or the keychain
are marked **(owner-run)** — this session could not run them and did not
attempt to.

```sh
# 0. From ios/. Regenerate the project if project.yml changed.
cd ios
xcodegen generate

# 1. Register the explicit App ID (owner-run; needs an authenticated
#    App Store Connect / Developer Portal session). Bundle id is the
#    working id below until DECISIONS 0004 settles a name (README: "it is
#    renamed with the app").
#    Team ID: 6X5YH93QNM (never ACKGM9XK9V — that is the enrollment id, not
#    the Team ID; see docs/DECISIONS.md and the portfolio's fg-ios-app-store-path note).
xcrun altool --list-apps -u "<owner apple id>" -p "<app-specific password>"
#    …or via the App Store Connect / Developer Portal web UI:
#    App ID: com.chelseakr.queertvguide, capabilities: none (no push, no
#    iCloud, no App Groups — this app doesn't use any).

# 2. Confirm a valid Distribution certificate + provisioning profile exist
#    for Team 6X5YH93QNM (owner-run; System Settings/Keychain Access work,
#    or Xcode's Settings > Accounts > Manage Certificates).
security find-identity -v -p codesigning

# 3. Archive (device build; needs the profile from step 1-2 present
#    locally — this session's simulator-only environment cannot run this
#    step to completion without them).
xcodebuild -project QueerTVGuide.xcodeproj -scheme QueerTVGuide \
  -configuration Release -destination 'generic/platform=iOS' \
  -archivePath build/QueerTVGuide.xcarchive \
  DEVELOPMENT_TEAM=6X5YH93QNM \
  archive

# 4. Validate the archive against App Store Connect before uploading.
xcodebuild -exportArchive \
  -archivePath build/QueerTVGuide.xcarchive \
  -exportPath build/export \
  -exportOptionsPlist ExportOptions.plist \
  # ExportOptions.plist (owner creates once): method=app-store-connect,
  # teamID=6X5YH93QNM, signingStyle=automatic.

# 5. Upload to App Store Connect (owner-run; needs an app-specific
#    password or API key).
xcrun altool --validate-app -f build/export/QueerTVGuide.ipa \
  -t ios -u "<owner apple id>" -p "<app-specific password>"
xcrun altool --upload-app -f build/export/QueerTVGuide.ipa \
  -t ios -u "<owner apple id>" -p "<app-specific password>"

# 6. In App Store Connect (owner-run, web UI): attach the build to a
#    TestFlight group, fill in the "Notes for Review" text from §3 above,
#    complete the privacy label as "Data Not Collected" per §2, set the
#    price tier per §1, and submit for internal testing.
```

Nothing above installs, signs, or uploads anything from this session — no
`xcrun altool`/`xcodebuild archive`/`-exportArchive` command in this section
was run here; they are the ordered commands for the owner to run with
Apple credentials this environment doesn't have.
