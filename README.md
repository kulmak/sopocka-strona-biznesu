# Sopocka Strona Biznesu — a merchant panel for Sopot's small businesses

**„Miasto i firmy oddychają tym samym rytmem."** — *the city and the businesses in it breathe the same
rhythm.* One new tab in the municipal resident card (`karta.sopot.pl`) tells a restaurateur what is
*normal* for her street at this hour on this weekday, how far today deviates, and which driver carries
the signal. **It is built on 378,212 anonymised card transactions, and it publishes no cell that fails
the challenge's three privacy gates — no card, merchant or transaction is identifiable from it.**

**Live now.**
Demo — <https://kulmak.github.io/sopocka-strona-biznesu/app/>
Code — <https://github.com/kulmak/sopocka-strona-biznesu>
Deck — <https://kulmak.github.io/sopocka-strona-biznesu/deck/deck.pdf>

`make data` runs all eight stages and exits 0, producing `artifacts/aggregate.json` byte-identically on
repeat runs. `make check` is green. `make verify` recomputes all 200 published numbers. The demo gate
passes **39 of 39** assertions against the live URL: every preset prints a real number, draws a full
venue lane, keeps every released cell inside the three privacy gates, and shows no fabricated value at
any point in the load. First real number: ~2.5 s cold, ~0.17 s warm.

---

## 1. Run it locally

```bash
make data        # rebuild artifacts/aggregate.json from the source parquet — needs the Organiser Data
make run         # serves the demo at http://127.0.0.1:8099/app/
```

`make data` needs the Organiser Data, which we do not redistribute (challenge §7.2–7.4). Everything after
it — the app, the map, the gates — runs from that one JSON with no network access at all. Other targets:
`make check` (the gates as tests), `make verify` (recomputes every published number and fails if one has
moved), `make deck` (the slide deck from `docs/deck/slides.html`).

---

## 2. What this is

A ten-table restaurant on ul. Emila Platera has no analyst and no benchmark. The city holds, and already knows how to disclose, the aggregate payment signal she cannot buy — but it arrives in a management report, not in her kitchen. This panel returns it: one sentence about one day, in the card she already carries. Built for the **owner-operator of a small food-service venue (MCC 5812) in Sopot**, with the **City of Sopot's card office** as the second reader.

---

## 3. What is proven

Each row is a claim, its English rendering and the artifact that owns the number. **No value here travels without a command**, including the headline above: every figure is in `docs/claims.json` — 200 rows, each naming the command that prints it — or in the document cited beside it.

| Claim — Polish | English | Verified by |
| --- | --- | --- |
| „378 212 transakcji MCC 5812 w Sopocie, 546 dni" | "378,212 MCC 5812 transactions in Sopot over 546 days" | `docs/claims.json#rows` · `data/MANIFEST.sha256` |
| „38 443 wiersze (10,2 %) mają czas zastępczy `'000000'` i są oznaczone jako poprawne" | "38,443 rows (10.2 %) carry the sentinel time `'000000'` and are marked valid" | `docs/claims.json#zero_timecode` · R22 |
| „18 z 62 kodów przechodzi wszystkie trzy bramki i niesie 90,7 % wolumenu" | "18 of 62 postcodes pass all three privacy gates and carry 90.7 % of volume" | `docs/claims.json#gate_all_three` · `contracts/privacy.py` |
| „Pogoda nie różni się między kodami: 0 z 13 102 godzin" | "Weather does not vary by postcode: 0 of 13,102 hourly timestamps" | `docs/claims.json#weather_spatial_variation` · R12 |
| „Efekt wydarzeń 59,8 pp → 9,0 pp po kontroli miesiąc × dzień tygodnia" | "The event effect collapses from 59.8 pp to 9.0 pp under month × weekday control" | R27 · `docs/adr/0003` |
| „Deszcz, nie wydarzenia: β = −0,364 (t = −8,8)" | "Rain, not events, is the robust driver: β = −0.364 (t = −8.8)" | `docs/claims.json#driver_rain_t` · `docs/claims.json#driver_events_t` |
| „Backtest: MAPE 24,1 % — najlepsza z pięciu metod" | "Backtest: MAPE 24.1 %, the best of five candidate methods" | `docs/claims.json#backtest_mape_base` |
| „Granice obszarów są modelowane, nie oficjalne; 12 z 151 ekstrapolowanych" | "Area boundaries are modelled, not official; 12 of 151 are extrapolated" | R11 · `docs/ARCHITECTURE.md` §8 |

*R-numbers are entries in `docs/ROADMAP.md`.* Two structural proofs matter more than any single figure: **the claims are reproducible** (`docs/claims.json` binds each one to the command that prints it), and **the failures are on the record** (`docs/ROADMAP.md` carries 30 four-beat entries, including the ones where we were wrong).

---

## 4. What is a prototype

Challenge §5 requires this split. It is the same table as `docs/ARCHITECTURE.md` §5.

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

--- | --- | --- |
| Aggregate pipeline (`pipeline/`) | **PARTIAL** | eight stages run and print their counters; the run stops on its own DST assertion in `pipeline/enrich.py` before writing the artifact, so `aggregate.json` does not exist yet |
| Privacy gate (`contracts/privacy.py`) | **PROTOTYPE (runs today)** | an independent audit; gate **G4** is implemented and documented but not yet asserted on every release path |
| Contract and schema (`contracts/`) | **PROTOTYPE (runs today)** | a versioning policy agreed with the city |
| Panel UI (`app/`) | **PROTOTYPE (runs today)** | authentication, role-based views, and URL state so a view can be linked |
| Model layer (baseline, drivers) | **PARTIAL** | a retraining cadence and a difference-in-differences isolating the event effect from season |
| Municipal-site integration (`integrations/municipal-site/`) | **DESIGN ONLY** | an agreement with the city, a write path, and a host for the JSON |

---

## 5. What we do NOT claim

- **We do not claim to count restaurants.** The GIS package carries no commercial-POI layer, so we can say "90.7 % of card volume sits in 18 postcodes" and never "X % of restaurants in this area" (R14).
- **We do not claim our model beats a naive forecast.** Adding weather and events to a same-weekday baseline made the forecast *worse* (29.2 % / 29.5 % vs 24.1 % MAPE). What we give the owner is the baseline she cannot compute, plus the drivers that explain the deviation — see `docs/adr/0003`.
- **We do not claim the event effect** — the table above is the honest reading of it.
- **We do not claim official geography.** The sectors are a model, Sopot has no official district names, and every district label in the UI is our own toponym (R11, R13).
- **We do not claim the film's numbers.** It states 475,000 transactions and five MCCs absent from the data; the deck carries the correction (R26).
- **We do not claim the demo runs from a clean clone yet** — it needs the Organiser Data, which we may not redistribute. `docs/ARCHITECTURE.md` §7 states what a juror can run without it.

---

## 6. Materials

| What | Where | Read it if you want |
| --- | --- | --- |
| What we tried, found and rejected | [`docs/ROADMAP.md`](docs/ROADMAP.md) | to judge the work — 30 four-beat entries, failures kept |
| How it is built, and what is not | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | to see the data flow and the prototype boundary |
| The words we use | [`docs/CONTEXT.md`](docs/CONTEXT.md) | to check a Polish term (MCC, PKD, kaskada, obszar, THIN, „zwykle") |
| Six decisions and what they beat | [`docs/adr/`](docs/adr/) | to see where the trade-offs were |
| Every claimed number and its command | [`docs/claims.json`](docs/claims.json) | to check a figure yourself |
| The presentation | [`docs/deck/slides.html`](docs/deck/slides.html) | for the pitch |
| The data contract and the privacy gates | [`contracts/`](contracts/) | to check what the app may read and what may not be released |
| The pipeline | [`pipeline/`](pipeline/) | to check the cleaning rules and rerun `make data` |
| The app and the municipal integration | [`app/`](app/) · [`integrations/municipal-site/`](integrations/municipal-site/) | to check what runs and what is mocked |
| The film and the figures | [`artifacts/film/`](artifacts/film/) · [`artifacts/figures/`](artifacts/figures/) | for the media extras |
| Rules for whoever works here next | [`AGENTS.md`](AGENTS.md) | to continue the work |
| Twelve audit reports on everything before this repo | [`../research/`](../research/) | to check a MEASURED-AUDIT citation |
| The municipal-site replica (a design mockup, not our code) | `../karta-mockup/NOTES.md` | to see how the tab fits without a CSS change |

Every named artifact is produced by a `make` target from the sources in this repository. The audit reports in `../research/` were written before it and are cited as **MEASURED-AUDIT** wherever a `make` target does not yet cover them.

---

## 7. Known limitations

- **No commercial-POI layer**, so restaurant coverage is not measurable — only card volume is (R14).
- **12 of 151 postcode sectors are extrapolated**, 105 observed, the rest intermediate (R11); **weather is city-level**, duplicated across 155 postcodes, so no per-area weather claim is derivable (R12).
- **MCC 5812 only, and 7 of 72 columns**, so no cross-category comparison is possible (R18).
- **10.2 % of rows carry the sentinel time `'000000'`**, excluded from hourly views but kept in totals, so every hourly figure rests on 89.8 % of the rows (R22).
- **The privacy gate is k-anonymity, not differential privacy**, and does not protect against an attacker who already holds the raw feed; G4 addresses differencing and is not a substitute.
- **The pipeline is a reconstruction of an unrecorded run**, so `make data` reimplements it rather than recovering it (R21); if its counters differ from the shipped artifacts, it is wrong.
