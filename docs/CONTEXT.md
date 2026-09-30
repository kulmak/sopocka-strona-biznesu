# CONTEXT — the words a reader must not misread

*Sopocka Strona Biznesu* is a merchant panel for small businesses in Sopot, built on anonymised card
transactions. It is read by restaurateurs, city officials and a jury; every term below has one meaning in
this repository, and the panel uses the same word for it. This file is a glossary and nothing else — for
how the system is built, read `docs/ARCHITECTURE.md`.

## Domain language

- **MCC** (Merchant Category Code): the four-digit code a card network assigns to a merchant's line of
  business. The panel's data contains exactly one value, `5812` (restaurants). _Avoid_: "category",
  "branch" as synonyms for MCC.
- **PKD** (*Polska Klasyfikacja Działalności*): the Polish statutory business classification, e.g.
  `56.10.A`. It shares no key with MCC, so the panel carries a hand-curated 7-entry bridge; a merchant
  picks her PKD and the bridge resolves it to an MCC. _Avoid_: treating PKD and MCC as interchangeable.
- **MCC group** (*grupa MCC*): a pool of several MCCs shown together (GASTRO, HOTEL, FOOD, …) so a small category can satisfy the privacy gate without exposing anyone.
- **kaskada** (cascade): the ordered fallback deciding what a merchant may see — her own MCC locally →
  the MCC group locally → the MCC group for the region → analysis blocked. Each level names why it was
  reached; the last level is a compliance answer, not an error state.
- **obszar** (area): the unit a number is attached to — one postcode sector, or a named parent of
  several. Every area value carries *„Dane dla obszaru <kod>, nie dla Twojego lokalu."* _Avoid_:
  "location"; `region` (*region*) is reserved for the Trójmiasto fallback.
- **rejon** (district): a group of sectors sharing a postcode stem (`81-77x`). Sopot has no official
  district names, so a *rejon* is a grouping key, not a place name; any readable name in the UI is our
  own toponym.
- **obszar ukryty** (hidden area): an area failing a privacy gate at every reachable level. It renders
  hatched with a reason, **never as zero and never as blank** — "no business here" is a different and
  false claim from "we may not show you this". _Avoid_: "empty", "no data".
- **THIN**: the statistical floor for drawing a comparison — the trailing 30-day base must reach 12 transactions in the 3-hour window, or the hour is reported as too thin to read. THIN is a *readability* guard, not a privacy gate; the two are never merged in copy.
- **„zwykle"** (usually): the comparison baseline, always a same-weekday mean over the last four weeks,
  never an average over all weekdays. On screen it is the grey reference line; in text,
  `zwykle (średnia 30 dni)`.
- **k-anonimowość** (k-anonymity): the release rule — a shown cell must contain at least 30 distinct
  cards from at least 3 distinct merchants with no single merchant above 75 % of the cell. It is **not**
  differential privacy: it bounds one released cell, not a sequence of queries.
- **privacy gate**: one of the predicates above, applied per cell by the pipeline — **G1** (≥30 cards), **G2** (≥3 merchants), **G3** (≤75 % top-1 share), and **G4**, a differencing test that strengthens the letter of the rule.
- **sektor** (sector): one modelled postcode polygon. Boundaries are inferred from parcels, addresses and
  the Poczta Polska street reference, not published by the operator; each sector carries a confidence
  class — `observed`, `inferred`, `extrapolated` or `none`. _Avoid_: "postcode boundary" unqualified.
- **karta / podmiot / transakcja** (card / merchant / transaction): three different denominators, never
  interchanged. A **card** is an anonymous payment instrument, counted by `nCards`; a **merchant**
  (*podmiot*) is a distinct merchant descriptor, counted by `merchants`; a **transaction** is one row.
  The gate is defined on cards and merchants, so a transaction count is never offered as evidence of one.
- **wpływ** (uplift / impact): the deviation of a period from its same-weekday baseline, in percent or in
  percentage points. `wpływ +17 pkt` is points, `+108 %` is percent; the panel states which.
- **driver**: a variable explaining part of a deviation — weather, weekday, month, city events. A driver
  is reported as an explanation, never multiplied into a forecast unless it measurably improves it — and
  on this dataset it does not.
- **sentinel time**: the value `'000000'` in the transaction-time column, carried by 38,443 rows (10.2 %)
  that are otherwise marked valid. It means "time unknown", so those rows count in totals and are
  excluded from every hourly view; the artifact reports the count rather than spreading or deleting them.
- **preset**: a starting state of the panel (a venue, a day, an hour) offered to the merchant. A preset is
  admissible only if every area it touches passes all three gates; presets are chosen by a data-driven
  feasibility table, not by hand.
- **cube**: the precomputed aggregate — counts, whole-złoty amounts and issuer-country buckets over
  `code × day × hour`. It is the only data structure the app reads, and `contracts/AGGREGATE.md` defines
  it.
- **Organiser Data**: the transaction and reference files supplied by the event organiser. Confidential —
  never committed, never served, never sent to a public model. The released artifact is an aggregate of
  it and nothing else.

## Status vocabulary (closed lists — do not invent tokens)

| Token | Means |
| --- | --- |
| `MEASURED` | produced by a command on real data, with the command recorded |
| `MEASURED-AUDIT` | same, but the command is recorded in `../research/` and not yet as a `make` target |
| `DERIVED` | computed from other measured values |
| `INFERRED-FROM-CODE` | read out of source and not yet exercised |
| `SIMULATED` | produced on generated or placeholder data; never rendered in the same style as a measured number |
| `NOT PROVEN` | the claim stands but its falsifier has not been run — the falsifier is always named |
| `PROTOTYPE (runs today)` / `PARTIAL` / `DESIGN ONLY` | the three permitted prototype-boundary tokens, used in `docs/ARCHITECTURE.md` §5 and README §4 |

_Avoid_: "approximately", "roughly", "should be", "mostly works" — an uncertainty is a `±`, a sample size,
a tolerance or a named falsifier.
