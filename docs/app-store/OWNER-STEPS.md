# Owner steps: from here to "Submitted for Review"

Written 2026-10-02. This is the one ordered list of what is left before
Queer Frame can be submitted, and every step on it needs the owner: an
Apple ID, App Store Connect, a signing key, a legal or payment form, or a
decision. Everything an agent can do in the repository is done, and is
listed in [What is already done](#what-is-already-done) so you can check it
rather than redo it.

Values in `code` are exact; paste them as they are. What to paste and what
to answer in App Store Connect is in
[`docs/APP-STORE-LISTING.md`](../APP-STORE-LISTING.md); the listing strings
themselves are in [`docs/app-store-listing.json`](../app-store-listing.json).
The reasoning (search terms, categories, review clauses, the privacy check
against the code) is in [`docs/APP-STORE.md`](../APP-STORE.md).

## Values used below

| Field | Value | Where it comes from |
|---|---|---|
| App name | `Queer Frame` | DECISIONS 0006; `INFOPLIST_KEY_CFBundleDisplayName` in `ios/Config/Product.xcconfig` |
| Bundle ID (app) | `com.chelseakr.queertvguide` | `ios/Config/Product.xcconfig`. It keeps its working name (DECISIONS 0006) and can't change once registered. |
| Bundle ID (widget) | `com.chelseakr.queertvguide.widgets` | `ios/Config/Widgets.xcconfig` |
| App Group | `group.com.chelseakr.queertvguide` | both `.entitlements` files |
| Team ID | `6X5YH93QNM` | `DEVELOPMENT_TEAM` in `ios/Config/Shared.xcconfig`. Never `ACKGM9XK9V`, which is the enrollment ID; `make appstore` fails if it appears. |
| SKU | `queer-frame-ios` (suggested) | Any unique string; it can't be changed later. |
| Price | USD 4.99, paid up front | DECISIONS 0003, 0011, confirmed in 0015. No in-app purchase, no subscription. |
| Storefronts | United States only | DECISIONS 0015. No Digital Services Act trader declaration. |
| Version, build | `1.0.0`, build `1` | `MARKETING_VERSION`, `CURRENT_PROJECT_VERSION` in `ios/Config/Shared.xcconfig`; DECISIONS 0015 |
| Support URL | `https://chelseakr.github.io/queer-tv-guide/support.html` | DECISIONS 0010; 200 on 2026-10-02 |
| Privacy Policy URL | `https://chelseakr.github.io/queer-tv-guide/privacy.html` | DECISIONS 0007; 200 on 2026-10-02 |

## 1. Decided, and what is still yours

Decided 2026-10-02 and recorded in DECISIONS 0015:

- **Version: 1.0.0**, build 1. The project already says so in every
  target, and `CHANGELOG.md` has a `## [1.0.0] - TBD` section that step 9
  fills in.
- **Storefronts: United States only.** So no Digital Services Act trader
  declaration is needed.
- **Age rating: the answers in `APP-STORE-LISTING.md` are confirmed**,
  expected to compute **13+**.
- **Price: USD 4.99, paid up front**, no in-app purchase (confirmed).
- **Support contact: kept** on the support page (step 5).

Done 2026-10-02:

- **Trademark screen for "Queer Frame": done, no conflict found**
  (recorded under DECISIONS 0006). The official USPTO trademark search
  (`https://tmsearch.uspto.gov/`, a word search typed into the search box),
  the US App Store search API, and the Justia, uspto.report and Trademarkia
  mirrors found no "QUEER FRAME" mark and no app by that name. The nearest
  marks were QUEER EYE (live, classes 41 and 25, Scout Productions) and the
  dead QUEER TV and QUEER TELEVISION. This is a screen, not legal advice;
  an attorney's clearance search is the standard next step for certainty.

Still yours:

1. **Optional description line** for the widget and reminders
   (`APP-STORE-LISTING.md`, "Not in the description today").

## 2. Merge what the build depends on

1. This branch, `agent/qf-appstore` (readiness check, release workflow,
   these docs).
2. Optional for the first version: the open app pull requests in the merge
   queue. If any that change a screen go in, regenerate the screenshots
   afterwards (step 9).

## 3. Xcode on your Mac

- First-launch content: **already installed** (checked 2026-10-02:
  `xcodebuild -checkFirstLaunchStatus` exits 0 with Xcode 26.6). If that
  ever exits non-zero, run this in **Terminal.app** (it asks for your
  password, which can't pass through an agent session):
  `sudo xcodebuild -runFirstLaunch`
- Sign in: Xcode → Settings → Accounts → **+** → Apple ID, and check that
  team `6X5YH93QNM` is listed. Interactive; only you can do it.

## 4. Agreements, tax and banking

App Store Connect → **Business**: the **Paid Applications Agreement** must
be **Active**, with tax forms and a bank account done; a paid app can't go
on sale without it. The agreement is once per developer account, so if you
already completed it for Trout Truck, there is nothing more to do here.
The App Store Small Business Program (15%, DECISIONS 0011) is also once
per account: enroll if you haven't.

## 5. Support contact

Guideline 1.5 asks for a Support URL that gives an easy way to reach you.
This site has no build variable for it: `docs/site/support.html` is a static
page the nightly `snapshot` workflow copies as it is, so no
`gh variable set` is involved. This branch adds the address you chose on
2026-10-01, `chelsea@chelseakr.com`, as a `mailto:` line in the Contact
section of the support page, in its own commit; the privacy policy already
sends questions to that page. Check the line, and after the next nightly
run check that the live page shows it. If you drop that commit, the
`TODO(owner)` marker comes back and `make -C ios presubmit-check` fails
again until a contact is added.

## 6. Register the identifiers

developer.apple.com → Certificates, Identifiers & Profiles:

1. Identifiers → **+** → App Groups: `group.com.chelseakr.queertvguide`.
2. Identifiers → **+** → App IDs → App: Description `Queer Frame`, Bundle ID
   **Explicit** `com.chelseakr.queertvguide`, capability **App Groups**
   with the group above. Nothing else: no Push Notifications (reminders are
   local), no iCloud.
3. The same for the widget: Description `Queer Frame Widget`, Bundle ID
   **Explicit** `com.chelseakr.queertvguide.widgets`, **App Groups** with
   the same group.

Xcode's automatic signing can create these on the first archive, but the
app's ID has to exist before step 7 can select it.

## 7. Create the app record

App Store Connect → Apps → **+** → New App: Platform **iOS**; Name
`Queer Frame`; Primary Language **English (U.S.)**; Bundle ID
`com.chelseakr.queertvguide`; SKU `queer-frame-ios`; User Access
**Full Access**.

## 8. Fill in the record

Paste from `docs/app-store-listing.json`; answer from
`docs/APP-STORE-LISTING.md`.

1. **App Information:** Subtitle; Category Primary **Entertainment**,
   Secondary **Reference**; Content Rights **Yes**, with the rights
   (`APP-STORE-LISTING.md`, "Content rights"); **Age Rating**: the confirmed
   answers in the listing file (13+).
2. **Pricing and Availability:** price **USD 4.99**, paid up front.
   Availability: **United States** only (deselect every other country or
   region). With no EU storefront, skip the Digital Services Act trader
   declaration.
3. **App Privacy:** Privacy Policy URL from the table above; "Do you or your
   third-party partners collect data from this app?" **No**. The label
   becomes **Data Not Collected**. Publish the answers.

## 9. Prepare the release commit (a normal pull request)

On a branch from `main`:

1. The version is already `1.0.0`, build `1`, in every target. For any
   later upload, including a re-upload of 1.0.0 after a rejection, raise
   `CURRENT_PROJECT_VERSION` in `ios/Config/Shared.xcconfig` (the release
   workflow refuses a build number that isn't higher than every earlier
   tag's).
2. In `CHANGELOG.md`, replace `TBD` in `## [1.0.0] - TBD` with the date
   (`YYYY-MM-DD`), replace the placeholder paragraph with the release
   notes, and move what ships from `[Unreleased]` into it. The release
   workflow refuses the section while it says TBD, and `make appstore`
   fails if the app's version has no section at all.
3. Regenerate the screenshots with no other simulator work running:
   `make -C ios bundle-snapshot`, then `make -C ios screenshots`. Look at
   the five images before committing them: every reveal must be closed.
4. `make verify` passes (it runs `make appstore`), then open the pull
   request and merge it once its checks are green.

## 10. Tag and run the release workflow

Optional before the first tag (issue #21): a tag ruleset over
`refs/tags/v*` so a release tag can't be moved or deleted. The bypass
list is your call; the portfolio's rule against an empty bypass list
applies.

From a clone whose `origin` is `ChelseaKR/queer-tv-guide`, on the merged
`main`, up to date with GitHub. Tag the tip of `main` and dispatch right
away: the run builds the commit `main` points at when it is dispatched and
refuses if the tag is on any other commit. If something merges first, cut
the next patch version from the new tip. The tag is signed with your
release-signing key, whose public half is committed in
`.github/allowed_signers`:

    git config gpg.format ssh
    git config user.signingkey ~/.ssh/github-release-signing.pub
    git tag -s v1.0.0 -m "release: v1.0.0"
    git push origin v1.0.0
    gh workflow run ios-release.yml --repo ChelseaKR/queer-tv-guide -f tag=v1.0.0

`ios-release` verifies the
tag's signature and that it is on the dispatched commit, checks that the
tag matches `MARKETING_VERSION`, that the build number is higher than every
earlier release's and that the CHANGELOG section is there and dated, runs
the readiness check and the GuideCore tests, archives the app **unsigned**
for a generic iOS device, reads the archived app and widget back
(versions, name, bundle IDs, iPhone only, export compliance, privacy
manifests, required-reason symbols, no StoreKit, no framework), and
creates a **draft** GitHub Release with the notes and a
`release-stamp.json`. It never signs or uploads anything. If it fails, fix
the cause on `main` and cut the next patch version; release tags aren't
moved.

## 11. Archive and upload from Xcode

1. `git checkout v1.0.0` (the commit the workflow verified).
2. `make -C ios bundle-snapshot`: the app ships the snapshot that is
   current when you archive (it is gitignored, so the tag can't pin it).
   It checks the published checksum and refuses a fixture.
3. Open `ios/QueerTVGuide.xcodeproj`, scheme **QueerTVGuide**, destination
   **Any iOS Device (arm64)**, Product → **Archive**. Signing: automatic,
   team `6X5YH93QNM`.
4. Organizer → the archive → **Validate App**, then **Distribute App** →
   **App Store Connect** → Upload. Export compliance isn't asked: the build
   sets `ITSAppUsesNonExemptEncryption` to NO (the only encryption is iOS's
   own HTTPS).
5. Optional: Organizer → the archive → **Generate Privacy Report**. It
   should list no collected data and one required-reason API, UserDefaults
   (`CA92.1`), matching `PrivacyInfo.xcprivacy`.

## 12. TestFlight, internal testing

Once the build finishes processing: TestFlight → Internal Testing → add
yourself → install on your iPhone, then check:

- Airplane mode on, first launch: the app opens on its bundled data and
  says how old it is.
- A show: "Do any queer characters die?" is closed until you tap; "View on
  LezWatch.TV" opens the show's page; the next episode credits TVmaze with
  its license link.
- About: both sources, their licenses, "LezWatch.TV and TVmaze do not
  endorse this app", the privacy and support links.
- Favorites → "New-episode reminders": the explanation comes first, and iOS
  asks for notification permission only after "Turn on reminders".
- Add the Up Next widget: it lists your favorites' next episodes.

## 13. Version page and submit

On the iOS App version page:

1. **Screenshots → iPhone 6.9" Display:** the five PNGs in
   `docs/app-store/screenshots/`, in numbered order. iPhone only, so no
   iPad set.
2. **Promotional Text, Description, Keywords, Support URL, Copyright:**
   from the JSON and the listing file.
3. **Build:** **+** → the uploaded build.
4. **App Review Information:** Sign-in required **off**; your name, phone
   and email; **Notes:** the block in `APP-STORE-LISTING.md`.
5. **Version Release:** **Manually release this version**.
6. **Add for Review → Submit to App Review.**

After approval, press **Release**, then publish the draft GitHub Release
for the same tag.

## What is already done

Checked 2026-10-02 against the code on this branch. `make appstore`
re-checks the first six on every `make verify` and every pull request.

- One version and one integer build number for every target, set only in
  `ios/Config/Shared.xcconfig`; the widget's Info.plist takes both from
  the build settings, and the app's Info.plist is generated from them.
- iPhone only (`TARGETED_DEVICE_FAMILY = 1` in every target and
  configuration), team `6X5YH93QNM` for device builds, iOS 17.0 minimum.
- Export compliance declared (`ITSAppUsesNonExemptEncryption` NO), a
  generated launch screen, display name `Queer Frame`, and no background
  mode.
- Privacy manifests for the app and the widget: no tracking, no tracking
  domains, no collected data, and every required-reason API the shipped
  Swift calls declared (the app: UserDefaults, `CA92.1`; the widget:
  none).
- No third-party code: every shipped import is an Apple framework or the
  local GuideCore package, the project has no remote package, and there is
  no StoreKit code or configuration (paid up front).
- Entitlements: the one App Group, nothing else (no push, no iCloud).
- App icon: every size it names plus the 1024x1024 marketing image, all
  opaque.
- Listing strings within Apple's limits and in step with the build
  (`AppStoreReadinessTests`, in `swift test`).
- Privacy policy and support pages are live on the snapshot host and
  linked from About.
- A release workflow (`.github/workflows/ios-release.yml`) and the signer
  file it verifies against (`.github/allowed_signers`).
