# DATA — provenance, licence and the column dictionary

*Sopocka Strona Biznesu* analyses one anonymised, synthetic card-transaction extract that the Organiser
supplied for the Visa Data Sprint: **MCC 5812 (restaurants), Sopot, 2025-01-01 → 2026-06-30**. It was
given to us **for this challenge only**, we do not redistribute it, and the raw parquet never enters
git, never gets served and never lands in a bucket. Every figure in this submission is an aggregate of
it. The published artifacts never carry a card identifier: `pymt_crd_acct_num_raw` and `mrch_nm_raw` are
read as *cardinalities only* and are excluded from every emitted file by a test.

## 1. Verify the inputs

```sh
shasum -a 256 -c data/MANIFEST.sha256   # 5 files: OK OK OK OK OK ; exit 0  (manifest_files=5 ok=5 failed=0)
```

## 2. Provenance

| | Value | Source |
|---|---|---|
| Extracts | `mcc5812_transactions.part01.parquet`, `part02.parquet` | Organiser, `/Users/kulma/Downloads` |
| Rows | **378,212** (189,106 + 189,106) | `docs/claims.json#rows`, `#parquet_part01_rows` |
| Columns | **72** — the 30 documented raw fields plus 42 the original run derived | `#raw_schema_columns` |
| Dates | **546** days, 2025-01-01 → 2026-06-30, no gaps | `#days` |
| MCC | **5812**, a single value — there is no second category to compare against | `#mcc_values` |
| Merchants | **347** distinct descriptors | `#merchants` |
| Cards | **160,127** distinct anonymous card accounts | `#cards` |
| Postcodes | **62** distinct non-null: 54 Sopot (`81-*`) + 8 out-of-town | `#postcodes`, `#sopot_codes`, `#foreign_codes` |
| Ticket | median **81.33**; range **0.0276 … 41,308.92** (fictional PLN) | `#median_ticket`, `#min_ticket`, `#max_ticket` |
| Checksums | `9fc82163…1ae1` (part01), `aecb77de…d2e9` (part02) | `#sha256_part01`, `#sha256_part02` |

**The amounts are not złoty.** The challenge documents `cs_tran_amt` as *„waluta fikcyjna,
przygotowana na potrzeby hackathonu"* — a fictional currency prepared for the hackathon. Every `zł`
in this repository is a label of convenience; no exchange rate, price level or revenue statement is
derivable from these numbers. Read them as counts whose scale happens to look like a restaurant bill.

**The split is not a first-half/second-half split.** The two parquet parts are disjoint contiguous
ranges of one extraction, carved at `source_transaction_row` 1,177,268 / 1,177,271. They share **0**
transaction ids and **0** source-row indices, which `pipeline/ingest.py::assert_disjoint` asserts on
every run, and which is why the pipeline unions them and never joins or dedupes. A second emission of
the same rows as `part01.csv.xz` + `part02.csv.xz` carries the same **378,212** rows
(`#csv_emission_rows`) at a *different* boundary — so "part01 is the first half" is false in the CSV
sense and true in neither.

## 3. Licence and permitted use

The extract is provided **wyłącznie na potrzeby realizacji wyzwania** — solely for the purposes of this
challenge. The challenge also forbids *„podejmowanie prób identyfikacji pojedynczych osób, podmiotów
lub rzeczywistych transakcji"*, and the data is described by the Organiser as anonymised and synthetic.

What that means here, concretely:

* **Not redistributed.** No parquet, no row extract and no per-transaction record is committed or
  served. `data/samples/` is a k-anonymised *aggregate* (postcode × day), and `artifacts/*.json` is the
  Since contract **v5** the published cube also drops the counts of every cell that fails the privacy
  gates, so a thin area ships as a name and a reason rather than as a one-card statistic.
  privacy-gated cube; neither can be differenced back to a person, a card or a transaction.
* **Not joined outward.** We join the transactions to public geography, a public postcode register, a
  public event calendar and a public weather series — never to any register of people or businesses.
* **Card-level attributes are not read.** `lau_enr`, `fua_enr` and `pstl_cd_enr` describe the
  *cardholder's* usual area. We publish no value keyed by them and use none of them as a feature.
* **Two columns exist only as counts.** `pymt_crd_acct_num_raw` is read by `count(DISTINCT …)` to
  evaluate the 30-card gate, and `mrch_nm_raw` by `GROUP BY` to compute a top-1 share. Neither is
  emitted: `tests/pipeline/test_invariants.py::test_no_forbidden_columns_leak` asserts their absence
  from the artifact, by exact name.

## 4. Data dictionary

### 4.1 The 30 documented fields (challenge §7)

| Column | Meaning as used here | Read into a published artifact? |
|---|---|---|
| `tran_id_raw` | transaction key; used to prove the two parts are disjoint | no — key only |
| `tran_id_gmt_tm` | time of day, `HHMMSS` **GMT**; `'000000'` is a sentinel, not midnight | only via the local-hour axis |
| `pymt_crd_acct_num_raw` | anonymised card/account id — the unit the 30-card gate counts | **count only** |
| `prod_id_pltfrm_cd_vcis` | product code (CN/CO/BZ/GV) | no |
| `transaction_type` | POS / ATM | no |
| `transaction_pos_entry_mode` | terminal entry mode | no |
| `mrch_regn_cd`, `mrch_regn_nm` | merchant region code and name | no |
| `mrch_ctry_cd`, `mrch_ctry_nm` | merchant country | no — one value, Poland |
| `mrch_nm_raw` | merchant descriptor | **count only** (distinct merchants, top-1 share) |
| `mrch_catg_cd` | MCC; **5812 only** | no — constant |
| `mrch_catg_nm` | MCC name | no — constant |
| `mrch_city_nm_raw` | merchant city label — **the whole of the Sopot filter** | no |
| `mrch_postal_code` | raw postcode, two encodings (`81-777` and `81777`) | via the normalised column |
| `cs_tran_amt` | amount, **fictional currency** | yes, as whole units in `amt` |
| `issr_jurn` | issuer jurisdiction, Domestic / Foreign | no |
| `issr_ctry_cd`, `issr_ctry_nm` | issuer country — the `nat` buckets 0–5 | yes, as 6 buckets |
| `crd_typ_cd`, `crd_typ_nm` | card type | no |
| `channel_flg` | 8-value channel vocabulary | **rejected** — see `docs/CLEANING.md` §5 |
| `cp_flag` | 1 = card present, 0 = not | no |
| `prch_mnth_id` | purchase month `YYYYMM`; re-derived, 0 mismatches | no |
| `prch_dt` | purchase date; the origin of `purchase_date` | yes, as the day axis |
| `myweek` | ISO year + week; re-derived, 0 mismatches | no |
| `report_ctry` | reporting country | no |
| `lau_enr` | local administrative unit ≈ cardholder's usual area | **never read** |
| `fua_enr` | aggregated urban area of the cardholder | **never read** |
| `pstl_cd_enr` | postal code assigned to the card | **never read** |

### 4.2 The 42 derived and evidence columns

The original run appended these to the raw 30. They are how `docs/CLEANING.md` proves each rule ran.
`pipeline/ingest.py::EXPECTED_COLUMNS` pins all 72 in schema order, so a schema drift fails the build.

| Group | Columns | What it is |
|---|---|---|
| Audit keys (2) | `source_transaction_row` | dense key over the pre-filter extract, 22 … 2,345,173 |
| Sopot membership (5) | `sopot_match_basis`, `sopot_match_status`, `sopot_geo_conflict`, `sopot_country_status`, `sopot_rule_version` | the rule stamp `sopot-city-labels-only-v1`; `geo_conflict` is 100% NULL |
| Typed re-derivations (3) | `purchase_date`, `transaction_amount`, `transaction_time_gmt` | 0 mismatches against their raw columns |
| Parse statuses (3) | `*_status` for the three above | all three carry exactly one value, `valid` |
| Calendar (4) | `purchase_year`, `purchase_month`, `purchase_weekday_iso`, `purchase_is_weekend` | 0 mismatches |
| Postcode (3) | `merchant_postal_code_normalized`, `merchant_postal_code_status`, `weather_match_status` | the 3-branch rewrite; the last two are a 1:1 relabelling |
| Weather (13) | `weather_observed_hours`, 2 × temperature, 2 × wind, 3 × condition hours, 3 × fractions; plus the two status columns above | city-level, one signature per date |
| Events (6) | `event_calendar_match_status`, `event_listings_count`, `event_single_day_listings_count`, `event_multiday_listings_count`, `event_recurring_listings_count`, `event_nonrecurring_starts_count`, `event_ids_json`, `event_titles_json`, `has_event_listings`, `event_unresolved_listings_total` | the city calendar flattened onto every row |
| Channel cross-check (1) | `sopot_channel` | `cp_flag` as CP/CNP, 0 mismatches — proves row identity survived |

## 5. Public data used

The challenge suggested three Kraków portals; we checked them and did not use them, because this
analysis is Sopot-scoped. The public data we did use is listed with what it actually changed.

| Source | Used for | Effect on any published number |
|---|---|---|
| **Urząd Miasta Sopotu** — address points (`mapa.um.sopot.pl/iip/ows`, 3,767 records) | the evidence base for every sector polygon; the denominator of the 19.0% address share | none directly — geometry only (`#gis_addresses`, `#address_share_passing18`) |
| **Urząd Miasta Sopotu** — parcels (8,289) and building footprints (5,440) | constraining inferred postcode sectors to addressed land | none directly |
| **PRG / GUGiK** — official municipality polygon (TERYT 2264011) and 52 cadastral districts | the city outline and the land/sea split | none directly |
| **BDOT10k / GUGiK** — shoreline, inland water, woodland | topographic context for the seafront strip | none directly |
| **Poczta Polska** postcode register (278 rows, 155 distinct codes) | the code catalogue a sector must belong to | decides which 151 sectors exist (`#gis_sectors`) |
| **OpenStreetMap** | map base layer *in the prototype's earlier iteration only*; not in the panel today | none |
| **Public weather service** (`sopot_weather_by_postal_code_*.csv`, 2,030,965 hourly rows) | rain, temperature, wind, sunshine | the weather regressors (`#weather_source_rows`) |
| **Public event calendar** | `event_listings_count` and event titles | the event regressor (`#event_ids_distinct`) |
| **otwartedane.um.krakow.pl · msip.krakow.pl · dane.gov.pl** (Organiser-suggested) | **evaluated and not used** — Kraków datasets; the analysis is Sopot | none |

**None of it carries personal data, and none of it changes a transaction count.** Weather and events
enter only as regressors; geography enters only as a label and a coordinate.

## 6. Privacy constraints

Every published figure is an aggregate that passed the gates in `contracts/privacy.py`:
**≥ 30 distinct cards**, **≥ 3 distinct merchants**, **no merchant above 75%** of the cell, plus a
voluntary leave-one-out differencing test. The full argument, the measured pass counts and the exact
threshold semantics are `docs/PRIVACY.md`; the machine-readable audit is
`artifacts/privacy-report.json` (`python3 scripts/privacy_report.py --src /Users/kulma/Downloads
--out artifacts/privacy-report.json`).

## 7. Known limitations in the data

- **The pre-filter extract does not exist on disk.** Both emissions are post-filter, so the retention
  rate **16.127%** is computed against the largest surviving audit key, not against a file we can open,
  and the *order* of the MCC filter and the Sopot label filter is unobservable. Mechanism:
  `docs/CLEANING.md` §7; the four transaction-level artefacts on disk are
  `#raw_extract_absent`.
- **10.2% of rows carry no usable time.** **38,443** rows hold the sentinel `'000000'` and the original
  layer stamped every one of them `valid` (`#zero_timecode`, `#zero_timecode_pct`,
  `#sentinel_status_flagged`). They stay in totals and are excluded from every hourly view, so each
  hourly figure rests on 89.8% of the rows.
- **The merchant's city label can be wrong.** **2,527** rows carry a Sopot label and a postcode 450–500 km
  away, and `sopot_geo_conflict` is populated on **0** rows, so nothing in the extract distinguishes a
  mislabelled row from a correctly labelled one (`#foreign_postcode_rows`, `#geo_conflict_populated`).
- **Weather carries no spatial information.** **0** of the **10,483** observed local (date, hour) slots
  differ between postcodes; the theoretical axis is **13,102** slots
  (`#weather_spatial_variation`, `#local_hour_slots`, `#hour_axis_slots`). Any "weather by district"
  reading is unsupported. One timestamp — 2025-10-26 02:00, the DST fall-back hour — does carry two
  temperatures (**7.9** and **8.1**) because the repeated local hour was averaged into one bucket
  (`#weather_dual_temperature`, `#weather_dst_hour_dates`).
- **Sector boundaries are a model, not a register.** The package says so itself: *"Derived, not official
  Poczta Polska boundaries"*. Our pipeline grades all **151** sectors with a two-criterion rule —
  **116** observed, **24** inferred, **11** extrapolated (`#gis_sectors`, `#sectors_observed`). The
  audit's published split is **105 / 34 / 12**, which adds a third criterion (`extrapolated_pct < 10`)
  that the shipped sector model does not carry; that split is **MEASURED-AUDIT** and is *not*
  reproducible from this repository. Any count of "extrapolated areas" must say which rule it used.
- **There is no event-free day.** `event_listings_count` has minimum **2** across all 546 dates, so no
  clean baseline exists and the event effect is identified off a seasonal contrast, not a control
  period (`#event_listings_min`).
- **MCC 5812 only.** One category, so no cross-category comparison, no substitution story and no
  "restaurants versus retail" claim is available.
- **One postcode dominates.** `81-777` holds **51.1%** of transactions from **241** merchants
  (`#top_postcode_share`, `#top_postcode_merchants`), so city totals are largely one street.
- **The NULL-postcode bucket looks healthy and is not a place.** **6,431** rows from **179** merchants
  and **5,505** cards (`#postcode_branch_null_or_empty`, `#unknown_bucket_merchants`,
  `#unknown_bucket_cards`). It would pass the gates in most months; the panel excludes it by name.
