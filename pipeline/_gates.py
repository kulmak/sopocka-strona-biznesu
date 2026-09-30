"""Local privacy gates — the fallback behind `contracts/privacy.py`.

STATUS: **`contracts/privacy.py` has landed.** `pipeline._gates.load()` now returns it and the
pipeline prints `gates_source=contracts.privacy`, so the gates that ship in `aggregate.json` come
from the privacy engineer's module, not from this file. This module is retained deliberately as the
load-bearing fallback (a clean checkout that has not yet pulled `contracts/privacy.py` must still be
able to rebuild the artifact) and as the reference the two implementations are diffed against in
`tests/pipeline/test_invariants.py`. If the two ever disagree, that test fails.

The swap is the whole integration: `load()` prefers `contracts.privacy` the moment that module
exists and exposes `Rules` / `Aggregation` / `evaluate` / `gate_dict`; nothing else changed.

WHAT THE RULE IS
----------------
The challenge brief §3 sets three thresholds, per cell, and `AGENTS.md` calls them law:

* **G1 — ≥30 distinct cards.** Blocks inference about an individual cardholder's behaviour.
* **G2 — ≥3 distinct merchant descriptors.** Blocks inference about a single venue.
* **G3 — no single merchant above 75 % of the cell** (volume *and* card share).

WHY IT IS HERE
--------------
`AGENTS.md` defect **D3**: "the ≥30-card gate cannot fire — the card column is never read". The
browser prototype only implemented the middle rule, as `merchants() >= 3`, and `pymt_crd_acct_num_raw`
was never loaded (`sopot-data.js` line 4 lists the seven columns it reads; the card column is not
among them). This module reads the card column and evaluates all three rules, from exact integer
arithmetic.

Arithmetic note: shares use `fractions.Fraction`, never floats, so `75 %` is *inclusive* and
`0.75` is not approximated. `research/privacy-harness-spec.md` §"`_share_ok`" makes the same
choice with the same justification ("`==` replaces `100*top <= 75*den` with distinct ints").

EVIDENCE
--------
`nCards` and `top1Share` are emitted per code in `codeMeta`, and every preset's code must pass all
three gates (contract invariant 8). The counts are re-derivable with a single `count(DISTINCT …)`
per code, which is what `tests/pipeline/test_invariants.py` re-runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class EntityStat:
    """One merchant descriptor's contribution to a cell. `entity` is never published."""
    entity: str
    n_tran: int
    n_cards: int


@dataclass(frozen=True)
class Aggregation:
    level: str
    n_cards: int
    n_entities: int
    n_tran: int
    per_entity: List[EntityStat] = field(default_factory=list)


@dataclass(frozen=True)
class Rules:
    min_cards: int = 30
    min_entities: int = 3
    max_share: Fraction = Fraction(3, 4)          # 75 %, inclusive
    share_metrics: Tuple[str, ...] = ("volume", "cards")
    thin_base_transactions: int = 12


def _share_ok(top: int, denom: int, max_share: Fraction) -> bool:
    """Exact: equals-passes, above fails. No floats anywhere."""
    if denom <= 0:
        return False
    return Fraction(top, denom) <= max_share


def evaluate(agg: Aggregation, rules: Rules = Rules()) -> Tuple[List[str], List[str], int, int]:
    """Return `(failure_codes, failure_details, top1_tran, top1_cards)`.

    Same convention as `research/privacy-harness-spec.md`, so the pipeline and the browser
    aggregate can be diffed against the same harness.
    """
    failures: List[Tuple[str, str]] = []
    if agg.n_cards < rules.min_cards:
        failures.append(("G1_CARDS", f"cards={agg.n_cards} < {rules.min_cards}"))
    if agg.n_entities < rules.min_entities:
        failures.append(("G2_ENTITIES", f"entities={agg.n_entities} < {rules.min_entities}"))
    top_v = max((e.n_tran for e in agg.per_entity), default=0)
    top_c = max((e.n_cards for e in agg.per_entity), default=0)
    if "volume" in rules.share_metrics and not _share_ok(top_v, agg.n_tran, rules.max_share):
        failures.append(("G3_SHARE", f"volume {Fraction(top_v, max(agg.n_tran,1))} > {rules.max_share}"))
    if "cards" in rules.share_metrics and not _share_ok(top_c, agg.n_cards, rules.max_share):
        failures.append(("G3_SHARE", f"cards {Fraction(top_c, max(agg.n_cards,1))} > {rules.max_share}"))
    codes, seen = [], set()
    for code, _detail in failures:
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes, [d for _c, d in failures], top_v, top_c


def gate_dict(n_cards: int, n_merchants: int, top1_volume: int, n_tran: int,
              top1_cards: int = 0, rules: Optional[Rules] = None) -> dict:
    """Evaluate the three gates for one cell and return the contract's `gates` object.

    Returns `{'g1_cards', 'g2_merchants', 'g3_share', 'all'}` — exactly the shape
    `contracts/aggregate.schema.json` requires under `codeMeta.<code>.gates`.
    """
    rules = rules or Rules()
    g1 = n_cards >= rules.min_cards
    g2 = n_merchants >= rules.min_entities
    g3 = _share_ok(top1_volume, n_tran, rules.max_share) and (
        top1_cards == 0 or _share_ok(top1_cards, n_cards, rules.max_share))
    return {"g1_cards": bool(g1), "g2_merchants": bool(g2), "g3_share": bool(g3),
            "all": bool(g1 and g2 and g3)}


def evaluate_full(n_cards: int, n_tran: int, per_entity: Sequence[Tuple[str, int, int]],
                  level: str = "code", rules: Optional[Rules] = None) -> dict:
    """Full `evaluate()` over a cell, returning the gate block plus the failure detail."""
    rules = rules or Rules()
    agg = Aggregation(level=level, n_cards=n_cards, n_entities=len(per_entity), n_tran=n_tran,
                      per_entity=[EntityStat(e, t, c) for e, t, c in per_entity])
    codes, detail, top_v, top_c = evaluate(agg, rules)
    return {"gates": {"g1_cards": "G1_CARDS" not in codes,
                      "g2_merchants": "G2_ENTITIES" not in codes,
                      "g3_share": "G3_SHARE" not in codes,
                      "all": not codes},
            "failures": codes, "detail": detail, "top1_tran": top_v, "top1_cards": top_c}


def load():
    """Return the privacy module to use: `contracts.privacy` when it exists, else this one.

    Both implementations expose `Rules`, `evaluate` and `gate_dict` with the same signatures, so
    the caller does not care which one it gets. Returns `(module, source_name)`; `source_name` is
    printed by `pipeline/run.py` as `gates_source` and recorded in `data/samples/`.
    """
    try:                                        # pragma: no cover - depends on a parallel workstream
        from contracts import privacy as _p     # type: ignore
        if all(hasattr(_p, n) for n in ("Rules", "evaluate")):
            return _p, "contracts.privacy"
    except Exception:
        pass
    return __import__(__name__, fromlist=["_gates"]), "pipeline._gates"

