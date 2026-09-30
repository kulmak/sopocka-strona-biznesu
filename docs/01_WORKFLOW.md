# Workflow — what we did

**Deadline 2026-09-30 12:00 CEST.** The build was one human operator directing AI agents — 15 agent
sessions, 7 Codex rollouts, one design thread that left no transcript, and **six real product
instructions** in total (`research/work-timeline.md` §4). "Done" meant a package someone else can
check: `make data` exits 0 and is byte-identical on a re-run, `make check` and `make verify` are
green, the released artifact holds no cell that fails its own privacy gates, every demo preset prints
a real number, and the result ships as a new `DataSprint` tab inside a copy of `karta.sopot.pl`. No
language model sits in the product's decision path (`SUBMISSION.md` §9).

## At a glance

| # | Phase | What came out of it |
|---|---|---|
| 1 | Problem framing | one named reader; `Strona Biznesu` |
| 2 | Data intake and profiling | 378,212-row MCC 5812 subset |
| 3 | Cleaning and lineage | `pipeline/` (8 stages) → `artifacts/aggregate.json` |
| 4 | Analysis and findings | drivers, baseline, `docs/claims.json` |
| 5 | Model | backtest with intervals; `artifacts/backtest.json` |
| 6 | Privacy gate | `contracts/privacy.py`; 17 of 62 areas released |
| 7 | Dashboard build | `app/` — parquet read in the browser |
| 8 | Municipal integration | the `DataSprint` tab in the site copy |
| 9 | Verification | adversarial review; 10-agent audit fleet |
| 10 | Publication | deck, film, GitHub Pages, `SUBMISSION.md` |

## Phase 1 — Problem framing

One reader: the owner of a ten-table restaurant in one postcode, no analyst, no CRM, with Sopot's card
office as second reader (`SUBMISSION.md` §4). `README.md` §2 fixes the product as calibration of
expectations, not a dashboard — four sentences about one day, opening with
`Dziś spodziewaj się ~X transakcji`.

## Phase 2 — Data intake and profiling

Two password-protected archives (17.5 GB AES, 84.2 GB ZipCrypto) met a full cryptanalytic campaign
that produced a 0-byte `full.hash` and an interrupted session; `work-timeline.md` gap G2 records that
the password in fact arrived through the participant channel, **unevidenced**. Profiling gave 378,212
rows, 72 columns, 546 days, 62 postcodes, 347 merchants, 160,127 cards, MCC 5812 only.

## Phase 3 — Cleaning and lineage

Filtered to Sopot, typed, postal-normalised, joined to weather and events, stamped with 41 evidence
columns: `mcc5812_transactions.part01/02.parquet`, 2 × 189,106 rows, DuckDB 1.5.6, later rebuilt as
the eight-stage `pipeline/`. The original run was never recorded (`work-timeline.md` U4), so
`make data` **reimplements** it. Two defects survived: 38,443 rows (10.2 %) carry the sentinel time
`'000000'` while marked valid, and 2,527 rows pair a Sopot city label with a non-Sopot postcode.

## Phase 4 — Analysis and findings

The cleaned subset plus weather and events produced the rhythm, the drivers, and `docs/claims.json`,
binding every published figure to the command that prints it. Rain is the robust driver (t ≤ −8.5 in
every specification, −9.7 primary); the event effect is **59.8 pp raw and 8.8 pp under month × weekday
control**; weather does not vary by postcode (0 of 13,102 hours); `81-777` alone holds 51.1 % of rows.

## Phase 5 — Model

The shipped model is an explicit formula — the mean of four same weekdays plus a factor regression —
with a rolling backtest and an 80 % interval (`artifacts/backtest.json`). MAPE 20.5 % against a best
baseline of 22.8 %, the P80 interval covering 80.6 % of days: calibrated, not merely narrow. An
expanding OLS reaches 16.13 % and is **not shipped**, being less explainable to the owner it is for.

## Phase 6 — Privacy gate

Cells pass a four-level cascade (own MCC → MCC group locally → group region → blocked) at 3 merchants,
30 cards and no merchant above 75 % share, plus a leave-one-out differencing gate;
`contracts/privacy.py` carries 31 tests against 18 fixtures, non-vacuity proven by perturbing each
threshold until its test flips. 17 of 62 areas pass, carrying 89.95 % of volume, and the 33,197
transactions in suppressed areas stay inside the exact city total. This is k-anonymity, **not**
differential privacy.

## Phase 7 — Dashboard build

The 26 MB parquet is read in the browser (hyparquet plus an explicit ZSTD compressor), aggregated
into typed arrays of `MAXC(200) × DAYS(546) × 24`, cached in IndexedDB behind `CACHE_VER = 3`, and
bucketed by local hour with a **per-day** Europe/Warsaw DST offset. `app/` needs no server and reads
no card numbers. 26 MB is its entire cost: 2.4 s cold, 0.16 s warm.

## Phase 8 — Municipal integration (the `DataSprint` tab)

The live `karta.sopot.pl` was mirrored into a hostable replica — 161 pages, 903 mirrored URLs, 14
documented `STRONA ZASTĘPCZA` stubs, 10 CDP probes — and the panel attached with one `<li>` in the
primary-menu `<ul>` (`cb0f0b4`, `71347fe`); here
`src/tools-datasprint-tab/add_datasprint_tab.py` writes a `DataSprint` item into 166 pages, served at
`app/pl/datasprint/index.html`. An eighth menu item needs **no CSS change**, and 7 of 12 page ×
viewport comparisons are byte-identical to live (0-diff on Aktualności).

## Phase 9 — Verification

A ten-agent audit fleet, then an adversarial pass over four surfaces — claims, privacy, demo,
reproducibility — fixed or documented every finding: 12 reports in `research/` (~9,000 lines) plus
the fix commits below. Every failure was found by our own tooling rather than by a juror.

## Phase 10 — Publication

The verified build became a deck, a 90-second film, a public repository and a GitHub Pages site
carrying the demo, the municipal tab and `SUBMISSION.md` with the mandatory AI disclosure;
`DELIVERED.md` lists every link. The remaining risks are human: nobody had looked at the screenshots
or the film, the portal was unconfirmed, and the §11 copyright transfer needs a team decision.

## What went wrong and how we caught it

- **Both demo presets rendered empty**, in Sopot's thinnest postcodes: the baseline window held 7 and
  0 transactions, and a 126-state sweep found venue 1 thin in **70 of 72** states and venue 2 in
  **72 of 72**. They now sit in `81-777` and `81-759`, from a data-driven feasibility table.
  (`research/live-repro.md` §3–4.)
- **The privacy gate did not exist on the release path.** 37 postcodes published a series *and* their
  merchant, card and top-1-share counts while their own `gates.all` was false — `81-814` showed 1
  transaction, 1 card, 1 merchant. Commit `57d4469` ships artifact v5: 17 released, 37 suppressed with
  their name and reason, and `sum(cnt) + suppressedVolume == rows` asserted.
- **We were publishing our own suppression audit.** `artifacts/privacy-report.json`, whose first line
  reads "do not serve, do not bundle", was committed and served at HTTP 200 with every postcode's
  counts. Commit `79bc7e8` untracked it, added `privacy-summary.json` with funnel counts only, and
  moved the review out of the repository.
- **The panel invented numbers when the aggregate was missing**, painting a fabricated dashboard from
  fixture data under the real row count. Commit `c9af96b` deletes that path: `?agg=` is now a
  developer action, and a blocked file yields an explicit error and no figure.
- **The headline claim was wrong and we corrected it ourselves.** The event effect runs 59.8 pp raw
  and **8.8 pp** under control — in the deck, not a footnote (`SUBMISSION.md` §8; commit `2f22654`
  moved it from 9.0 pp). The same pass fixed ten published figures with no command behind them,
  including the sector split (116/24/11, not 105/34/12).
- **Four claims in the film contradicted our own data** — 475,000 transactions, merchant categories
  absent from a single-MCC dataset, and a 17 % error rate against a measured 24.1 %. Corrected in the
  90-second cut; `artifacts/film/RECONCILIATION.md` lists ten residuals, including the uncorrected
  `+38 %` placeholder and unconfirmed photo rights. (`DELIVERED.md` counts six invented categories,
  `README.md` five MCCs.)

## Verification gates

| Gate | Command | Result |
|---|---|---|
| Data pipeline | `make data` | exit 0, 8 stages, byte-identical across repeat runs |
| Gate tests | `make check` | **64 passed** |
| Claim ledger | `make verify` | **202/202** published numbers re-derived |
| Live demo | `make demo-ready` | **39/39** assertions, 3 presets |
| Load budget | demo gate | 2.4 s cold / 0.16 s warm |
| Origin isolation | network log | **0** off-origin requests |
| Organiser-data leak guard | `python3 tools/check_no_organiser_data.py` | clean tree passes; **6/6** planted leaks caught |
| Adversarial review | 4 surfaces attacked | every finding fixed or documented |

These are the final revision's numbers. They moved during the day — 62 passed, `make verify` 29/29
then 186/186 — and both make targets were briefly **red** while the v5 release gate and the app
contract were half-landed (`adversarial-review.md`, "State of the tree").

## Reproducing this

```bash
git clone https://github.com/kulmak/sopocka-strona-biznesu
cd sopocka-strona-biznesu
make data        # 8 stages -> artifacts/aggregate.json (needs the Organiser Data)
make check       # the gates as tests
make verify      # recomputes all 202 published numbers
make run         # demo at http://127.0.0.1:8099/app/
make demo-ready  # 39 assertions against the live URL
make deck        # slide deck from docs/deck/slides.html
python3 tools/check_no_organiser_data.py   # leak guard
```

The Organiser Data is not redistributed (challenge §7.2–7.4), so `make data` cannot run from a clean
clone; everything after it does (`README.md` §1).

## Timeline

- **2026-09-28 18:01** — earliest artifact: `Dictionary_data_Visa.xlsx`.
- **2026-09-28 22:28–22:40** — the 84.2 GB archive lands; the password campaign is interrupted.
- **2026-09-28 23:27** — GIS extracts pulled from `mapa.um.sopot.pl/iip/ows`.
- **2026-09-29 13:02–14:28** — the `karta.sopot.pl` replica built and handed over.
- **2026-09-29 21:31** — a `git init` never committed to (0 commits, 408 dangling blobs).
- **2026-09-29 22:23–00:41** — the *Rytm miasta* film; its agent refused two unverified brief claims.
- **2026-09-30 01:44 / 02:09** — `.csv.xz` then parquet written by DuckDB 1.5.6.
- **2026-09-30 03:29–03:38** — replica re-rendered after the live site changed 16 px → 14 px.
- **2026-09-30 03:55–04:12** — finalisation session and the ten-agent audit fleet.
- **2026-09-30** — 17 commits, `4b25d6a` "chore: bootstrap repository" through `2f22654` "docs: fix
  the ten numbers our own documentation pass could not verify", including `79bc7e8` and `57d4469`.
- **2026-09-30 12:00 CEST** — deadline.

_Source material: research/work-timeline.md, research/findings-ledger.md, DELIVERED.md, SUBMISSION.md, git history._
