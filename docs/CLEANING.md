# CLEANING — the eight stages, the rules, and the ones we rejected

This document is the cleaning methodology of `pipeline/`, rule by rule, with the row counts that prove
each one ran. The extract is Organiser Data: two parquet parts, 378,212 rows, MCC 5812, Sopot,
2025-01-01 → 2026-06-30. **The original cleaning script does not exist on disk** — an audit searched four
roots and found none (`research/cleaning-lineage.md` §8.3, **MEASURED-AUDIT**) — so this is a
*reconstruction*: it re-derives every observable rule from the evidence columns the original run left
behind and asserts each against the column that proves it. Where a rule is not recoverable, §6 says so.

## 1. Reproduce

```sh
python3 -m pipeline.run --src /Users/kulma/Downloads --out artifacts   # 8 stages, ~10 s, exit 0
```

The console output *is* the evidence: one line per gate, `[n/8 STAGE]   ok   key=value`; a failed assertion
prints `FAIL` with the measured value and exits non-zero. No `--force`, no degraded path, and two runs are byte-identical (`#aggregate_sha256`).

## 2. The eight stages, in execution order

```
part01.parquet (189,106) ─┐   [1] INGEST ──► [2] VALIDATE ──► [3] NORMALISE ──► [4] FILTER
                          ├─► 378,212 · 0 overlap · 0 mismatch · 6,431|350,838|20,943 · 47,052 excluded
part02.parquet (189,106) ─┘   [5] ENRICH ──► [6] AGGREGATE ─► [7] BASELINE ───► [8] EVALUATE
                              3 rows clamped · 720,720 cells · weekday index · 490 forecast days
```

The order is not cosmetic: evidence columns are appended in pipeline order, so a rule can only be proven
against a stage that already ran, and the aggregate cannot precede the DST conversion because `cnt`'s
hour axis is *local* — a wrong axis is invisible in every downstream total.

## 3. Rules applied, stage by stage

Each stage gives its rule as implemented, the evidence column that proves it ran, the row counts, and
the code. Zero-valued gates read as `name=0` so they cannot pass by matching a digit in another number.

### 3.1 INGEST — `pipeline/ingest.py::manifest`

**Rule.** `read_parquet([part01, part02])` is a `UNION ALL` — never a JOIN, never a dedupe. Disjointness
is asserted on **both** keys: `tran_id_raw` (business) and `source_transaction_row` (audit).

| | Value | Statement |
|---|---|---|
| rows in → out | 189,106 + 189,106 → **378,212** | `#parquet_part01_rows`, `#parquet_part02_rows`, `#rows` |
| id overlap / row overlap | **0 / 0** | `#overlap_tran_id`, `#overlap_source_row` |
| source-row span | **22 … 2,345,173** | `#source_row_min`, `#source_row_max` |
| columns | **72**, pinned in schema order | `#raw_schema_columns` |

The parts are carved at `source_transaction_row` 1,177,268 / 1,177,271 — the CSV emission of the same
rows splits at a *different* boundary — so "part01 = first half" is false in the CSV sense. The start
offset **22** is unexplained: reported, not repaired, because repairing it would fabricate a source row.

### 3.2 VALIDATE — `pipeline/validate.py::assert_validated`

**Rule.** Re-derive each typed column from its raw VARCHAR and compare with `IS DISTINCT FROM`, so a
NULL on either side counts as a mismatch rather than silently evaluating to NULL.

| Derived column | Expression | Mismatches |
|---|---|---|
| `purchase_date` | `CAST(prch_dt AS DATE)` | 0 |
| `transaction_amount` | `CAST(cs_tran_amt AS DECIMAL(38,10))` | 0 |
| `transaction_time_gmt` | `CAST(strptime(lpad(tran_id_gmt_tm,6,'0'),'%H%M%S') AS TIME)` | 0 |

**Rows in → out:** 378,212 → 378,212. **Evidence columns:** `purchase_date_status`,
`transaction_amount_status`, `transaction_time_gmt_status` — all three carry exactly one value, `valid`.
A status column with one possible value is unfalsifiable on its own, which is why the 0-mismatch
comparison exists beside it. Also asserted: the date span (**546** days, no gaps), the amount domain
(**0.0276 … 41,308.92**), and the week keys `prch_mnth_id` and `myweek` (0 mismatches each). `#rederivation_mismatches`.

### 3.3 NORMALISE — `pipeline/normalise.py::assert_normalised`

**Rule.** One string `CASE`, three branches, no lookup table:

```sql
CASE WHEN mrch_postal_code IS NULL OR mrch_postal_code = '' THEN NULL
  WHEN length(mrch_postal_code) = 6 THEN mrch_postal_code            -- already NN-NNN
  WHEN length(mrch_postal_code) = 5 THEN substr(x,1,2)||'-'||substr(x,3,3) END
```

| Branch | Rows | What it proves | Claim |
|---|---:|---|---|
| NULL / `''` → NULL | **6,431** | 5,490 NULL + 941 empty string | `#postcode_branch_null_or_empty` |
| 6-character pass-through | **350,838** | every value matches `^\d{2}-\d{3}$`, 0 exceptions | `#postcode_branch_six_char` |
| 5-digit re-hyphenation | **20,943** | every value matches `^\d{5}$`, 0 exceptions | `#postcode_branch_five_digit` |
| **sum** | **378,212** | exact partition of the table | `#rows` |

Without it, any `GROUP BY` on the raw column splits `81-777` into two places and any join keyed on it
silently drops **20,943** rows. The 4th branch is the trap: a value that is neither NULL, nor 6 chars,
nor 5 would fall through the CASE to NULL and vanish as "postcode-less"; it is asserted zero so a future
4-character value fails loudly. The stored column is re-derived for all rows — **stored_mismatches=0**
(`#normalise_stored_mismatches`). **Rows in → out:** 378,212 → 378,212.

### 3.4 FILTER — `pipeline/filter.py::assert_filter`

Three rules run here, and this is where the story is.

**(a) Sopot membership.** The original rule kept rows whose merchant city label is Sopot:
`upper(trim(mrch_city_nm_raw)) = 'SOPOT'`. There is **no postcode, geometry or bounding-box predicate**
— that is the whole of rule set `sopot-city-labels-only-v1`. The source files contain only surviving
rows, so re-filtering them is a no-op, and the no-op is asserted: all **378,212** rows carry
`sopot_match_basis = 'CITY_EXACT'` and `sopot_rule_version = 'sopot-city-labels-only-v1'`.

**Retention: 378,212 of 2,345,173 source rows = 16.127%** (`#city_filter_retention`). Read that number
with §6 in mind: the denominator is the largest surviving audit key, not a file we can open.

**(b) The non-Sopot postcode leak — the fix.** Because the filter never consulted the postcode,
**2,527 rows (0.668%) carry a foreign postcode with a Sopot city label** (`#foreign_postcode_rows`):

| Code | Rows | Presumed city | | Code | Rows | Presumed city |
|---|---:|---|---|---|---:|---|
| `20-315` | 914 | Lublin | | `01-221` | 114 | Warszawa |
| `70-035` | 622 | Szczecin | | `91-402` | 13 | Łódź |
| `02-495` | 504 | Warszawa | | `31-029` | 6 | Kraków |
| `62-030` | 353 | Września area | | `01-825` | 1 | Warszawa |

All **8** codes (`#foreign_codes`) are 450–500 km away and sat inside every aggregate the dashboard
computed. They are **routed to the excluded bucket** — `codes[0]`, the `"—"` entry — not deleted, so the
row count stays 378,212, `sum(cnt) == rows` holds, and the count is published so the panel can say out
loud how much of it is not Sopot. `sopot_geo_conflict` is **populated on 0 rows**
(`#geo_conflict_populated`): the rule that should have caught this never fired. `81-796` (**8** rows,
`#rows_81_796`) is deliberately **kept** — in the Sopot range, merely absent from the PNA catalogue, a
different defect class from a Lublin postcode.

**(c) Defect D2 — the `'000000'` sentinel.** `tran_id_gmt_tm` is `HHMMSS` in GMT. **38,443 rows
(10.2%)** carry the literal `'000000'` and the original layer stamped every one of them
`transaction_time_gmt_status = 'valid'` — a parse that succeeded on a value that is not a time
(`#zero_timecode`, `#zero_timecode_pct`, `#sentinel_status_flagged`). The hole is visible in the
histogram: GMT hour 00 holds **1,547** real rows and hour 01 holds **569**, against 38,443 on the
sentinel (`#gmt_hour0_real_rows`, `#gmt_hour1_rows`). Because the city's traffic peaks at 13:00–14:00,
that mass moves into local 01:00/02:00 and fabricates a **phantom 02:00 spike**.

**The choice, and its cost.** Sentinel rows are **kept in `cnt`** — so the headline total stays true —
but **routed to `codes[0]`** at their local clock hour, which makes them separable without a second
array: any curve over `ci >= 1` drops all 38,443. The cost, stated rather than buried: an area's *daily*
total no longer includes its un-timed rows, because a shape that is 10.2% fabricated is worse than a
level that is provably low. `nat` still counts every row, so `sum(nat) == rows` holds.

**Rows in → out:** 378,212 → 378,212, of which **47,052** land in `codes[0]`
(`#excluded_bucket_rows`). The three reasons **overlap** — **349** rows are both postcode-less and
sentinel-bearing (`#excluded_overlap_rows`) — so the published counts (6,431 + 2,527 + 38,443) must never be summed to predict `cnt[0]`.

### 3.5 ENRICH — `pipeline/enrich.py::assert_dst`, `calendar_features`, `code_meta`

**Rule 1 — GMT → Europe/Warsaw, DST-correct.** Europe/Warsaw has a 23-hour day on the last Sunday of
March and a 25-hour day on the last Sunday of October, both inside the window, so a fixed `+1 h` / `+2 h` rule is wrong twice a year.

**The DuckDB trap.** `timezone('Europe/Warsaw', TIMESTAMP '2025-07-01 12:00:00')` **silently no-ops**:
a naive `TIMESTAMP` is treated as already-local, so the call returns **`2025-07-01 12:00:00+02`** instead
of 14:00 (`#dst_naive_trap`). Every summer transaction would be an hour early and nothing would look broken. The fix is to bind UTC first:

```sql
timezone('Europe/Warsaw', (<naive ts>) AT TIME ZONE 'UTC')   -- 12:00 → 2025-07-01 14:00:00
```

`assert_dst()` requires the naive form to disagree (`#dst_utc_bound`), pinning the trap in a test rather
than a comment. The three transitions are asserted by walking **every UTC hour** across each local day,
so the result is a property of the timezone rule, not of the volume: **2025-03-30 = 23 h**,
**2025-10-26 = 25 h**, **2026-03-29 = 23 h** (`#dst_spring_2025_hours`, `#dst_autumn_2025_hours`,
`#dst_spring_2026_hours`). The same signature appears independently in the source data:
`weather_observed_hours` leaves 24 on exactly **3** dates (`#weather_dst_hour_dates`), which is why the
weather extract is local-time hourly rather than UTC.

**Rule 2 — the day axis clamps, it does not drop.** A transaction at 2026-06-30 23:00 GMT is 2026-07-01
01:00 local — day index 546, one past the end of the 546-day axis. **3** rows are affected
(`#dst_clamped_rows`) and clamped to day 545, because dropping them would break invariant 1 and a
silently short total is the failure mode this pipeline exists to remove.

**Rule 3 — calendar features and geometry.** The four calendar features are asserted with 0 mismatches.
Per-code metadata comes from the **card column the old browser layer never read**: `nCards`,
`merchants`, `top1Share` as an exact integer ratio. Every published centroid is a point **inside that
code's own polygon** — a coastal multi-part sector's centroid routinely lands in the sea, and `81-777`
is a strip in five parts. The shipped contract's preset coordinates are **wrong**:
`54.4466,18.5700` (labelled 81-777) falls in `81-720`, `54.4447,18.5625` in `81-706`, `54.4459,18.5697`
in no sector. `assert_presets()` fails the build if any emitted coordinate is outside its own code.

**Rows in → out:** 378,212 → 378,212.

### 3.6 AGGREGATE — `pipeline/aggregate.py::build_artifact`, `assert_invariants`

**Rule.** Emit one precomputed, privacy-gated file instead of making the browser read 26 MB of parquet.
Since **v5** the builder's last step is a **release gate**: a cell that fails the privacy gates leaves with
its code, its name, its polygon provenance and its failure reason, and with **no series and no counts** —
because *"81-814: 1 transakcja, 1 karta, 1 podmiot"* is the identification the rule forbids whether or not a
chart is drawn from it. The gate removes **37 of the 54** cells carrying **33,197** transactions
(`#released_codes`, `#suppressed_codes`, `#suppressed_volume`), so invariant 1 becomes
`sum(cnt) + suppressedVolume == rows` — **345,015 + 33,197 = 378,212** (`#cube_sum_cnt`). The exact city
series ships beside it as `cityCnt`, summing to **331,160** (`#city_cnt_sum`), so suppressing the parts never makes the whole quietly short.

```
cnt[(ci · 546 + di) · 24 + h]        Uint16, base64     counts
amt[same index]                      Uint16, base64     WHOLE złoty, amtScale=1
nat[(di · 24 + h) · 6 + bucket]      Uint32, base64     issuer country 0=PL…5=OTHER
```

| | Value | Claim |
|---|---|---|
| contract version | **5** (adds the release gate) | `#aggregate_ver` |
| codes | **55** = index 0 (excluded) + 54 Sopot postcodes | `#aggregate_codes` |
| cells | **720,720** | `#aggregate_cells` |
| busiest cell / largest amount | **214** transactions · **47,489** zł, amtScale **1.0** | `#aggregate_max_cnt`, `#aggregate_max_amt`, `#aggregate_amt_scale` |
| codes gated | **17 of 54** | `#gated_codes_pipeline`, `#codes_total_pipeline` |

**Evidence.** All eight invariants are asserted on the **decoded base64 that will be written**, not on
the in-memory arrays — a serialisation bug cannot pass the gate built to catch serialisation bugs.
`tests/pipeline/test_invariants.py` re-checks each against the written file.

### 3.7 BASELINE — `pipeline/baseline.py::build`, `assert_weekday_index`

**Rule.** For a target cell *(code, day, hour)* the baseline is the mean of the **same
`purchase_weekday_iso`** over the trailing **4** weeks (`#baseline_weeks`), not the mean of the last 30
days. Measured over all 378,212 rows in local time:

| | Pn | Wt | Śr | Cz | Pt | Sb | Nd |
|---|---:|---:|---:|---:|---:|---:|---:|
| weekday index | **0.7214** | 0.7269 | 0.7370 | 0.8546 | 1.0721 | **1.5240** | 1.3640 |

**Evidence.** The index is derivable two ways — from the stored `purchase_weekday_iso` and from the
local-day axis inside `cnt` — and `assert_weekday_index()` requires both to agree
(`parquet_agreement=True`). If they diverge, the hour/DST conversion has broken and every per-hour curve
is wrong. D1's size is measured, not asserted: against the weekday-blind mean a Saturday reads
**−36.18%** and a Monday **+30.12%** before any real deviation, worst cell **+220.74%** at 81-777, day
543, hour 22 (`#d1_gap_saturday`, `#d1_gap_monday`, `#d1_gap_worst`).

**Rows in → out:** 720,720 cells → `artifacts/baseline.json`.

### 3.8 EVALUATE — `pipeline/backtest.py::build`

**Rule.** Walk-forward, expanding window, past-only, **490** forecast days from 2025-02-26; at every
origin the forecast uses data strictly before the target day. **Rows in → out:** 378,212 rows → 546
daily totals → 490 forecast days. The daily series is asserted to sum to `rows` exactly (**378,212**),
so an axis drift is loud. Protocol and failures: `docs/EVALUATION.md`; the model: `docs/MODEL.md`.

## 4. Rules evaluated and rejected

Status vocabulary: `1:1` · `justified deviation` · `addition, test <id>` · `evaluated and rejected` · `not reproduced`.

| # | Candidate rule | Measured objection | Status |
|---|---|---|---|
| R1 | **Weekday-blind 30-day mean** as "zwykle" (the prototype's `avg()`) | reads a Saturday −36.18% and a Monday +30.12% before any real deviation; worst +220.74% | **evaluated and rejected** — replaced by the same-weekday mean (§3.7, test `test_d1_weekday_index_is_data_derived`) |
| R2 | **Add a 4th postcode branch** for shapes that are neither NULL, empty, 6-char nor 5-char | the objection is real but the population is **0** rows | **evaluated and rejected** as unnecessary; the *absence* is asserted instead (`#postcode_branch_unhandled`) |
| R3 | **Exclude `81-796`** with the foreign codes | **8** rows; in the Sopot range, merely absent from the PNA catalogue | **justified deviation** — kept, and named as a different defect class |
| R4 | **Delete** the 38,443 sentinel rows | `sum(cnt)` would fall to 339,769 ≠ `rows`, breaking invariant 1 and silently shrinking every total | **evaluated and rejected** — routed to `codes[0]` instead |
| R5 | **Spread** the sentinel across the hours in proportion to real traffic | fabricates a shape that looks plausible at every hour; the phantom spike would survive in a subtler form | **evaluated and rejected** |
| R6 | **Drop** the 3 rows whose local day rolls past the axis | breaks invariant 1 for a 3-row saving | **evaluated and rejected** — clamped (§3.5) |
| R7 | A fixed **+1 h / +2 h** offset instead of a timezone library | wrong on the **23**-hour and **25**-hour days, i.e. on 2 of 546 days, silently | **evaluated and rejected** (test `test_dst_transitions_are_real`) |
| R8 | The **naive** `timezone()` call | returns `2025-07-01 12:00:00+02`, one hour early all summer, with no error | **evaluated and rejected** — UTC must be bound first (`#dst_naive_trap`) |
| R9 | **Equal event quartiles (144/144 days)** for the season control | moves the raw high side from +32.9 pp to +31.1 pp — the audit's published 59.8 pp spread does not reproduce | **evaluated and rejected** in favour of the bottom-140 / top-123 split (`#season_split_days`) |
| R10 | A **decile** split of the event contrast | raw sweep **69.9 pp** → controlled **10.7 pp**, i.e. a bigger raw number that is a different, unpublished comparison | **evaluated and rejected** as the headline; published as a secondary reading |
| R11 | Measuring the event contrast against the **trailing matched baseline** (lag 4) | collapses the raw spread to **9.9 pp** — the control removes the effect being measured, so the raw leg is no longer interpretable | **evaluated and rejected** in favour of the global same-weekday mean |
| R12 | The **8-value `channel_flg`** vocabulary | `channel_flg='mobile'` is the majority channel even for card-present rows (183,639) | **evaluated and rejected** in favour of the binary `cp_flag` (**MEASURED-AUDIT**; no repo command) |
| R13 | Rival **event-count identities**: `multiday + nonrecurring_starts`, `single_day + nonrecurring_starts` | hold on **41,592 / 189,106** (22.0%) and **7,772 / 189,106** (4.1%) rows, against 100% for the accepted identity | **evaluated and rejected** (**MEASURED-AUDIT**) |
| R14 | Recomputing the **event-id hash** to re-verify the calendar | 8 candidate functions (md5, sha1, sha256, sha512, blake2b, blake2s, FNV-1a-64, and title-plus-date) all fail; the hash stays unidentified | **evaluated and rejected (not reproducible)** — the calendar source is gone (**MEASURED-AUDIT**) |
| R15 | **OSM/Nominatim centroids + Voronoi** partitioning (**133** codes) for the map | pure geometric guess with no postal evidence; replaced by **151** PNA-constrained sectors | **evaluated and rejected** (**MEASURED-AUDIT**) |
| R16 | **Demoing the NULL-postcode ("UNKNOWN") bucket** | **6,431** rows, **179** merchants, **5,505** cards — it would pass the privacy gates in most months, and it is not a place | **evaluated and rejected** — excluded by name (`#unknown_bucket_merchants`) |
| R17 | Returning **`0.0`** when no baseline history exists | a 0 baseline silently yields "+0%" — a missing baseline must be visibly missing | **evaluated and rejected** — `None` is returned and the panel says "brak historii" |
| R18 | Reading the **parquet in the browser** (26 MB, pure-JS ZSTD + IndexedDB) | 2.9–5.6 s cold, 23–28 s on a 10 Mbit/s link, and 1.4–2.7 s of **fabricated** `Dane przykładowe` numbers | **evaluated and rejected** — replaced by the precomputed aggregate (§3.6) |
| R19 | Evaluating G3 on the **volume share alone** | the conservative reading (volume **and** cards) costs exactly **one** cell, `81-740` | **justified deviation** — we take the conservative reading; see `docs/PRIVACY.md` |
| R20 | The **shipped contract's preset coordinates** | two of three land in a different postcode and one in no sector at all | **evaluated and rejected** — every coordinate is recomputed and point-in-polygon asserted |
| R21 | Dropping **`lpad(...,6,'0')`** as a no-op | it is a no-op on this extract (0 rows have a bad length) but a future 5-character value would parse as `0H:MM:SS` — the same class of bug as D2 | **justified deviation** — kept and commented |

## 5. Output contract

`artifacts/aggregate.json` **v5**, frozen in `contracts/AGGREGATE.md` and machine-checked against
`contracts/aggregate.schema.json` by a dependency-free validator (`jsonschema` is not installed, so the
subset is implemented in ~40 lines). The app refuses any other `ver` and renders an explicit error.

## 6. What we cannot prove

This is the section that matters most: the pipeline is a reconstruction, not the original run.

- **The pre-filter extract is not on disk.** The only transaction-level artefacts are the two parquet
  parts and the two CSV emissions, all four post-filter and all four carrying exactly **378,212** rows
  (`#raw_extract_absent`, `#csv_emission_rows`).
- **So the retention rate is inference, and the filter order is unrecoverable.** **16.127%** is
  `count(*) / max(source_transaction_row)`; the denominator is an audit key that survived the filter,
  not a file we can open, and `mrch_catg_cd` holds one value (5812) in the output, so whether the MCC
  filter ran before or after the Sopot label filter is unobservable. The audit names the missing
  quantity: *"the 1,966,961 filtered-out rows"* (`cleaning-lineage.md` §8.2, **MEASURED-AUDIT**).
- **Our stage numbering is ours.** The audit reconstructed **10** stages (Stage 0–9); `pipeline/` has
  **8**, folding MATCH and ENRICH-A/B/C into one ENRICH and dropping Stage 0. Counts agree; numbering does not.
- **Stage 0 cannot be reproduced.** The raw extract sits in a ZipCrypto archive; the attack left a
  **0-byte** hash file and a truncated test file — **MEASURED-AUDIT**, a documented dead end.
- **The original MATCH rule set is gone.** `sopot_geo_conflict` is 100% NULL and no matching code exists
  on disk, so whatever produced `CITY_EXACT` / `SUPPORTED` is unrecoverable.
- **Derived ≠ recovered.** "The rule is X" here means the re-derivation reproduces the stored column
  exactly — not that the original ran that expression. Invisible in the output, decisive for a reader.
- **The original engine version is unrecorded.** The audit reproduced on DuckDB v1.4.4; we run the
  installed DuckDB. A version difference cannot pass silently, but we cannot say which engine wrote it.

## 7. Known limitations

- **Every hourly figure rests on 89.8% of the rows.** The 38,443 sentinel rows are excluded from hourly
  views by construction. The excluded bucket is **12.4%** of the table — 47,052 rows in `codes[0]` — and a
  further **33,197** sit in cells the release gate suppresses, so a reader comparing the per-area view with
  378,212 finds a gap unless they read `excluded.*` and `released.*`.
- **`81-796` is a Sopot-range code we cannot place.** 8 rows are kept with no polygon, no catalogue
  entry and no weather reference: they reach the city total and no area.
- **Sector confidence uses a two-criterion rule where the audit used three.** Our **116 / 24 / 11** is
  reproducible from this repo; the audit's **105 / 34 / 12** is not, because the shipped sector model
  lacks the `extrapolated_pct` attribute the third criterion needs.
