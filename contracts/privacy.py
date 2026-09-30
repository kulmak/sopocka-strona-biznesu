"""contracts/privacy.py — THE single source of truth for the Sopocka Strona Biznesu privacy gates.

WHAT
    Pure functions that decide whether one aggregate ("cell") may be released, and at which
    level of the area hierarchy. Four gates, in the vocabulary of the product:

        G1  lt_30_cards        the cell covers at least 30 DISTINCT CARDS
        G2  lt_3_merchants     the cell covers at least 3 DISTINCT MERCHANTS (entities)
        G3  top1_gt_75         no single merchant holds more than 75% of the cell
        G4  g4_differencing    the cell still satisfies G1-G3 after removing any one merchant

    G1-G3 are the binding rules of the challenge document §3 („Oczekiwany rezultat”):

        „analizy i prezentacje wyników powinny być prowadzone wyłącznie na grupach obejmujących
          co najmniej 30 kart”
        „każda grupa porównawcza powinna obejmować co najmniej 3 podmioty/graczy, przy czym
          udział żadnego z nich nie może przekraczać 75% analizowanej grupy”
        „Rozwiązanie nie powinno umożliwiać identyfikacji pojedynczych użytkowników, kart,
          transakcji ani podmiotów”

    30 is 30 distinct CARDS (`pymt_crd_acct_num_raw`), never cardholders, never transactions,
    never visitors. G4 is a voluntary strengthening beyond the letter of the rule (see its
    docstring); it is OFF in `BASE_RULES` (the letter of the challenge, used by the boundary
    tests and the 18 reference fixtures) and ON in `PRODUCT_RULES` (the audited build the app
    and the pipeline use).

WHY THIS MODULE EXISTS
    * The ≥30-card gate could not fire: the browser loader never read the card column, so the
      only "privacy gate" in the prototype was a merchant-count check on a whole-period union
      with a fail-open branch (`!s ||` → an unknown key passed). A gate that cannot fail is not
      a gate (research/privacy-harness-spec.md §8).
    * Three local audited artifacts claim enforcement, one denies it, and the code enforced one
      gate of three (research/privacy-compliance.md §1.6, defects I-2/I-4/I-6).
    * Everything downstream — pipeline, artifact, browser — must import THIS module (or its
      hand-mirror `contracts/privacy.ts`, whose parity is tested against the same
      `tests/privacy/fixtures.json`). One constructor, one gate, one release guard.

ROUNDING IS A CORRECTNESS PROPERTY
    Every gate decision is taken on exact integers / `fractions.Fraction`. **Never float
    division.** Exactly 75.000000% PASSES and 75.000025% FAILS — the two differ by 1 part in
    4,000,000 and a `float` comparison is not guaranteed to keep them apart once the numerator
    or denominator grows. `top1_share()` returns a `Fraction`; `format_share()` is the ONLY
    place a decimal string is produced, and it is presentation-only, applied AFTER the gate.
    Rounding must never move a cell across a threshold (compliance §2.3 R2/R4).

FAILURE MODE OF THIS MODULE
    * No I/O, no globals, no clock, no randomness: same input ⇒ byte-identical output. The
      caller reads `rules.json`; `Rules.from_mapping()` is pure.
    * Invalid input raises (`CellError`, `RulesError`, `ReleaseGuardError`) instead of being
      coerced. A cell whose numbers cannot be true (volumes that do not sum to the cell total,
      a phantom zero-volume merchant, a residual outside its arithmetic bounds) is REJECTED:
      trusting it is how a gate is bypassed.
    * Unknown aggregation-level keys raise: a cascade candidate silently dropped is an
      escalation path silently lost.
    * A suppressed record can never carry a value and a released record can never carry a
      reason — enforced at construction and re-checked by `assert_released()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

__all__ = [
    # thresholds (the only place these numbers appear)
    "MIN_CARDS", "MIN_MERCHANTS", "MAX_TOP1_SHARE", "THIN_BASE_TRANSACTIONS", "RULE_VERSION",
    "R_OK", "R_LT_30_CARDS", "R_LT_3_MERCHANTS", "R_TOP1_GT_75", "R_MULTI",
    "R_ALL_LEVELS_FAILED", "R_G4_DIFFERENCING", "R_THIN_BASE", "R_NO_DATA", "REASON_CODES",
    "CASCADE_ORDER", "L_CELL", "L_PARENT", "L_CITY", "L_LOCKED",
    "Cell", "Rules", "ReleasedValue", "LevelTrace", "GateResult",
    "CellError", "RulesError", "ReleaseGuardError",
    "BASE_RULES", "PRODUCT_RULES",
    "top1_share", "max_share", "format_share", "gate", "cascade", "residual_cell",
    "assert_released", "release", "plausibility_findings", "contract_fingerprint",
    # pipeline adapter (same gate, legacy shape)
    "Aggregation", "EntityStat", "evaluate", "gate_dict", "LEGACY_REASON_CODES",
]

# --------------------------------------------------------------------------------------------
# 1. THE THRESHOLDS — challenge document §3, verbatim. The ONLY place these numbers appear.
#    `contracts/privacy.ts` mirrors this block line for line; tests/privacy/test_mirror.mjs
#    fails the build if the two drift.
# --------------------------------------------------------------------------------------------

MIN_CARDS = 30                    # „co najmniej 30 kart” — distinct cards, inclusive
MIN_MERCHANTS = 3                 # „co najmniej 3 podmioty/graczy” — distinct merchants, inclusive
MAX_TOP1_SHARE = Fraction(3, 4)   # „udział … nie może przekraczać 75%” — 75% exactly PASSES
THIN_BASE_TRANSACTIONS = 12       # display floor, NOT a privacy gate (see R_THIN_BASE)
RULE_VERSION = "sopot-privacy-v1+datasprint-2026-09-30"

# --- stable machine codes. The UI maps these to human strings; nothing else may invent one. ---
R_OK = "ok"
R_LT_30_CARDS = "lt_30_cards"
R_LT_3_MERCHANTS = "lt_3_merchants"
R_TOP1_GT_75 = "top1_gt_75"
R_MULTI = "multi"                     # >1 gate failed in the same cell; `failures` names them
R_ALL_LEVELS_FAILED = "all_levels_failed"
R_G4_DIFFERENCING = "g4_differencing"   # extension: residual gate (G4), not in the six-code set
R_THIN_BASE = "thin_base"               # reference fixture F-17 (display floor, not k-anonymity)
R_NO_DATA = "no_data"                   # reference fixture F-18 (empty relation is never a pass)

#: Every code this module can return. F-17/F-18 and G4 need a code of their own, so this set is
#: the frozen six (`ok`, `lt_30_cards`, `lt_3_merchants`, `top1_gt_75`, `multi`,
#: `all_levels_failed`) plus exactly three documented additions. A test asserts that every code
#: here is produced by at least one fixture — a code no test can reach is a code no reviewer
#: can trust (harness spec §8.2).
REASON_CODES: Tuple[str, ...] = (
    R_OK, R_LT_30_CARDS, R_LT_3_MERCHANTS, R_TOP1_GT_75, R_MULTI, R_ALL_LEVELS_FAILED,
    R_G4_DIFFERENCING, R_THIN_BASE, R_NO_DATA,
)

#: Canonical reporting order when several gates fail (harness spec §2.3: G1 → G2 → G3 → G4).
_FAILURE_ORDER: Tuple[str, ...] = (
    R_LT_30_CARDS, R_LT_3_MERCHANTS, R_TOP1_GT_75, R_G4_DIFFERENCING,
)

#: The cascade the app walks: the requested cell, its parent area, then the whole city.
CASCADE_ORDER: Tuple[str, ...] = ("cell", "parent", "city")

L_CELL, L_PARENT, L_CITY, L_LOCKED = "cell", "parent", "city", "locked"
LEVELS: Tuple[str, ...] = (L_CELL, L_PARENT, L_CITY, L_LOCKED)


class CellError(ValueError):
    """A cell is arithmetically impossible. Raised, never coerced: trusting it bypasses a gate."""


class RulesError(ValueError):
    """A rules object is nonsense (e.g. max_share > 1, which would silently disable G3)."""


class ReleaseGuardError(PermissionError):
    """A record reached a renderer without passing `gate()`.

    Codes (``err.code``): ``ungated_path`` · ``orphan_release`` · ``leak`` · ``no_trace`` ·
    ``stale_rules`` · ``suppressed_with_value`` · ``released_with_reason``.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code.upper()}: {message}")
        self.code = code
        self.message = message


# --------------------------------------------------------------------------------------------
# 2. Exact share arithmetic. No float ever decides anything.
# --------------------------------------------------------------------------------------------

def max_share(values: Mapping[str, int], denominator: Optional[int] = None) -> Fraction:
    """The largest value in ``values`` over ``denominator``, as an exact ``Fraction``.

    WHAT  ``max(v) / denominator`` with ``Fraction``, or ``0`` for an empty mapping.
    WHY   G3 is a share test, and a share test on floats mis-decides the 75.000025% boundary.
    FAIL  An empty mapping or a non-positive denominator returns ``Fraction(0, 1)``: no
          merchant can dominate a group with no transactions. A group with no transactions is
          suppressed by ``no_data`` before G3 is consulted, so this cannot release anything.
    """
    if not values:
        return Fraction(0, 1)
    top = max(values.values())
    denom = sum(values.values()) if denominator is None else denominator
    if denom <= 0:
        return Fraction(0, 1)
    return Fraction(top, denom)


def top1_share(merchants: Mapping[str, int]) -> Fraction:
    """Exact share of the largest merchant in ``merchants`` (``{merchant_id: transactions}``).

    WHAT  ``max(merchants.values()) / sum(merchants.values())``, as a ``Fraction``.
    WHY   This is the number the ≤75% rule constrains („udział żadnego z nich”). Exact
          arithmetic is mandatory: 75.000000% must PASS and 75.000025% must FAIL.
    FAIL  Empty mapping ⇒ ``Fraction(0, 1)``. ``Cell`` guarantees
          ``sum(merchants.values()) == n_transactions``, so this denominator is the cell's
          transaction total. Callers that want a share over a different denominator (e.g. the
          card-share leg of G3) must use :func:`max_share` with that denominator explicitly.
    """
    return max_share(merchants)


def format_share(value: Fraction, decimals: int = 1) -> str:
    """Render an exact share as a percentage string, half-up, **for display only**.

    WHAT  Integer half-up rounding: ``floor(n/d * 10^decimals + 1/2)``, computed on integers.
    WHY   Compliance §2.3 R4: display rounding happens AFTER the gate. Doing it with floats
          invites a cell to be shown as "75.0%" while the gate compared a different number.
    FAIL  A negative ``decimals`` raises ``ValueError`` (a display bug must not silently
          truncate to an integer percentage, which is how "75%" becomes indistinguishable from
          "75.4%" in a footnote).
    """
    if decimals < 0:
        raise ValueError("decimals must be >= 0")
    scale = 10 ** decimals
    n, d = value.numerator, value.denominator
    scaled = (2 * n * 100 * scale + d) // (2 * d)    # floor(value*100*scale + 1/2), exact
    whole, frac = divmod(scaled, scale)
    if decimals == 0:
        return str(whole)
    return f"{whole}.{str(frac).rjust(decimals, '0')}"


# --------------------------------------------------------------------------------------------
# 3. Rules — data, not literals (p146/p317: restrictions may be amended mid-event).
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Rules:
    """The gate configuration. Pure data; construct with :meth:`from_mapping` from JSON.

    All four thresholds live here, which is why the app can be re-pointed at an amended rule
    set without editing a renderer.
    """

    min_cards: int = MIN_CARDS
    min_merchants: int = MIN_MERCHANTS
    max_share: Fraction = MAX_TOP1_SHARE
    share_metrics: Tuple[str, ...] = ("volume", "cards")
    require_differencing: bool = False
    thin_base_transactions: int = THIN_BASE_TRANSACTIONS
    rule_version: str = RULE_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.min_cards, int) or self.min_cards < 1:
            raise RulesError(f"min_cards must be a positive int, got {self.min_cards!r}")
        if not isinstance(self.min_merchants, int) or self.min_merchants < 1:
            raise RulesError(f"min_merchants must be a positive int, got {self.min_merchants!r}")
        share = self.max_share
        if isinstance(share, float):                       # a float threshold is a bug, not a rule
            raise RulesError(
                "max_share must be an exact Fraction or 'n/d' string, never a float: "
                "a float threshold cannot decide the 75.000000% / 75.000025% boundary"
            )
        if not isinstance(share, Fraction) or not (0 < share <= 1):
            raise RulesError(f"max_share must be an exact Fraction in (0, 1], got {share!r}")
        for metric in self.share_metrics:
            if metric not in ("volume", "cards"):
                raise RulesError(f"unknown share metric {metric!r}")
        if not isinstance(self.thin_base_transactions, int) or self.thin_base_transactions < 1:
            raise RulesError("thin_base_transactions must be a positive int")

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "Rules":
        """Build from a JSON-shaped mapping. Pure: the caller does the file read.

        Keys (all optional, camelCase as in tests/privacy/fixtures.json):
        ``minCards``, ``minMerchants``, ``maxShare`` (``"3/4"`` — a string, so a float can never
        enter), ``shareMetrics``, ``requireDifferencing``, ``thinBaseTransactions``,
        ``ruleVersion``. Shares given as ``[n, d]`` or ``n/d`` strings only.
        """
        def _share(raw: Any) -> Fraction:
            if isinstance(raw, Fraction):
                return raw
            if isinstance(raw, str):
                return Fraction(raw)
            if isinstance(raw, (list, tuple)) and len(raw) == 2:
                return Fraction(int(raw[0]), int(raw[1]))
            raise RulesError(f"maxShare must be 'n/d', [n, d] or Fraction — got {raw!r}")

        return cls(
            min_cards=int(mapping.get("minCards", MIN_CARDS)),
            min_merchants=int(mapping.get("minMerchants", MIN_MERCHANTS)),
            max_share=_share(mapping.get("maxShare", MAX_TOP1_SHARE)),
            share_metrics=tuple(mapping.get("shareMetrics", ("volume", "cards"))),
            require_differencing=bool(mapping.get("requireDifferencing", False)),
            thin_base_transactions=int(
                mapping.get("thinBaseTransactions", THIN_BASE_TRANSACTIONS)
            ),
            rule_version=str(mapping.get("ruleVersion", RULE_VERSION)),
        )

    @property
    def min_entities(self) -> int:
        """Legacy alias for :attr:`min_merchants`.

        `pipeline/_gates.py` (a stop-gap written before this module landed) spells the field
        `min_entities`. Keeping the alias means the pipeline's loader can adopt this module without
        a second copy of the threshold, which is the whole point of AGENTS.md rule 6.
        """
        return self.min_merchants

    def to_mapping(self) -> Dict[str, Any]:
        """JSON-shaped, shares as ``"n/d"`` strings. Used by the report and the mirror tests."""
        return {
            "minCards": self.min_cards,
            "minMerchants": self.min_merchants,
            "maxShare": f"{self.max_share.numerator}/{self.max_share.denominator}",
            "shareMetrics": list(self.share_metrics),
            "requireDifferencing": self.require_differencing,
            "thinBaseTransactions": self.thin_base_transactions,
            "ruleVersion": self.rule_version,
        }


#: The letter of the challenge: G1, G2, G3. Used by the 18 reference fixtures, by the boundary
#: tests and by the "18 of 62 postcodes" measurement, which must stay comparable to the audit.
BASE_RULES = Rules()

#: The audited build. Adds G4 (differencing). The app and the pipeline use THIS object. Its
#: `rule_version` differs from BASE_RULES on purpose: a record produced under the letter of the
#: rule must not be displayed under the audited rule set, and `assert_released` enforces that.
PRODUCT_RULES = Rules(require_differencing=True, rule_version=RULE_VERSION + "+g4")


# --------------------------------------------------------------------------------------------
# 4. Cell — the only shape the gate accepts.
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class Cell:
    """One aggregate of one area × period × daypart, plus the evidence the gate needs.

    WHAT
        ``n_cards``          distinct cards in the cell's UNION relation (never a sum of children)
        ``merchants``        ``{opaque_merchant_id: transactions}`` — the cell's own partition
        ``n_transactions``   ``|R|``; MUST equal ``sum(merchants.values())``
        ``merchant_cards``   optional ``{opaque_merchant_id: distinct cards}``; enables the
                             card-share leg of G3 (conservative reading, compliance §2.3 R7)
        ``residual_n_cards`` optional ``{opaque_merchant_id: distinct cards after removing it}``
                             — MEASURED leave-one-out union counts; enables exact G4

    WHY
        * ``n_cards`` is a union count because card counts are NOT additive across a partition:
          measured on the delivered data, Σ cards over the 54 Sopot codes is 223,800 against a
          city union of 157,327 (+42.25%). A gate that sums children can pass a parent that
          does not qualify (harness spec §5, invariant P-3).
        * ``merchants`` keys are OPAQUE ids. The gate never sees a merchant name, a street or a
          ``postcode × merchant`` pair, so it cannot put one into a reason string.

    FAIL (raises ``CellError`` — never a silent coercion)
        * negative counts, non-integer volumes;
        * ``sum(merchants.values()) != n_transactions`` — the entity share must be conserved,
          or ``top1_share`` is computed against a denominator nobody measured;
        * a zero-volume merchant — a phantom entity added to satisfy G2;
        * ``merchant_cards`` for an unknown merchant, with 0 cards, or with more cards than that
          merchant has transactions;
        * ``n_cards > n_transactions`` — more distinct cards than transactions is impossible;
        * ``residual_n_cards`` outside ``[n_cards - min(volume, n_cards), n_cards]`` — a residual
          below the arithmetic bound would be evidence of a bypass, not evidence of anonymity.
    """

    n_cards: int
    merchants: Mapping[str, int]
    n_transactions: int
    merchant_cards: Optional[Mapping[str, int]] = None
    residual_n_cards: Optional[Mapping[str, int]] = None
    label: Optional[str] = None   # human area label for reports/UI; NEVER an identity or a venue

    def __post_init__(self) -> None:
        if not isinstance(self.n_cards, int) or isinstance(self.n_cards, bool):
            raise CellError(f"n_cards must be an int, got {self.n_cards!r}")
        if not isinstance(self.n_transactions, int) or isinstance(self.n_transactions, bool):
            raise CellError(f"n_transactions must be an int, got {self.n_transactions!r}")
        if self.n_cards < 0 or self.n_transactions < 0:
            raise CellError("counts must be non-negative")
        if self.n_cards > self.n_transactions:
            raise CellError(
                f"n_cards={self.n_cards} > n_transactions={self.n_transactions}: "
                "every card needs at least one transaction"
            )
        total = 0
        for merchant, volume in self.merchants.items():
            if not isinstance(volume, int) or isinstance(volume, bool):
                raise CellError(f"volume for an entity must be an int, got {volume!r}")
            if volume <= 0:
                raise CellError(
                    "every entity in a cell must have at least one transaction; "
                    "a zero-volume entry is a phantom entity inflating the G2 count"
                )
            total += volume
        if total != self.n_transactions:
            raise CellError(
                f"sum(merchants.values())={total} != n_transactions={self.n_transactions}: "
                "the cell's partition does not add up to the cell"
            )
        if self.merchant_cards is not None:
            unknown = set(self.merchant_cards) - set(self.merchants)
            if unknown:
                raise CellError("merchant_cards names entities that are not in the cell")
            for merchant, cards in self.merchant_cards.items():
                if not isinstance(cards, int) or isinstance(cards, bool) or cards < 1:
                    raise CellError("merchant_cards entries must be positive ints")
                if cards > self.merchants[merchant]:
                    raise CellError(
                        f"entity with {self.merchants[merchant]} transactions cannot hold "
                        f"{cards} distinct cards"
                    )
        if self.residual_n_cards is not None:
            unknown = set(self.residual_n_cards) - set(self.merchants)
            if unknown:
                raise CellError("residual_n_cards names entities that are not in the cell")
            for merchant, cards in self.residual_n_cards.items():
                lower = self.n_cards - min(self.merchants[merchant], self.n_cards)
                if not isinstance(cards, int) or isinstance(cards, bool) or not (lower <= cards <= self.n_cards):
                    raise CellError(
                        f"residual_n_cards[{merchant!r}]={cards!r} is outside "
                        f"[{lower}, {self.n_cards}] — impossible evidence"
                    )

    # -- equality/hash on normalised, order-insensitive form (dicts are not hashable) ---------
    def _key(self) -> Tuple[Any, ...]:
        return (
            self.n_cards, self.n_transactions, self.label,
            tuple(sorted(self.merchants.items())),
            None if self.merchant_cards is None else tuple(sorted(self.merchant_cards.items())),
            None if self.residual_n_cards is None else tuple(sorted(self.residual_n_cards.items())),
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Cell) and self._key() == other._key()

    def __hash__(self) -> int:
        return hash(self._key())

    @property
    def n_merchants(self) -> int:
        """Distinct merchants — DERIVED from ``merchants``, never a separate declared field.

        The reference fixture set declared ``n_entities`` independently of ``per_entity`` and
        three cases (F-08, F-12, F-13) declared more entities than they listed, i.e. they
        violated the reference's own completeness invariant P-4. Deriving the count makes that
        class of bug unrepresentable (harness spec §2.2.2).
        """
        return len(self.merchants)

    @property
    def is_empty(self) -> bool:
        """No transactions ⇒ ``no_data``. An empty relation must never be treated as a pass."""
        return self.n_transactions == 0

    def schema(self) -> Dict[str, Any]:
        """JSON-shaped, identity-free summary. Deliberately omits merchant volumes and ids."""
        return {
            "n_cards": self.n_cards,
            "n_merchants": self.n_merchants,
            "n_transactions": self.n_transactions,
            "top1_share": f"{top1_share(self.merchants).numerator}/{top1_share(self.merchants).denominator}",
            "label": self.label,
        }


# --------------------------------------------------------------------------------------------
# 5. Results — a suppressed record can never carry a value.
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ReleasedValue:
    """The only payload a renderer may print. Counts + an exact share, at a named level."""

    level: str
    n_transactions: int
    n_cards: int
    n_merchants: int
    top1_share: Fraction

    def to_mapping(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "n_transactions": self.n_transactions,
            "n_cards": self.n_cards,
            "n_merchants": self.n_merchants,
            "top1_share": f"{self.top1_share.numerator}/{self.top1_share.denominator}",
            "top1_share_pct": format_share(self.top1_share, 1),
        }


@dataclass(frozen=True)
class LevelTrace:
    """What one candidate level looked like. Recorded for released AND suppressed cells.

    The detail strings name a GATE or a RANK, never an entity: „entity #1 of 3 (largest by
    volume)” is allowed; a merchant id, a name or an address is not (compliance §2.5).
    """

    level: str
    n_cards: int
    n_merchants: int
    n_transactions: int
    top1_share: Fraction
    top1_card_share: Optional[Fraction]
    ok: bool
    failures: Tuple[str, ...]
    detail: Tuple[str, ...]
    differencing_evidence: str          # 'measured' | 'bound' | 'not_evaluated'
    card_share_evaluated: bool

    def to_mapping(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "n_cards": self.n_cards,
            "n_merchants": self.n_merchants,
            "n_transactions": self.n_transactions,
            "top1_share": f"{self.top1_share.numerator}/{self.top1_share.denominator}",
            "top1_card_share": (
                None if self.top1_card_share is None
                else f"{self.top1_card_share.numerator}/{self.top1_card_share.denominator}"
            ),
            "ok": self.ok,
            "failures": list(self.failures),
            "detail": list(self.detail),
            "differencing_evidence": self.differencing_evidence,
            "card_share_evaluated": self.card_share_evaluated,
        }


_SEAL = object()   # module-private. Only gate()/cascade() can produce a sealed record.


@dataclass(frozen=True)
class GateResult:
    """The outcome for one cell (``gate``) or one cascade (``cascade``).

    ``ok=True``  ⇒ ``value_or_none`` is a :class:`ReleasedValue`, ``reason == "ok"``,
                   ``failures == ()``, ``level in {cell, parent, city}``, ``trace`` non-empty and
                   its last entry passed.
    ``ok=False`` ⇒ ``value_or_none is None``, ``level == "locked"``, ``reason`` is a documented
                   code naming WHY (``multi`` ⇒ ``failures`` names every failing gate).

    ``value`` is an alias for the frozen field name ``value_or_none``.
    """

    ok: bool
    value_or_none: Optional[ReleasedValue]
    reason: str
    level: str
    failures: Tuple[str, ...] = ()
    detail: Tuple[str, ...] = ()
    escalated: bool = False
    trace: Tuple[LevelTrace, ...] = ()
    levels_evaluated: Tuple[str, ...] = ()
    levels_missing: Tuple[str, ...] = ()
    rule_version: str = RULE_VERSION
    _seal: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.ok:
            if self.value_or_none is None:
                raise ReleaseGuardError("orphan_release", "ok=True with no value")
            if self.reason != R_OK:
                raise ReleaseGuardError("released_with_reason", f"ok=True but reason={self.reason!r}")
            if self.level == L_LOCKED or self.level not in CASCADE_ORDER:
                raise ReleaseGuardError("orphan_release", f"ok=True at level={self.level!r}")
            if self.failures:
                raise ReleaseGuardError("orphan_release", "ok=True with failing gates recorded")
        else:
            if self.value_or_none is not None:
                raise ReleaseGuardError("leak", "a suppressed record carries a value")
            if self.level != L_LOCKED:
                raise ReleaseGuardError("orphan_release", f"ok=False must be level='locked', got {self.level!r}")
            if self.reason not in REASON_CODES or self.reason == R_OK:
                raise ReleaseGuardError("orphan_release", f"unknown suppression reason {self.reason!r}")

    @property
    def value(self) -> Optional[ReleasedValue]:
        """Alias for :attr:`value_or_none` (the frozen field name)."""
        return self.value_or_none

    def to_mapping(self) -> Dict[str, Any]:
        """Deterministic JSON shape: no sets, no dict ordering, no timestamps."""
        return {
            "ok": self.ok,
            "value": None if self.value_or_none is None else self.value_or_none.to_mapping(),
            "reason": self.reason,
            "level": self.level,
            "failures": list(self.failures),
            "detail": list(self.detail),
            "escalated": self.escalated,
            "levels_evaluated": list(self.levels_evaluated),
            "levels_missing": list(self.levels_missing),
            "rule_version": self.rule_version,
            "trace": [t.to_mapping() for t in self.trace],
        }


# --------------------------------------------------------------------------------------------
# 6. The gate
# --------------------------------------------------------------------------------------------

def _ordered(codes: Iterable[str]) -> Tuple[str, ...]:
    """Deduplicate and put failure codes in the canonical order (G1 → G2 → G3 → G4)."""
    seen = set(codes)
    return tuple(code for code in _FAILURE_ORDER if code in seen)


def _entity_rank_label(merchant: str, cell: Cell) -> str:
    """„entity #k of n (largest by volume)” — a rank, never an id. Ranks cannot identify."""
    order = sorted(cell.merchants.items(), key=lambda kv: (-kv[1], kv[0]))
    rank = [m for m, _ in order].index(merchant) + 1
    return f"entity #{rank} of {len(order)} (ranked by volume)"


def residual_cell(cell: Cell, merchant: str) -> Cell:
    """The cell with ``merchant`` removed — the aggregate an inside attacker can reconstruct.

    WHAT  ``R \\ {merchant}``: merchants minus that one, transactions minus its volume, cards
          minus its cards.
    WHY   G4. The merchant is INSIDE every comparison cell we show them; given the released
          aggregate and its own volume, it can subtract itself out and hold the complement
          (compliance §2.7, §2.8).
    FAIL  ``KeyError`` if the merchant is not in the cell (removing a non-member would produce a
          residual that is larger and more compliant than the truth — a silent bypass).
          The card count comes from measured ``residual_n_cards`` when supplied; otherwise from
          the sound lower bound ``n_cards - volume`` — which can only OVER-suppress, never
          release something that should not be released. The mode is reported in the trace, so
          a reviewer can see which cells were gated on a bound rather than a measurement.
    """
    if merchant not in cell.merchants:
        raise KeyError(f"merchant is not in the cell: cannot form the residual ({merchant!r})")
    volume = cell.merchants[merchant]
    residual_merchants = {m: v for m, v in cell.merchants.items() if m != merchant}
    if cell.residual_n_cards is not None and merchant in cell.residual_n_cards:
        residual_cards = cell.residual_n_cards[merchant]
    else:
        residual_cards = max(0, cell.n_cards - min(volume, cell.n_cards))
    residual_merchant_cards: Optional[Dict[str, int]] = None
    if cell.merchant_cards is not None:
        # |cards(m')| <= |cards(R \ {merchant})| for m' != merchant, so clamping is sound and
        # keeps the residual's own invariants. In measured mode a violation would mean the
        # supplied evidence contradicts itself, so it is caught by Cell's validation instead.
        clamped = {m: min(c, residual_cards) for m, c in cell.merchant_cards.items() if m != merchant}
        # If the bound forces any clamped count below 1 the residual carries no usable card
        # evidence at all. Dropping only the small entries would evaluate the top-1 card share
        # over a SUBSET of merchants — which understates it. Withhold the whole map instead and
        # let the trace say the card leg was not evaluated (fail-closed, never fail-silent).
        residual_merchant_cards = clamped if clamped and min(clamped.values()) >= 1 else None
    return Cell(
        n_cards=residual_cards,
        merchants=residual_merchants,
        n_transactions=cell.n_transactions - volume,
        merchant_cards=residual_merchant_cards,
        residual_n_cards=None,          # one level of differencing only; no recursion
        label=None,                     # a residual has no area label and must not inherit one
    )


def _core_failures(n_cards: int, n_merchants: int, top1_volume: int, n_transactions: int,
                   top1_cards: Optional[int], n_cards_denominator: Optional[int],
                   rules: Rules) -> Tuple[list, list, Fraction, Optional[Fraction], bool]:
    """G1, G2 and G3 on plain numbers. THE only place the three thresholds are compared.

    Returns ``(failures, detail, volume_share, card_share, card_share_evaluated)``.

    WHY IT IS A SEPARATE FUNCTION
        The Cell path, the leave-one-out residual path and the pipeline's legacy adapter all have
        to reach the same verdict from the same numbers. Two copies of `>= 30` is how a codebase
        ends up enforcing one gate of three (AGENTS.md defect D3), so every caller goes through
        here. ``top1_cards=None`` means „per-merchant card counts are unknown”; the card leg of G3
        is then skipped and the fact is recorded in ``detail`` — never silently.
    """
    failures: list = []
    detail: list = []

    if n_cards < rules.min_cards:
        failures.append(R_LT_30_CARDS)
        detail.append(f"n_cards={n_cards} < {rules.min_cards}")

    if n_merchants < rules.min_merchants:
        failures.append(R_LT_3_MERCHANTS)
        detail.append(f"n_merchants={n_merchants} < {rules.min_merchants}")

    def _share_fails(top: int, denominator: int) -> bool:
        """A share whose denominator is non-positive cannot be SHOWN to be within the limit, so it
        fails. An empty group is already `no_data`, and a group whose cardinality is unknown must
        never be released on the strength of an undefined ratio."""
        if denominator <= 0:
            return True
        return Fraction(top, denominator) > rules.max_share

    volume_share = max_share({"top": top1_volume}, n_transactions)
    if "volume" in rules.share_metrics and _share_fails(top1_volume, n_transactions):
        failures.append(R_TOP1_GT_75)
        detail.append(
            "top-1 volume share "
            f"{volume_share.numerator}/{volume_share.denominator} = {format_share(volume_share, 6)}%"
            f" > {rules.max_share.numerator}/{rules.max_share.denominator}"
        )

    card_share: Optional[Fraction] = None
    card_share_evaluated = False
    if "cards" in rules.share_metrics:
        if top1_cards is None:
            # Loud, not silent: the conservative reading could not be applied to this cell.
            detail.append(
                "card-share metric requested but the cell carries no per-merchant card counts; "
                "G3 was evaluated on volume alone"
            )
        else:
            card_share_evaluated = True
            card_denominator = n_cards_denominator if n_cards_denominator is not None else 0
            card_share = max_share({"top": top1_cards}, card_denominator)
            if _share_fails(top1_cards, card_denominator):
                failures.append(R_TOP1_GT_75)
                detail.append(
                    "top-1 card share "
                    f"{card_share.numerator}/{card_share.denominator} = {format_share(card_share, 6)}%"
                    f" > {rules.max_share.numerator}/{rules.max_share.denominator}"
                    " (conservative leg: a cell fails if EITHER metric exceeds the limit)"
                )

    return failures, detail, volume_share, card_share, card_share_evaluated


def _cell_numbers(cell: Cell) -> Tuple[int, Optional[int], Optional[int]]:
    """``(top1_volume, top1_cards, card_denominator)`` from the cell's own partition."""
    top1_volume = max(cell.merchants.values()) if cell.merchants else 0
    if cell.merchant_cards is None:
        return top1_volume, None, None
    top1_cards = max(cell.merchant_cards.values()) if cell.merchant_cards else 0
    return top1_volume, top1_cards, cell.n_cards


def _evaluate(cell: Cell, rules: Rules) -> LevelTrace:
    """Run G1-G4 against ONE cell. Returns the trace entry; no decision is taken here."""
    top1_volume, top1_cards, card_denominator = _cell_numbers(cell)
    failures, detail, share_volume, share_cards, card_share_evaluated = _core_failures(
        cell.n_cards, cell.n_merchants, top1_volume, cell.n_transactions,
        top1_cards, card_denominator, rules,
    )

    differencing_evidence = "not_evaluated"
    if rules.require_differencing:
        differencing_evidence = (
            "measured"
            if cell.residual_n_cards is not None and set(cell.residual_n_cards) == set(cell.merchants)
            else "bound"
        )
        for merchant in sorted(cell.merchants):
            residual = residual_cell(cell, merchant)
            sub = _evaluate_residual(residual, rules)
            if sub:
                failures.append(R_G4_DIFFERENCING)
                detail.append(
                    "after removing " + _entity_rank_label(merchant, cell)
                    + f": {'+'.join(sub)} (differencing attack: the merchant subtracts its own "
                    "volume from the released aggregate)"
                )
                break

    ordered = _ordered(failures)
    return LevelTrace(
        level=L_CELL,
        n_cards=cell.n_cards,
        n_merchants=cell.n_merchants,
        n_transactions=cell.n_transactions,
        top1_share=share_volume,
        top1_card_share=share_cards,
        ok=not ordered,
        failures=ordered,
        detail=tuple(detail),
        differencing_evidence=differencing_evidence,
        card_share_evaluated=card_share_evaluated,
    )


def _evaluate_residual(residual: Cell, rules: Rules) -> Tuple[str, ...]:
    """G1-G3 on the leave-one-out residual. Returns the failing codes (empty ⇒ G4 passes)."""
    top1_volume, top1_cards, card_denominator = _cell_numbers(residual)
    failures, _detail, _v, _c, _evaluated = _core_failures(
        residual.n_cards, residual.n_merchants, top1_volume, residual.n_transactions,
        top1_cards, card_denominator, rules,
    )
    return _ordered(failures)


def _reason_for(failures: Sequence[str]) -> str:
    """One failing gate names itself; several are reported as ``multi`` with ``failures`` full."""
    if not failures:
        return R_OK
    if len(failures) == 1:
        return failures[0]
    return R_MULTI


def gate(
    cell: Cell,
    level: str = L_CELL,
    *,
    rules: Optional[Rules] = None,
    thin_base: Optional[int] = None,
) -> GateResult:
    """Decide whether ONE cell may be released, and why not if it may not.

    WHAT  ``gate(cell)`` → :class:`GateResult`. ``ok`` is True only when every gate passes.
    WHY   This is the frozen interface the pipeline and the app import. ``level`` labels the
          cell's position in the cascade (``cell`` | ``parent`` | ``city``); ``thin_base`` is
          the display floor (transaction count), which is NOT a privacy gate and gets its own
          reason code so the UI never says „too few cards” when the real cause was a thin window.
    FAIL  ``no_data`` (empty relation) → then ``thin_base`` → then G1, G2, G3, G4. Order is
          fixed so a suppression reason is deterministic. A cell that fails is ``locked`` and
          carries NO value; there is no code path that returns a value with a reason.
    """
    rules = rules or BASE_RULES
    if level not in CASCADE_ORDER:
        raise ValueError(f"level must be one of {CASCADE_ORDER}, got {level!r}")

    if cell.is_empty:
        return GateResult(
            ok=False, value_or_none=None, reason=R_NO_DATA, level=L_LOCKED,
            detail=("the relation is empty: an empty cell is never a pass",),
            levels_evaluated=(level,), rule_version=rules.rule_version, _seal=_SEAL,
        )

    if thin_base is not None and cell.n_transactions < thin_base:
        return GateResult(
            ok=False, value_or_none=None, reason=R_THIN_BASE, level=L_LOCKED,
            detail=(f"n_transactions={cell.n_transactions} < thin_base={thin_base}; "
                    "a thin window is a display floor, not a k-anonymity failure",),
            levels_evaluated=(level,), rule_version=rules.rule_version, _seal=_SEAL,
        )

    trace = _evaluate(cell, rules)
    trace = replace(trace, level=level)
    if trace.ok:
        return GateResult(
            ok=True,
            value_or_none=ReleasedValue(
                level=level,
                n_transactions=cell.n_transactions,
                n_cards=cell.n_cards,
                n_merchants=cell.n_merchants,
                top1_share=trace.top1_share,
            ),
            reason=R_OK,
            level=level,
            detail=trace.detail,
            trace=(trace,),
            levels_evaluated=(level,),
            rule_version=rules.rule_version,
            _seal=_SEAL,
        )
    return GateResult(
        ok=False,
        value_or_none=None,
        reason=_reason_for(trace.failures),
        level=L_LOCKED,
        failures=trace.failures,
        detail=trace.detail,
        trace=(trace,),
        levels_evaluated=(level,),
        rule_version=rules.rule_version,
        _seal=_SEAL,
    )


def cascade(
    cell_by_level: Mapping[str, Cell],
    *,
    rules: Optional[Rules] = None,
    thin_base: Optional[int] = None,
) -> GateResult:
    """Walk ``cell → parent → city`` and release the FIRST level that passes every gate.

    WHAT  ``cascade({"cell": c, "parent": p, "city": k})`` → one :class:`GateResult`. The value,
          when released, is the ancestor's — ``level`` says which, ``escalated`` says it is not
          the cell that was asked for.
    WHY   k-anonymity's standard remedy for a thin cell is aggregation upward: ``cards`` and
          ``merchants`` are monotone non-increasing under refinement, so a bigger area can
          qualify where a small one cannot. Escalation is NOT an exemption: the ancestor must
          independently satisfy every gate (compliance §2.4, §2.6).
    FAIL  Every level failing ⇒ ``reason="all_levels_failed"``, ``level="locked"``,
          ``failures`` = the union of what went wrong, so the UI can name the gates instead of
          showing a bare „hidden”. An unknown level key raises ``ValueError`` — silently
          dropping a candidate would silently drop an escalation path. Missing levels are listed
          in ``levels_missing`` so no view can claim a check that never ran.
    """
    rules = rules or BASE_RULES
    unknown = sorted(set(cell_by_level) - set(CASCADE_ORDER))
    if unknown:
        raise ValueError(
            f"unknown cascade levels {unknown}; the froze order is {CASCADE_ORDER}"
        )
    if L_CELL not in cell_by_level:
        raise ValueError("cascade requires at least the 'cell' level")

    trace: list = []
    evaluated: list = []
    missing = tuple(level for level in CASCADE_ORDER if level not in cell_by_level)
    for level in CASCADE_ORDER:
        cell = cell_by_level.get(level)
        if cell is None:
            continue
        result = gate(cell, level, rules=rules, thin_base=thin_base)
        evaluated.append(level)
        trace.extend(result.trace)
        if result.ok:
            return GateResult(
                ok=True,
                value_or_none=result.value_or_none,
                reason=R_OK,
                level=level,
                detail=result.detail,
                escalated=level != L_CELL,
                trace=tuple(trace),
                levels_evaluated=tuple(evaluated),
                levels_missing=missing,
                rule_version=rules.rule_version,
                _seal=_SEAL,
            )
        if result.reason in (R_NO_DATA, R_THIN_BASE):
            # Pre-gate reasons short-circuit the walk: an empty or thin relation says nothing
            # about the ancestors' anonymity, and pretending otherwise would be a silent
            # substitution of one reason for another.
            return GateResult(
                ok=False, value_or_none=None, reason=result.reason, level=L_LOCKED,
                detail=result.detail, trace=tuple(trace), levels_evaluated=tuple(evaluated),
                levels_missing=missing, rule_version=rules.rule_version, _seal=_SEAL,
            )

    union_failures = _ordered(code for entry in trace for code in entry.failures)
    return GateResult(
        ok=False,
        value_or_none=None,
        reason=R_ALL_LEVELS_FAILED,
        level=L_LOCKED,
        failures=union_failures,
        detail=tuple(
            f"{entry.level}: {'+'.join(entry.failures)}" for entry in trace if not entry.ok
        ),
        trace=tuple(trace),
        levels_evaluated=tuple(evaluated),
        levels_missing=missing,
        rule_version=rules.rule_version,
        _seal=_SEAL,
    )


# --------------------------------------------------------------------------------------------
# 7. The release guard — no orphan releases.
# --------------------------------------------------------------------------------------------

def assert_released(record: GateResult, *, rules: Optional[Rules] = None) -> GateResult:
    """Prove a record came from :func:`gate`/:func:`cascade` and is internally consistent.

    WHAT  Returns ``record`` unchanged if it is safe to hand to a renderer; raises otherwise.
    WHY   „Every aggregate that reaches the client must have been produced by gate(). There is no
          other path.” The gate is worthless if a renderer can build a number itself — the
          prototype shipped exactly that bug: the whole cube was aggregated in the browser and
          the gate was a *rendering* decision, not a *release* decision (harness spec §6.1).
    HOW THE APP CALLS IT (the single sanctioned path — see contracts/PRIVACY-COPY.md):

        result = cascade({"cell": cell, "parent": parent, "city": city}, rules=PRODUCT_RULES)
        assert_released(result, rules=PRODUCT_RULES)      # or: value = release(result, ...)
        paint(result.value_or_none)                       # None ⇒ render the suppression state

    FAIL  ``ReleaseGuardError`` (never a warning) with codes: ``ungated_path`` (the object was
          not produced by the gate — the module-private seal is missing), ``orphan_release``,
          ``leak``, ``no_trace``, ``stale_rules``.
    """
    if not isinstance(record, GateResult):
        raise ReleaseGuardError(
            "ungated_path",
            f"{type(record).__name__} is not a GateResult: it cannot have passed gate()",
        )
    if record._seal is not _SEAL:
        raise ReleaseGuardError(
            "ungated_path", "record was constructed by hand, not produced by gate()/cascade()"
        )
    if record.ok:
        if record.value_or_none is None:
            raise ReleaseGuardError("orphan_release", "released record without a value")
        if not record.trace:
            raise ReleaseGuardError("no_trace", "released record without a gate trace")
        if record.trace[-1].ok is not True:
            raise ReleaseGuardError(
                "orphan_release", "the trace does not end in a passing level"
            )
        if record.trace[-1].level != record.level:
            raise ReleaseGuardError(
                "orphan_release",
                f"released at {record.level!r} but the last trace entry is {record.trace[-1].level!r}",
            )
    else:
        if record.value_or_none is not None:
            raise ReleaseGuardError("leak", "a suppressed record carries a value")
    if record.reason not in (R_NO_DATA, R_THIN_BASE):
        # The two pre-gate reasons are decided BEFORE any level is walked, so an empty trace is
        # legitimate for them and for nothing else.
        if not record.trace:
            raise ReleaseGuardError("no_trace", f"reason={record.reason!r} without a gate trace")
        if len(record.trace) != len(record.levels_evaluated):
            raise ReleaseGuardError(
                "no_trace",
                f"{len(record.levels_evaluated)} level(s) evaluated but "
                f"{len(record.trace)} trace entr(ies)",
            )
    if rules is not None and record.rule_version != rules.rule_version:
        raise ReleaseGuardError(
            "stale_rules",
            f"record rule_version={record.rule_version!r} != active {rules.rule_version!r}",
        )
    return record


def release(record: GateResult, *, rules: Optional[Rules] = None) -> Optional[ReleasedValue]:
    """The ONLY function allowed to hand a value to a view or a transport.

    Returns ``None`` for a suppressed cell — views MUST handle ``None`` by rendering the
    suppression state (reason code + evidence), never by substituting a placeholder number
    (the „Dane przykładowe” anti-pattern, AGENTS.md rule 4).
    """
    assert_released(record, rules=rules)
    return record.value_or_none


# --------------------------------------------------------------------------------------------
# 8. Input plausibility (advisory, for real producers — the gate itself never guesses)
# --------------------------------------------------------------------------------------------

def plausibility_findings(cell: Cell) -> Tuple[str, ...]:
    """Physical-consistency findings a real producer must be able to detect. Empty ⇒ coherent.

    WHAT  Two checks that ``Cell`` deliberately does NOT enforce, because a cell that is merely
          *unlikely* must still be gateable:
            (1) ``cards(m) <= n_cards`` for every merchant — a merchant's cards are a subset of
                the cell's card union, so a larger per-merchant count is a query bug;
            (2) ``sum(merchant_cards.values()) >= n_cards`` — the union of the per-merchant card
                sets IS the cell's card set, so the per-merchant counts cannot sum to less.
    WHY   These are the signatures of a broken join (row multiplication in the aggregation SQL).
          A cell like that silently overstates a numerator or understates a denominator, which is
          precisely how a share gate is passed by accident. The report script asserts this is
          empty for every real cell before it publishes a number.
    FAIL  Returns strings; the caller decides. The gate never repairs an impossible input, and
          never treats a finding as a reason to release.
    """
    findings: list = []
    if cell.merchant_cards is not None:
        for merchant, cards in sorted(cell.merchant_cards.items()):
            if cards > cell.n_cards:
                findings.append(
                    f"an entity holds {cards} cards but the cell union has only {cell.n_cards}"
                )
        total_cards = sum(cell.merchant_cards.values())
        if len(cell.merchant_cards) == len(cell.merchants) and total_cards < cell.n_cards:
            findings.append(
                f"per-merchant card counts sum to {total_cards} < the cell union {cell.n_cards}: "
                "the union of the per-merchant card sets cannot be smaller than the union"
            )
    return tuple(findings)


def contract_fingerprint() -> Dict[str, Any]:
    """The frozen constants, for the TypeScript mirror test and for the report's provenance.

    WHY  Two implementations of one gate drift silently unless something asserts they agree.
          `tests/privacy/test_mirror.mjs` compares this object with its TypeScript twin.
    """
    return {
        "rule_version": RULE_VERSION,
        "min_cards": MIN_CARDS,
        "min_merchants": MIN_MERCHANTS,
        "max_share": f"{MAX_TOP1_SHARE.numerator}/{MAX_TOP1_SHARE.denominator}",
        "thin_base_transactions": THIN_BASE_TRANSACTIONS,
        "cascade_order": list(CASCADE_ORDER),
        "reason_codes": list(REASON_CODES),
    }


# ---------------------------------------------------------------------------------------------
# 9. Pipeline adapter — the same gate, reached through the loader the pipeline already calls.
#
#    `pipeline/_gates.py` was written as a stop-gap with its own copy of the three thresholds and a
#    TODO asking the privacy owner to expose `Rules` / `Aggregation` / `evaluate` / `gate_dict` so
#    the fallback could be deleted. This section is that surface. It is an ADAPTER, not a second
#    implementation: every verdict comes from `_core_failures`, so the numbers 30 / 3 / 75% appear
#    exactly once in the repository.
#
#    The adapter speaks the reference vocabulary of research/privacy-harness-spec.md
#    (`G1_CARDS`, `G2_ENTITIES`, `G3_SHARE`) because the pipeline's artifact schema and its tests
#    already do. The mapping is total and explicit in `LEGACY_REASON_CODES`.
# ---------------------------------------------------------------------------------------------

#: frozen code → the reference code the pipeline already prints. `g4_differencing` has no reference
#: equivalent: the reference mislabelled every residual failure as `G3_SHARE`, which is the wart
#: this contract fixes (see tests/privacy/fixtures.json `_edits_vs_reference`).
LEGACY_REASON_CODES: Dict[str, str] = {
    R_LT_30_CARDS: "G1_CARDS",
    R_LT_3_MERCHANTS: "G2_ENTITIES",
    R_TOP1_GT_75: "G3_SHARE",
    R_G4_DIFFERENCING: "G4_DIFFERENCING",
}


@dataclass(frozen=True)
class EntityStat:
    """Legacy entity shape: one merchant's contribution to a cell. ``entity`` is never published."""

    entity: str
    n_tran: int
    n_cards: int


@dataclass(frozen=True)
class Aggregation:
    """Legacy aggregation shape (research/privacy-harness-spec.md §2.1). **Adapter only.**

    FAIL  Constructing one whose declared ``n_entities`` disagrees with ``len(per_entity)``, whose
          per-entity volumes do not sum to ``n_tran``, or that lists the same entity twice, raises
          ``CellError``. The reference fixtures F-08/F-12/F-13 violate the first of those — which is
          precisely why this contract derives the entity count from the partition instead of
          trusting a declared number (harness spec invariant P-4).
    """

    level: str
    n_cards: int
    n_entities: int
    n_tran: int
    per_entity: Sequence["EntityStat"] = ()

    def __post_init__(self) -> None:
        if self.n_entities != len(self.per_entity):
            raise CellError(
                f"n_entities={self.n_entities} != len(per_entity)={len(self.per_entity)}: "
                "a truncated partition under-counts entities and can pass a group of one"
            )
        names = [e.entity for e in self.per_entity]
        if len(set(names)) != len(names):
            raise CellError("per_entity lists the same entity twice")
        if sum(e.n_tran for e in self.per_entity) != self.n_tran:
            raise CellError(
                f"per-entity volumes sum to {sum(e.n_tran for e in self.per_entity)} "
                f"!= n_tran={self.n_tran}"
            )

    def to_cell(self) -> Cell:
        """The frozen :class:`Cell` this legacy object describes."""
        return Cell(
            n_cards=self.n_cards,
            merchants={e.entity: e.n_tran for e in self.per_entity},
            n_transactions=self.n_tran,
            merchant_cards={e.entity: e.n_cards for e in self.per_entity} or None,
            residual_n_cards=None,
        )


def evaluate(
    aggregation: Any,
    rules: Optional[Rules] = None,
) -> Tuple[list, list, int, int]:
    """Reference-shaped ``evaluate(agg, rules)`` → ``(codes, details, top1_tran, top1_cards)``.

    Accepts a :class:`Cell` or a legacy :class:`Aggregation`. G4 is NOT evaluated here — the
    reference's ``evaluate`` had no differencing step; use :func:`gate` with ``PRODUCT_RULES`` for
    that. Codes are returned in the reference vocabulary, in canonical order and deduplicated.
    """
    rules = rules or BASE_RULES
    cell = aggregation if isinstance(aggregation, Cell) else aggregation.to_cell()
    top1_volume, top1_cards, card_denominator = _cell_numbers(cell)
    failures, detail, _volume_share, _card_share, _evaluated = _core_failures(
        cell.n_cards, cell.n_merchants, top1_volume, cell.n_transactions,
        top1_cards, card_denominator, rules,
    )
    codes: list = []
    for code in _ordered(failures):
        legacy = LEGACY_REASON_CODES[code]
        if legacy not in codes:
            codes.append(legacy)
    return codes, list(detail), top1_volume, top1_cards or 0


def gate_dict(
    n_cards: int,
    n_merchants: int,
    top1_volume: int,
    n_tran: int,
    top1_cards: int = 0,
    rules: Optional[Rules] = None,
) -> Dict[str, bool]:
    """The pipeline's per-postcode gate block: ``{g1_cards, g2_merchants, g3_share, all}``.

    This is the shape `contracts/aggregate.schema.json` requires under ``codeMeta.<code>.gates``.
    ``top1_cards=0`` means „per-merchant card counts were not measured for this cell”, which skips
    the card leg of G3 exactly as the stop-gap did. An empty relation yields ``all: false`` because
    G1 fails on zero cards — the individual flags still report their own predicate, which is what
    makes the block auditable; ``gate()``, by contrast, returns the single reason ``no_data``.
    """
    rules = rules or BASE_RULES
    failures, _detail, _volume_share, _card_share, _evaluated = _core_failures(
        n_cards, n_merchants, top1_volume, n_tran, top1_cards or None, n_cards, rules,
    )
    codes = set(failures)
    g1 = R_LT_30_CARDS not in codes
    g2 = R_LT_3_MERCHANTS not in codes
    g3 = R_TOP1_GT_75 not in codes
    return {"g1_cards": bool(g1), "g2_merchants": bool(g2), "g3_share": bool(g3),
            "all": bool(g1 and g2 and g3)}
