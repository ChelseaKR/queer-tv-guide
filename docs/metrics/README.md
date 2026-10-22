# Store sales ledger

Queer Frame has no telemetry, so the only sales numbers are the ones each
store reports to its owner. This folder holds them by hand, one row per month
and store, in `store-sales.csv`.

A month with no row is a month nobody has recorded. It is not zero. Add a row
with `0` only when the store's own report says zero units.

## Columns

| Column | Meaning |
|---|---|
| `month` | The calendar month the report covers, `YYYY-MM`. |
| `store` | `app-store` or `google-play`. |
| `units` | Paid units the store reports for that month, a whole number. |
| `source` | Where the number came from: `App Store Connect sales report` or `Play Console statistics`. |
| `recorded_on` | The date you copied it in, `YYYY-MM-DD`. It must fall after the month ends. |

## Adding a month

1. Open the store's own report for the finished month.
2. Append one line to `store-sales.csv`, keeping rows in month order, then
   `app-store` before `google-play`.
3. Run `make policy`. `scripts/check_metrics.py` refuses a malformed row, a
   month that has not ended, a duplicate, and a row out of order.

Nothing here is sent anywhere, and nothing in the app reads it.
