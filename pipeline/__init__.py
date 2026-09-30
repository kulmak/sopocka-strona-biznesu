"""Sopot MCC-5812 transaction pipeline — the reproducible cleaning + aggregation layer.

WHAT THIS PACKAGE IS
--------------------
The audit's single most damaging finding was that **no cleaning script exists on disk**
(`research/cleaning-lineage.md` §8.3: "The cleaning script does not exist on disk. A disk-wide
search … found **zero** Python, SQL, notebook or shell files belonging to this pipeline.").
The 378,212-row parquet pair under `/Users/kulma/Downloads` was produced by an unrecorded DuckDB
run and could not be regenerated. This package is that missing script. It re-derives every
*observable* rule of the original 8-stage pipeline from the emitted evidence columns, asserts each
one against the stored column that proves it ran, and then builds the browser artifact.

WHY IT EXISTS
-------------
1. **Reproducibility.** `python3 -m pipeline.run --src DIR --out artifacts` turns the two source
   parquet parts into `artifacts/aggregate.json` byte-identically on two consecutive runs
   (sorted keys + a timestamp derived from the source file mtime or `SOURCE_DATE_EPOCH`, never
   wall clock).
2. **Defect D1** (weekday-blind baseline): the app used to average the last 30 days across all
   weekdays, so a no-event Saturday read +75 %. Nothing in this package bakes in a weekday-blind
   baseline; `pipeline/baseline.py` emits the same-weekday-matched baseline and proves the
   weekday index it implies (Saturday ≈ 1.514, Monday ≈ 0.724).
3. **Defect D2** (the `'000000'` sentinel): 38,443 rows (10.2 %) carry `tran_id_gmt_tm = '000000'`
   and were marked `valid`, creating a phantom 02:00 spike. They are routed to the excluded
   bucket so that totals reconcile but hourly curves can exclude them. See `pipeline/filter.py`.
4. **Defect D3** (the ≥30-card gate could never fire): the card column was never read. Every gate
   is now evaluated here, from real distinct-card counts.

RULE VERSION
------------
`sopot-city-labels-only-v1+geo-cleanup-v1`

* `sopot-city-labels-only-v1` is the original rule stamp recovered from the parquet
  (`sopot_rule_version`, 100 % of rows). It names the *restriction*: Sopot membership was decided
  by the merchant city label alone, with no postcode or geometry predicate.
* `+geo-cleanup-v1` is the fix applied here: the 8 non-Sopot postcodes that survived that
  city-label filter (2,527 rows) are routed to the excluded bucket instead of being counted as
  Sopot, and postcodes are placed on real sector polygons.

EVIDENCE COLUMNS
----------------
Every module docstring names the *evidence column* that proves its rule ran, per the convention
established in `research/cleaning-lineage.md` §1. A rule without an evidence column is a rule
nobody can falsify.

LAYOUT
------
=========================  ==================================================================
`ingest.py`                 UNION ALL of the two parts; disjointness assertions
`validate.py`               re-derivation gates (0 mismatches against the stored columns)
`normalise.py`              3-branch postcode normalisation (exact partition)
`filter.py`                 Sopot membership, non-Sopot postcode leak, D2 sentinel routing
`enrich.py`                 GMT→Europe/Warsaw (DST-correct), calendar features, geo, gates
`aggregate.py`              the base64 typed arrays + `codeMeta` + `presets` + invariants
`baseline.py`               same-weekday-matched baseline (D1) + weekday-index proof
`backtest.py`               walk-forward backtest (4 candidates) + driver regression
`sample.py`                 k-anonymised publishable sample (never the raw parquet)
`_gates.py`                 privacy-gate fallback; `contracts/privacy.py` wins when present
=========================  ==================================================================
"""

RULE_VERSION = "sopot-city-labels-only-v1+geo-cleanup-v1"

__all__ = ["RULE_VERSION"]
