"""tests/privacy/test_gates.py — the three regulatory gates, made real, tested and hard to bypass.

WHY THIS FILE EXISTS
    In the prototype the ≥30-card gate could not fire (the loader never read
    `pymt_crd_acct_num_raw`), the ≤75% share was never computed, and the only three-gate cascade
    ran on a hand-written `STATS` table with a fail-open branch (`!s || …` → an unknown key
    PASSED). This file is the evidence that the same class of defect cannot come back:

      1. boundary          exactly 30 cards / 3 merchants / 75.000000% pass; one step below fails
      2. cascade           a failing cell escalates to a passing parent, labelled as such
      3. F-10              a huge single-merchant cell is still suppressed (big is not anonymous)
      4. multi-failure     when all three gates fail the reason NAMES all three
      5. monotonicity      no refinement of a suppressed cell escapes (and G3's real limit, named)
      6. G4                the merchant inside the cell cannot difference itself out
      + the 18 reference fixtures, the release guard, reason coverage and determinism.

    Every check function takes the rules as an argument. `test_nonvacuous.py` re-runs them with a
    perturbed threshold and asserts the check FAILS — a gate that cannot fail is not a gate.

RUN
    python3 -m pytest tests/privacy -q
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from itertools import product
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "contracts"))

import privacy as P  # noqa: E402  (contracts/privacy.py — the single source of truth)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures.json"
FIXTURES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
FIXTURE_RULES = P.Rules.from_mapping(FIXTURES["rules"])


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------

def mk(n_cards: int, merchants, n_transactions: int | None = None,
       cards=None, residuals=None, label=None) -> P.Cell:
    """Build a Cell the way a producer would: volumes, transaction total, optional card evidence."""
    return P.Cell(
        n_cards=n_cards,
        merchants={k: int(v) for k, v in merchants.items()},
        n_transactions=sum(merchants.values()) if n_transactions is None else n_transactions,
        merchant_cards=None if cards is None else {k: int(v) for k, v in cards.items()},
        residual_n_cards=None if residuals is None else {k: int(v) for k, v in residuals.items()},
        label=label,
    )


def cell_from_spec(spec: dict) -> P.Cell:
    return mk(
        int(spec["n_cards"]),
        spec["merchants"],
        int(spec["n_transactions"]),
        spec.get("merchant_cards"),
        spec.get("residual_n_cards"),
    )


def rules_for(case: dict, base: dict | None = None, differencing: bool | None = None) -> P.Rules:
    merged = dict(base if base is not None else FIXTURES["rules"])
    merged.update(case.get("rules_override", {}))
    if differencing is not None:
        merged["requireDifferencing"] = differencing
    return P.Rules.from_mapping(merged)


def run_case(case: dict, rules: P.Rules) -> P.GateResult:
    """One fixture case → one GateResult. Single level ⇒ gate(); several ⇒ cascade()."""
    cells = {level: cell_from_spec(spec) for level, spec in case["levels"].items()}
    thin = FIXTURE_RULES.thin_base_transactions if case.get("thin_base") else None
    if len(cells) == 1:
        (level, cell), = cells.items()
        return P.gate(cell, level, rules=rules, thin_base=thin)
    return P.cascade(cells, rules=rules, thin_base=thin)


def compare(case: dict, got: P.GateResult, expect: dict) -> list:
    """Field-by-field comparison with a fixture expectation. Returns the list of mismatches."""
    errs = []
    if "ok" in expect and got.ok != expect["ok"]:
        errs.append(f"ok {got.ok} != {expect['ok']}")
    if "level" in expect and got.level != expect["level"]:
        errs.append(f"level {got.level!r} != {expect['level']!r}")
    if "reason" in expect and got.reason != expect["reason"]:
        errs.append(f"reason {got.reason!r} != {expect['reason']!r}")
    if "escalated" in expect and got.escalated != expect["escalated"]:
        errs.append(f"escalated {got.escalated} != {expect['escalated']}")
    if "failures" in expect and sorted(got.failures) != sorted(expect["failures"]):
        errs.append(f"failures {list(got.failures)} != {expect['failures']}")
    if "trace_failures" in expect:
        got_trace = [list(t.failures) for t in got.trace]
        if got_trace != [list(x) for x in expect["trace_failures"]]:
            errs.append(f"trace_failures {got_trace} != {expect['trace_failures']}")
    if "levels_missing" in expect and list(got.levels_missing) != list(expect["levels_missing"]):
        errs.append(f"levels_missing {list(got.levels_missing)} != {expect['levels_missing']}")
    if "detail_contains" in expect and not any(
        expect["detail_contains"] in d for d in got.detail
    ):
        errs.append(f"detail does not name {expect['detail_contains']!r}: {list(got.detail)}")
    if "trace_differencing_evidence" in expect:
        got_mode = got.trace[-1].differencing_evidence if got.trace else None
        if got_mode != expect["trace_differencing_evidence"]:
            errs.append(f"differencing_evidence {got_mode!r} != {expect['trace_differencing_evidence']!r}")
    return errs


# ---------------------------------------------------------------------------------------------
# 1. BOUNDARY — the thresholds are inclusive exactly as written
# ---------------------------------------------------------------------------------------------

def check_boundary_cards(rules: P.Rules) -> None:
    """Exactly `min_cards` distinct cards pass; one fewer fails, and ONLY on the card gate."""
    at_limit = P.gate(mk(30, {"E1": 10, "E2": 10, "E3": 10}), rules=rules)
    below = P.gate(mk(29, {"E1": 10, "E2": 10, "E3": 10}), rules=rules)
    assert at_limit.ok is True, f"exactly 30 cards must pass: {at_limit.to_mapping()}"
    assert below.ok is False, "29 cards must not be released"
    assert below.reason == P.R_LT_30_CARDS, f"expected {P.R_LT_30_CARDS}, got {below.reason!r}"
    assert P.R_LT_30_CARDS in below.failures


def check_boundary_merchants(rules: P.Rules) -> None:
    """Exactly `min_merchants` distinct merchants pass; one fewer fails on G2 alone."""
    at_limit = P.gate(mk(35, {"E1": 20, "E2": 10, "E3": 10}), rules=rules)
    below = P.gate(mk(35, {"E1": 20, "E2": 20}), rules=rules)
    assert at_limit.ok is True, f"exactly 3 merchants must pass: {at_limit.to_mapping()}"
    assert below.ok is False, "2 merchants must not be released"
    assert below.reason == P.R_LT_3_MERCHANTS, f"expected {P.R_LT_3_MERCHANTS}, got {below.reason!r}"


def check_boundary_share(rules: P.Rules) -> None:
    """75.000000% passes; 75.000025% fails. Exact arithmetic, never float division.

    The two cases are 1 part in 4,000,000 apart. This is the test that a `float` gate fails:
    it is why `top1_share()` returns a `Fraction` and why `maxShare` is a string in the fixtures.
    """
    exact = P.gate(mk(100, {"E1": 75, "E2": 15, "E3": 5, "E4": 5},
                      cards={"E1": 75, "E2": 15, "E3": 5, "E4": 5}), rules=rules)
    assert exact.ok is True, f"75.000000% must pass: {exact.to_mapping()}"
    assert isinstance(exact.value_or_none.top1_share, Fraction), "the released share must be exact"

    over = P.gate(mk(500_000, {"E1": 3_000_001, "E2": 600_000, "E3": 399_999}, 4_000_000,
                      cards={"E1": 120_000, "E2": 200_000, "E3": 180_000}), rules=rules)
    assert over.ok is False, "75.000025% must not be released"
    assert over.reason == P.R_TOP1_GT_75, f"expected {P.R_TOP1_GT_75}, got {over.reason!r}"

    # The same two shares one order of magnitude apart must decide the same way.
    assert P.top1_share({"E1": 75, "E2": 25}) == Fraction(3, 4)
    assert P.top1_share({"E1": 3_000_001, "E2": 999_999}) > Fraction(3, 4)
    assert P.top1_share({"E1": 3_000_000, "E2": 1_000_000}) == Fraction(3, 4)


def test_boundary_thresholds() -> None:
    check_boundary_cards(P.BASE_RULES)
    check_boundary_merchants(P.BASE_RULES)
    check_boundary_share(P.BASE_RULES)


def test_display_rounding_never_moves_a_cell() -> None:
    """Rounding is presentation-only and is applied AFTER the gate (compliance §2.3 R4)."""
    at_limit = Fraction(3, 4)
    above = Fraction(3_000_001, 4_000_000)
    assert P.format_share(at_limit, 1) == "75.0"
    assert P.format_share(above, 1) == "75.0", "the display rounds; the gate must not"
    assert above > at_limit, "…which is exactly why the comparison is exact"
    assert P.format_share(Fraction(1, 3), 6) == "33.333333"
    assert P.format_share(Fraction(2, 3), 0) == "67"


# ---------------------------------------------------------------------------------------------
# 2. CASCADE — escalation, and the difference between a parent value and a locked cell
# ---------------------------------------------------------------------------------------------

def check_cascade_escalation(rules: P.Rules) -> None:
    """A cell that fails at its own level but passes at the parent returns the PARENT value."""
    case = next(c for c in FIXTURES["cascade_cases"] if c["id"] == "C-01")
    got = run_case(case, rules_for(case, differencing=False))
    assert got.ok is True, f"C-01 must escalate: {got.to_mapping()}"
    assert got.level == "parent", f"expected the parent value, got level={got.level!r}"
    assert got.escalated is True, "an escalated value must be labelled as such"
    assert got.reason == P.R_OK
    assert [list(t.failures) for t in got.trace] == [["top1_gt_75"], []]
    assert got.value_or_none.level == "parent"
    assert got.value_or_none.n_transactions == 2400, "the value is the PARENT's, not the cell's"

    # …and a cell that fails everywhere is locked, with every level recorded.
    everywhere = next(c for c in FIXTURES["cases"] if c["id"] == "F-09")
    locked = run_case(everywhere, rules_for(everywhere, differencing=False))
    assert locked.ok is False and locked.level == "locked"
    assert locked.reason == P.R_ALL_LEVELS_FAILED
    assert locked.value_or_none is None, "a suppressed record must carry no value"
    assert len(locked.trace) == 3, "every evaluated level must appear in the trace"

    # A level that is simply absent must be reported, never silently skipped.
    missing = next(c for c in FIXTURES["cascade_cases"] if c["id"] == "C-02")
    got_missing = run_case(missing, rules_for(missing, differencing=False))
    assert list(got_missing.levels_missing) == ["parent"]
    assert list(got_missing.levels_evaluated) == ["cell", "city"]

    # An unknown level key is refused outright: a dropped candidate is a dropped escalation path.
    with pytest.raises(ValueError):
        P.cascade({"cell": mk(30, {"E1": 10, "E2": 10, "E3": 10}), "region": mk(30, {"E1": 10})},
                  rules=rules)


def test_cascade_escalation() -> None:
    check_cascade_escalation(P.BASE_RULES)


# ---------------------------------------------------------------------------------------------
# 3. F-10 — big is not anonymous
# ---------------------------------------------------------------------------------------------

def check_large_but_single_merchant(rules: P.Rules) -> None:
    """5,000 cards and 12,000 transactions from ONE merchant must still be suppressed."""
    got = P.gate(mk(5000, {"E1": 12000}, cards={"E1": 5000}), rules=rules)
    assert got.ok is False, "a single-merchant cell is never releasable, however large"
    assert got.reason == P.R_MULTI
    assert set(got.failures) == {P.R_LT_3_MERCHANTS, P.R_TOP1_GT_75}
    assert P.R_LT_30_CARDS not in got.failures, "the card gate PASSES here — that is the point"
    assert got.trace[0].n_cards == 5000 and got.trace[0].n_cards >= rules.min_cards


def test_f10_big_is_not_anonymous() -> None:
    check_large_but_single_merchant(P.BASE_RULES)


# ---------------------------------------------------------------------------------------------
# 4. MULTI-FAILURE — the reason must name every gate that failed
# ---------------------------------------------------------------------------------------------

def check_multi_failure(rules: P.Rules) -> None:
    """A cell failing all three gates reports `multi` AND the three codes."""
    got = P.gate(mk(12, {"E1": 20}, cards={"E1": 12}), rules=rules)
    assert got.ok is False
    assert got.reason == P.R_MULTI, f"expected {P.R_MULTI}, got {got.reason!r}"
    assert list(got.failures) == [P.R_LT_30_CARDS, P.R_LT_3_MERCHANTS, P.R_TOP1_GT_75]
    blob = " ".join(got.detail)
    for code_hint in ("n_cards=12", "n_merchants=1", "volume share"):
        assert code_hint in blob, f"the suppression detail must name the cause: {blob!r}"

    # One failing gate names itself instead of hiding behind `multi`.
    single = P.gate(mk(29, {"E1": 10, "E2": 10, "E3": 10}), rules=rules)
    assert single.reason == P.R_LT_30_CARDS and list(single.failures) == [P.R_LT_30_CARDS]


def test_multi_failure_reports_every_gate() -> None:
    check_multi_failure(P.BASE_RULES)


# ---------------------------------------------------------------------------------------------
# 5. MONOTONICITY under refinement
# ---------------------------------------------------------------------------------------------

def _refinements(cell: P.Cell, alphabet=("E1", "E2", "E3"), max_cards: int = 9):
    """Every cell that could be a refinement of `cell`: a subset of the merchants, no more
    volume each, no more cards, no longer transactions. Exhaustive over a bounded grid."""
    base = {m: cell.merchants.get(m, 0) for m in alphabet}
    ranges = [range(0, v + 1) for v in base.values()]
    for combo in product(*ranges):
        volumes = {m: v for m, v in zip(alphabet, combo) if v > 0}
        if not volumes:
            continue
        for cards in range(0, min(cell.n_cards, max_cards) + 1):
            if cards > sum(volumes.values()):
                continue
            try:
                yield mk(cards, volumes)
            except P.CellError:
                continue


def check_monotonicity(rules: P.Rules) -> None:
    """If a coarse cell is suppressed on a CARDINALITY floor, every refinement is suppressed too.

    WHAT IS PROVED (exhaustively over a bounded grid, through `gate()` itself)
        cards and merchants are monotone non-increasing under refinement — a child's card set is a
        subset of its parent's — so a cell suppressed for lt_30_cards or lt_3_merchants has no
        releasable refinement. This is the claim that makes the k-anonymity floor independent of
        how a user slices the data.

    WHAT IS **NOT** PROVED, and must not be asserted
        The same statement is FALSE when the suppression was `top1_gt_75`. A dominant merchant's
        transactions can be spread across siblings, so a refinement can pass G3 where its parent
        failed. `check_g3_is_not_monotone` asserts that counterexample explicitly — which is why
        the UI must name the failing gate („udział jednego podmiotu powyżej 75%”) and must never
        say „zbyt mała grupa” for a share suppression.
    """
    checked = 0
    for volumes in product(range(0, 4), repeat=3):
        if sum(volumes) == 0:
            continue
        parent = mk(min(6, sum(volumes)), {f"E{i+1}": v for i, v in enumerate(volumes) if v})
        got = P.gate(parent, rules=rules)
        if got.ok or not (set(got.failures) & {P.R_LT_30_CARDS, P.R_LT_3_MERCHANTS}):
            continue
        for child in _refinements(parent):
            child_result = P.gate(child, rules=rules)
            checked += 1
            assert child_result.ok is False, (
                "a refinement of a cell suppressed on a cardinality floor was released: "
                f"parent={parent.merchants} n_cards={parent.n_cards} "
                f"child={child.merchants} n_cards={child.n_cards}"
            )
            assert set(child_result.failures) & {P.R_LT_30_CARDS, P.R_LT_3_MERCHANTS}, (
                "the refinement must fail the SAME cardinality floor, not some other gate"
            )
    assert checked > 500, f"the property was barely exercised ({checked} parent/child pairs)"


def check_g3_is_not_monotone(rules: P.Rules) -> None:
    """The named counterexample: G3 is NOT monotone under refinement. Asserted, not ignored."""
    parent = mk(45, {"E1": 40, "E2": 6, "E3": 4})      # E1 = 40/50 = 80% -> suppressed by G3 alone
    child = mk(38, {"E1": 28, "E2": 6, "E3": 4})       # E1 = 28/38 = 73.7% -> passes all three
    assert child.merchants["E1"] <= parent.merchants["E1"]
    assert child.n_cards <= parent.n_cards, "a refinement can never hold more cards than its parent"
    parent_result = P.gate(parent, rules=rules)
    child_result = P.gate(child, rules=rules)
    assert parent_result.ok is False and list(parent_result.failures) == [P.R_TOP1_GT_75], (
        "the parent must be suppressed by the SHARE gate alone for this counterexample to bite"
    )
    assert child_result.ok is True, (
        "a refinement of a share-suppressed cell CAN be releasable — the pattern that proves the "
        "blanket monotonicity claim false, and the reason the UI names the gate that failed"
    )


def test_monotonicity_of_suppression_under_refinement() -> None:
    check_monotonicity(P.BASE_RULES)
    check_g3_is_not_monotone(P.BASE_RULES)


# ---------------------------------------------------------------------------------------------
# 6. G4 — leave-one-out differencing
# ---------------------------------------------------------------------------------------------

def check_g4(rules: P.Rules) -> None:
    """The merchant is INSIDE every comparison cell; it must not be able to subtract itself out.

    THE ATTACK
        A released cell says „this area took 1,000 transactions”. The merchant knows its own 500.
        It subtracts: the complement of the group is 500 transactions over 20 distinct cards —
        which is the other two businesses on the street. The three gates cannot see this, because
        the cell as a whole passes them. G4 re-runs the gates on R \\ {m} for every m.

    THE TEST
        G4-01: the raw cell passes G1-G3 and is suppressed ONLY because the residual after
        removing its largest merchant drops to 20 cards. The control run (differencing off)
        releases the same cell, proving the block comes from G4 and not from G1-G3.
    """
    products = {c["id"]: c for c in FIXTURES["g4_cases"]}
    case = products["G4-01"]
    # The `rules` argument is what is under test here (PRODUCT_RULES in the canonical run), so it
    # is passed through unchanged: turning G4 off in it must make this check fail.
    on = run_case(case, rules)
    assert on.ok is False, "the residual after differencing must block this cell"
    assert on.reason == P.R_G4_DIFFERENCING, f"expected {P.R_G4_DIFFERENCING}, got {on.reason!r}"
    assert any("lt_30_cards" in d for d in on.detail), (
        f"the detail must name the residual sub-gate that failed: {list(on.detail)}"
    )
    assert on.trace[-1].differencing_evidence == "measured"

    off = run_case(case, rules_for(case, differencing=False))
    assert off.ok is True, (
        "control failed: with G4 off the same cell passes G1-G3, so the suppression above is "
        "attributable to G4 alone"
    )

    # The literal case: a two-merchant cell can never be released, however large.
    two = run_case(products["G4-02"], rules)
    assert two.ok is False
    assert P.R_G4_DIFFERENCING in two.failures
    assert P.R_LT_3_MERCHANTS in two.failures

    # Bound mode: without measured residuals the gate uses the sound lower bound and SAYS SO.
    bound = run_case(products["G4-03"], rules)
    assert bound.ok is False
    assert bound.trace[-1].differencing_evidence == "bound", (
        "a cell gated on a bound instead of a measurement must be labelled — a reviewer has to be "
        "able to tell the two apart"
    )

    # A residual below its arithmetic bound is rejected, never trusted.
    with pytest.raises(P.CellError):
        mk(900, {"E1": 700, "E2": 250, "E3": 50}, residuals={"E1": 100})

    # Removing a non-member would manufacture a MORE compliant residual: refused.
    with pytest.raises(KeyError):
        P.residual_cell(mk(900, {"E1": 700, "E2": 250, "E3": 50}), "E9")


def test_g4_leave_one_out_differencing() -> None:
    check_g4(P.PRODUCT_RULES)


# ---------------------------------------------------------------------------------------------
# the 18 reference fixtures (F-01 … F-18), verbatim in tests/privacy/fixtures.json
# ---------------------------------------------------------------------------------------------

def run_all_cases(rules: P.Rules | None = None) -> dict:
    """Run every fixture case and return {case_id: GateResult} (plus 'C-*' and 'G4-*')."""
    out = {}
    for group in ("cases", "cascade_cases", "g4_cases"):
        for case in FIXTURES[group]:
            case_rules = rules if rules is not None else rules_for(case)
            out[case["id"]] = run_case(case, case_rules)
    return out


def test_reference_fixtures() -> None:
    """18/18 reference cases, plus the cascade and G4 cases, match their stated expectations."""
    total = 0
    failures = []
    for group in ("cases", "cascade_cases", "g4_cases"):
        for case in FIXTURES[group]:
            total += 1
            got = run_case(case, rules_for(case))
            errs = compare(case, got, case["expect"])
            if "expect_without_thin_base" in case:
                alt = P.gate(cell_from_spec(case["levels"]["cell"]), "cell",
                             rules=rules_for(case), thin_base=None)
                errs += ["without_thin_base: " + e
                         for e in compare(case, alt, case["expect_without_thin_base"])]
            if "expect_without_differencing" in case:
                alt = run_case(case, rules_for(case, differencing=False))
                errs += ["without_differencing: " + e
                         for e in compare(case, alt, case["expect_without_differencing"])]
            if errs:
                failures.append((case["id"], errs))
    assert FIXTURES["cases"].__len__() == 18, "the reference fixture set is 18 cases"
    assert not failures, "fixture mismatches: " + json.dumps(failures, indent=2)
    assert total == 18 + len(FIXTURES["cascade_cases"]) + len(FIXTURES["g4_cases"])


def test_every_reason_code_is_reachable() -> None:
    """A code no fixture can produce is a code no reviewer can trust (harness spec §8.2)."""
    produced = set()
    for case in FIXTURES["cases"] + FIXTURES["cascade_cases"] + FIXTURES["g4_cases"]:
        for differencing in (None, False, True):
            got = run_case(case, rules_for(case, differencing=differencing))
            produced.add(got.reason)
            produced.update(t.failures for t in got.trace)
    flat = set()
    for item in produced:
        flat.update(item if isinstance(item, tuple) else (item,))
    missing = sorted(set(P.REASON_CODES) - flat)
    assert not missing, f"reason codes no fixture produces: {missing}"
    assert flat <= set(P.REASON_CODES), "a fixture produced a code outside the frozen set"


def test_pre_gate_reasons_are_distinct() -> None:
    """`thin_base` (a display floor) and the privacy gates are never conflated."""
    case = next(c for c in FIXTURES["cases"] if c["id"] == "F-17")
    thin = run_case(case, rules_for(case))
    assert thin.reason == P.R_THIN_BASE and thin.trace == ()
    without = P.gate(cell_from_spec(case["levels"]["cell"]), "cell", rules=rules_for(case))
    assert without.reason == P.R_MULTI
    assert set(without.failures) == {P.R_LT_30_CARDS, P.R_LT_3_MERCHANTS, P.R_TOP1_GT_75}

    empty = next(c for c in FIXTURES["cases"] if c["id"] == "F-18")
    no_data = run_case(empty, rules_for(empty))
    assert no_data.reason == P.R_NO_DATA and no_data.value_or_none is None
    assert no_data.trace == (), "an empty relation is decided before any level is walked"


# ---------------------------------------------------------------------------------------------
# the release guard — no orphan releases
# ---------------------------------------------------------------------------------------------

def test_release_guard_refuses_orphan_values() -> None:
    """Every aggregate the app can display must have been produced by gate()."""
    released = P.gate(mk(30, {"E1": 10, "E2": 10, "E3": 10}), rules=P.BASE_RULES)
    assert P.release(released, rules=P.BASE_RULES) is released.value_or_none

    suppressed = P.gate(mk(29, {"E1": 10, "E2": 10, "E3": 10}), rules=P.BASE_RULES)
    assert P.release(suppressed, rules=P.BASE_RULES) is None, "views must render the None state"

    # A hand-built record never passed gate(): the module-private seal is missing.
    forged = P.GateResult(ok=True, value_or_none=released.value_or_none, reason="ok", level="cell")
    with pytest.raises(P.ReleaseGuardError) as caught:
        P.assert_released(forged)
    assert caught.value.code == "ungated_path"

    # A bare dict is not a record at all — the classic „just put the number in the payload” path.
    with pytest.raises(P.ReleaseGuardError) as caught:
        P.assert_released({"ok": True, "value": 1234})
    assert caught.value.code == "ungated_path"

    # A released record without a trace cannot be defended.
    trace_free = P.GateResult(ok=True, value_or_none=released.value_or_none, reason="ok", level="cell")
    object.__setattr__(trace_free, "_seal", released._seal)
    with pytest.raises(P.ReleaseGuardError) as caught:
        P.assert_released(trace_free)
    assert caught.value.code == "no_trace"

    # ok=False with a value is unrepresentable, not merely unused.
    with pytest.raises(P.ReleaseGuardError) as caught:
        P.GateResult(ok=False, value_or_none=released.value_or_none, reason=P.R_LT_30_CARDS,
                     level=P.L_LOCKED)
    assert caught.value.code == "leak"

    # A record produced under a different rule set must not be shown under the active one.
    with pytest.raises(P.ReleaseGuardError) as caught:
        P.assert_released(released, rules=P.PRODUCT_RULES)
    assert caught.value.code == "stale_rules"


def test_result_types_cannot_express_a_leak() -> None:
    """Structural guarantees: suppressed ⇒ locked, released ⇒ a level and no failures."""
    ok = P.gate(mk(30, {"E1": 10, "E2": 10, "E3": 10}), rules=P.BASE_RULES)
    assert (ok.level, ok.reason, ok.failures) == ("cell", P.R_OK, ())
    bad = P.gate(mk(29, {"E1": 10, "E2": 10, "E3": 10}), rules=P.BASE_RULES)
    assert bad.level == P.L_LOCKED and bad.value_or_none is None
    with pytest.raises(P.ReleaseGuardError):
        P.GateResult(ok=False, value_or_none=None, reason=P.R_OK, level=P.L_LOCKED)
    with pytest.raises(P.ReleaseGuardError):
        P.GateResult(ok=True, value_or_none=ok.value_or_none, reason=P.R_LT_30_CARDS, level="cell")


def test_cell_rejects_impossible_input() -> None:
    """Impossible cells are refused, because trusting one is how a gate is bypassed."""
    with pytest.raises(P.CellError):   # volumes must add up to the cell
        P.Cell(n_cards=30, merchants={"E1": 10, "E2": 10}, n_transactions=100)
    with pytest.raises(P.CellError):   # a phantom zero-volume merchant inflates G2
        P.Cell(n_cards=30, merchants={"E1": 20, "E2": 10, "E3": 0}, n_transactions=30)
    with pytest.raises(P.CellError):   # more cards than transactions
        P.Cell(n_cards=40, merchants={"E1": 30}, n_transactions=30)
    with pytest.raises(P.CellError):   # a merchant cannot hold more cards than transactions
        P.Cell(n_cards=30, merchants={"E1": 30}, n_transactions=30, merchant_cards={"E1": 31})
    with pytest.raises(P.CellError):   # a residual below the arithmetic bound is not evidence
        P.Cell(n_cards=900, merchants={"E1": 700, "E2": 250}, n_transactions=950,
               residual_n_cards={"E1": 100})
    with pytest.raises(P.RulesError):  # a float threshold cannot decide a boundary
        P.Rules(max_share=0.75)
    with pytest.raises(P.RulesError):  # a share limit above 1 would disable G3 silently
        P.Rules(max_share=Fraction(4, 3))


def test_plausibility_findings_catch_a_broken_join() -> None:
    """The two consistency checks a producer can still trip, and their absence on real cells."""
    ok = mk(30, {"E1": 20, "E2": 10}, cards={"E1": 20, "E2": 10})
    assert P.plausibility_findings(ok) == (), P.plausibility_findings(ok)
    understated = mk(268, {"E1": 160, "E2": 140}, cards={"E1": 100, "E2": 100})
    findings = P.plausibility_findings(understated)
    assert findings and "cannot be smaller than the union" in findings[0], findings


def test_determinism() -> None:
    """Same input ⇒ byte-identical output, including trace ordering (no sets, no clock)."""
    first = json.dumps({k: v.to_mapping() for k, v in run_all_cases().items()}, sort_keys=True)
    second = json.dumps({k: v.to_mapping() for k, v in run_all_cases().items()}, sort_keys=True)
    assert first == second


def test_pipeline_gate_dict_is_the_same_gate() -> None:
    """The pipeline's per-postcode gate block must be computed by THIS contract, not a copy.

    `pipeline/_gates.py` is a stop-gap with its own copy of the thresholds; its loader prefers
    `contracts.privacy` and is waiting for this module to expose the shape it calls. Two copies of
    „≥ 30 cards" is how the codebase ended up enforcing one gate of three (defect D3), so the two
    must agree everywhere — including on the real cells, where they must agree exactly.
    """
    pipeline_gates = pytest.importorskip(
        "pipeline._gates",
        reason="the pipeline's local fallback has been deleted — nothing left to compare against",
    )
    cases = []
    for n_cards in (0, 1, 29, 30, 31, 200, 900):
        for n_merchants in (0, 1, 2, 3, 4, 9):
            for n_tran in (0, 1, 30, 100, 1000):
                for top1_volume in (0, 1, 22, 75, 76, 750, 751):
                    for top1_cards in (0, 12, 22, 75, 76):
                        cases.append((n_cards, n_merchants, top1_volume, n_tran, top1_cards))
    upstream = ROOT / "artifacts" / "privacy-report.json"
    if upstream.exists():
        doc = json.loads(upstream.read_text(encoding="utf-8"))
        for row in doc["grain_postcode"]["cells"]:
            cases.append((row["n_cards"], row["n_merchants"], row["top1_transactions"],
                          row["n_transactions"], 0))

    mismatches = []
    for n_cards, n_merchants, top1_volume, n_tran, top1_cards in cases:
        theirs = pipeline_gates.gate_dict(n_cards=n_cards, n_merchants=n_merchants,
                                          top1_volume=top1_volume, n_tran=n_tran,
                                          top1_cards=top1_cards)
        ours = P.gate_dict(n_cards=n_cards, n_merchants=n_merchants, top1_volume=top1_volume,
                           n_tran=n_tran, top1_cards=top1_cards)
        if theirs != ours:
            mismatches.append((n_cards, n_merchants, top1_volume, n_tran, top1_cards, theirs, ours))
    assert not mismatches, f"{len(mismatches)} disagreements, first: {mismatches[:3]}"

    # And the loader must actually adopt this module once these symbols exist.
    module, source = pipeline_gates.load()
    assert source == "contracts.privacy", (
        f"pipeline/_gates.load() still returns {source!r}: the pipeline would keep using its own "
        "copy of the thresholds"
    )
    assert Path(module.__file__).resolve() == Path(P.__file__).resolve(), (
        f"the loader adopted {module.__file__}, not contracts/privacy.py"
    )


def test_measured_report_matches_the_audit() -> None:
    """The measured numbers the submission quotes must still be the numbers the command produces.

    Guards the claim „only 18 of 62 postcodes pass all three gates, and they carry 90.7% of volume”
    (AGENTS.md) and the conservative reading that follows from the card-share leg. Regenerate with
    `python3 scripts/privacy_report.py`; if this test fails, the deck and the copy block are stale.
    """
    artifact = ROOT / "artifacts" / "privacy-report.json"
    if not artifact.exists():
        pytest.skip("artifacts/privacy-report.json has not been generated in this checkout")
    doc = json.loads(artifact.read_text(encoding="utf-8"))
    summary = doc["grain_postcode"]["summary"]
    assert summary["cells"] == 62, summary
    assert summary["g1_pass"] == 54, summary
    assert summary["g2_pass"] == 25, summary
    assert summary["g3_pass_volume_only"] == 25, summary
    assert summary["all_three_pass_volume_only"] == 18, summary
    assert abs(summary["share_all_three_volume_only_pct"] - 90.7) <= 0.05, summary
    # The conservative dual-metric reading is one cell stricter, and it names the offending postcode.
    assert summary["all_three_pass"] == 17, summary
    card_leg = next(f for f in doc["findings"] if f["id"] == "F-G3-CARD-LEG")
    assert [c["pc"] for c in card_leg["cells"]] == ["81-740"], card_leg
    assert doc["matches_expected"]["ok"] is True, doc["matches_expected"]


def test_contract_fingerprint() -> None:
    fp = P.contract_fingerprint()
    assert fp["min_cards"] == 30 and fp["min_merchants"] == 3
    assert fp["max_share"] == "3/4" and fp["cascade_order"] == ["cell", "parent", "city"]
    assert set(fp["reason_codes"]) == set(P.REASON_CODES)


def test_typescript_mirror_parity() -> None:
    """The browser mirror must decide the same 18 fixtures the same way (build failure if not)."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: the TypeScript mirror could not be executed")
    runner = Path(__file__).resolve().parent / "run_mirror.mjs"
    with tempfile.TemporaryDirectory() as tmp:
        fingerprint = Path(tmp) / "fingerprint.json"
        fingerprint.write_text(json.dumps(P.contract_fingerprint()), encoding="utf-8")
        proc = subprocess.run([node, str(runner), str(fingerprint)],
                              capture_output=True, text=True, cwd=str(ROOT))
    assert proc.returncode == 0, (
        "contracts/privacy.ts diverges from contracts/privacy.py\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "fingerprint identical" in proc.stdout, proc.stdout
