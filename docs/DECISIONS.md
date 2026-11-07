# Decisions

Numbering: 0001–0004, 0006–0011, 0013, 0015, 0017, 0018, 0019, 0020, 0021 and 0023 live here. 0005, 0012 and
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

## 0017 — The system rating prompt may use StoreKit's review API (accepted, 2026-10-12)

**Status: accepted (owner, 2026-10-12). It amends 0003.**
0003 reads: "One-time purchase at the App Store, no IAP, no subscription:
no StoreKit code, no receipt validation, nothing to phone home about." Its
reason is the purchase: nothing to buy inside the app, nothing to verify,
nothing to report. The rating prompt is none of those, but "no StoreKit
code" says no to it as written.

**Decision.** 0003 keeps its purchase rule and loses its blanket
"no StoreKit code": the app may import StoreKit in exactly one file,
`ios/QueerTVGuide/App/ReviewRequest.swift`, for SwiftUI's `requestReview`
action and nothing else. No StoreKit purchase, product, receipt or
store-sheet API may appear anywhere, that file included, and no `.storekit`
file ships. `SourceTreeGuardTests` and `scripts/check_app_store.py` enforce
both halves, with negative controls.

**When the app asks** (`ReviewPromptPolicy` in GuideCore, unit-tested on an
injected clock): never during the first launch; only after a good moment
(a show opened from Favorites in this launch, or the third launch with a
favorite saved); at most once per app version and at least 120 days after
the last ask. iOS decides whether the prompt appears and caps it at three
times a year. Nothing is offered for a rating and nobody is asked how they
feel first (App Review 5.6.1).

**Privacy (0002 stands).** iOS draws the prompt and sends any rating to the
App Store; the app learns nothing, not even whether it showed. The timing
counters (launch counts, the last ask's date and version) stay in
`UserDefaults` on the device under `reviewPrompt.v1`, already covered by the
manifest's `CA92.1` reason. The privacy label stays "Data Not Collected".

**If the owner declines,** revert the commit that adds the prompt. The
About screen's "Rate" row does not use StoreKit and stays either way.

## 0018 — A native Android app with parity to iOS (2026-10-12)

**Status: accepted (owner, 2026-10-12).** The owner asked on 2026-10-12 for
an Android app with full parity with the iOS app, and accepted this record
the same day, with the answers under "Owner answers" below. The Play
listing, signing and the Data safety form are the owner's.

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

**Owner answers (2026-10-12).**
- **Ratings: the About row only.** "Rate Queer Frame" opens the Play
  listing. No Play In-App Review: that library
  (`com.google.android.play:review`) is Google Play code, and the app links
  none, whatever 0017 decides for iOS. The app's libraries are AndroidX and
  Kotlin's open-source ones; no Google Play services, Play Core or Firebase
  library, which `SourceGuardTest` holds the build to.
- **No Google cloud backup for favorites.** Favorites, the first-run flag
  and the reminder switch are excluded from cloud backup and move only in a
  device-to-device transfer (`res/xml/data_extraction_rules.xml`,
  `backup_rules.xml`), as built.
- **Links: the custom scheme only.** `queerframe://show/<id>` and
  `queerframe://character/<id>`. Android App Links (verified https links)
  wait on the universal-links decision for iOS.
- **Privacy policy.** `docs/site/privacy.html` gains an Android section
  (drafted with this record): the same one request, local reminders, no
  cloud backup of favorites, and the one request's User-Agent.
- **User-Agent: the app's own** (owner, 2026-10-12). The one GET sends
  "QueerFrame/<versionName> (Android)" in place of Android's default, which
  names the OS build and the phone's model. `StoreAndRefresherTest` checks
  the header on the wire; `UserAgentDeviceTest` checks on a device that it
  holds no `Build.MODEL`, `Build.VERSION` or build id.

**CI.** The `android` job runs `make android` on Linux on every run; the
emulator tests run locally (`make -C android instrumented`).

## 0019 — A static web page for each of 50 shows, with the answer closed (2026-10-22)

**Status: accepted (owner, 2026-10-22, decision A of the roadmap: the full
answer on the web). It amends 0001 and 0007.**

**Decision.** `qtv_pipeline.show_pages` builds a static page per show from the
same snapshot the app reads: `shows/<slug>/index.html`, a `shows/` index and
a `sitemap.xml`. The first 50 shows are those with the most characters
listed in the snapshot (ties to the lower LezWatch id; shows with no listed
character are never built). The page answers "does she die in <show>" in full,
inside a native `<details>` element that is closed on load, and nowhere else:
not in the title, description, structured data, headings, facts or character
list. A character with no recorded death is "Unknown", never "No" (LezWatch
records deaths, not survival). Every page credits LezWatch.TV and TVmaze with
their license text and links, as the app does (0013), and carries the
snapshot's CC BY-SA 4.0 notice because TVmaze's run status is on it.

**Amends 0001.** 0001 said there is no website to repackage. The site is
not the app and the app is still native; the pages are a free front door to
the same data, and App Review's "repackaged website" worry is about the
app. The app's own claims do not change.

**Amends 0007.** The privacy policy gains a "This website" section: the pages
set no cookies, run no analytics, load nothing from another host and run no
code. GitHub Pages still logs request IPs, as for the data file.

**Not decided here.** Deployment. `snapshot.yml` does not run the generator
and Pages publishes nothing new until the owner wires it in. A custom domain
is the owner's call (the canonical URLs, the sitemap and the privacy page
name the github.io host until then).

**Evidence rule (roadmap, Stage 1).** Eight weeks after the pages are
indexed: any page under position 30 in Search Console and the expansion
stops; the 50 pages stay.

**Reversible.** Yes: delete `show_pages.py`, its templates and tests, and the
privacy paragraph; nothing else depends on them.

## 0020 — The show pages publish on queerframe.app (2026-10-23)

**Status: accepted (owner, 2026-10-23). It settles what 0019 left open.**

**Decision.** The site's address is `https://queerframe.app`. The custom
domain is attached to the Pages site, so Pages answers the old
`chelseakr.github.io/queer-tv-guide` address with a 301. `snapshot.yml` now
builds the 50 show pages, `shows/index.html`, `sitemap.xml` and `robots.txt`
into the Pages artifact beside the snapshot files, and the generator's default
base URL is the domain, so every canonical URL, internal link, breadcrumb item
and sitemap entry names it. The home page (the data index) stays; it gains one
plain link to `shows/` when the show pages were built beside it.

**The pages never block the snapshot.** They are an extra. The workflow policy
forbids `continue-on-error` and `|| true`, so the generator carries the rule:
run with `--notice-on-failure` (as `snapshot.yml` does), any problem prints a
`::notice::` line, writes nothing and exits 0. All files are rendered before
the first is written, and a failed write removes what it wrote. The snapshot
publishing, its freshness alarm and its alerts are unchanged.

**Dates.** A sitemap entry's `lastmod` is the date in the snapshot's own
`generated_at`, never the clock of the machine that builds the pages.

**Not decided here.** The apps' fetch URL, privacy and support constants stay
on the github.io address until a separate change moves them with the next app
release (the 301 serves the shipped apps). The privacy policy is unchanged.

**Evidence rule.** Unchanged from 0019: eight weeks after the pages are
indexed, read Search Console; any page under position 30 and the expansion
stops; the 50 pages stay.

**Reversible.** Yes: remove the workflow step; the pages stop being published
at the next run and nothing else depends on them.

## 0021 — The 50 show pages are a hand-picked list (2026-10-23)

**Status: accepted (owner, 2026-10-23). It supersedes the selection rule in
0019; everything else in 0019 and 0020 stands.**

**Decision.** `pipeline/data/show_pages_pinned.json` names up to 50 shows, each
with its LezWatch id, slug, title and a one-line reason, and a `how_chosen`
header. `qtv_pipeline.show_pages` builds those shows in the file's order (the
order of the sitemap and of the shows index). A pin whose id is not in the
snapshot, or whose show lists no character there, is skipped and named in the
build log, and the slots it frees go to the 0019 rule (most listed
characters, then lower LezWatch id). With no file, that rule is the whole
rule. A file that exists but is wrong (more than 50 entries, a repeated id or
slug, a missing reason, title or slug, no `how_chosen`) fails the build, which
the workflow's `--notice-on-failure` turns into a notice and no pages. A show
with no listed character is never built, pinned or not.

**How the list was chosen.** The owner named about 50 titles. I kept each one
the snapshot has with at least 2 listed characters, in the owner's order, and
filled the one remaining slot with the highest TVmaze weight among shows not
already chosen that list 8 or more characters, excluding soaps (The Simpsons).
Every reason is taken from the snapshot only: the listed-character count,
the TVmaze weight, that the title is a named flagship. Nothing in the file
claims anything about search volume, because there is none to cite.

**Not in the snapshot, so not pinned:** Clea (no show by that title; The
Cleaner and The Cleaning Lady list 2 and 1), Bridgerton, House of the Dragon.
Where a title has several entries only the one named is pinned (Shameless
(US) not (UK); Orphan Black not Echoes; Degrassi: The Next Generation not
Next Class; The Walking Dead not Fear the Walking Dead).

**Why not a rule.** Two rules were tried on the 2026-10-23 data and rejected.
Most listed characters (0019) fills the list with long-running soaps. TVmaze
weight, with or without a floor of listed characters, is general-audience
popularity: 89 shows tie at weight 100, so it picks Grey's Anatomy, NCIS and
Friends over The L Word, Orange is the New Black and Pose, and a floor of 2, 3
or 4 characters does not change that. A list is the one tool that says what
the owner means.

**Cost.** The list does not update itself. A show LezWatch renames or removes
drops out with a log line and its slot goes to the 0019 rule; a new flagship
show gets no page until someone adds it. Merging this after the pages of 0019
are live replaces pages, and each removed URL answers 404.

**Reversible.** Yes: delete the file and the 0019 rule is the whole rule.

## 0023 — Show pages link to each other, warn before the answer, and carry the App Store switch (2026-10-23)

**Status: accepted under decision A of the roadmap (owner, 2026-10-22). It
extends 0019 and 0020 and changes nothing they decided.** Numbered 0023
because 0022 is taken by the snippet change on its own branch.

**Decision.** Each show page gains three things. (1) A "More shows" list:
the shows before and after it in the published order (the order of the shows
index and the sitemap, wrapping at the ends) and the shows index, so every
page is linked from two others as well as from the index. The link text is
the show's title only. (2) A line before the closed answer, outside it:
"Spoiler warning: the answer below says which listed characters LezWatch.TV
records as dying, if any." It names no character and no outcome. (3) When
`APP_STORE_LIVE` is on, Safari's Smart App Banner tag and a link whose text is
`app_store.PRICE_COPY` ("Queer Frame for iPhone. $4.99 on the App Store."),
on the show pages and the shows index, with the same URL and tag as
`app_store.py`. Off, as it stays until Apple approves the app, no page
changes. `app_store.apply` still reads only the top-level pages, so no page
gets the tag twice. The tag is a `<meta>` and the page fetches nothing for it;
Safari itself may look the app up at Apple to draw the banner, as it already
does on the site's top-level pages when the switch is on. The privacy page's
"This website" section does not mention that yet, so it should be updated
before the switch is turned on.

**Why.** The pages had no links between shows, so a visitor or a crawler
reached a show only from the index. The spoiler control was the summary
label alone. The site's top-level pages got the banner when the switch is
on, but the show pages, which are the pages search sends people to, did not.

**Not done.** No badge image on the show pages: they load nothing, and
Apple's artwork license needs the app on sale. No new facts: every word on a
page still comes from the snapshot or is fixed copy.

**Reversible.** Yes: remove the template blocks and `neighbors`.

## 0024 — Show pages use the words people search with (2026-10-29)

**Status: proposed (agent, 2026-10-29), under decision A of the roadmap.
It extends 0019 and 0023 and keeps their spoiler rule.**

**Evidence.** Search Console for `sc-domain:queerframe.app`, 2026-10-22 to
2026-10-27: 23 impressions, 0 clicks, 11 show pages with at least one
impression (average position 6 to 19), and the only queries Google showed
were "lezwatch", "lezwatch.tv" and a misspelling; the rest were withheld as
too rare. That is too little to rank queries, so the wording below follows
the shapes people use for this question ("does <character> die in <show>",
"<show> lgbt characters", "<show> bury your gays"), not measured volume.

**Decision.** (1) Title: "Do any queer characters die in <show>?
Spoiler-free", falling back to shorter forms within 60 characters; the site
name is dropped from show titles. (2) Description: "Does she die in
<show>?", the listed-character count and up to three names, regulars first
and then in page order, never in an order a death could affect. (3) The
heading over the character list is "LGBTQ characters in <show>", and one
fixed sentence on every page names the bury-your-gays trope. LezWatch's own
trope name stays inside the answer, as before. (4) The one JSON-LD block is
an `@graph`: the BreadcrumbList, plus a schema.org TVSeries on show pages
(name, page, LezWatch.TV and TVmaze pages, years, seasons, genres,
countries, character names) and an ItemList on the shows index. No
FAQPage: its answer would put the spoiler in the structured data. (5) Up to
four "Shows like <show>" links: LezWatch.TV's similar shows that have a
page, then the most shared genres. Tropes are never used for similarity.
(6) With `APP_STORE_LIVE` off, one fixed sentence says the app is not on
the App Store yet, with no link; on, the 0023 link replaces it.

**Not done.** No pages beyond the 50 of 0021: the 0019 evidence rule
(eight weeks after indexing) still decides any expansion.

**Reversible.** Yes: restore the old title and description functions,
template lines and `related`.

## 0025 — Show pages for every show with enough to answer (2026-10-29)

**Status: accepted (owner, 2026-10-29: "Expand now"). It supersedes the
evidence rule in 0019 and 0020 (wait eight weeks after indexing before any
expansion) and the "Not done" line of 0024. The hand-picked list of 0021,
and everything 0019 to 0024 decided about what a page says, stand. Partly
reversed by 0028 (2026-11-03): the pages are still built and linked, but
only the hand-picked 50 are in the sitemap and open to indexing.**

**Decision.** After the pinned list, `qtv_pipeline.show_pages` builds every
show with at least 5 characters listed in the snapshot and a TVmaze match (a
TVmaze page URL), most listed first, ties to the lower LezWatch id. On the
2026-10-29 snapshot that is 363 pages: the 50 pins plus 313 others (349
shows meet the rule; 36 of them are pinned). Of 2,287 shows, 2,280 list a
character; most list one or two.

**Why 5 and a TVmaze match.** The point is pages with substance, not one per
show. At 5 or more listed characters the closed answer covers several
characters, the description names three and says there are more, and the
character list is worth reading; the TVmaze match makes the run status,
network and TVmaze credit real rather than "Unknown". The counts on that
snapshot, with a TVmaze match: 3 or more characters, 736 shows; 4, 492; 5,
349; 6, 249; 8, 139. Five gives a few hundred pages; 3 or 4 would add
hundreds of thin pages, and 6 or more would leave out shows with real
casts. No part of the rule looks at deaths.

**Pins stay.** The 50 hand-picked pages keep their URLs, first in the
published order and in their own section of the shows index, even where a
pin lists fewer than 5 characters (14 of them do), so no published page
answers 404.

**Floor and cap.** If the pins and the rule make fewer than 50 pages, the
most-listed other shows fill up to 50 (the 0019 rule); on real data this
does not happen. At most 600 pages are built (`DEFAULT_LIMIT`); a cut drops
the fewest-listed and is logged. The sitemap refuses more than 50,000 URLs.

**Scale.** The shows index lists the hand-picked shows, then every show A to
Z under a letter heading (a leading "The", "A" or "An" is ignored; titles
that start with a digit, a symbol or a non-Latin script go under "#"), with
a list of letters to jump to; the ItemList keeps the published order. The
characters are indexed once per build, so the whole site builds in under a
second locally. The largest page is about 29 KB and the index about 83 KB;
the site is about 4.8 MB.

**Reversible.** Yes: set `MIN_LISTED` high enough that no show meets it, and
the site returns to the 50 pins; the removed URLs answer 404.

## 0026 — The site's root is a home page; the data description moves to /data/ (2026-10-29)

**Status: accepted (owner, 2026-10-29: replace the "Queer Frame snapshot"
page at queerframe.app with a real landing page).**

**Decision.** `qtv_pipeline.site_index` writes two pages. `index.html`, at
https://queerframe.app/, is a home page: what Queer Frame is (a guide to TV
shows with queer women, non-binary and trans characters, with a spoiler-free,
tap-to-reveal answer to "Do any queer characters die?"), how it works (the
closed answer, Unknown is not "lives", no account and no tracking, the two
sources credited with "LezWatch.TV and TVmaze do not endorse this app"), links
into the show pages (the hand-picked list first, then A to Z, and the first
12 hand-picked titles), and one line saying the iPhone app is coming soon,
with no link. The old page's content (license notice, files, this build's
counts) moves to `data/index.html`, at https://queerframe.app/data/, linked
from the footer of every page. The data files keep their URLs at the root:
`snapshot.v1.json` and `snapshot.v1.json.sha256` are unchanged, and the app
fetches the first one there.

**The App Store switch.** The "coming soon" line is `app_store.INDEX_SLOT`.
With `APP_STORE_LIVE` on, `app_store.apply` replaces it with the badge and the
price, so the page never says "coming soon" beside the badge; off, no byte of
the site changes. `play_store.apply` places its link after the badge, or
after the slot while the App Store switch is off.

**Spoiler rule.** The home page names show titles and nothing about any
character: no answer, no character name, no `<details>`, in the body, the
title, the description or the Open Graph tags (tested, with a negative
control). It has no script at all, not even structured data, and no image:
Open Graph carries no `og:image`.

**Links that resolve.** The home page links into `/shows/` only when the
shows index was published beside it, and names only hand-picked shows whose
page exists, since the show-pages step may be skipped. The sitemap lists the
home page first.

**Reversible.** Yes: restore the old `render_index` and the anchor after the
heading; `/data/` would then answer 404.

## 0027 — Show page titles and descriptions answer the searched question (2026-10-30)

**Status: proposed (agent, 2026-10-30). It amends the title and description
parts of 0024 and keeps the spoiler rule of 0019 to 0026.**

**Evidence.** Search Console for `sc-domain:queerframe.app`, all days to
2026-10-30: 46 impressions in a week, average position about 9, 0 clicks,
20 pages with an impression. The queries Google showed: "who dies in the l
word" (2), "is lisa simpson a lesbian", "the 100 lesbian", "adriana
delgadillo grey's anatomy", and "lezwatch", "lezwatch.tv" and a misspelling
on the home page. That is too few to measure a click rate, so this is a
wording change toward the questions people asked, not a tested result.

**Decision.** (1) Show title: "Do any of the <n> queer characters in <show>
die?" when there are at least two listed characters and it fits in 60
characters; otherwise the 0024 forms. The count is of listed characters,
never of deaths. "Spoiler-free" leaves this form, since someone searching
"who dies in <show>" wants the answer, and the description says where it
is. (2) Description: "LezWatch.TV lists <n> LGBTQ characters in <show>,
including <name> (<identity>) ...", then "Who dies, if anyone, is behind a
spoiler warning." Names are still regulars first and never in an order a
death could affect. The identity comes from the gender and sexuality terms
the page's character list already shows (`show_pages.identity`), trusting
LezWatch.TV's scope (queer women and non-binary characters; owner,
2026-10-30): "Homosexual" or "Lesbian" with a gender term of "Cisgender" or
one ending in "Woman" is "lesbian"; with a non-binary, genderqueer, agender
or other gender term it is never "lesbian" and the gender term is used
("non-binary"); other named sexualities as given ("bisexual", "queer",
"pansexual"); otherwise a gender term that is not cisgender or unknown
("trans woman", "non-binary", "trans man"); anything else, no label. Never
"gay". Labelled names come
before more names, then bare names if a long title leaves no room. (3) The
home page description names LezWatch.TV as the source, since the searches
that reached it were for LezWatch.TV; the footer still says LezWatch.TV
does not endorse the site.

**Not changed.** No answer, death count, death year or death trope in a
title, description, heading or structured data; no FAQPage; the App Store
switch is off and the pages keep saying, with no link, that the app is not
on the App Store yet.

**Reversible.** Yes: restore the 0024 `show_title` and `show_description`
and the old home description.

## 0028 — Only the hand-picked show pages are open to search, for now (2026-11-03)

**Status: accepted (owner, 2026-11-03). It partly reverses 0025 ("Expand
now"): every page 0025 builds is still built and linked, but only the
hand-picked list of 0021 is in the sitemap. What a page says (0019 to 0027)
does not change.**

**Evidence.** Search Console for `sc-domain:queerframe.app`, 10-22 to
11-03: 96 impressions, 0 clicks, average position 9.3. Every impression
went to a hand-picked page (28 of them), the home page or /shows/; none
went to the 313 pages 0025 added on 10-30. URL Inspection called 9 of 9
sampled added pages "URL is unknown to Google". Google last read the sitemap
on 10-29, when it listed 51 URLs; it now lists 365. The added pages share
most of their text: at the median, about 68% of a page's words are
sentences found on at least 30% of pages. A young domain that suddenly
shows Google hundreds of similar template pages is the most plausible cause
of Trout Truck's fall of about 97% in impressions on 10-22. That cause was
never confirmed, so this is a hedge, not a measured fix.

**Decision.** `show_pages.indexed_show_ids` is the one place that decides
which show pages may be indexed: the hand-picked shows that were built
(without a pinned list, the first 50 pages in the published order). The
sitemap lists the home page, /shows/ and those pages, and no other show
page. Every other show page carries `<meta name="robots"
content="noindex,follow">`. It stays built, keeps its URL and canonical, and
is still linked from the shows index (which the home page links to) and
from the pages next to it, so search engines can still reach it and follow
its links. On the 2026-11-03
snapshot the sitemap goes from 365 URLs to 52: 50 show pages are indexed and
313 are held back. Privacy, terms, support and /data/ carry no robots tag
and stay out of the sitemap, as before. The site has no IndexNow key and
pings nothing, so the sitemap is the only list search engines are given.

**The check.** `show_pages.index_problems` runs on every build and refuses
it if the sitemap and the robots tags disagree: a page in the sitemap with a
robots tag, a page left out without exactly `noindex,follow`, a sitemap URL
that is not a built page, or a sitemap without the home page or /shows/.
`tests/test_show_pages_indexing.py` has negative controls that break each
side and assert the build is refused.

**How to widen.** In `show_pages.py`, add LezWatch ids to `INDEX_EXTRA_IDS`
(by list), or set `INDEX_MIN_LISTED` so every built show with at least that
many listed characters is indexed (by rule). Both go through a reviewed PR,
and the check keeps the sitemap and the tags in step. Setting
`INDEX_MIN_LISTED` to `MIN_LISTED` (5) undoes this decision.

**When to widen.** After Google has read the 52-URL sitemap, the
hand-picked pages need steady clicks for 4 weeks: at least one click in
each of 4 weeks in a row in Search Console, with weekly impressions not
falling. Then open the held-back pages in batches of about 50, most listed
characters first, and wait 2 weeks between batches. Stop and roll back the
last batch if the hand-picked pages' impressions fall. Next look: about
11-17.

**Not changed.** Page content, titles, descriptions, structured data, the
shows index, the app and the App Store material. Do not resubmit the
sitemap in Search Console until this is live; after that, resubmitting is
fine.

**Reversible.** Yes, with one constant (see "How to widen").

## 0029 — Each show page opens with a sentence only that show can have (2026-11-04)

**Status: proposed (agent, 2026-11-04). It extends 0024 and 0027 and keeps
the spoiler rule of 0019 to 0028. Indexing (0028) does not change.**

**Evidence.** The 2026-11-03 search review found that the opening paragraph
of every show page was the same except for the show's name, and that at the
median about 68% of a page's words are sentences found on at least 30% of
pages. Measured again on the 2026-11-04 snapshot (363 pages, sentences split
on end punctuation, the same 30% threshold): the median repeated share falls
from 65.0% to 60.6%, and the median of show-specific words rises from 215 to
248. Most of what remains is the shared credits and license block, which
this change does not touch (shortening it needs a licensing sign-off).

**Decision.** `show_pages.opening` writes the page's first paragraph, right
under the heading: "LezWatch.TV lists <n> queer characters in <show>
(<network>, <years>), including <name> and <name>." then, from TVmaze, "Its
most recent episode on TVmaze aired on <date> (season <s>, episode <e>),
and the next is listed for <date>." ("last" instead of "most recent" when
TVmaze says the show has ended and lists no next episode). The count is of
listed characters, as in the title. The names are the first two in the
description's order (regulars first, then the page's order), never an order
a death could affect. The network is LezWatch.TV's, then TVmaze's only when
the schedule is known, as in the facts list. The fixed paragraph after it is
shorter and still names the bury-your-gays trope (0024).

**What it never says.** No death, death count, death year or death trope,
and no episode name (one can give the answer away: "Dead Air"). A test swaps
every death record and death tally and asserts no opening changes.

**Absence.** A fact the snapshot lacks is left out of the sentence, never
printed: no years, no network, no TVmaze match, an unreadable date or a
missing season or episode number each make the sentence shorter. A show
with none of them gets "LezWatch.TV lists one queer character in <show>:
<name>." A start year with no end year and no "on air" flag says "from
<year>", never "to present". The facts list keeps saying "Not recorded"
where a value is missing, as before.

**Not changed.** The title, description, structured data, the closed answer,
the facts list, the credits and license block, the sitemap and robots tags,
the shows index, the home page and the app.

**Reversible.** Yes: restore the old first paragraph in `show.html.j2` and
drop `opening`.

## 0030 — A death counts for a show only when it falls in that show (2026-11-05)

**Evidence.** The 2026-11-05 quality audit found show pages counting a
death from another show. The L Word: Generation Q said "Yes. 1 of 42 listed
characters dies: Dana Fairbanks." Her recorded death (2007) is in The L
Word; LezWatch.TV links her to Generation Q only as a 2022 guest. Supergirl
counted Sara Lance (Arrow and Legends) and Nora West-Allen (The Flash), and
Batwoman counted Sara Lance. LezWatch.TV records a death on the character,
not on a show.

**Decision.** For a character linked to more than one show, the death
counts for a show only when a death year is one of the character's years in
that show (the link's `years`, already in the snapshot). Otherwise the
character's line says Unknown, names the recorded death year, and says it
is not in a year the character appears in this show; a note under the
headline says how many such characters are not counted. A death with no
year, or a link with no years, is also Unknown for a multi-show character:
the snapshot cannot place it, so the page does not guess either way. A
character linked to one show keeps its death, as before. On the 2026-11-04
snapshot this changes the headline on 7 of 363 pages (Batwoman, Scandal,
Steven Universe, Supergirl, The L Word: Generation Q, The Vampire Diaries,
Vis a Vis); 3 of them move from "Yes" to "Unknown".

**Also.** Every show page now says, beside its credit to LezWatch.TV, that
LezWatch.TV covers queer women, non-binary and trans characters, so the
page does not list cisgender gay and bisexual men. The characters heading
says "Queer women, non-binary and trans characters in <show>" instead of
"LGBTQ characters in <show>". The answer element carries `data-nosnippet`,
so a search engine does not quote it.

**Not changed.** The app (the same rule goes into `Presentation.showDeaths`
in a later build), the title, description, opening and selection.

**Reversible.** Yes: drop the `show_years` check in `_death_status`.

## 0031 — Show-page facts: TVmaze's season count for an ended show, the trigger level, one survival sentence (2026-11-05)

**Status: accepted (Chelsea, decision D6, 2026-11-05).**

**Evidence.** The 2026-11-05 quality audit found LezWatch.TV season counts
that are wrong for ended shows: Wentworth "11" (it had 8 by most sources;
TVmaze's last season is 9), Cobra Kai "4" (6; it ended February 13, 2025),
Bad Girls "5" (8), and 69 pages saying "Seasons: Not recorded" two lines
under an opening that names the latest season from TVmaze. It also found
that no page showed LezWatch.TV's trigger-warning level, and that 150
"Yes" answers printed "LezWatch.TV records deaths, not survival." twice in
a row.

**Decision.**

- Seasons (`seasons_fact`). TVmaze's season number is the season of the
  latest aired episode it lists (`schedule.previous_episode.season`, already
  in the snapshot; no new request to TVmaze). For a show TVmaze lists as
  Ended, when that number differs from LezWatch's count, the page shows
  TVmaze's, in a row labeled "Seasons, per TVmaze". When LezWatch has no
  count, TVmaze's number fills it, as "3" for an ended show and "3 so far"
  for any other. A running show keeps LezWatch's count, since a next season
  may be announced before TVmaze lists it. A TVmaze season number of 1900 or
  more is a year (soaps and anime numbered by year), not a count, and is
  never used; a show with neither stays "Not recorded". The schema.org
  `numberOfSeasons` uses the same number. There is no hand-kept override
  file: the rule is the only source of a changed number.
- Trigger warning. A facts row, "Trigger warning, per LezWatch.TV", shows
  LezWatch.TV's level (Low, Medium or High), or "Not rated" when none is
  recorded. The three levels rate how intense a show is and name no event,
  so they can sit outside the answer. Any other trigger term is not printed
  anywhere on the page (it could name a death); the row then says "See
  LezWatch.TV". On the 2026-11-05 snapshot all 192 recorded trigger terms
  are one of the three levels, and 50 of the 363 pages show one.
- The note under a "Yes" answer now says only "For the other N, the answer
  is unknown." The fixed line under it already says why.

On the 2026-11-05 snapshot the Seasons row changes on 93 of 363 pages.
The four record errors found in LezWatch.TV's own data (Wentworth's and
Cobra Kai's season counts, Buffy on The CW, and the year of Dana Fairbanks's
death) are to be reported to LezWatch.TV by Chelsea; this rule does not wait
for them.

**Not changed.** The network. It stays LezWatch.TV's stations first, then
TVmaze's only when LezWatch.TV lists none, in both the facts row and the
opening sentence, as in 0029. Chelsea chose this on 2026-11-05 after a trial
of TVmaze's network showed TVmaze names a show's current home (The L Word:
"Paramount+ with Showtime"). Buffy's "The CW" is left to LezWatch.TV to
correct. Also not changed: the app, the years row, the title, description
and selection. A season count from TVmaze can still differ from a show's
official count where TVmaze numbers seasons differently (Wentworth's final
20 episodes are season 8 in most sources and seasons 8 and 9 on TVmaze); the
label says whose number it is.

**Reversible.** Yes: `seasons_fact` returns LezWatch's count, and the
trigger row is dropped from `_facts`.

## 0032 — The apps follow 0030, and say what a trigger-warning level means (2026-11-05)

**Evidence.** 0030 changed the show pages only. The iOS and Android apps
still counted a death from another show: The L Word: Generation Q's reveal
said "1 of 42 listed characters has a recorded death" (Dana Fairbanks, who
dies in The L Word). The show screen also printed LezWatch.TV's trigger
level as a bare word under "Trigger warnings" ("High"), and the store
listings promised "content notes".

**Decision.** `Presentation.deathPlacement` (GuideCore) and its Kotlin
port apply 0030's rule to the reveal, the show summary and the "no recorded
deaths" filter. A death the snapshot places in another show (no death year
among the character's years in this show) is not counted. The reveal says
it is not recorded in this show, and a note says how many are left out. The
filter is stricter than the reveal: a death the snapshot cannot place at
all (no death year, or a link with no years) still keeps the show out, so
the filter never admits a show on a guess. On the 2026-11-05 snapshot the
reveal changes for 21 of 2,289 shows; 13 of them move from "Yes" to "Not
recorded".

The show screen's heading is "LezWatch.TV trigger-warning level". The level
is followed by LezWatch.TV's own description of it, quoted from its page
for that level, or "Not rated" with a line saying that does not mean the
show has no difficult content. The store listings and the support page say
"trigger-warning level" instead of "content notes". The Android app also
gets "Happiness then Tragedy" and "None!" behind the reveal, as on iOS
(#112).

**Not changed.** No link to LezWatch.TV's level pages: the app source names
one host (SourceTreeGuardTests), so adding one is a separate decision.

**Reversible.** Yes: `deathPlacement` returning "only show" for every
recorded death restores the old count.

## 0033 — One airing-now page, /airing/, open to search (2026-11-05)

**Status: proposed (agent, 2026-11-05), from the Stage 2 web plan
(`qf-stage2-plan-2026-11-05.md`, section 4.2) with the owner's choice of
"indexable, soaps under their own heading". It adds one URL and keeps the
spoiler rule of 0019 to 0030. 0028's hold on the show pages does not change.**

**Evidence.** On the 2026-11-05 snapshot, 43 shows have a TVmaze next
episode between November 5, 2026 and March 31, 2027. 42 of them are marked
on air by LezWatch.TV. The odd one is Law & Order: LezWatch.TV ends it in
2010 and TVmaze lists the revival (the issue #52 pattern). 9 of the 42 are
season premieres (Shetland, Yellowjackets, P-Valley, Only Murders in the
Building, Emily in Paris, The Rookie, Your Friendly Neighborhood
Spider-Man, Common Side Effects, High Potential) and 11 are soaps or
telenovelas. 22 of the 42 have a show page. New-episode reminders and the Up
Next widget are the app's features this page leads to.

**Decision.** `airing_page.py` builds `airing/index.html` inside
`show_pages.render_site`, from the snapshot and nothing else (no request).
A show is listed when LezWatch.TV marks it on air, its LezWatch end year
(if any) is not before the episode's year, TVmaze has a schedule for it,
and its next episode falls between the snapshot's date and the last day of
the month four months later. The window rolls with each nightly build. The
page groups season premieres (episode 1 of a numbered season), then other
new episodes, then soaps and telenovelas (LezWatch.TV genres `soap-opera`
and `telenovela`), each by date and then A to Z. A line gives the title
(linked to its show page when one is built, otherwise to LezWatch.TV), the
network, the date as "Friday, November 20, 2026" in a `<time>` element, the
season and episode when TVmaze gives both (never for a soap), and how many
queer characters LezWatch.TV lists. Shows left out by the on-air rule are
named in the build log.

**What it never says.** No episode name ("Dead Air"). No character at all,
so no character's years, which would say who is still there in the new
season. No trope, death record, death count or answer element, and no
order a death could change. A test swaps every death record and asserts not
a byte of the page changes; negative controls plant an episode name, a
character, her years and a trope and assert the check catches each.

**Absence.** A show with no TVmaze date is not listed, and one sentence says
that does not mean it is not coming back. A missing network, season or
episode number, or character count shortens the line. A build with no
TVmaze schedule at all says so, never "nothing airs".

**Indexing and links.** `/airing/` is in the sitemap after `/shows/` and
carries no robots tag. `index_problems` now also refuses a build where the
page is built but not listed, listed but not built, or tagged. The home
page's "Find a show" list and the shows index link to it. It is one page, not
a family of templates, so 0028's reason for holding pages back does not
apply.

**The app and privacy.** Switch off: one sentence says the iPhone app does
new-episode reminders and the Up Next widget and is not on the App Store
yet, with no link. Switch on: the plain App Store URL from `app_store.py`,
with no campaign or tracking parameter, and the Smart App Banner tag, as on
the show pages. No script, image, analytics or request to another host. The
page credits TVmaze under CC BY-SA 4.0 for the dates, and the footer carries
every source credit.

**Not changed.** The show pages, their selection and indexing, the app,
the workflow (the page is built by the existing show-pages step) and the
privacy page.

**Reversible.** Yes: `render_site(..., airing=False)` drops the page, its
sitemap entry and both links.

## 0034 — Announce new and changed pages to IndexNow after each deploy (2026-11-05)

**Evidence.** IndexNow is how a site tells Bing (which ChatGPT search leans
on) and the other participating engines that a page is new or changed,
instead of waiting for the next crawl. Trout Truck, Next Home Game, Lake
Notice and Tide Hours run the same `indexnow.py`; their runs on 2026-11-04
and 2026-11-05 got HTTP 200 or 202. 0028 said this site has no IndexNow key
and pings nothing; this entry changes that, and nothing else in 0028.

**Decision.** Every page's footer carries the build date and the sitemap's
`lastmod` is that same date, so neither says whether a page changed. A new
step in `snapshot.yml`, after the site is assembled and before the Pages
upload, copies the key file to the site root and writes `lastmod.json`: a
SHA-256 of each sitemap page with the one footer sentence "It was last
built from the sources on <date>." taken out. Any other date on a page
still counts as content. It then compares that with the live
`lastmod.json` and keeps the sitemap pages that are new or whose
fingerprint changed. A separate `indexnow` job, which needs `deploy` and
has read-only permissions and no secret, submits the list. A rebuild of
unchanged data announces nothing and sends no request, except the
airing-now page (0033): its window starts on the build day, so a build on
a new day changes it and it is announced, one URL a night. Only https URLs on
queerframe.app, only built pages without a robots noindex (so the held-back
show pages are never sent), at most 10,000 a request. If the live
`lastmod.json` cannot be read, nothing is sent. The first deploy finds no
live copy (404) and announces every sitemap page once. The script exits 0
on any problem and prints a notice, so the snapshot always publishes.

**The check.** `tests/test_indexnow.py` builds the fixture site twice with
only the build date changed and requires identical fingerprints for every
page but `/airing/`, and an empty submission for a same-day rebuild, so a
reworded footer fails CI instead of announcing every page every night. A changed show title in the same test does select
pages.

**Not changed.** No analytics, no third-party request from any page, no
page text. The key file is public by design.

**Reversible.** Yes: delete the two build steps, the `indexnow` job and the
key file.

## 0035 — Show pages list each character with an anchor and "played by" (2026-11-05)

**Status: accepted (Chelsea approved the Stage 2 plan's character-list change, 2026-11-05).**

**Evidence.** Of the 17 Search Console impressions from 2026-10-20 to
2026-11-05 that came with a named query, 8 were for a character ("candy
ferocity", "sense8 lila", "molly milkovich gender", "adriana delgadillo
grey's anatomy", "faking it lauren", "is lisa simpson a lesbian"), at
positions 8 to 50. Every one of those characters is already on a hand-picked
show page, as a bare line with no actor.

**Decision.** On existing show pages only (no new URL), the character list
outside the answer gives each character, regulars first:

- a link anchor from the character's LezWatch slug (`#candy-ferocity`). It
  is the same from build to build and unique on the page: a slug that is not
  a plain slug, is reserved (`main`) or repeats one earlier on the page
  falls back to `character-<LezWatch id>`, then a `-2` suffix;
- "played by <actor>", with the actor names exactly as LezWatch.TV gives
  them. An actor id that did not resolve to a name is left out, and a
  character with no named actor gets no clause, never a placeholder. Actor
  names are plain text; there are no actor pages.

The list never shows a character's years in the show (of the 711
dead-character links that have years, 63% end before the show does, so
years give a death away), a death date or year, or any cliche or trope. The
answer stays in the closed `<details>`. LezWatch.TV attribution and the
no-analytics rule are unchanged.

**Tests.** `test_show_pages_characters.py`: a planted character year, a
death date and a death-revealing cliche must each be caught by the leak
checker when sabotaged into the list; swapping every death record leaves the
list byte for byte the same; anchors are unique per page, and a repeated
anchor is caught.

**Reversible.** Yes: the template's list goes back to the plain line.

## 0036 — The Good Wife takes the one filled pin from The Simpsons (2026-11-05)

**Status: accepted (owner, 2026-11-05: option A of the indexing review).
It changes one entry of the hand-picked list of 0021. Indexing (0028) and
the cap of 50 do not change.**

**Evidence.** Search Console for `sc-domain:queerframe.app`, pages, 28 days
to 2026-11-05 (`dataState: all`), read with the read-only Search Console
scope. The Good Wife's page earned 9 impressions at an average position of
3 while it carried `noindex,follow`, the most of any held-back page (the
next ones have 1 or 2 each). Its noindex is now taking it out of Google's
index. The Simpsons, the one pin that no owner list named (0021 gave it the
last slot by TVmaze weight), earned 2 impressions at an average position of
16. The snapshot lists 12 queer characters for The Good Wife and 25 for The
Simpsons.

**Why this pin.** Nineteen of the 49 named flagships earned no impressions
in those 28 days, so by impressions alone several pins are weaker than The
Simpsons. They are on the owner's list of flagship titles, and the site's
search data starts on 2026-10-22, so a few quiet weeks say little about
them. The
Simpsons is the one slot that a rule filled rather than the owner, which
makes it the one this data can overrule without second-guessing that list.

**Decision.** In `pipeline/data/show_pages_pinned.json`, entry 50 is The
Good Wife (LezWatch id 69) in place of The Simpsons (id 4082), in the same
position. The Good Wife's page is in the sitemap and carries no robots tag;
The Simpsons' page is still built (25 listed characters meet the inclusion
rule of 0025), keeps its URL and links, and carries `noindex,follow`. The
sitemap stays at 52 URLs. `index_problems` keeps the sitemap and the tags in
step, as before.

**Not changed.** Page content, titles and descriptions, the other 49 pins,
`INDEX_EXTRA_IDS`, `INDEX_MIN_LISTED`, the app.

**Reversible.** Yes: restore the entry. When the held-back pages open in
batches (0028, "When to widen"), The Simpsons comes back on its own.

## 0037 — Show pages date the next episode, and name a season premiere (2026-11-05)

**Status: proposed (agent, 2026-11-05). It adds one facts row and one
clause to the 0029 opening, and keeps the spoiler rule of 0019 to 0035.
Selection (0021, 0025) and indexing (0028, 0036) do not change.**

**Evidence.** On the 2026-11-05 snapshot, 9 shows have a TVmaze season
premiere from November 2026 through February 2027 (the airing page's
season-premiere group, 0033). Three have a show page: Yellowjackets
(season 4, November 20, 2026; pinned and indexed), Only Murders in the
Building (season 6, December 8, 2026) and The Rookie (season 9, January 6,
2027), both held back with `noindex,follow`. Each page has its character
list with "played by" (0035) and full facts, but said only that "the next
is listed for <date>", never that the date opens a new season, and the
facts list had no date at all. The other six (Shetland, P-Valley, Emily in
Paris, Your Friendly Neighborhood Spider-Man, Common Side Effects, High
Potential) list 1 to 3 characters, under the 5 of 0025, so they get no page
and the airing page links them to LezWatch.TV.

**Decision.** A facts row, "Next episode, per TVmaze", follows the run
status (`show_pages.next_episode_fact`): "Season 4 premiere, Friday,
November 20, 2026" for episode 1 of a numbered season, "Season 10, episode
4, Thursday, November 5, 2026" otherwise, and only the date for a soap or
telenovela (0033's genres) or when a number is missing or is a year. The
opening says "and the first episode of season 4 is listed for November 20,
2026" in place of "and the next is listed for" when the next episode is a
premiere. Both come from the snapshot's TVmaze schedule; there is no new
source and no new request. On the 2026-11-05 snapshot 22 of 363 show pages
change; the airing page does not.

**Absence.** No row when TVmaze has no schedule, lists no next episode,
gives an unreadable date or a date before the snapshot's day (a stale
listing). "No next episode listed" is not a value, so the row is left out
rather than printed as "Not recorded".

**What it never says.** No episode name, no "final season" or other claim
TVmaze's schedule does not carry, and nothing a death record decides (a test
swaps every death record and asserts the row and opening do not change).

**Not changed.** Which shows get pages, and which pages are indexed. The
premiering held-back pages stay `noindex,follow` until 0028's "When to
widen" test is met; opening them early is Chelsea's call. Also not changed:
the airing page, the pins, the app.

**Reversible.** Yes: `_facts` without `today`, and the old opening clause.

## 0038 — The website gets its own look: the app icon's colors, a condensed title face, a sealed answer (2026-11-05)

**Status: proposed (agent, 2026-11-05). Visual and structural only: no URL,
`<title>`, H1 or meta description changes, and the spoiler rule of 0019 to
0037 holds. It replaces the "system colors only" rule the stylesheet test
held since 0019.**

**Why.** The pages used the browser's own colors and font, so they looked
like an unstyled document and like nothing else Queer Frame makes. The app
icon (aubergine, coral, a diagonal split, a cream play triangle) is the one
brand mark Queer Frame has; the site did not use it anywhere, not even as a
browser-tab icon. The portfolio also has a live App Store 4.3(a) "template"
problem, so each product's identity is chosen from its own subject.

**Decision.** One stylesheet, still inline and still loading nothing:
- Palette from the icon. Light: paper #f6f1fa, ink #2b1740, links #6a2c9c,
  coral #ff6f4f for bars and edges only (never text on paper). Dark: paper
  #1d1027, ink #f3ecf7, links #d9b8ff, coral #ff8a6b. Every text pair is
  WCAG AA (4.5:1) and every border and focus ring 3:1, in both schemes,
  checked by `tests/test_site_identity.py` with negative controls.
- Type: system fonts only. Titles in a heavy condensed face (Avenir Next
  Condensed on Apple devices, Roboto Condensed elsewhere, then the system
  font); body text in the system font. No web font, so no request.
- The one bold element is the answer box: a thick aubergine frame (coral in
  dark mode) whose summary bar carries the icon's diagonal corner. The CSS
  never styles a closed answer's content: no `::details-content`, no
  generated text, no display or position rule on the answer body (tested).
  Opening it fades the answer in, only when reduced motion is not asked for.
- A header mark: the icon drawn as a 32 px inline SVG, `aria-hidden`, next
  to the unchanged "Queer Frame" link. The same drawing is `/favicon.svg`,
  named by a `<link rel="icon">` on every generated page, served from this site.
- Forced-colors mode (Windows high contrast) hands every color back to the
  system's, as the old rule did.
- A not-found page, `/404.html`, which GitHub Pages serves for any address
  with no page: `noindex`, no canonical, absolute links home and, when they
  are published, to the A to Z list and the airing page.
- The privacy, support and terms pages share the palette, the mark and a
  link home. Their words do not change, and they still have no `<link>`:
  privacy and support are the App Store's URLs, and GuideCore's
  AppStoreReadinessTests hold them to no requests of their own.

**Not changed.** Titles, headings, descriptions, structured data, which
pages exist (apart from the 404), indexing, the app. Every page's bytes
change, so the next IndexNow run (0034) announces every sitemap page once.

**Reversible.** Yes: the previous `style.css`, base template and static
page styles; delete `404.html.j2`, `mark.svg` and the two `write_site`
lines.

## 0039 — About gets an "Email support" row, on iOS and Android (2026-11-06)

**Status: proposed (agent, 2026-11-06). Branch only; it merges when
Chelsea decides, since the app may be in or near App Review.**

**Evidence.** The 2026-11-05 app parity audit found no in-app way to write
to the developer (0 `mailto:` in the app). About had a "Support" button that
opens the support page in the browser, and that page lists the address
(0015), so reaching a person took two apps and a copy. Family Greenhouse,
the portfolio's reference app, has a direct help path.

**Decision.** A row, "Email support", follows "Rate <app name>" in About's
Version section on both platforms. It hands a `mailto:` link to the system
(iOS `openURL`, Android `ACTION_SENDTO`), so the person's own mail app opens
a new message to `chelsea@chelseakr.com` with the subject "<app name>
<version>". The link is built in one tested place per platform (GuideCore
`SupportEmail`, the Android core's `SupportEmail`), and a test checks the
address against the support page and the Play listing. When no mail app
can take it, the row opens the support page instead.

**Privacy.** The app sends nothing: a `mailto:` link names no host and makes
no request (the one-host guards are unchanged), and the draft carries only
the app name and version, never the device model, OS version, favorites or
anything else. The person can edit the subject or not send it.

**Absence.** With no version available, the subject is the app name alone,
not a placeholder.

**Not changed.** The privacy label and Data safety answers, the App Store
and Play copy, the screenshots (the Version section is below the fold on
both About screenshots), and the purchase model: paid up front with no
in-app purchase (0003, 0011, 0018), so there is nothing to restore and no
"Restore purchases" button, by design.

**Reversible.** Yes: remove the row and the two `SupportEmail` files.

## 0042 — A dated findings page on when queer characters die, and a press page (2026-11-06)

**Status: approved by Chelsea (2026-11-06) for findings A to C, on one dated
page, without the non-binary result. Branch only until she merges it.**

**Evidence.** The 2026-11-06 research
(`_agent-tools/growth/qf-progress-and-stats-2026-11-06.md`) matched LezWatch.TV
death dates to TVmaze episode air dates. Recomputed here from the snapshot of
2026-11-06T23:21:02Z and the TVmaze episode lists read that day: of 142 regulars'
deaths placed in an episode, 50 (35%) fall in a season finale, against 8% of
their shows' episodes; guests 11 of 165 (7%), against 8%. The first season holds
27% of placed deaths and 28% of episodes. In ended shows, 32 of 329 deaths (10%)
fall in the series finale, against 3%. LezWatch.TV publishes no statistic that
uses episode or season structure, so these need TVmaze and are new.

**Decision.** `/findings/finales/` states findings A (the headline), B (spread
across seasons) and C (series finales, a supporting line with its sample size),
with the date, method, definitions and caveats on the page, and a counts-only
CSV, `/findings/finales/finales.csv`. Page and CSV are adapted from TVmaze's
CC BY-SA 4.0 data, so both are CC BY-SA 4.0; LezWatch.TV and TVmaze are named
and linked in the text as well as in the footer. `/press/` gives a one-paragraph
description, key facts (price, platform, no data collected, sources), the
findings headline, the contact address, and the app icon and App Store
screenshots from this repository. Both are in the sitemap and linked from the
footer of every generated page.

**Frozen, not nightly.** `qtv_pipeline.findings compute` writes
`pipeline/data/findings_finales.json` from a snapshot and a directory of TVmaze
episode lists; the site build renders the pages from that file. Published
claims change only when the owner regenerates it, and a test pins the approved
figures so a regeneration is a visible change. The templates hold no typed
number (a test fails on any digit outside a template expression).

**Never on the page.** No character, show or episode name, and no list of
deaths (one would be a spoiler list); the data file holds counts only and a
test checks every string in it. Not the non-binary result, which may reflect
recording practice and is sensitive. Not the streaming-versus-broadcast death
rate, which showed no clear difference.

**Reversible.** Yes: drop the two templates, `findings.py`, the data file, the
two sitemap entries and the footer links.
