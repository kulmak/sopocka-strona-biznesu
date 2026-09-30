# 0004 — The privacy gate lives in one module, and every release passes through it

**Status:** accepted · **Date:** 2026-09-30 · **Supersedes:** the prototype's render-time gate

**Context.** The prototype implemented the three gates in three different places and two of them did not
work. G2 (≥3 merchants) was real, in `sopot-model.js`. G3 (≤75 % top-1 share) existed only against an
invented `STATS` table in a different file. G1 (≥30 cards) existed nowhere — the card column was never in
the loader's column list, so no card count could be computed at all. Measured consequences: of the
**67,204 cells the map painted, 2,006 (3.0 %) passed all three gates**; 48,404 had fewer than 3 merchants
active in that hour. The thresholds were also quoted two ways across internal materials, and the same
conflict was found twice, by two different agents, in two different tools, and was still unresolved at
submission time.

**Decision.** One implementation, in `contracts/privacy.py`. The pipeline imports it and refuses to write
an artifact whose cells fail it; the app mirrors it and never recomputes it; `tests/privacy/` is the only
place it is verified. Every released cell carries its gate flags (`nCards`, `merchants`, `top1Share`,
`g1_cards`, `g2_merchants`, `g3_share`) so no consumer can draw a value without them. The thresholds are
stated once and every other mention is checked against that source rather than retyped.

**Consequences.** Adding a new release path means touching one file; a threshold change is a one-place edit.
The tests must carry a 29-card fixture and a 76 %-share fixture, or the gate can pass vacuously — a gate
that cannot fail is the specific defect we already made once in this project. The app loses the ability to
"decide" to show a gated cell, which is intended.

**How the single module is reached.** The pipeline and the app do not import the rules directly: they go
through one loader (`pipeline/_gates.py` → `contracts/privacy`), which resolves to `contracts.privacy` when
that module exposes the documented entry points and otherwise substitutes a local copy **and reports which
one it used** (`gates_source` in the artifact). No artifact is ever written with an unknown gate source, so
the rule holds even while the module is being changed underneath it.

**Alternatives rejected.**
- **Enforce in the UI only, as the prototype did.** Rejected: the whole cube leaves the pipeline ungated and
  is persisted client-side, so a viewer can read cells the interface hides. Measured as finding N-5.
- **Enforce inside the aggregation SQL.** Rejected: not testable without a database in the loop, and the app
  could not mirror a rule it cannot import.
- **Document the thresholds and rely on writers.** Rejected: already tried — the numbers drifted between the
  model, two module documents and the film script, and both a film agent and an audit agent flagged it
  independently without either being able to fix it.
