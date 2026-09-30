# ARCHITECTURE — components, data flow, and the prototype boundary

A merchant panel for small Sopot businesses, delivered as one new tab in the municipal resident card
(`karta.sopot.pl`). It reads a single precomputed, privacy-gated JSON file and renders everything client
side; the raw transactions never reach the browser. **One static folder plus one gated JSON is the whole
deployment unit — no server code, no database, and no external origin at runtime.**

```bash
make run        # serves the demo at http://127.0.0.1:8099/app/  (rebuild the data first with: make data)
```

Numbers in this document carry the same provenance rule as `docs/ROADMAP.md`: `cmd:` is a repository
command that prints the number, `audit:` is a reading from `../research/*.md` marked **MEASURED-AUDIT**.

---

## 1. Components

```
  /Users/kulma/Downloads/                          ORGANISER DATA — never committed, never served
  ├── mcc5812_transactions.part0{1,2}.parquet   378,212 rows · 72 cols · MCC 5812 · 2025-01-01→2026-06-30
  ├── Sopot_GIS_2026-09-29.zip                  151 inferred sectors · 3,767 address points · 8,289 parcels
  └── sopot_weather_by_postal_code_*.csv        546 days × 155 codes · city-level (see §8)
          │  sha256 pinned in data/MANIFEST.sha256
          ▼
  pipeline/                                                          ◄── make data
  ├── ingest.py     stage 1  UNION ALL of both parts + disjointness proof on tran_id_raw
  ├── validate.py   stage 2  re-derive the three typed columns, assert 0 mismatches
  ├── normalise.py  stage 3  the 3-branch postcode rewrite, asserted to be an exact partition
  ├── filter.py     stage 4/5 Sopot membership · defect D2 · the non-Sopot postcode leak (2,527 rows)
  ├── enrich.py     stage 6/7 DST-correct local hour · calendar · real sector geometry · per-code gates
  ├── baseline.py            same-weekday baseline and the backtest
  └── aggregate.py  stage 9  build the cube ─► [ PRIVACY GATE ] ─► artifacts/aggregate.json
          │                                   G1 ≥30 cards · G2 ≥3 merchants · G3 ≤75 % share · G4
          ▼
  contracts/         aggregate.schema.json (ver 4) + AGGREGATE.md — validated on write and read
          ▼
  artifacts/aggregate.json   base64 typed arrays + per-code gate flags · the ONLY data file the app reads
          ▼
  app/               static HTML/CSS/JS: index.html · states/ · data/ · vendor/   (no bundler, no CDN)
          ▼
  integrations/municipal-site/   one <li> in the karta.sopot.pl nav + one page that hosts the app
```

### Module list

| Module | One-line responsibility | Owns |
| --- | --- | --- |
| `pipeline/ingest.py` | Union the two source parts and prove they are disjoint on both keys. | the population |
| `pipeline/validate.py` | Re-derive the three typed columns and assert zero mismatches. | types |
| `pipeline/normalise.py` | Rewrite the two postcode encodings into one, as an exact partition. | the join key |
| `pipeline/filter.py` | Sopot membership, the sentinel-time defect D2, the non-Sopot postcode leak. | row eligibility |
| `pipeline/enrich.py` | DST-correct local hour, calendar features, sector geometry, per-code gate inputs. | time and place |
| `pipeline/baseline.py` | Same-weekday baseline and the walk-forward backtest. | the comparison |
| `pipeline/aggregate.py` | Build the cube, assert every contract invariant, write the artifact. | **the privacy choke point** |
| `contracts/` | Fix the released artifact's shape and hold the gates; both writer and reader validate. | `aggregate.json` v4 · `privacy.py` |
| `app/` | Render the panel from `aggregate.json` alone, or render an explicit failure. | the merchant-facing UI |
| `app/data/` | Committed reduced geometry (`sopot-sectors.geojson`, `sopot-codes.json`, `sea-km.json`) and the city-level weather series. | map geometry, offline |
| `integrations/municipal-site/` | Describe and mock the insertion into the live municipal CMS. | the deployment boundary |
| `tools/` | Release gates: claim verification, Organiser-Data check, figures, deck build, replica build. | does the release pass |
| `tests/` | `pipeline/`, `contracts/`, `models/`, `privacy/` — the gates as executable predicates. | do the gates fire |
| `artifacts/` | Small committed outputs the deck cites; no file above 5 MB. | figures, film, claim table |
| `data/` | `MANIFEST.sha256`, the acquisition recipe, a ≤5 MB k-anonymised sample. | input provenance |
| `docs/` | Roadmap, architecture, glossary, ADRs, the claim→command index. | the assessable record |

---

## 2. Data flow

```
 raw parquet ──► ingest ──► validate ──► normalise ──► filter ──► enrich ──► aggregate ──► aggregate.json
      │             │           │             │            │          │            │              │
  378,212 rows   disjoint    typed cols    one postcode   D2 + the   local hour   the cube     one file,
  72 columns     on 2 keys   0 mismatch    encoding       leak       + gates      + gate       versioned,
  MCC 5812       asserted    asserted      partition      removed    per code     asserts      gated
```

| Stage | Input → output | Invariant asserted before the next stage |
| --- | --- | --- |
| `ingest` | two parts → one population | the parts are disjoint on `tran_id_raw` and `source_transaction_row`; never deduped |
| `validate` | raw varchars → typed columns | re-running the parse reproduces the stored column with 0 mismatches |
| `normalise` | raw postcode → `NN-NNN` | the three branches are an exact partition of the input |
| `filter` | rows → eligible rows | every removed row is attributed to a named rule (`excluded.*` in the artifact) |
| `enrich` | rows → cubes + gate inputs | the local hour axis is DST-correct; every code's centroid is inside its own polygon |
| `aggregate` | cubes → `aggregate.json` | `sum(cnt) == rows`, `sum(nat) == rows`, every preset passes **all** gates |

The cube is three flat typed arrays, not objects: `cnt` (`Uint16Array`), `amt` (`Uint16Array`, whole złoty,
with `amtScale` if the ceiling is hit) and `nat` (`Uint32Array`, city-wide only). Indexing is
`index(ci, di, h) = (ci * days + di) * hours + h` and must match byte-for-byte between pipeline and app —
that formula, not the JSON, is the real interface. `contracts/AGGREGATE.md` "Cell indexing"

The `codes` array reserves index 0 for the **excluded bucket** — non-Sopot postcodes and rows with no postcode — so the conservation invariants hold without inventing a geography for them.

---

## 3. Interfaces

| Interface | Written by | Read by | Failure behaviour |
| --- | --- | --- | --- |
| `contracts/aggregate.schema.json` | hand | `pipeline/aggregate.py`, `app/` | a file that does not validate is not written and not rendered |
| `artifacts/aggregate.json` (`ver: 4`) | `make data` | `app/` only | **the app refuses any other `ver` and shows an explicit error** — it never falls back to sample numbers |
| `contracts/privacy.py` | hand | `pipeline/_gates.py`, `tests/privacy/`, `app/` | the app mirrors the gate; a disagreement is a test failure, not a rendering choice |
| `docs/claims.json` | hand, verified by `make verify` | deck, README, these docs | a figure not in this file may not appear in the deck or the README |
| `data/MANIFEST.sha256` | hand, checked by `tools/check_no_organiser_data.py` | any reader | a hash mismatch means the inputs are not the inputs we measured |

The app's read path is one `fetch` of one same-origin file. There is no API, no auth token, no database connection and no query language anywhere in the runtime.

---

## 4. The privacy boundary — what never leaves the pipeline

**The boundary is drawn at the artifact, not at the read.** The pipeline may read an identifier where an
integrity proof requires it; **no identifier value ever reaches `aggregate.json`**, and the released file
carries counts and gate flags in their place.

| Identifier column | Where the pipeline reads it | What the artifact carries instead | Checked by |
| --- | --- | --- | --- |
| `pymt_crd_acct_num_raw` | `pipeline/enrich.py` — to count **distinct cards** per code, which is gate G1 | `codeMeta[code].nCards`, a count | `contracts/privacy.py` · `tests/privacy/test_gates.py` |
| `tran_id_raw` | `pipeline/ingest.py` — for the disjointness proof that the two parts never overlap | nothing | `pipeline/ingest.py` assertion |
| `mrch_nm_raw` | `pipeline/enrich.py` — to count distinct merchants (G2) and the top-1 share (G3) | `merchants` and `top1Share`, a count and a ratio | `contracts/privacy.py` · `tests/privacy/test_gates.py` |
| the other 69 columns | not read | nothing | `tools/check_no_organiser_data.py` |
| any per-transaction row | never emitted | a released cell is an aggregate or it is nothing | `tools/check_no_organiser_data.py --staged` |

What the artifact *does* carry is a per-code gate block — `nCards`, `merchants`, `top1Share`, and the gate booleans (`g1_cards` / `g2_merchants` / `g3_share` / `all`) — so the app can refuse a cell without recomputing anything and without ever seeing its inputs. The binding rules are `≥30 distinct cards`, `≥3 distinct merchants` and `≤75 % top-1 share`, per cell, from challenge §3; **G4**, the differencing test, is a voluntary strengthening defined in `contracts/privacy.py` alongside them.

Two consequences to hold us to. The gate is **k-anonymity, not differential privacy**: it bounds what one released cell reveals, not what a sequence of queries reveals. And the released artifact is safe to publish precisely because the identifiers were never in it — which is why `aggregate.json` can be served from a municipal CMS while the 26 MB parquet cannot.

---

## 5. Prototype boundary

Challenge §5 requires the submission to state which elements work and which need further development
before deployment. This is that statement, in one table and a closed three-token vocabulary.

| Component | Status | Needs development before deployment |
| --- | --- | --- |
| Aggregate pipeline (`pipeline/`) | **PARTIAL** | eight stages run and print their counters, but the run stops on its own DST assertion in `pipeline/enrich.py` before writing the artifact; deployment needs a scheduled ingest and a secure store |
| Privacy gate (`contracts/privacy.py`) | **PROTOTYPE (runs today)** | an independent audit; gate **G4** exists and is tested but is not yet asserted on every release path |
| Contract and schema (`contracts/`) | **PROTOTYPE (runs today)** | a versioning policy agreed with the city before the first schema change |
| Panel UI (`app/`) | **PROTOTYPE (runs today)** | authentication, role-based views, and URL state so a view can be linked |
| Demo presets (`artifacts/aggregate.json` → `presets`) | **PROTOTYPE (runs today)** | a user test with real owners; today they are chosen by a data-driven feasibility table, not by an owner |
| Model layer (baseline, drivers) | **PARTIAL** | a retraining cadence, drift monitoring, and a difference-in-differences that isolates the event effect from season |
| Municipal-site integration (`integrations/municipal-site/`) | **DESIGN ONLY** | an agreement with the city, a write path, and a decision on where the JSON is hosted |
| Film and deck assets | **PARTIAL** | re-encode and re-link; the film's on-screen numbers are corrected in the deck, not on the frames |

A component that does not run is never described in the present tense anywhere in these documents.

---

## 6. Municipal-site integration

The product is an eighth navigation tab on `karta.sopot.pl`, not a standalone site; the replica exists to prove the tab can be inserted without touching the theme.

| Question | Answer | Evidence |
| --- | --- | --- |
| Where does the tab go? | one `<li>` in `header … .main-menu nav#mobile-menu > ul`, after `menuItem_392` (`Załóż konto`); every captured page carries a comment marking the spot | `audit: ../research/karta-integration.md §0`, `karta-mockup/site/index.html:178-186` (MEASURED-AUDIT) |
| Does it need CSS changes? | no — the `<ul>` is centred by a flex parent and items are `inline-block`, so a ninth item re-centres on its own; on mobile `meanmenu.js` clones it | `audit: ../research/findings-ledger.md §B10` (MEASURED-AUDIT) |
| How is the panel embedded? | an iframe welded into a real municipal page — the only option that removes the CSS and keyboard collisions, and it is visually indistinguishable because the surrounding chrome *is* the real chrome | `audit: ../research/karta-integration.md §0, §6` (MEASURED-AUDIT) |
| What is mocked? | the write path: nothing in this repository posts to the municipal CMS. Forms are stubbed with `data-mock-action` preserving the original `action` verbatim | `karta-mockup/NOTES.md` §5 |
| What is not mocked? | the surrounding chrome — the page the demo sits in is a faithful capture of the live site, verified to 0 difference on the news index | `karta-mockup/NOTES.md` §3 |

---

## 7. Offline story, and the deployment shape

**Zero CDN origins at runtime.** The prototype panel it replaces loaded React, ReactDOM and Babel from `unpkg.com`, d3 and Leaflet from the same host, `hyparquet` and its ZSTD codec from `cdn.jsdelivr.net`, and the display font from `fonts.googleapis.com` — six external origins, any one of which failing silently re-rendered *fabricated* numbers. None of that survives here: React, Babel standalone, d3, Leaflet and every font are vendored into `app/vendor/`, the geometry and weather are committed under `app/data/`, and the only network read is the same-origin data file.

| Asset class | Where it comes from at runtime | Network needed |
| --- | --- | --- |
| HTML, CSS, JS | `app/` and `app/vendor/` | none |
| Fonts | self-hosted, latin + latin-ext (Polish diacritics) | none |
| Data | `artifacts/aggregate.json`, same origin | none |
| Map geometry | `app/data/*.geojson`, reduced from the GIS package | none |
| Map tile imagery | *not bundled* | a tile server, or a blank frame with working markers |

That last row is the honest exception: the styled map frame and every marker work offline, the basemap imagery does not. `audit: ../research/findings-ledger.md §B12` (MEASURED-AUDIT)

**Deployment shape:**

```
  municipal CMS  ──iframe──►  one page  ──fetch──►  artifacts/aggregate.json
                              app/ (static)          same origin · ver 4 · privacy-gated · cacheable
```

Three properties follow, and they are the argument for the design. There is **no server to operate**: the unit is a directory of static files plus one JSON. There is **nothing confidential to host**, because the identifiers were dropped at ingest and the gate ran in the pipeline. And a cold visitor **never sees a number that is not measured** — the old panel showed `Dane przykładowe` for the first 1.4–2.7 s of every load, and that behaviour is deleted rather than hidden.

---

## 8. Known limitations

- **Weather is city-level and duplicated across 155 postcodes** — 0 of 13,102 hourly timestamps carry more than one distinct sky condition, mean cross-postcode temperature SD is 8 × 10⁻⁶ °C — so no per-area weather claim is derivable, only per-area *sensitivity* to city weather. `audit: ../research/geo-enrichment.md §6.2` (MEASURED-AUDIT)
- **The postcode sectors are an inferred model, not published boundaries.** 105 of 151 are `observed`, **12 are `extrapolated`**, and Sopot has no official district names, so every district label in the UI is our own toponym. `audit: ../research/geo-enrichment.md §3.3, §1.1` (MEASURED-AUDIT)
- **One MCC and 7 of 72 columns.** The dataset contains exactly one merchant-category value (`5812`), so the pipeline cannot generalise to another sector without new data and no cross-category comparison is possible.
- **10.2 % of rows (38,443) carry the sentinel time `'000000'`** — kept in the totals, excluded from hourly views, counted in `excluded.zeroTimecode` — so every hourly figure rests on 89.8 % of the rows and the artifact says so rather than absorbing it.
- **The gate block in `aggregate.json` carries G1–G3, not G4.** G4 — the differencing test — is implemented in `contracts/privacy.py` and covered by `tests/privacy/test_gates.py`, but it is not asserted on every release path, so a merchant can still in principle subtract her own settlement volume from a released area total.
- **Babel standalone still compiles in the browser at load.** Vendoring removed the external origin and the silent-fallback failure mode, but not the parse cost — a build step is the deployment fix, and the app is not yet built.
- **The pipeline is a reconstruction.** No script produced the original 189 k-row subset, so `make data` reimplements it rather than recovering it; if its exclusion counters differ from the shipped artifacts, the reconstruction is wrong. `audit: ../research/work-timeline.md §6.3 U4` (MEASURED-AUDIT)
