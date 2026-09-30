# 0002 — Patch and vendor the prototype panel instead of rewriting it

**Status:** accepted · **Date:** 2026-09-30 · **Supersedes:** the `.dc.html` + CDN runtime

**Context.** The prototype is `Panel v4.dc.html` (62,668 B) plus `sopot-model.js`, `sopot-map.js`,
`sopot-data.js` and a generated `support.js` runtime. `support.js` throws unless `window.React` exists and
fetches React, ReactDOM and Babel standalone from `unpkg.com`; the panel also pulls d3 and Leaflet from the
same host and Barlow from `fonts.googleapis.com` — **six external origins**. But the forensics verdict on
it is not "discard": the information architecture, the Polish copy, the chart geometry and the venue-lane
concept survive a demo, roughly **700 of 2,600 lines are reusable verbatim**, and `sopot-map.js` is
self-contained enough to be reused as-is. What must change is the runtime, the default state and the
baseline arithmetic.

**Decision.** Keep the panel's structure, copy and charts. Vendor React, Babel standalone, d3, Leaflet and
the fonts into `app/vendor/`; delete the parquet path in favour of `aggregate.json`; replace the hand-picked
default venues with the feasibility-table presets (see 0005); fix the four arithmetic defects; and split
the 1,300-line model into privacy, cube, series and events modules.

**Consequences.** We inherit the prototype's UI debt — no URL state, and constants duplicated three times
(`EVENTS`, `SHAPES`, `TICKET`) — and we must correct four defects we did not write. We do not inherit the
CDN dependency or the silent fabricated-number fallback. Babel standalone still compiles in the browser at
load: vendoring removes the network origin, not the parse cost, so a build step remains a deployment task.

**Alternatives rejected.**
- **Rewrite in Streamlit, Power BI or Tableau** — the stack the challenge *suggests*. Rejected: it needs a
  Python host inside a municipal CMS and destroys the zero-install, embed-in-a-tab property that is the
  product's whole application-potential argument. (The challenge permits other tools.)
- **Rewrite as a fresh React or vanilla SPA.** Rejected: days of work to rebuild a screen that already
  exists, at the cost of the fidelity work that proves the tab fits.
- **Ship `.dc.html` unchanged as the demo.** Rejected: it cannot render without a CDN, and it renders
  invented traffic numbers before the real data arrives.
