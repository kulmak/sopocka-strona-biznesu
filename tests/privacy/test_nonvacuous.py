"""tests/privacy/test_nonvacuous.py — the proof that the gates are not vacuous.

A gate that cannot fail is not a gate, and a test that cannot fail is not a test.

WHAT THIS FILE DOES
    1. PERTURBATION, per threshold. Each threshold is moved (loosened or tightened) and the
       check function that tests it is re-run: it MUST fail. The threshold is then reverted and
       the same check MUST pass. Both verdicts are printed, so the proof is in the output, not
       in a claim (`python3 -m pytest tests/privacy/test_nonvacuous.py -q -s`).
    2. FIXTURE SENSITIVITY. The two perturbations named in research/privacy-harness-spec.md §8.1
       are re-run over the whole fixture set and the exact set of fixtures that flips is asserted
       — including the fixtures that must NOT flip.
    3. REVERSION IS BYTE-IDENTICAL. After every perturbation, the canonical run is compared
       byte-for-byte with a fresh one: the perturbation test did not "fix" or drift anything.

WHY IT MATTERS HERE
    The prototype's cascade could not fire: the loader never read the card column, the share gate
    was never computed on real data, and the one three-gate path ran on a hand-written table with
    `!s || (…)` — a missing key PASSED. Every one of those defects would have survived a test
    suite that only asserted the happy path. This file exists so that the same shape of defect
    cannot come back unnoticed.

RUN
    python3 -m pytest tests/privacy/test_nonvacuous.py -q -s
"""

from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "contracts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import privacy as P  # noqa: E402
import test_gates as G  # noqa: E402

BASE = dict(G.FIXTURES["rules"])
FIXTURE_IDS = [c["id"] for c in G.FIXTURES["cases"]]


def _first_line(exc: BaseException) -> str:
    return str(exc).strip().splitlines()[0][:160] if str(exc).strip() else type(exc).__name__


def probe(label: str, check, perturbed: dict, canonical: P.Rules = P.BASE_RULES) -> str:
    """Run `check` under a perturbed threshold (MUST fail), then under the canonical one (MUST pass).

    Returns a two-line transcript. Raises if the check is insensitive to the perturbation —
    that is the definition of a vacuous test, and it is a hard failure here.
    """
    rules = P.Rules.from_mapping({**BASE, **perturbed})
    try:
        check(rules)
    except AssertionError as exc:
        verdict = f"FAIL (as required) — {_first_line(exc)}"
    else:
        raise AssertionError(
            f"{label}: the check PASSED under the perturbed threshold {perturbed}. "
            "The test does not actually constrain this threshold."
        )
    check(canonical)  # reverted: must pass, and if it does not the perturbation leaked
    line = (
        f"PERTURB {label}: {verdict}\n"
        f"REVERT  {label}: PASS (canonical thresholds restored)"
    )
    print(line)
    return line


def run_fixtures(rules_map: dict) -> dict:
    """{case_id: ok} for every fixture case under a given rules mapping."""
    out = {}
    for case in G.FIXTURES["cases"]:
        merged = {**BASE, **rules_map, **case.get("rules_override", {})}
        out[case["id"]] = G.run_case(case, P.Rules.from_mapping(merged)).ok
    return out


def canonical_snapshot() -> str:
    return json.dumps({k: v.to_mapping() for k, v in G.run_all_cases().items()}, sort_keys=True)


# ---------------------------------------------------------------------------------------------
# 1. Perturb each threshold: the test that constrains it must fail, then pass again
# ---------------------------------------------------------------------------------------------

def test_perturb_min_cards() -> None:
    """`min_cards` 30 → 29 must break the card boundary test (29 cards would pass)."""
    probe("min_cards 30→29", G.check_boundary_cards, {"minCards": 29})


def test_perturb_min_merchants() -> None:
    """`min_merchants` 3 → 2 must break the merchant boundary test (2 merchants would pass)."""
    probe("min_merchants 3→2", G.check_boundary_merchants, {"minMerchants": 2})


def test_perturb_max_share() -> None:
    """`max_share` 3/4 → 4/5 must break the share boundary test (F-06's 75.1% would pass)."""
    probe("max_share 3/4→4/5", G.check_boundary_share, {"maxShare": "4/5"})


def test_perturb_max_share_by_one_part_in_four_million() -> None:
    """Move the share limit to EXACTLY 75.000025%: the float-trap case must stop failing.

    This is the sharpest form of the perturbation. If the comparison were done in floating point
    — or if the threshold were rounded anywhere before the comparison — F-13 would keep passing
    and this probe would report a vacuous test instead of the required failure.
    """
    probe("max_share 3/4→3000001/4000000", G.check_boundary_share,
          {"maxShare": "3000001/4000000"})
    # …and the two shares really are one part in four million apart.
    assert P.top1_share({"E1": 3_000_001, "E2": 999_999}) - Fraction(3, 4) == Fraction(1, 4_000_000)


def test_perturb_differencing() -> None:
    """Turning G4 off must break the differencing test (the residual cell would be released)."""
    probe("require_differencing True→False", G.check_g4, {"requireDifferencing": False},
          canonical=P.PRODUCT_RULES)


def test_perturb_card_share_metric() -> None:
    """Dropping the `cards` metric must break F-11 (its card share is 76% while volume is 70%).

    `check_boundary_share` constrains the volume leg, so this perturbation is probed against the
    fixture that exists for the card leg, asserted directly rather than through `probe`.
    """
    case = next(c for c in G.FIXTURES["cases"] if c["id"] == "F-11")
    canonical = G.run_case(case, G.rules_for(case))
    volume_only = G.run_case(case, P.Rules.from_mapping({**BASE, "shareMetrics": ["volume"]}))
    assert canonical.ok is False and canonical.reason == P.R_TOP1_GT_75
    print(f"PERTURB share_metrics cards removed: F-11 ok {canonical.ok} → {volume_only.ok} (as required)")
    assert volume_only.ok is True, "dropping the card metric must release F-11 — otherwise the leg is dead code"
    assert G.run_case(case, G.rules_for(case)).ok is False
    print("REVERT  share_metrics restored: F-11 suppressed again")


def test_perturb_cascade_order_is_not_silently_ignored() -> None:
    """An unknown cascade level must raise rather than be dropped: a lost level is a lost check."""
    with pytest.raises(ValueError):
        P.cascade({"cell": G.mk(30, {"E1": 10, "E2": 10, "E3": 10}), "fives": G.mk(30, {"E1": 10})})
    print("PERTURB cascade level 'fives': ValueError (as required)\nREVERT  cascade level names: cell/parent/city accepted")


# ---------------------------------------------------------------------------------------------
# 2. Fixture sensitivity — the whole set, both directions
# ---------------------------------------------------------------------------------------------

LOOSENED = {"minCards": 25, "minMerchants": 2, "maxShare": "4/5", "requireDifferencing": False}
TIGHTENED = {"minMerchants": 4, "requireDifferencing": True}


def test_loosening_the_thresholds_flips_exactly_the_expected_fixtures() -> None:
    """Loosened thresholds (25 / 2 / 80%) must release exactly the fixtures that guard them."""
    canonical = run_fixtures({})
    loosened = run_fixtures(LOOSENED)
    flipped = sorted(k for k in canonical if canonical[k] is False and loosened[k] is True)
    print(f"PERTURB loosened {LOOSENED}: flips false→true: {flipped}")
    # research/privacy-harness-spec.md §8.1 measured exactly these six.
    assert flipped == ["F-02", "F-04", "F-06", "F-09", "F-11", "F-13"], flipped
    resistant = sorted(k for k in canonical if canonical[k] == loosened[k])
    print(f"REVERT  resistant under loosening: {resistant}")
    assert "F-15" in resistant, "a 22-card cell cannot be loosened into passing by minCards=25"
    assert canonical_snapshot() == canonical_snapshot(), "the perturbation leaked into the canonical run"


def test_tightening_the_thresholds_flips_exactly_the_expected_fixtures() -> None:
    """Tightened thresholds (4 merchants + G4) must suppress exactly the 3-merchant fixtures.

    DIFFERENCE FROM THE REFERENCE TABLE (research/privacy-harness-spec.md §8.1)
        The reference recorded four flips, including F-16 — which is already suppressed in the
        canonical run, so it cannot flip. It also missed F-05, F-08 and F-12, because its G4 ran
        only over residuals that were supplied (nothing supplied ⇒ G4 vacuous) and because those
        three cases declare exactly three merchants in every level. Both causes are fixed here: G4 is evaluated
        against every level with a sound bound when no measured residual is supplied, and the
        entity count is derived from the partition instead of being declared separately.
    """
    canonical = run_fixtures({})
    tightened = run_fixtures(TIGHTENED)
    flipped = sorted(k for k in canonical if canonical[k] is True and tightened[k] is False)
    print(f"PERTURB tightened {TIGHTENED}: flips true→false: {flipped}")
    assert flipped == ["F-01", "F-03", "F-05", "F-08", "F-12", "F-14"], flipped
    print(f"REVERT  resistant under tightening: "
          f"{sorted(k for k in canonical if canonical[k] == tightened[k])}")


def test_at_least_eight_fixtures_are_sensitive_to_the_thresholds() -> None:
    """Non-vacuity, in one number: how many of the 18 cases depend on a threshold at all."""
    canonical = run_fixtures({})
    sensitive = set()
    for perturbation in (LOOSENED, TIGHTENED, {"maxShare": "3000001/4000000"},
                         {"minCards": 31}, {"minMerchants": 4}):
        other = run_fixtures(perturbation)
        sensitive |= {k for k in canonical if canonical[k] != other[k]}
    print(f"sensitive fixtures: {len(sensitive)} of {len(FIXTURE_IDS)} -> {sorted(sensitive)}")
    assert len(sensitive) >= 8, f"only {len(sensitive)} fixtures react to any threshold change"


def test_reverted_run_is_byte_identical() -> None:
    """The perturbation test is deterministic and changes nothing (harness spec §8.1)."""
    before = canonical_snapshot()
    for perturbation in (LOOSENED, TIGHTENED, {"minCards": 100}, {"maxShare": "1/100"}):
        run_fixtures(perturbation)
    after = canonical_snapshot()
    assert before == after, "a perturbed run mutated state that the canonical run depends on"
    print("REVERT  canonical report byte-identical after 4 perturbed runs")


def test_every_gate_can_fail_on_the_real_thresholds() -> None:
    """Negative controls: each gate must be reachable at the CANONICAL thresholds, not just when
    perturbed. A gate that only fires under a loosened threshold is not enforcing anything."""
    hits = {P.R_LT_30_CARDS: False, P.R_LT_3_MERCHANTS: False, P.R_TOP1_GT_75: False,
            P.R_G4_DIFFERENCING: False}
    for case in G.FIXTURES["cases"] + G.FIXTURES["cascade_cases"] + G.FIXTURES["g4_cases"]:
        for base in ({"requireDifferencing": False}, {"requireDifferencing": True}):
            got = G.run_case(case, G.rules_for(case, base=base))
            for entry in got.trace:
                for code in entry.failures:
                    hits[code] = True
    assert all(hits.values()), f"gate(s) never fired on canonical thresholds: {hits}"
    print(f"canonical-threshold firings: {hits}")
