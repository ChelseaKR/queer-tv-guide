# Owner steps: Queer Frame for Android, from here to Google Play

Written 2026-10-17. This is the ordered list of what is left before Queer
Frame for Android can be on Google Play, the Play twin of
[`../app-store/OWNER-STEPS.md`](../app-store/OWNER-STEPS.md). Every step
needs the owner: a Google account, Play Console, a payments profile, an
upload key, testers, or a decision. What an agent can do in the repository
is listed in [What is already done](#what-is-already-done) so you can check
it rather than redo it. Nothing here has been submitted anywhere.

Values in `code` are exact. The listing strings and the App content answers
are in [`play-listing.json`](play-listing.json), the one copy to paste
from; `make playstore` (part of `make verify` and every pull request) holds
them to Play's limits and to the build.

**Not checked against Google's pages this session.** Google's help pages
could not be fetched from this environment on 2026-10-17. The closed-test
rule below is from search results quoting Play Console Help ("App testing
requirements for new personal developer accounts"); the rest is how Play
Console has worked. Where a step depends on a rule that could have
changed, it says "check", and Play Console's own wording wins.

## Values used below

| Field | Value | Where it comes from |
|---|---|---|
| App name | `Queer Frame` | DECISIONS 0006; `app_name` in `android/app/src/main/res/values/strings.xml` |
| Package name | `com.chelseakr.queertvguide` | `applicationId` in `android/app/build.gradle.kts`; DECISIONS 0018. It can't change once an app is created. |
| Version | `1.0.0`, version code `1` | `versionName`, `versionCode` in `android/app/build.gradle.kts`, the same as the iOS app |
| Price | USD 4.99, paid up front | DECISIONS 0011, 0018. No in-app purchase, no subscription, no ads. |
| Countries | United States only | DECISIONS 0015, 0018 |
| Category | Entertainment | as on the App Store |
| Contact email | `chelsea@chelseakr.com` | the support page (DECISIONS 0015). Play shows it on the listing. |
| Website | `https://chelseakr.github.io/queer-tv-guide/support.html` | DECISIONS 0010 |
| Privacy policy | `https://chelseakr.github.io/queer-tv-guide/privacy.html` | DECISIONS 0007; it has the Android section 0018 asked for |

## 1. Decided, and what is still yours

Decided in DECISIONS 0018 (accepted 2026-10-12): native app, package name,
version 1.0.0, paid at the US price equivalent of $4.99, no in-app
purchase, no ads, United States only, no Play In-App Review, no Google
cloud backup of favorites, Data safety "No data collected" and "No data
shared".

Still yours, before step 2:

1. **Account type.** A personal account is the usual choice for one
   person; an organization account needs a D-U-N-S number. The closed-test
   rule in step 6 applies to personal accounts created after 2023-11-13.
2. **Target audience** (step 8): the draft is 13 and over (`13-15`,
   `16-17`, `18 and over`), matching the iOS rating of 13+. Confirm or
   change it in `play-listing.json`.
3. **Content rating answers** (step 8): the draft repeats the iOS answers
   you confirmed on 2026-10-02. Confirm them for Play.
4. **Refunds on the support page.** `docs/site/support.html` says
   "Purchases are handled by Apple" and links Apple's refund page. Android
   buyers need Google Play's refund route there too, before launch. It is
   not added: the page's Android wording is a decision, and the site's
   tests allow Android wording only inside marked regions of
   `privacy.html` (`pipeline/tests/test_app_store.py`), so adding it to
   `support.html` also adds that page to the allowed list.

## 2. Play Console developer account

play.google.com/console: sign up with the Google account that will own
the app, pay the one-time registration fee (US$25), and complete identity
verification. New personal accounts may also be asked to verify a phone
number and access to an Android device. This is interactive; only you can
do it.

## 3. Payments profile (merchant account)

A paid app needs a Google payments profile linked to the developer account:
Play Console → **Setup → Payments profile**. It holds your legal name,
address, tax information and bank account for payouts. Check what Play
Console says it will show publicly: developer accounts that sell apps have
been asked for an address that Google may display on the store listing.

## 4. Upload key and app bundle

Google Play requires an Android App Bundle (`.aab`) for new apps, signed
with your **upload key**; Play App Signing then signs what users install
with a key Google holds.

1. Make an upload key once, outside the repository:
   `keytool -genkeypair -v -keystore ~/keys/queer-frame-upload.jks -alias upload -keyalg RSA -keysize 4096 -validity 10000`
   Keep the file and its password in your password manager. If it is lost,
   Play can reset an upload key, but only through support.
2. Create `android/signing.properties` (gitignored, as are `*.jks` and
   `*.keystore`; `make playstore` fails if those ignore lines go):

       storeFile=/Users/you/keys/queer-frame-upload.jks
       storePassword=…
       keyAlias=upload
       keyPassword=…

   `android/app/build.gradle.kts` signs release builds with it only when
   the file is there; CI builds unsigned.
3. `make -C android verify` passes, then
   `cd android && ./gradlew --no-daemon :app:bundleRelease`. The bundle is
   `android/app/build/outputs/bundle/release/app-release.aab`.

Each later upload needs a higher `versionCode` in
`android/app/build.gradle.kts`; keep `versionName` equal to the iOS
`MARKETING_VERSION` (`make playstore` checks it).

## 5. Create the app

Play Console → **Create app**: App name `Queer Frame`; default language
**English (United States) – en-US**; **App**; **Paid**; accept the
declarations.

**Paid, from the start.** Choose Paid here, before anything is released on
any track. An app released as free cannot later be made paid.

## 6. Closed test: 12 testers for 14 days

For a personal developer account created after 2023-11-13, Play Console
keeps the Production track closed until a closed test has run with **at
least 12 testers who have stayed opted in for at least 14 consecutive
days**. Then **Apply for production** asks about the test, and Google
reviews the application (search results quoting Play Console Help, read
2026-10-17; check the current numbers in Play Console's Dashboard, which
shows the requirement and your progress).

1. **Testing → Closed testing → Create track** (or use the default
   "Closed testing - Alpha"). Testers: an email list of the Google
   accounts of at least 12 people, more if you can, because someone who
   opts out or uninstalls during the window can stop the count.
2. Create a release on that track with the `.aab` from step 4, release
   name `1.0.0 (1)`, and release notes such as "First test of Queer Frame
   for Android." Roll it out to the track.
3. Share the opt-in link with the testers. Each one opts in, then installs
   from Google Play.
4. **Check the paid-app rule for testers.** The app is paid. Check Play
   Console Help ("Set up an open, closed, or internal test") for whether
   closed testers must buy a paid app to install it, before inviting
   anyone, so nobody is charged by surprise.
5. Keep at least 12 opted in for 14 consecutive days. What to ask testers
   to look at is the TestFlight list in
   [`../app-store/OWNER-STEPS.md`](../app-store/OWNER-STEPS.md) step 12,
   on Android: airplane mode first launch, the closed reveal, About's
   credits and "do not endorse" line, reminders asking for notification
   permission only after "Turn on reminders", the Up Next widget.
6. Dashboard → **Apply for production** once the requirement shows met.

## 7. Store listing

**Grow → Store presence → Main store listing**, from `play-listing.json`:

| Field | Value | Limit |
|---|---|---|
| App name | `title` | 30 |
| Short description | `short_description` | 80 |
| Full description | `full_description` | 4,000 |

The copy is the approved App Store copy (`docs/app-store-listing.json`),
with the subtitle and the promotional text's "hidden until you tap" as the
short description, and two changes to the description for Android:
"Favorites stay on your phone" and "No tracking code" in place of "No
third-party SDKs" (the Android app links AndroidX and Kotlin libraries;
the privacy policy names them). Spoiler-safe as on iOS: no field names a
show or a character, or answers "does she die".

Graphics, which the repository does not have yet:

- **App icon:** 512 × 512 PNG. Export it from the launcher icon
  (`android/app/src/main/res/drawable/ic_launcher_*.xml`) or from the iOS
  1024 × 1024 icon, so the two stores match.
- **Feature graphic:** 1024 × 500, no transparency.
- **Phone screenshots:** at least two. `android/scripts/screenshots.sh
  <out-dir> phone` runs the screenshot tour on a connected device in light
  and dark. Look at every image before uploading: every reveal closed. A
  7-inch and a 10-inch tablet set are optional; the app has a tablet
  layout, so the same script on a tablet emulator, named `tablet`, makes
  them.

**Store settings:** category **Entertainment**; contact email and website
from the table above. Tags are optional; choose ones that describe what is
on screen (TV, guides), never another app's name.

## 8. App content

**Policy and programs → App content.** Each answer is in
`play-listing.json`, with its reason.

1. **Privacy policy:** the URL above.
2. **App access:** all functionality is available without special access
   (no account, no login).
3. **Ads:** No.
4. **Content rating:** the IARC questionnaire, from `content_rating`.
   Category: the reference, news or educational one; the app shows text
   about TV shows. Violence, sexual themes, language and drug or alcohol
   references appear as text in plot notes and tropes, never as images,
   so answer them as text references, as on iOS. User interaction,
   location sharing, digital purchases, unrestricted internet and gambling
   are No, and the build is held to that (`make playstore`). IARC computes
   the ratings; if one is higher than you want, change an answer only if
   it is still true.
5. **Target audience and content:** `target_age_groups`; the app is not
   designed to appeal to children.
6. **News app:** No.
7. **Data safety:** from `data_safety`. "Does your app collect or share
   any of the required user data types?" **No.** The listing then shows
   "No data collected" and "No data shared with third parties". Accounts:
   the app does not let anyone create one, so no deletion URL is needed.
   Why it is true: the one request is a GET of the public data file with
   no account, cookie or identifier; GitHub, which serves it, logs IP
   addresses for security and the developer never receives that log
   (DECISIONS 0007, stated in the privacy policy); favorites stay on the
   device, out of cloud backup; reminders are local; no analytics, crash
   reporting, ads, Firebase or Play services library is linked
   (`SourceGuardTest`, `make playstore`).
8. **Government apps, financial features, health:** none apply.
9. **Foreground service and other permission declarations:** the app
   declares three permissions (internet, network state, notifications).
   WorkManager's own manifest adds a few at build time, including a
   foreground-service declaration the app never starts. If Play Console
   asks about one, answer from the merged manifest a release build writes
   under `android/app/build/intermediates/`, not from memory.

## 9. Pricing and countries

**Monetize → Products → App pricing:** USD 4.99. **Production → Countries
/ regions:** United States only (and the same for the closed-testing
track). No in-app products, no subscriptions.

## 10. Production release

After production access is granted:

1. **Publishing overview → Managed publishing: on**, so an approved
   release waits for you to press **Publish**, as "Manually release this
   version" does on iOS.
2. **Production → Create new release:** the same `.aab` the testers
   used, or a newer one with a higher `versionCode`; release notes from
   the CHANGELOG.
3. **Send for review.** When it is approved, publish it.

Rollback: Play cannot reinstall an older build on people's phones. Halt a
staged rollout if one is running, or release a fixed build with a higher
`versionCode`. The data file is shared with iOS, so a bad snapshot is
fixed by republishing the previous one.

## What is already done

Checked 2026-10-17 against the code on this branch. `make playstore`
re-checks the first five on every `make verify` and every pull request;
`make android` (CI, Linux) runs the rest.

- The listing strings within Play's limits and the copy rules, the title
  the app's name, and the package, version name, version code and price in
  step with the build and the App Store listing.
- The privacy policy has its Android section, and the support page lists
  the contact email the listing uses.
- The Data safety answer matches the build: three permissions; no Play
  services, Play Core, In-App Review, Firebase, analytics, ads or billing
  library; no web view, location, advertising ID or Android ID; nothing in
  cloud backup.
- Target SDK 36, above Play's floor for new apps.
- The upload key and `signing.properties` are gitignored, and release
  builds sign with them only when they are present.
- The app itself, at parity with iOS and with its own source guard
  (DECISIONS 0018): `make -C android verify`.
