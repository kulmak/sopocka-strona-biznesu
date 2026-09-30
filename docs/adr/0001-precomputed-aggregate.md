# 0001 — Read a precomputed aggregate instead of the parquet in the browser

**Status:** accepted · **Date:** 2026-09-30 · **Supersedes:** the prototype's in-browser parquet loader

**Context.** The prototype loaded the 26 MB analytics parquet directly in the page (`hyparquet` + a pure-JS
ZSTD decoder), built an hourly × postcode cube in typed arrays and cached it in IndexedDB behind
`CACHE_VER = 3`. Measured: **2.9–5.6 s** cold on a fast link, **8–14 s on a 50 Mbps link** for
26,071,536 B, and for the first **1.4–2.7 s** of every load the panel displayed *fabricated* numbers under
the label `Dane przykładowe`. The deployment unit was therefore the whole folder plus **six external CDN
origins**, any one of which failing re-triggered the fake-data path. It also meant publishing Organiser
Data to make the demo work at all, which challenge §7.2–7.4 forbids.

**Decision.** The pipeline writes one precomputed, privacy-gated `artifacts/aggregate.json` (`ver: 4`,
base64 typed arrays, per-code gate flags). The app reads that file and nothing else, refuses any other
contract version, and renders an explicit error instead of a substitute number. There is no silent
fallback anywhere on the read path.

**Consequences.** The deployment unit becomes static files plus one JSON, hosting nothing confidential;
the aggregate is **1.98 MiB** against a 26.84 MiB source. Analysis moves to build time, so a change to the
cube's shape is a pipeline change rather than a client change, and the app can no longer answer a question
the cube does not contain — a new question needs `make data`. Cache invalidation becomes a version
constant instead of a size-based IndexedDB key.

**Alternatives rejected.**
- **Keep the parquet in the browser plus the IndexedDB cache.** Rejected: 26 MB in the deployment unit, a
  8–14 s cold start, and publishing Organiser Data breaches challenge §7.2–7.4.
- **Add a small backend that aggregates on request.** Rejected: it adds a service to operate, an auth
  surface and a hosting agreement with the city, when the entire point is to fit inside an existing CMS.
- **Server-side row-level queries.** Rejected: the privacy boundary would move into a runtime component we
  would have to audit continuously, instead of a build step we can test once.
- **A smaller parquet (fewer columns) instead of a cube.** Rejected: it reduces bytes but keeps JS-side
  decoding, the IndexedDB cache key and the fabricated-first-paint window.
