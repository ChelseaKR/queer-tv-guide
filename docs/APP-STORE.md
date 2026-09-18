# App Store listing, review notes, and the path to TestFlight

Everything here is a draft for the owner to approve, edit, or reject — nothing
in this file has been submitted anywhere. `ios/` has no App Store Connect
access and this session did not attempt any.

## 1. Listing draft

The owner's decisions of 2026-09-17 (DECISIONS 0006–0011, 0013) settled name,
devices, support URL and price. The fields App Store Connect takes as text
are in **`docs/app-store-listing.json`**, the one copy to paste from.
`AppStoreReadinessTests` enforces Apple's limits on it and keeps it in step
with the build: name = display name, iPhone-only = device family, URLs on
the snapshot host with pages that exist.

Character counts, recounted 2026-09-17:

| Field | Value | Count / limit | Source |
|---|---|---|---|
| Name | **Queer Frame** | 11 / 30 | DECISIONS 0006 |
| Subtitle | "Does she die? Is it worth it?" | 29 / 30 | research §6 rank 1 |
| Promotional text | see the JSON | 141 / 170 | — |
| Keywords | see §Keywords below | 97 / 100 | — |
| Description | see the JSON | 1,139 / 4,000 | — |
| Category | Entertainment (primary); no secondary | — | — |
| Price | **$4.99**, one-time. No IAP, no subscription. Apple Small Business Program (15%). | — | DECISIONS 0003, 0011 |
| Devices | **iPhone only** (`TARGETED_DEVICE_FAMILY = 1`). Screenshots: iPhone only (6.9" set). iPads can still run it in iPhone compatibility mode, and App Review may test it there (2.4.1). | — | DECISIONS 0009 |
| Age rating | **13+ expected**, computed by App Store Connect from the questionnaire below. Apple's current tiers are 4+, 9+, 13+, 16+, 18+; "12+" no longer exists (checked 2026-09-17). | — | Apple, research §7 |
| Privacy label | **"Data Not Collected"** for every category (see §2) | — | DECISIONS 0002, 0007 |
| Privacy Policy URL | `https://chelseakr.github.io/queer-tv-guide/privacy.html`, from `docs/site/privacy.html` | — | DECISIONS 0007 |
| Support URL | `https://chelseakr.github.io/queer-tv-guide/support.html`, from `docs/site/support.html`. Both are published by the nightly workflow and linked from the About screen. **Still owed: a contact method on the page.** | — | DECISIONS 0010 |
| Export compliance | "No" to non-exempt encryption, declared in the build (`ITSAppUsesNonExemptEncryption = NO`). | — | — |

### Before submission (hard gates)

1. **A support contact method** on `docs/site/support.html`, currently a
   `TODO(owner)` marker (DECISIONS 0010). `make -C ios presubmit-check`
   fails until it is resolved, and CI puts a warning on every run. The owner
   has deferred it; nothing invents an address.
2. `make -C ios bundle-snapshot` then `make -C ios test` on the build you
   archive.
3. Screenshots from that build: `make -C ios screenshots` (§Screenshots).
4. The owner steps in §6.

Data use is settled: the app ships on LezWatch.TV's published terms with full
attribution (DECISIONS 0013; the permission request of 0008 was not sent).

### Description

In `docs/app-store-listing.json`. It names the sources, states the spoiler
reveal, and says "no death is recorded" never becomes "survives".

Copy rule: no "only", "first" or other uniqueness claims about the market
(the space has TV Time — shut down 2026-07-15 — Does the Dog Die, Serializd,
TVmaze and Sapphic Signal). Claims about the app's own behaviour ("no
account") are fine because they are checkable.

### Keywords (draft, adult branches excluded per research §7 / 1.1.4)

App Store Connect allows **100 characters**, commas included; spaces after
commas waste characters, and words already in the name or subtitle add
nothing. The earlier draft was 140 characters. This one is 97:

`lesbian,sapphic,lgbtq,bury your gays,where to watch,character,tracker,episode,trans,nonbinary,wlw`

Not included: "LezWatch" and "TVmaze" (credit them in the description, not
as search terms), competitor app names (Apple forbids them), and anything
from the adult branches below.

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
- Expected result: **13+**, Apple's nearest current tier to Sapphic
  Signal's older 12+ rating (research §3.1), and below Groove/qcal/QLIST's
  17+/18+. App Store Connect computes it from these answers.

### Screenshots (iPhone 6.9", 1320 × 2868, real data)

Produced by `make -C ios screenshots`. It creates a throwaway iPhone 17 Pro
Max simulator, sets a 9:41 status bar, and runs `AppStoreScreenshotTests` on
the real bundled snapshot. The test refuses the fixture, and every shot
asserts that no death answer is on screen. The shots are then exported:

1. `docs/app-store/screenshots/01-browse.png`: Search, browsing shows with a
   where-to-watch link.
2. `docs/app-store/screenshots/02-show-reveal-closed.png`: a show (Abbott
   Elementary) with "Do any queer characters die?" **closed** and its
   worth-it explanation collapsed.
3. `docs/app-store/screenshots/03-where-to-watch.png`: the same show's
   where-to-watch links, with the LezWatch.TV and TVmaze credits.
4. `docs/app-store/screenshots/04-next-episodes.png`: Favourites with each
   followed show's next episode, credited to TVmaze.
5. `docs/app-store/screenshots/05-privacy-and-sources.png`: About, with the
   privacy posture and the sources.

The shows used have no outcome tropes on screen (their trope list is
"None!"), and every reveal and collapsible stays closed. iPhone only
(DECISIONS 0009): no iPad set. Re-shoot after any UI change or snapshot
refresh; the dates in "next episode" and "Data as of" are real.

## 2. Privacy label

"Data Not Collected" for every category Apple's privacy label asks about.
This is true of the build in this PR:

- **The host sees request IPs, and the policy says so (DECISIONS 0007).**
  The snapshot is served by GitHub Pages. GitHub's own docs say "the
  visitor's IP address is logged and stored for security purposes". The
  developer never receives that log, and Apple's definition of "collect"
  covers the developer and "third-party partners" (its examples: analytics
  tools, ad networks, SDKs), not a static host. So the label stays true.
  The privacy policy and the About screen both say plainly that GitHub
  serves the file and sees requesting IPs, and that the app collects
  nothing.

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
  use."* The app ships on LezWatch.TV's published terms (free reuse, link
  back requested) and TVmaze's CC BY-SA 4.0, with every credit both ask for
  (DECISIONS 0013; audit in `docs/LICENSES-AND-ATTRIBUTION.md`). The review
  note below says so. Keep the dated terms copies in `docs/terms-snapshots/`
  ready if Apple asks for authorization.
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
  Collected": `docs/site/privacy.html`, published to
  `https://chelseakr.github.io/queer-tv-guide/privacy.html` by the nightly
  workflow and linked from the About screen. It says plainly that GitHub
  Pages, the host, logs the IP address of every request "for security
  purposes", and that the developer never sees that log.
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
  HTTPS GET of a static JSON file published at https://chelseakr.github.io/queer-tv-guide/snapshot.v1.json, sent when the
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

### App Review note (paste into "Notes" under App Review Information)

> **Data sources, licences and attribution (5.2.2).** Queer Frame shows data
> from two public sources. It bundles a snapshot and refreshes it from one
> static file we publish.
>
> 1. **LezWatch.TV** (https://lezwatchtv.com): shows, characters, recorded
>    deaths, ratings, tropes and where-to-watch links, from its public API.
>    Its terms of use (https://lezwatchtv.com/tos/) say: "You are welcome to
>    use, reuse, and extend the data here for no fees … We do ask you link
>    back to us, or note us by name." Every show and character screen links
>    to its LezWatch.TV page ("View on LezWatch.TV"), and the About screen
>    names LezWatch.TV with a link.
> 2. **TVmaze** (https://www.tvmaze.com): episode schedules, from its API,
>    licensed CC BY-SA 4.0 (https://www.tvmaze.com/api, "Licensing"). TVmaze
>    asks for attribution by linking back to it from within the app. Every
>    next-episode line is shown with "Schedule data from TVmaze", linked,
>    and the CC BY-SA 4.0 licence, linked.
>
> The About screen states: "LezWatch.TV and TVmaze do not endorse this
> app." No images or articles are used. The combined data file is itself
> published under CC BY-SA 4.0 at
> https://chelseakr.github.io/queer-tv-guide/snapshot.v1.json, with its
> licence and credits. The app makes one network request, a GET of that
> file. It has no accounts, analytics, ads or third-party SDKs. Nothing
> requires sign-in.

## 4. Screens this build ships (2 of 2 planned before this PR / 5 total)

The brief's five screens, all present in `ios/QueerTVGuide/Views`:

1. **Search** (`SearchView.swift`) — search across shows and characters,
   worth-it/no-recorded-deaths/has-a-watch-link filters, pull to refresh.
2. **Show detail** (`ShowDetailView.swift`) — "View on LezWatch.TV" (this
   show's page), worth-it/quality/realness/screentime (the worth-it
   explanation collapsed, since some name a death), "do any queer characters die?" behind `SpoilerReveal`
   (closed by default; per listed character, and says when a death may
   belong to another of the character's shows or when LezWatch's own tally
   disagrees), tropes (minus "Bury Your Queers", which moves inside the
   reveal), trigger warnings, characters, where-to-watch as `openURL` links,
   next episode (schedule-known vs schedule-unknown distinguished, and a
   date that has passed is called past, never "next") with TVmaze's credit
   and licence link, plot notes behind a
   spoiler disclosure, attribution footer with `generated_at`.
3. **Character detail** (`CharacterDetailView.swift`) — "View on
   LezWatch.TV" (this character's page), identity fields
   (minus the "Dead Queers" cliché, which would answer the reveal),
   "Does <name> die?" behind `SpoilerReveal` (closed by default; VoiceOver
   focus moves to the answer on reveal), shows the character appears in.
4. **Favourites** (`FavouritesView.swift`) — local list with each show's
   next episode, credited to TVmaze with its licence, swipe to remove, empty state explains the local-only
   posture.
5. **About & Privacy** (`AboutView.swift`) — the posture statement, every
   `attribution` entry from the snapshot with its source and licence links,
   "LezWatch.TV and TVmaze do not endorse this app", the licence notice, coverage
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
#    App Store Connect / Developer Portal session). The bundle id keeps
#    its working form even though the app is named Queer Frame
#    (DECISIONS 0006): it is never shown to users and cannot change once
#    registered.
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

# 3. REQUIRED before any archive: refresh the bundled snapshot.
#    ios/QueerTVGuide/Resources/snapshot.v1.json is the app's first-launch
#    and offline catalogue (gitignored, never committed): a byte-for-byte
#    copy of a pipeline-PUBLISHED snapshot (real LezWatch.TV + TVmaze data, the same bytes anyone can
#    fetch under CC BY-SA 4.0). Re-copy the latest before archiving so the
#    release ships current data. The target verifies the published .sha256
#    and refuses a fixture or a locally built file (no workflow run id):
make bundle-snapshot
#    GuideCore's BundledSnapshotTests and the hosted
#    AppModelIntegrationTests re-check the result (not the fixture, published
#    by the nightly workflow, decodes with the app's decoder, real-catalogue
#    scale). Run them before archiving:
make test

# 4. Archive (device build; needs the profile from step 1-2 present
#    locally — this session's simulator-only environment cannot run this
#    step to completion without them).
xcodebuild -project QueerTVGuide.xcodeproj -scheme QueerTVGuide \
  -configuration Release -destination 'generic/platform=iOS' \
  -archivePath build/QueerTVGuide.xcarchive \
  DEVELOPMENT_TEAM=6X5YH93QNM \
  archive

# 5. Validate the archive against App Store Connect before uploading.
xcodebuild -exportArchive \
  -archivePath build/QueerTVGuide.xcarchive \
  -exportPath build/export \
  -exportOptionsPlist ExportOptions.plist \
  # ExportOptions.plist (owner creates once): method=app-store-connect,
  # teamID=6X5YH93QNM, signingStyle=automatic.

# 6. Upload to App Store Connect (owner-run; needs an app-specific
#    password or API key).
xcrun altool --validate-app -f build/export/QueerTVGuide.ipa \
  -t ios -u "<owner apple id>" -p "<app-specific password>"
xcrun altool --upload-app -f build/export/QueerTVGuide.ipa \
  -t ios -u "<owner apple id>" -p "<app-specific password>"

# 7. In App Store Connect (owner-run, web UI): attach the build to a
#    TestFlight group, fill in the "Notes for Review" text from §3 above,
#    complete the privacy label as "Data Not Collected" per §2, set the
#    price tier per §1, and submit for internal testing.
```

Nothing above installs, signs, or uploads anything from this session — no
`xcrun altool`/`xcodebuild archive`/`-exportArchive` command in this section
was run here; they are the ordered commands for the owner to run with
Apple credentials this environment doesn't have.

## 6. Owner steps to submit (the remaining, owner-only work)

Nothing below was run from this repository. Each step needs the owner's
Apple account.

1. **Agreements** (App Store Connect → Business): the Paid Apps agreement
   active, with banking and tax forms complete. A paid app cannot go on
   sale without it. Enrol in the App Store Small Business Program (15%).
2. **Bundle ID** (Certificates, Identifiers & Profiles → Identifiers →
   +): explicit App ID `com.chelseakr.queertvguide`, Team `6X5YH93QNM`,
   no capabilities.
3. **App record** (App Store Connect → Apps → + → New App):
   - Platform: iOS
   - Name: **Queer Frame**
   - Primary language: English (U.S.)
   - Bundle ID: `com.chelseakr.queertvguide`
   - SKU: any internal id you choose, never shown to users (for example
     `queer-frame-ios`)
   - User access: Full
4. **Pricing and Availability:** price **$4.99** (USD base price, one-time).
   Storefronts are your call (research §7 on where LGBTQ content is
   restricted).
5. **App Information:**
   - Category: Entertainment
   - Age rating questionnaire: answer as in §1, which should compute **13+**
   - Privacy Policy URL: `https://chelseakr.github.io/queer-tv-guide/privacy.html`
6. **App Privacy:** "Data Not Collected" (§2).
7. **Version page:**
   - Subtitle, promotional text, description and keywords from
     `docs/app-store-listing.json`
   - Support URL `https://chelseakr.github.io/queer-tv-guide/support.html`,
     **after its contact method is added** (blocker 1 above)
   - The five screenshots in `docs/app-store/screenshots/` in the 6.9"
     iPhone slot
   - The App Review note above, and your own contact details for the
     reviewer
   - Sign-in required: No
8. **Build:** from `ios/`, run `make bundle-snapshot`, `make test` and
   `make presubmit-check`. Then open `QueerTVGuide.xcodeproj` in Xcode and
   choose Product → Archive with the "Any iOS Device" destination (signing:
   automatic, Team `6X5YH93QNM`). Then Organizer → Distribute App → App
   Store Connect → Upload. Export compliance is answered by the build
   (`ITSAppUsesNonExemptEncryption = NO`).
9. **Submit:** select the processed build on the version page, then Add for
   Review → Submit. Optionally TestFlight it internally first.

