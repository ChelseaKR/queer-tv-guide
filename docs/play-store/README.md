# Google Play kit

Everything for publishing Queer Frame for Android (DECISIONS 0018) on
Google Play, in the order you need it. The iPhone app's kit is
[`../app-store/`](../app-store/README.md).

- [`OWNER-STEPS.md`](OWNER-STEPS.md): the ordered owner steps from a Play
  Console account to a production release, including the closed test that
  new personal developer accounts must run first, and what is already done.
- [`play-listing.json`](play-listing.json): the store listing strings
  (title, short and full description), the store settings, price and
  countries, and the draft App content answers (Data safety, content
  rating, target audience), each with its reason. The one copy to paste
  from.

The readiness check behind "already done" is `make playstore`
(`scripts/check_play_store.py`), part of `make verify` and CI's pipeline
job. It holds the JSON to Play's limits and the copy rules, and the Data
safety and content-rating answers to what the Android build does. Nothing
in this folder has been submitted to Google.
