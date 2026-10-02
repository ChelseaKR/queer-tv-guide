# App Store Connect: what to paste and what to answer (draft)

Written 2026-10-02. Nothing here has been submitted. The ordered steps that
use this file are in [`app-store/OWNER-STEPS.md`](app-store/OWNER-STEPS.md);
the reasoning behind the listing (search terms, categories, the review
clauses) stays in [`APP-STORE.md`](APP-STORE.md).

**The listing strings live in one place:**
[`app-store-listing.json`](app-store-listing.json). `AppStoreReadinessTests`
holds them to Apple's limits and keeps them in step with the build (the name
is the display name, iPhone only, the URLs are the pages the app links, the
price is DECISIONS 0011), so they are not copied here. Counts below were
measured with Python's `len()` on the JSON on 2026-10-02.

| Field | Limit | Value | Chars |
|---|---|---|---|
| Name | 30 | `Queer Frame` | 11 |
| Subtitle | 30 | `Does she die? Lesbian TV guide` | 30 |
| Promotional text | 170 | `promotional_text` in the JSON | 168 |
| Keywords | 100 | `keywords` in the JSON | 98 |
| Description | 4,000 | `description` in the JSON | 1,327 |
| Primary category | | Entertainment | |
| Secondary category | | Reference | |
| Price | | USD 4.99, paid up front. No in-app purchase, no subscription (DECISIONS 0003, 0011). | |
| Support URL | | `https://chelseakr.github.io/queer-tv-guide/support.html` | |
| Privacy Policy URL | | `https://chelseakr.github.io/queer-tv-guide/privacy.html` | |
| Marketing URL | | Leave empty. | |
| Copyright | | `2026 [legal name of the account holder]` | |

**Copy rules the JSON keeps** (tested): no "only", "first" or "best"; no
keyword repeats a word of the name or subtitle; no field answers a "does
she die" question or names a show or character.

**Paid up front, as built.** The code has no StoreKit import, no
`.storekit` file and no purchase screen (`make appstore` fails on any of
them), so App Store Connect's price is the whole purchase. The description
already ends "One-time purchase. No subscription, no in-app purchases."

**Not in the description today** (your call, optional): the Up Next home
screen widget and the opt-in new-episode reminders. Both ship. If you want
them named, one line under "Look up a show and see:" would do, for example
`• An Up Next widget and optional new-episode reminders, set on your iPhone.`
(the description would then be 1,403 characters, well under the
limit). Change it in the JSON so the tests see it.

## Content rights

App Information → Content Rights: **Yes**, the app shows third-party
content, and **yes**, you have the rights to use it: LezWatch.TV's published
terms ("You are welcome to use, reuse, and extend the data here for no fees
… We do ask you link back to us, or note us by name") and TVmaze's
CC BY-SA 4.0, with every credit both ask for (DECISIONS 0013; the audit is
in `LICENSES-AND-ATTRIBUTION.md`, the dated terms copies are in
`terms-snapshots/`).

## App Privacy questionnaire

- **Do you or your third-party partners collect data from this app?**
  **No.** The label then reads **Data Not Collected**.
- **Tracking:** none, so no App Tracking Transparency prompt. Both privacy
  manifests say `NSPrivacyTracking` false with no tracking domains.

### Apple's data categories, one by one

App Store Connect asks only the first question when the answer is "No", so
this table is for checking the answer, not for pasting. "Collect", in
Apple's words, means "transmitting data off the device in a way that allows
you and/or your third-party partners to access it for a period longer than
what is necessary to service the transmitted request in real time", and
"data that is processed only on device is not 'collected'"
(developer.apple.com/app-store/app-privacy-details, read 2026-09-18).

| Apple category | Collected? | Why not |
|---|---|---|
| Contact Info (name, email, phone, address) | No | No account, sign-up or form anywhere in the app. The support address is on a web page, outside the app. |
| Health and Fitness | No | No HealthKit, no fitness data. |
| Financial Info | No | The app is bought on the App Store. There is no purchase code in the app at all. |
| Location (precise or coarse) | No | No Core Location. Filters are pickers over the bundled data. |
| Sensitive Info | No | Nothing is asked for or inferred. What someone looks up stays on the iPhone. |
| Contacts | No | No Contacts framework. |
| User Content | No | Favorites are kept in the app's `UserDefaults` on the iPhone and never synced. "Export favorites" writes a file and hands it to the share sheet, where the person chooses where it goes; nothing reaches the developer (ADR 0014). |
| Browsing History | No | No web view. Where-to-watch and source links open outside the app. |
| Search History | No | Search runs over the data on the iPhone; no query is sent anywhere. |
| Identifiers (user ID, device ID) | No | No account ID, no `identifierForVendor`, no advertising identifier. The one request carries no identifier. |
| Purchases | No | Purchase history stays with Apple; the app has no purchase code. |
| Usage Data (product interaction, advertising data) | No | No analytics SDK, no ads, no event logging. |
| Diagnostics (crash, performance) | No | No crash reporter. Crash reports a person chooses to share with Apple are Apple's, not the developer's collection. |
| Other Data | No | The only network request is a conditional GET of the public data file. GitHub Pages, the static host, sees the request's IP address to serve it and logs it "for security purposes"; the developer never receives that log, and the privacy policy says so (DECISIONS 0007). |

Also on the iPhone only: new-episode reminders are local notifications the
iPhone schedules itself, off until the person turns them on (no push
service, no device token), and the Up Next widget reads one small file the
app writes into its own App Group container.

`make appstore` fails if a privacy manifest gains a collected data type or
tracking, if a shipped Swift file imports a non-Apple module, or if the code
calls a required-reason API its bundle's manifest does not declare.
`SourceTreeGuardTests` in `swift test` hold the one-host, one-request and
no-push rules.

## Age rating answers (draft; your call)

App Information → Age Rating. Apple's current tiers are 4+, 9+, 13+, 16+
and 18+, and App Store Connect computes the rating from these answers. The
app depicts nothing: it shows text from LezWatch.TV (plot notes, behind a
spoiler disclosure; tropes; content-note levels) and TVmaze (episode
titles and dates). The draft answers describe that text honestly. Measured
on the snapshot generated 2026-10-01T09:47:11Z (2,280 shows, 7,406
characters; 10,341 show summaries, show notes and longer character text
fields): "murder" appears in 116 of them, "suicide" in 12, "rape" in 6,
"drug" in 23, "alcohol" in 6, and "fuck" or "shit" in 7. There are no
images and nothing explicit.

| Questionnaire item | Draft answer | Why |
|---|---|---|
| Parental controls | No | |
| Age assurance | No | |
| Unrestricted web access | No | No web view; links open outside the app. |
| User-generated content | No | Nothing is posted or shared between people. |
| Messaging and chat | No | |
| Advertising | No | |
| Profanity or crude humor | Infrequent | A handful of plot notes quote profanity. |
| Horror or fear themes | None | Genre labels only; nothing depicted. |
| Alcohol, tobacco or drug use or references | Infrequent | Plot notes mention drugs and alcohol. |
| Medical or treatment information | None | |
| Health or wellness topics | None | |
| Mature or suggestive themes | Infrequent | Tropes and plot notes name sex work, coming out, queerbashing, relationships. |
| Sexual content or nudity | None | Text mentions only; no sexual content is shown. |
| Graphic sexual content and nudity | None | |
| Cartoon or fantasy violence | None | |
| Realistic violence | Infrequent | Character deaths, murders and violence are named in text, never shown. |
| Prolonged graphic or sadistic realistic violence | None | |
| Guns or other weapons | None | |
| Simulated gambling, contests, gambling, loot boxes | None / No | |

Expected result: **13+**, as `APP-STORE.md` has planned since 2026-09-17.
These are judgment calls. Answering "None" where the table says
"Infrequent" would understate what the plot notes say, and answering
"Frequent" would overstate a text guide. If App Store Connect computes a
higher rating than you want, change an answer only if it is still true.

## App Review notes

Paste everything between the two rules into App Review Information →
Notes. Sign-in required: **off** (there are no accounts). The limit is
4,000 characters; this block is 2,664, measured with Python's `len()` on
the text between the rules.

---

No account or sign-in exists in this app, so no demo account is needed.

WHAT IT DOES
Queer Frame is a guide to TV shows with queer women, non-binary and trans characters. For each show it answers "is it worth watching?" and "do any queer characters die?", with that second answer hidden until the person taps to reveal it, so they find out only when they choose to. To see it: Search, open any show, then tap "Do any queer characters die?". The app also has filters (worth it, no recorded deaths, has a where-to-watch link), tropes and content notes, where-to-watch links, the next episode, local favorites, opt-in reminders and a home screen widget. It works fully offline from a bundled copy of its data (4.2).

DATA SOURCES, LICENSES AND ATTRIBUTION (5.2.2)
1. LezWatch.TV (https://lezwatchtv.com): shows, characters, recorded deaths, ratings, tropes and where-to-watch links, from its public API. Its terms of use (https://lezwatchtv.com/tos/) say: "You are welcome to use, reuse, and extend the data here for no fees … We do ask you link back to us, or note us by name." Every show and character screen links to its LezWatch.TV page ("View on LezWatch.TV"), and the About screen names LezWatch.TV with a link.
2. TVmaze (https://www.tvmaze.com): episode schedules, from its API, licensed CC BY-SA 4.0 (https://www.tvmaze.com/api, "Licensing"). Every next-episode line is shown with "Schedule data from TVmaze", linked, and the CC BY-SA 4.0 license, linked.
The About screen states: "LezWatch.TV and TVmaze do not endorse this app." No images or articles are used. The combined data file is published under CC BY-SA 4.0 at https://chelseakr.github.io/queer-tv-guide/snapshot.v1.json, with its license and credits.

NETWORK AND PRIVACY
The app makes one network request: an HTTPS GET of the data file above, when the app opens, on pull to refresh, or when it returns to the foreground with data more than 3 days old (at most every 6 hours). It is conditional on an ETag, so an unchanged file transfers nothing. No accounts, analytics, ads or third-party SDKs. Privacy label: Data Not Collected.

REMINDERS ARE LOCAL
New-episode reminders are local notifications scheduled on the iPhone. There is no push service, no APNs and no device token, and no background mode. To see them: favorite a show, open Favorites, and turn on "New-episode reminders"; the app explains first, and iOS asks for notification permission only then, never at launch.

WIDGET
The Up Next widget reads one small file the app writes into its own App Group container. It makes no network request.

PURCHASE
Paid up front on the App Store. There is no in-app purchase and nothing to unlock.

---

## Before pasting: open items

| Item | Blocks | Status |
|---|---|---|
| Support contact on `support.html` | Support URL (guideline 1.5) | Added on this branch (`chelsea@chelseakr.com`); live after the next nightly run. OWNER-STEPS step 5. |
| Screenshots | Version page | Regenerate before upload: the five in `app-store/screenshots/` date from 2026-09-18 and predate the opaque status strip and filter bar (#48) and the first-run page changes (#77). OWNER-STEPS step 9. |
| Trademark screen for "Queer Frame" | Name | Not run. OWNER-STEPS step 1. |
| Age rating answers | App Information | Draft above; yours to confirm. |
| Storefronts | Pricing and Availability | Yours. OWNER-STEPS step 1. |
