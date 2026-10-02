# App Store kit

Everything for submitting the Queer Frame iOS app, in the order you need it:

- [`OWNER-STEPS.md`](OWNER-STEPS.md): the ordered owner steps from here to
  "Submitted for Review", the decisions to settle first, and what is
  already done.
- [`../app-store-listing.json`](../app-store-listing.json): the listing
  strings (name, subtitle, promotional text, keywords, description,
  categories, price, URLs), the one copy to paste from.
  `AppStoreReadinessTests` holds them to Apple's limits and to the build.
- [`../APP-STORE-LISTING.md`](../APP-STORE-LISTING.md): measured character
  counts, content rights, the App Privacy answers with the reasoning per
  Apple data category, the draft age-rating answers, and the App Review
  notes.
- [`../APP-STORE.md`](../APP-STORE.md): the reasoning behind the listing
  (search terms, categories), the privacy check against the code, and the
  review clauses that apply.
- [`screenshots/`](screenshots/): the iPhone 6.9" screenshots, made by
  `make -C ios screenshots` from the snapshot bundled with the app.

The readiness check behind "already done" is `make appstore`
(`scripts/check_app_store.py`), and the release workflow is
`.github/workflows/ios-release.yml`.
