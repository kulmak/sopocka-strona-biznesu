# AGENTS.md — facts and rules for whoever works here next

You are working on **Sopocka Strona Biznesu**, the Visa Data Sprint submission.
Read this file completely before touching anything. Then read `../PLAN.md` and `../SWARM.md`.

## The one hard fact

**The submission deadline is 2026-09-30 12:00 CEST.** Everything is time-boxed. If a task cannot be
finished inside its slot, ship the smaller honest version and record the gap in `docs/ROADMAP.md`.
Never trade verification for scope.

## What this is

A merchant panel for small Sopot businesses, delivered as a new tab in the municipal resident card
(karta.sopot.pl). Built on anonymised synthetic Visa card transactions, **MCC 5812 only**, Sopot,
2025-01-01 → 2026-06-30. It tells a restaurateur what is *normal* for her street at this hour on this
weekday, how far today deviates, and which driver carries signal.

## Standing rules (violations fail the work)

1. **One owner per artifact.** Never write a file another agent is writing.
2. **No number without a command.** Every number in the UI, the deck or the docs has one row in
   `docs/EVALUATION.md` §5 naming the command and the artifact that produce it.
3. **Real gates, never summaries.** A green line from an agent is not evidence. The artifact and the
   command output are.
4. **No silent fallbacks.** Every degraded path renders an explicit, honest state. The old
   `Dane przykładowe` fallback showed fabricated numbers for the first 1.4–2.7 s of every load and is
   the anti-pattern this rule exists to kill.
5. **Never publish Organiser Data.** Public artifacts are the privacy-gated aggregate only. The raw
   parquet never enters git, never gets served, never lands in a public bucket.
6. **The privacy gates are 30 distinct cards / 3 merchants / ≤75% top-1 share**, per cell. They are
   implemented once, in `contracts/privacy.py`, mirrored in the app, and tested in `tests/privacy/`.
7. **Report in four beats:** TRIED / FOUND / CONCLUDED / NOT PROVEN, with evidence paths.

## Source material (READ-ONLY — never modify)

| What | Where |
|---|---|
| Transactions (378,212 rows, 72 cols) | `/Users/kulma/Downloads/mcc5812_transactions.part01.parquet`, `part02.parquet` |
| The prototype panel (canonical) | `/Users/kulma/Downloads/Dashboard website application planning/Panel v4.dc.html` + `sopot-model.js`, `sopot-map.js`, `sopot-data.js`, `support.js` |
| Municipal site replica (161 pages) | `/Users/kulma/Documents/Projects/Hackathon/karta-mockup/site/` |
| GIS package | `/Users/kulma/Downloads/Dashboard website application planning/uploads/Sopot_GIS_2026-09-29/` |
| Finished 300 s film | `/Users/kulma/Documents/ChatGPT/Hackathon/rytm-miasta/final/rytm-miasta-1080p.mp4` |
| **12 audit reports** | `/Users/kulma/Documents/Projects/Hackathon/research/` ← **read the relevant one first** |

## Measured facts you can rely on (all re-verified)

- 378,212 rows · 546 days · 2025-01-01 → 2026-06-30 · **62 Sopot postcodes** · 347 merchant
  descriptors · 160,127 distinct cards · median ticket 81.33 (fictional PLN).
- **81-777 holds 51.1%** of all transactions from 241 of 347 merchants. 98 of 151 sectors are empty.
- **Only 18 of 62 postcodes pass all three privacy gates, and they carry 90.7% of volume.**
- **Weather has zero spatial variation** (0 of 13,102 hourly timestamps differ across postcodes).
- **10.2% of rows (38,443) carry the sentinel time `'000000'`** and are marked `valid`.
- Raw event effect **59.8 pp → 9.0 pp** after month × weekday control. Rain β = −0.364 (t = −8.8).
- Backtest: weekday-matched mean gives **MAPE 24.1%** — the best of four candidates.
- The working demo presets are **81-777** and **81-759**. 81-718 draws a curve and withholds the
  number (defect D4) — it is the regression test, not a demo.

## The four defects that must stay fixed

| | Defect | Fix |
|---|---|---|
| D1 | Baseline averages all weekdays; a no-event Saturday reads +75% | same-weekday matched baseline |
| D2 | 10.2% of rows have a `'000000'` sentinel creating a phantom 02:00 spike | flag, exclude from hourly views, surface the count |
| D3 | The ≥30-card gate cannot fire — the card column is never read | implement G1–G4 in `contracts/privacy.py` |
| D4 | A thin cell draws a curve and withholds the readout | escalate the *number* to the parent unit, or print it with a band |

## Commands

```sh
make data      # rebuild artifacts/aggregate.json from the parquet  (needs the source files)
make run       # serve the demo at http://127.0.0.1:8099
make check     # pipeline + contracts + models + privacy tests
make demo-ready# headless render of every preset; fails on an empty or withheld lane
make deck      # rebuild docs/deck/deck.pdf
```
