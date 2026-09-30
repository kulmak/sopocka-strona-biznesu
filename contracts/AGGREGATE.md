# Aggregate contract `aggregate.json` — v4

**Owner:** `pipeline/aggregate.py` (writer) · `app/` (reader) · `contracts/aggregate.schema.json` (schema)
**Status:** FROZEN. Changes require bumping `ver` and updating all three places in the same commit.

## Why this contract exists

The panel used to read 26 MB of parquet in the browser (pure-JS ZSTD decode + IndexedDB cache). That
cost 2.9–5.6 s cold (23–28 s on a 10 Mbit/s link), and for the first 1.4–2.7 s it displayed
**fabricated** numbers labelled `Dane przykładowe` — numbers that look *better* than the real ones.
It also meant the app could not be deployed without publishing Organiser Data.

`aggregate.json` is the precomputed, privacy-gated replacement. It is the only data file the app reads.

## Top-level shape

```jsonc
{
  "ver": 4,                       // contract version; the app refuses any other value
  "generated": "2026-09-30T05:00:00+02:00",
  "source": {
    "files": ["mcc5812_transactions.part01.parquet", "..."],
    "sha256": ["9fc82163…", "aecb77de…"],
    "rule_version": "sopot-city-labels-only-v1+geo-cleanup-v1"
  },

  "start": "2025-01-01",          // day index 0
  "days": 546,                    // day axis length (inclusive of both ends)
  "hours": 24,

  "codes": ["—", "81-704", "81-720", "81-777", "…"],   // index 0 = EXCLUDED bucket
  "codeMeta": {
    "81-777": {
      "name": "Molo i Plac Zdrojowy",      // Polish display label (street-derived, honest)
      "merchants": 241,                     // distinct merchant descriptors, whole period
      "transactions": 193234,
      "centroid": [54.4466, 18.5700],
      "polygonConfidence": "observed",      // observed | inferred | extrapolated | none
      "gates": { "g1_cards": true, "g2_merchants": true, "g3_share": true, "all": true },
      "nCards": 96817,
      "top1Share": 0.1144
    }
  },

  "cnt": "<base64>",              // Uint16Array, length codes.length * days * 24
  "amt": "<base64>",              // Uint16Array, WHOLE złoty, same length
  "amtScale": 1,                  // multiply decoded amt by this to get zł
  "nat": "<base64>",              // Uint32Array, length days * 24 * 6  (city-wide only)

  "eventsByDay": { "2026-06-20": ["Koncert letni na Molo", "…"] },

  "rows": 378212,
  "excluded": {
    "zeroTimecode": 38443,        // tran_id_gmt_tm == '000000' — kept in `cnt`, NOT in hourly views
    "nonSopotPostcode": 2527,     // Sopot city label, foreign postcode → index 0
    "noPostcode": 6431            // NULL postcode → index 0
  },

  "presets": [                    // the three demo states; every one must pass tools/demo_ready.py
    { "id": "molo",   "code": "81-777", "name": "Restauracja przy Molo",
      "lat": 54.4466, "lng": 18.5700, "why": "241 merchantów, 51.1% wolumenu" },
    { "id": "monciak","code": "81-759", "name": "Bistro na Monciaku",
      "lat": 54.4447, "lng": 18.5625, "why": "39 merchantów, pełne 18 miesięcy" },
    { "id": "przystan","code": "81-777","name": "Bar na plaży",
      "lat": 54.4459, "lng": 18.5697, "why": "drugi lokal w tej samej strefie" }
  ]
}
```

## Cell indexing (must match byte-for-byte)

```
index(ci, di, h) = (ci * days + di) * hours + h
```
- `ci` — index into `codes` (0 = excluded bucket)
- `di` — day index, `0 == start`, `days-1 == 2026-06-30`
- `h` — local hour in **Europe/Warsaw**, `0..23`, DST-corrected by the pipeline

`nat` is indexed `(di * hours + h) * 6 + bucket` with buckets
`0=PL 1=DE 2=SE 3=NO 4=GB 5=OTHER` (issuer country).

## Invariants the pipeline must assert before writing

1. `sum(cnt) == rows` (every row lands exactly once, including excluded ones in index 0).
2. `len(cnt) == len(amt) == codes.length * days * 24`.
3. `len(nat) == days * 24 * 6`.
4. `sum(nat) == rows`.
5. Max cell of `cnt` < 65535 (Uint16 safety).
6. Max cell of `amt` (whole zł) < 65535; if violated, raise `amtScale` and rescale.
7. Every code in `codeMeta` exists in `codes`; every code except index 0 has `codeMeta`.
8. Every preset's `code` passes **all** privacy gates in `contracts/privacy.py`.

## What the app must do

- Refuse to render if `ver != 4` — show an explicit error, never a fallback number.
- Decode base64 → typed arrays once, at load.
- Compute the **weekday-matched baseline** from `cnt` in the client (defect D1): for a target
  (code, hour) the baseline is the mean of the same `purchase_weekday_iso` over the trailing 4 weeks,
  not the mean of all days.
- Never show a value for a cell that fails G1/G2/G3 unless it escalated to a parent unit that passes.
- Never draw a curve and withhold the readout (defect D4).
- Label every area value with *„Dane dla obszaru <code>, nie dla Twojego lokalu."*

## What is deliberately absent

- **No card-level data.** `pymt_crd_acct_num_raw` is never read into this artifact. `nCards` exists
  only as a **per-code aggregate count** for the privacy gate.
- **No merchant-level rows.** `mrch_nm_raw` is never emitted — only distinct counts.
- No raw parquet, no per-transaction records. This artifact is safe to publish.
