# `data/samples/` — the publishable sample

**This directory never contains the raw parquet.** It contains `sample.csv`, a k-anonymised
aggregate that is safe to publish, and the manifest that lets a reader check it.

| | |
|---|---|
| Rows | 3610 |
| Grain | one row per **postcode × day** |
| Codes | 17 (only those passing all three privacy gates) |
| Suppressed rows | 3458 of 7068 code-day pairs (below k = 3 transactions or 3 merchants) |
| SHA-256 (first 16) | `6731376affb7ccbd…` |

## What is in it

`postcode, date, weekday_iso, month, transactions, transactions_dated, amount_pln, merchants,
temperature_mean_c, rainy_fraction, wind_speed_mean_kmh, event_listings_count`

## What is deliberately absent

Card identifiers, merchant names, transaction identifiers, **times of day**, and any per-transaction
record. The hourly curve — the panel's actual product — cannot be reconstructed from this file.

## Why `transactions_dated`

10.2 % of the source rows carry the sentinel timecode `'000000'` (defect D2). `transactions` counts
every row for that code-day; `transactions_dated` counts only the rows with a real timecode. Both
are published so the hole is visible instead of silently shrinking the totals.

## Regenerating

```sh
python3 -m pipeline.run --src <DIR with mcc5812_transactions.part0*.parquet> --out artifacts
```

The manifest records the sha256 of the CSV, so a diff is a one-line check.
