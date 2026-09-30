# Solution

**Sopocka Strona Biznesu** turns 378,212 anonymised Visa card transactions into one new tab in the
municipal resident card: a `Panel przedsiębiorcy` (entrepreneur panel) that tells a small Sopot
restaurateur what is *normal* for her street at this hour on this weekday, how far today deviates, and
which driver carries the signal. The finished result is the `DataSprint` page integrated into a faithful
copy of `karta.sopot.pl`. Demo: <https://kulmak.github.io/sopocka-strona-biznesu/app/>

## Project title

**Sopocka Strona Biznesu** — *Sopot Business Page* — `„Miasto i firmy oddychają tym samym rytmem."`
("the city and the businesses in it breathe the same rhythm."). The screen a business owner opens is
`Panel przedsiębiorcy`, and the municipal navigation entry that leads to it is `DataSprint`.

## The problem

The owner of a ten-table restaurant in Sopot has no analyst, will not buy data and will not pay for a
report. Card payments in her city *are* measured — every one of the 378,212 rows in this dataset is a
restaurant payment in Sopot — but that measurement ends up in a municipal management report, not in her
kitchen. So she plans on memory and habit: how many people to roster, how much to prep, whether to run a
promotion. She cannot answer three ordinary questions. Will the coming Saturday be an ordinary Saturday?
If it rains, how much of her trade goes with it? When a concert lands at the hall up the road, does that
reach her street at all? A dashboard of charts would not help her; she does not have the time or the
training to read one.

## The end user

**The owner-operator of a small food-service venue (MCC 5812) in Sopot** — concretely, a ten-table
restaurant in a single postcode, with no analyst, no CRM and no BI tool. She is not a data person: she
reads one screen between the lunch and dinner services, on a phone, and she needs a sentence, not a
scatter plot. The **second reader is the City of Sopot's card office** (`Biuro Karty Sopockiej` in the
Urząd Miasta Sopotu), which can offer the same tab to businesses that settle in the city without
building an analytics team.

## The solution

One new tab in the service the city already uses. The integration is deliberately small: one `<li>` in
the primary menu plus one page, `app/pl/datasprint/index.html`, which opens the dashboard shell
`app/v2/index.html` and states `Panel przedsiębiorcy otwiera się w osobnym oknie`. The shell embeds the
panel in an iframe, so the surrounding municipal chrome stays exactly the real chrome.

| Sidebar section | What it holds |
|---|---|
| `Wydarzenia i biznes` | `Panel przedsiębiorcy` — the day's expected transactions, the deviation from a typical same-weekday reading, the named driver, the event calendar, the area map |
| `Mój rynek` | the market/forecast view (`market.html`, demo mode) for the same venue |
| `Moje Sprawy` | the owner's municipal case list — permits, fees, filings — kept from the portal layout |

## What the user gets

The panel is **calibration of expectations, not a dashboard**: four sentences, each computed in the
pipeline rather than written by a model.

| The screen says | The decision it supports |
|---|---|
| `Dziś spodziewaj się ~X transakcji` | **staffing** — how many people to roster for that service |
| `To o N% więcej niż typowa sobota w czerwcu` | **stock and prep** — whether to order the ordinary quantity or more |
| `Główny czynnik: deszcz` with its contribution in pp | **promotion timing** — whether a rainy day needs an offer to defend the covers |
| the same readout for an event day | **opening hours** — whether to extend a service when the city is full |

## How it works

```
parquet ─► ingest ─► validate ─► normalise ─► filter ─► enrich ─► aggregate ─► artifacts/aggregate.json
                                                                      │
                                                           [ PRIVACY GATE ]
                                                                      ▼
                                     app/ (static) ──fetch──► the one data file · no server, no CDN
```

| Stage | File | What it does |
|---|---|---|
| ingest | `pipeline/ingest.py` | `UNION ALL` of both parquet parts, disjointness asserted on two keys |
| validate | `pipeline/validate.py` | re-derives the typed columns, asserts 0 mismatches |
| normalise | `pipeline/normalise.py` | the three-branch postcode rewrite, asserted to be an exact partition |
| filter | `pipeline/filter.py` | Sopot membership, the foreign-postcode leak, the `'000000'` sentinel |
| enrich | `pipeline/enrich.py` | DST-correct local hour, calendar, sector geometry, per-code gate inputs |
| aggregate | `pipeline/aggregate.py` | builds the cube, asserts every contract invariant, writes the artifact |
| gate | `contracts/privacy.py`, `pipeline/_gates.py` | `≥30` cards, `≥3` merchants, `≤75%` share, plus the differencing test |

The contract is `contracts/aggregate.schema.json` (pinned to `ver: 5`); the writer and the reader both
validate. `app/aggregate-loader.js` refuses any other version and has **no fixture fallback** — a missing
file yields an explicit error and no figure. `make data` exits 0, produces a byte-identical artifact on a
re-run, and `make verify` recomputes all 202 published numbers.

## Two headline findings

**1. Almost all of the "event effect" is the season.** Days split by event count look like a huge effect:
the most event-heavy days run **+32.9 pp** against a same-weekday mean and the least event-heavy
**−26.9 pp**, a **59.8 pp** spread. Residualise on month and weekday dummies and the spread collapses to
**8.8 pp** (+4.1 pp / −4.8 pp). The raw leg reproduces the inherited audit exactly; the collapse is the
finding, and it is in the deck rather than a footnote. What survives every specification is **rain**
(t ≤ −8.5 everywhere, −9.7 in the primary one).

**2. The forecast error is 24.1%, not 17%.** The finished film claimed a 17% error rate; our own walk-forward
backtest over 490 days measures the mean-of-4-same-weekdays baseline at **MAPE 24.1%** (a different, weaker
estimator than the one we ship). The shipped model — that baseline plus weather and events — reaches
**20.5% MAPE** against a best baseline of **22.8%**, with the 80% interval covering **80.6%** of days, so
the interval is calibrated rather than merely narrow. An expanding OLS reaches **16.13%** and is **not
shipped**, because it is less explainable to the person the panel is for.

## Prototype vs. what still needs work

| Component | Status | Needs before deployment |
|---|---|---|
| Aggregate pipeline (`pipeline/`) | **PARTIAL** | a scheduled ingest and a secure store; the shipped run is a reconstruction of an unrecorded one |
| Privacy gate (`contracts/privacy.py`) | **PROTOTYPE (runs today)** | an independent audit; gate G4 is implemented and tested but not asserted on every release path |
| Contract and schema (`contracts/`) | **PROTOTYPE (runs today)** | a versioning policy agreed with the city |
| Panel UI (`app/`) | **PROTOTYPE (runs today)** | authentication, role-based views, URL state so a view can be linked |
| Demo presets | **PROTOTYPE (runs today)** | chosen from a data-driven feasibility table, not by a real owner |
| Model layer | **PARTIAL** | a retraining cadence, drift monitoring, and a difference-in-differences isolating the event effect |
| Municipal-site integration | **DESIGN ONLY** | an agreement with the city, a write path, a host for the JSON |

Honest limits we do not paper over: the 151 area boundaries are a **model, not official Poczta Polska
geometry** (12 of 151 extrapolated); there is **no commercial-POI register**, so we never claim "X% of
restaurants in this area"; weather is **city-level**, so no per-district weather claim is derivable; the
event calendar carries **no hours**; the basemap imagery is the one runtime network dependency.

## Requirement traceability

| Requirement (challenge §4/§5/§3) | Where it is satisfied |
|---|---|
| Project title | this document, `## Project title`; `SUBMISSION.md` §1; `deck/deck.pdf` slide 1 |
| Short description of the problem | `## The problem` above; `SUBMISSION.md` §2 |
| Solution description + value for the end user | `## The solution`, `## What the user gets`; `SUBMISSION.md` §3 |
| Named end user | `## The end user`; `SUBMISSION.md` §4 |
| Description of the data used | `docs/03_DATA.md`; `SUBMISSION.md` §5 |
| Presentation PDF, max 10 slides | `deck/deck.pdf` — **10 pages**, verified |
| Link to project materials | <https://kulmak.github.io/sopocka-strona-biznesu/> |
| Code repository | <https://github.com/kulmak/sopocka-strona-biznesu> |
| Working demo link | <https://kulmak.github.io/sopocka-strona-biznesu/app/>; municipal tab `app/pl/datasprint/index.html` |
| Prototype vs. further development (§5) | `## Prototype vs. what still needs work`; `src/sopocka-strona-biznesu/docs/ARCHITECTURE.md` §5 |
| No identification; ≥30 cards; ≥3 entities; none >75% (§3) | `docs/04_PRIVACY.md`; `src/sopocka-strona-biznesu/contracts/privacy.py` |

_Source material: SUBMISSION.md, DELIVERED.md, research/*, the challenge brief._
