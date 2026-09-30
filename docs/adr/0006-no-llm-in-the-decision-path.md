# 0006 — No LLM in the decision path

**Status:** accepted · **Date:** 2026-09-30 · **Supersedes:** the concept document's AI features

**Context.** Challenge §8.4 scores *"rolę AI w działaniu rozwiązania i jej dopasowania do postawionego
problemu"*, and the FAQ makes AI disclosure mandatory: which elements were AI-assisted, with which tools,
and which materials come from external sources. The earlier concept document proposed AI features for the
wider product — summarising public procurement notices, and generating a plain-language description of the
data. The delivered path is deterministic: ingest, clean, aggregate, gate, baseline, backtest. The
prototype, by contrast, silently substituted *simulated* traffic numbers whenever a data load failed, which
is the failure mode this decision exists to make impossible.

**Decision.** AI built and analysed this project; it produces **no number that ships**. Every released value
is computed by deterministic code from the gated cube, and every value in the deck, the panel and these
documents has a command or an audit section behind it. The AI disclosure states which tools were used, what
they produced, and what a human had to catch and correct — including the failures recorded in
`docs/ROADMAP.md`.

**Consequences.** We cannot present "AI inside the product" as a feature, and we do not claim one; the
criterion is answered instead by the disclosed role and by the reproducibility it buys. No output is
irreproducible, so a juror can recompute any number we print. The cost is that prose the product shows on
screen must be written as fixed, reviewed templates rather than generated per merchant.

**Alternatives rejected.**
- **An LLM to write the merchant's sentence** ("expect more guests, prepare stock"). Rejected: the sentence
  would be generated from a number the model did not compute, and a hallucinated quantification inside a
  compliance-gated panel cannot be tested for.
- **An LLM to summarise public procurement notices**, as the concept document proposed. Rejected for this
  build: it needs a live external fetch from inside a municipal CMS and adds a second privacy surface to
  audit, for a feature no demo path uses.
- **An LLM to "explain the chart" on demand.** Rejected: same untestable failure mode, with no fixed prompt
  to review. A deterministic template carries the same value at zero risk.
- **Ship the prototype's simulated fallback as the AI story.** Rejected: it is not a model, it is fabricated
  data, and it is the single behaviour we most want a reader to know we deleted.
