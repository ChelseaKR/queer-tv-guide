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
and everything 0019 to 0024 decided about what a page says, stand.**

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
the page's character list already shows (`show_pages.identity`): LezWatch.TV
lists queer women, non-binary and trans characters, so its "Homosexual" on a
cisgender character or a woman reads "lesbian"; other sexualities are used
as they are; "Heterosexual", "Undefined" and "Not Straight" fall back to a
non-cisgender gender ("trans woman"), or no label. Labelled names come
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

