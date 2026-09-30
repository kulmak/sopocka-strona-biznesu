# 0005 — Demo presets come from a data-driven feasibility table, not from a hand

**Status:** accepted · **Date:** 2026-09-30 · **Supersedes:** the hard-coded default venues

**Context.** The prototype's default demo state was `Restauracja przy Molo` + `Bistro przy dworcu`, on
Saturday **2026-06-20 at 19:00**, with a fictional `Koncert letni na Molo` — all three chosen by hand. Those
coordinates resolve to `81-720` (**16 merchants, 9,711 rows over 546 days**) and `81-805` (**12 merchants,
7,245 rows**), two of the thinnest of Sopot's 151 sectors, while **51.1 % of all 378,212 transactions sit in
a single sector, `81-777`** (241 merchants, 193,234 rows) and 98 sectors contain nothing at all. Against
`THIN = 12`, **71 of 72** hours were unreadable for the first venue and **72 of 72** for the second: both
rows read `—`, both lane charts were drawn as literal zeros with an axis top of `2e-9`, and the map beside
them showed a number in **18 of 151** areas. The failure was invisible to the person choosing the venue,
because the thinness is in the data and the screen simply looked empty.

**Decision.** Presets are selected mechanically. Every candidate venue × day × hour cell is scored against
the three privacy gates and the `THIN` base, in `../research/demo-feasibility-table.csv` and again in the
pipeline; a preset is admissible only if **every area it touches passes** and its lane is non-empty.
`make demo-ready` renders every preset headlessly and **fails on an empty or withheld lane**, so a bad preset
cannot reach a stage.

**Consequences.** The presets can be re-derived whenever the data changes, and the demo becomes a
reproducible build output rather than a curation. The regression case is deliberately kept: `81-718` draws a
curve and withholds the readout, so it stays in the check as the case that must fail. Choosing a preset now
costs a table row, not a judgement call.

**Alternatives rejected.**
- **Keep the hand-picked venues.** Rejected: the person picking cannot see the thinness, and the failure
  only appears in front of an audience.
- **Default to the median sector to look representative.** Rejected: honest but weak — a demo on a thin
  sector shows an empty screen and teaches nothing. Name the data's shape instead of hiding it.
- **Pick the largest sector (`81-777`) as the only preset.** Rejected: it makes the panel look like a
  single-street instrument; two presets in different sectors show the same method on different data.
- **Remove the venue lanes and show only city totals.** Rejected: the venue lane is the only element tying
  an area aggregate to the owner's own site, which is the product's reason to exist.
