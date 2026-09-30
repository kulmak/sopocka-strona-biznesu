/**
 * contracts/privacy.ts — the browser's copy of the privacy gates.
 *
 * ================================ MIRROR NOTICE =================================
 * This file is a HAND-WRITTEN MIRROR of `contracts/privacy.py`, which is the single source
 * of truth. It is not generated, and it is not allowed to drift: the two implementations are
 * run against the SAME fixture file (`tests/privacy/fixtures.json`) and the SAME contract
 * fingerprint by `tests/privacy/run_mirror.mjs`, which `tests/privacy/test_gates.py` executes.
 * If they disagree, that test fails the build. Behaviour changes belong in `privacy.py` first,
 * then here, in the same commit — never the other way round.
 * =================================================================================
 *
 * WHAT
 *     The four gates (G1 ≥30 cards · G2 ≥3 merchants · G3 no merchant above 75% · G4 the
 *     residual after removing any one merchant still satisfies G1–G3) as pure functions.
 *
 * WHY
 *     The panel used to aggregate the whole cube in the browser and then *suppress at render
 *     time*: every value was already in the client, retrievable from DevTools, and the gate
 *     could not fire because the card column was never read. In this build the browser cannot
 *     even see a raw count: it receives gated aggregates and re-checks them here, so a value
 *     that reaches the DOM has passed `gate()` in one of the two implementations.
 *
 * ROUNDING IS A CORRECTNESS PROPERTY
 *     Every decision uses exact rationals over `BigInt` — never `number` division. JavaScript
 *     numbers are IEEE-754 doubles: 75.000000% must PASS and 75.000025% must FAIL, and those
 *     differ by one part in four million. `formatShare()` is the ONLY place a decimal string
 *     appears, and it is applied AFTER the gate.
 *
 * FAILURE MODE
 *     `CellError`, `RulesError` and `ReleaseGuardError` are thrown, never warned. A cell whose
 *     numbers cannot be true, a threshold that is not an exact rational, and a record that did
 *     not come from `gate()`/`cascade()` are all refused. Views must handle `null` (suppressed)
 *     by rendering the suppression state — never by substituting a placeholder number.
 *
 * SCOPE OF THE MIRROR
 *     The browser needs `gate`, `cascade`, the release guard and the helpers. The pipeline's
 *     legacy adapter (`Aggregation` / `EntityStats` / `evaluate` / `gate_dict`, section 9 of
 *     contracts/privacy.py) is Python-only: the browser never sees a per-code artifact block.
 *
 * NOTE ON SYNTAX
 *     Written in erasable TypeScript only (no `enum`, no `namespace`, no parameter
 *     properties) so Node ≥ 23 can execute it directly with type stripping, which is how the
 *     parity test runs it without a build step.
 */

// ---------------------------------------------------------------------------------------------
// Thresholds — mirror of contracts/privacy.py §1. The ONLY place these numbers appear.
// ---------------------------------------------------------------------------------------------

export const MIN_CARDS = 30; // „co najmniej 30 kart" — distinct cards, inclusive
export const MIN_MERCHANTS = 3; // „co najmniej 3 podmioty/graczy" — distinct merchants, inclusive
export const MAX_TOP1_SHARE = { n: 3n, d: 4n }; // „udział … nie może przekraczać 75%" — 75% PASSES
export const THIN_BASE_TRANSACTIONS = 12;
export const RULE_VERSION = "sopot-privacy-v1+datasprint-2026-09-30";

export const R_OK = "ok";
export const R_LT_30_CARDS = "lt_30_cards";
export const R_LT_3_MERCHANTS = "lt_3_merchants";
export const R_TOP1_GT_75 = "top1_gt_75";
export const R_MULTI = "multi";
export const R_ALL_LEVELS_FAILED = "all_levels_failed";
export const R_G4_DIFFERENCING = "g4_differencing";
export const R_THIN_BASE = "thin_base";
export const R_NO_DATA = "no_data";

export const REASON_CODES = [
  R_OK, R_LT_30_CARDS, R_LT_3_MERCHANTS, R_TOP1_GT_75, R_MULTI,
  R_ALL_LEVELS_FAILED, R_G4_DIFFERENCING, R_THIN_BASE, R_NO_DATA,
];

const FAILURE_ORDER = [R_LT_30_CARDS, R_LT_3_MERCHANTS, R_TOP1_GT_75, R_G4_DIFFERENCING];

export const CASCADE_ORDER = ["cell", "parent", "city"];
export const L_CELL = "cell";
export const L_PARENT = "parent";
export const L_CITY = "city";
export const L_LOCKED = "locked";

export class CellError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CellError";
  }
}

export class RulesError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RulesError";
  }
}

export class ReleaseGuardError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(`${code.toUpperCase()}: ${message}`);
    this.name = "ReleaseGuardError";
    this.code = code;
  }
}

// ---------------------------------------------------------------------------------------------
// Exact rationals over BigInt. No float ever decides anything.
// ---------------------------------------------------------------------------------------------

export type Frac = { readonly n: bigint; readonly d: bigint };

function abs(a: bigint): bigint {
  return a < 0n ? -a : a;
}

function gcd(a: bigint, b: bigint): bigint {
  let x = abs(a);
  let y = abs(b);
  while (y) {
    const t = x % y;
    x = y;
    y = t;
  }
  return x;
}

/** Build a normalised exact fraction. Denominator must be > 0. */
export function frac(n: bigint | number, d: bigint | number): Frac {
  let nn = BigInt(n);
  let dd = BigInt(d);
  if (dd === 0n) throw new RulesError("a fraction cannot have denominator 0");
  if (dd < 0n) {
    nn = -nn;
    dd = -dd;
  }
  const g = gcd(nn, dd) || 1n;
  return { n: nn / g, d: dd / g };
}

export function cmpFrac(a: Frac, b: Frac): number {
  const left = a.n * b.d;
  const right = b.n * a.d;
  return left < right ? -1 : left > right ? 1 : 0;
}

export function lteFrac(a: Frac, b: Frac): boolean {
  return cmpFrac(a, b) <= 0;
}

export function fracToString(f: Frac): string {
  return `${f.n}/${f.d}`;
}

/** Display-only: half-up percentage, computed on integers, applied AFTER the gate. */
export function formatShare(value: Frac, decimals = 1): string {
  if (decimals < 0) throw new Error("decimals must be >= 0");
  const scale = 10n ** BigInt(decimals);
  const scaled = (2n * value.n * 100n * scale + value.d) / (2n * value.d); // floor(x*100*scale + 1/2)
  const whole = scaled / scale;
  const rest = scaled % scale;
  if (decimals === 0) return String(whole);
  return `${whole}.${String(rest).padStart(decimals, "0")}`;
}

/**
 * Largest value over `denominator`, exact. Empty ⇒ 0 (no merchant can dominate an empty group;
 * an empty group is suppressed as `no_data` before G3 is consulted).
 */
export function maxShare(values: Record<string, number>, denominator?: number): Frac {
  const keys = Object.keys(values);
  if (keys.length === 0) return frac(0n, 1n);
  let top = 0;
  for (const k of keys) top = Math.max(top, values[k]);
  const denom = denominator === undefined ? keys.reduce((sum, k) => sum + values[k], 0) : denominator;
  if (denom <= 0) return frac(0n, 1n);
  return frac(top, denom);
}

/** Exact share of the largest merchant: max(volume) / sum(volume). Never a float. */
export function top1Share(merchants: Record<string, number>): Frac {
  return maxShare(merchants);
}

/**
 * Does a share with this numerator/denominator exceed the limit?
 *
 * A non-positive denominator FAILS: a ratio that is undefined cannot be SHOWN to be within the
 * limit, so it must not be released. Mirrors `_core_failures` in contracts/privacy.py exactly —
 * an empty group is `no_data` before this is reached, this is the second line of defence.
 */
export function shareFails(top: number, denominator: number, rules: Rules): boolean {
  if (denominator <= 0) return true;
  return cmpFrac(frac(top, denominator), rules.maxShare) > 0;
}

// ---------------------------------------------------------------------------------------------
// Rules
// ---------------------------------------------------------------------------------------------

export type Rules = {
  minCards: number;
  minMerchants: number;
  maxShare: Frac;
  shareMetrics: string[];
  requireDifferencing: boolean;
  thinBaseTransactions: number;
  ruleVersion: string;
};

export function rulesFromMapping(mapping: Record<string, unknown> = {}): Rules {
  const shareRaw = mapping.maxShare;
  let share: Frac;
  if (shareRaw === undefined) {
    share = MAX_TOP1_SHARE;
  } else if (typeof shareRaw === "string") {
    const parts = shareRaw.split("/");
    if (parts.length !== 2) throw new RulesError(`maxShare must be 'n/d', got ${shareRaw}`);
    share = frac(BigInt(parts[0].trim()), BigInt(parts[1].trim()));
  } else if (Array.isArray(shareRaw) && shareRaw.length === 2) {
    share = frac(BigInt(shareRaw[0] as number), BigInt(shareRaw[1] as number));
  } else {
    throw new RulesError("maxShare must be an exact 'n/d' string or [n, d] — never a float");
  }
  const rules: Rules = {
    minCards: Number(mapping.minCards ?? MIN_CARDS),
    minMerchants: Number(mapping.minMerchants ?? MIN_MERCHANTS),
    maxShare: share,
    shareMetrics: (mapping.shareMetrics as string[] | undefined) ?? ["volume", "cards"],
    requireDifferencing: Boolean(mapping.requireDifferencing ?? false),
    thinBaseTransactions: Number(mapping.thinBaseTransactions ?? THIN_BASE_TRANSACTIONS),
    ruleVersion: String(mapping.ruleVersion ?? RULE_VERSION),
  };
  validateRules(rules);
  return rules;
}

export function validateRules(rules: Rules): void {
  if (!Number.isInteger(rules.minCards) || rules.minCards < 1) {
    throw new RulesError(`minCards must be a positive int, got ${rules.minCards}`);
  }
  if (!Number.isInteger(rules.minMerchants) || rules.minMerchants < 1) {
    throw new RulesError(`minMerchants must be a positive int, got ${rules.minMerchants}`);
  }
  if (typeof (rules.maxShare as unknown) === "number") {
    throw new RulesError("maxShare must be an exact fraction, never a float");
  }
  if (cmpFrac(rules.maxShare, frac(0n, 1n)) <= 0 || cmpFrac(rules.maxShare, frac(1n, 1n)) > 0) {
    throw new RulesError("maxShare must be in (0, 1]");
  }
  for (const metric of rules.shareMetrics) {
    if (metric !== "volume" && metric !== "cards") throw new RulesError(`unknown share metric ${metric}`);
  }
}

export const BASE_RULES: Rules = {
  minCards: MIN_CARDS, minMerchants: MIN_MERCHANTS, maxShare: MAX_TOP1_SHARE,
  shareMetrics: ["volume", "cards"], requireDifferencing: false,
  thinBaseTransactions: THIN_BASE_TRANSACTIONS, ruleVersion: RULE_VERSION,
};

export const PRODUCT_RULES: Rules = { ...BASE_RULES, requireDifferencing: true, ruleVersion: `${RULE_VERSION}+g4` };

// ---------------------------------------------------------------------------------------------
// Cell
// ---------------------------------------------------------------------------------------------

export type CellSpec = {
  nCards: number;
  merchants: Record<string, number>;
  nTransactions: number;
  merchantCards?: Record<string, number> | null;
  residualNCards?: Record<string, number> | null;
  label?: string | null;
};

export type Cell = CellSpec;

export function makeCell(spec: CellSpec): Cell {
  const cell: Cell = {
    ...spec,
    merchantCards: spec.merchantCards ?? null,
    residualNCards: spec.residualNCards ?? null,
    label: spec.label ?? null,
  };
  validateCell(cell);
  return cell;
}

export function validateCell(cell: Cell): void {
  if (!Number.isInteger(cell.nCards) || cell.nCards < 0) throw new CellError("nCards must be a non-negative int");
  if (!Number.isInteger(cell.nTransactions) || cell.nTransactions < 0) {
    throw new CellError("nTransactions must be a non-negative int");
  }
  if (cell.nCards > cell.nTransactions) {
    throw new CellError(
      `nCards=${cell.nCards} > nTransactions=${cell.nTransactions}: every card needs at least one transaction`,
    );
  }
  let total = 0;
  for (const [merchant, volume] of Object.entries(cell.merchants)) {
    if (!Number.isInteger(volume)) throw new CellError(`volume for entity ${merchant} must be an int`);
    if (volume <= 0) {
      throw new CellError(
        "every entity in a cell must have at least one transaction; a zero-volume entry is a phantom entity inflating the G2 count",
      );
    }
    total += volume;
  }
  if (total !== cell.nTransactions) {
    throw new CellError(
      `sum(merchants.values())=${total} != nTransactions=${cell.nTransactions}: the cell's partition does not add up to the cell`,
    );
  }
  if (cell.merchantCards) {
    for (const [merchant, cards] of Object.entries(cell.merchantCards)) {
      if (!(merchant in cell.merchants)) throw new CellError("merchantCards names entities that are not in the cell");
      if (!Number.isInteger(cards) || cards < 1) throw new CellError("merchantCards entries must be positive ints");
      if (cards > cell.merchants[merchant]) {
        throw new CellError(
          `entity with ${cell.merchants[merchant]} transactions cannot hold ${cards} distinct cards`,
        );
      }
    }
  }
  if (cell.residualNCards) {
    for (const [merchant, cards] of Object.entries(cell.residualNCards)) {
      if (!(merchant in cell.merchants)) throw new CellError("residualNCards names entities that are not in the cell");
      const lower = cell.nCards - Math.min(cell.merchants[merchant], cell.nCards);
      if (!Number.isInteger(cards) || cards < lower || cards > cell.nCards) {
        throw new CellError(
          `residualNCards[${merchant}]=${cards} is outside [${lower}, ${cell.nCards}] — impossible evidence`,
        );
      }
    }
  }
}

export function nMerchants(cell: Cell): number {
  return Object.keys(cell.merchants).length;
}

export function isDifferencingMeasured(cell: Cell): boolean {
  if (!cell.residualNCards) return false;
  const keys = Object.keys(cell.residualNCards).sort();
  const merchants = Object.keys(cell.merchants).sort();
  return keys.length === merchants.length && keys.every((k, i) => k === merchants[i]);
}

/** R \ {merchant} — the aggregate an inside attacker can reconstruct. */
export function residualCell(cell: Cell, merchant: string): Cell {
  if (!(merchant in cell.merchants)) {
    throw new Error(`merchant is not in the cell: cannot form the residual (${merchant})`);
  }
  const volume = cell.merchants[merchant];
  const merchants: Record<string, number> = {};
  for (const [m, v] of Object.entries(cell.merchants)) if (m !== merchant) merchants[m] = v;
  const measured = cell.residualNCards && merchant in cell.residualNCards;
  const residualCards = measured
    ? (cell.residualNCards as Record<string, number>)[merchant]
    : Math.max(0, cell.nCards - Math.min(volume, cell.nCards));
  let merchantCards: Record<string, number> | null = null;
  if (cell.merchantCards) {
    const clamped: Record<string, number> = {};
    let usable = true;
    for (const [m, c] of Object.entries(cell.merchantCards)) {
      if (m === merchant) continue;
      const value = Math.min(c, residualCards);
      if (value < 1) usable = false;
      clamped[m] = value;
    }
    merchantCards = usable && Object.keys(clamped).length > 0 ? clamped : null;
  }
  return makeCell({
    nCards: residualCards,
    merchants,
    nTransactions: cell.nTransactions - volume,
    merchantCards,
    residualNCards: null, // one level of differencing only; no recursion
    label: null,
  });
}

// ---------------------------------------------------------------------------------------------
// Results
// ---------------------------------------------------------------------------------------------

export type LevelTrace = {
  level: string;
  nCards: number;
  nMerchants: number;
  nTransactions: number;
  top1Share: Frac;
  top1CardShare: Frac | null;
  ok: boolean;
  failures: string[];
  detail: string[];
  differencingEvidence: string;
  cardShareEvaluated: boolean;
};

export type ReleasedValue = {
  level: string;
  nTransactions: number;
  nCards: number;
  nMerchants: number;
  top1Share: Frac;
};

export type GateResult = {
  ok: boolean;
  valueOrNone: ReleasedValue | null;
  reason: string;
  level: string;
  failures: string[];
  detail: string[];
  escalated: boolean;
  trace: LevelTrace[];
  levelsEvaluated: string[];
  levelsMissing: string[];
  ruleVersion: string;
  seal: symbol | null;
};

/**
 * Module-private seal: only gate()/cascade() produce a sealed record.
 *
 * Honest about its strength: in a browser, module internals are reachable by anyone who
 * inspects the bundle, so this is not a cryptographic boundary. It exists to make the
 * ACCIDENTAL new code path — „just put the number in the payload” — fail loudly instead of
 * shipping, which is exactly how the prototype leaked (`sopot-data.js` returned the whole
 * ungated cube and the gate was a rendering decision). `Object spread` copies the symbol, so a
 * copy of a genuine record still passes; a payload assembled from scratch does not.
 */
const SEAL = Symbol("sopocka-privacy-seal");

function result(partial: Partial<GateResult> & { ok: boolean; reason: string; level: string }): GateResult {
  const out: GateResult = {
    valueOrNone: null, failures: [], detail: [], escalated: false, trace: [],
    levelsEvaluated: [], levelsMissing: [], ruleVersion: RULE_VERSION, seal: SEAL,
    ...partial,
  } as GateResult;
  checkResultShape(out);
  return out;
}

function checkResultShape(record: GateResult): void {
  if (record.ok) {
    if (record.valueOrNone === null) throw new ReleaseGuardError("orphan_release", "ok=true with no value");
    if (record.reason !== R_OK) throw new ReleaseGuardError("released_with_reason", `ok=true but reason=${record.reason}`);
    if (record.level === L_LOCKED || !CASCADE_ORDER.includes(record.level)) {
      throw new ReleaseGuardError("orphan_release", `ok=true at level=${record.level}`);
    }
    if (record.failures.length) throw new ReleaseGuardError("orphan_release", "ok=true with failing gates recorded");
  } else {
    if (record.valueOrNone !== null) throw new ReleaseGuardError("leak", "a suppressed record carries a value");
    if (record.level !== L_LOCKED) throw new ReleaseGuardError("orphan_release", `ok=false must be level='locked', got ${record.level}`);
    if (record.reason === R_OK || !REASON_CODES.includes(record.reason)) {
      throw new ReleaseGuardError("orphan_release", `unknown suppression reason ${record.reason}`);
    }
  }
}

export function resultToMapping(record: GateResult): Record<string, unknown> {
  return {
    ok: record.ok,
    value: record.valueOrNone === null ? null : releasedValueToMapping(record.valueOrNone),
    reason: record.reason,
    level: record.level,
    failures: record.failures.slice(),
    detail: record.detail.slice(),
    escalated: record.escalated,
    levels_evaluated: record.levelsEvaluated.slice(),
    levels_missing: record.levelsMissing.slice(),
    rule_version: record.ruleVersion,
    trace: record.trace.map(traceToMapping),
  };
}

export function releasedValueToMapping(value: ReleasedValue): Record<string, unknown> {
  return {
    level: value.level,
    n_transactions: value.nTransactions,
    n_cards: value.nCards,
    n_merchants: value.nMerchants,
    top1_share: fracToString(value.top1Share),
    top1_share_pct: formatShare(value.top1Share, 1),
  };
}

export function traceToMapping(trace: LevelTrace): Record<string, unknown> {
  return {
    level: trace.level,
    n_cards: trace.nCards,
    n_merchants: trace.nMerchants,
    n_transactions: trace.nTransactions,
    top1_share: fracToString(trace.top1Share),
    top1_card_share: trace.top1CardShare === null ? null : fracToString(trace.top1CardShare),
    ok: trace.ok,
    failures: trace.failures.slice(),
    detail: trace.detail.slice(),
    differencing_evidence: trace.differencingEvidence,
    card_share_evaluated: trace.cardShareEvaluated,
  };
}

// ---------------------------------------------------------------------------------------------
// The gate
// ---------------------------------------------------------------------------------------------

function ordered(codes: string[]): string[] {
  const seen = new Set(codes);
  return FAILURE_ORDER.filter((code) => seen.has(code));
}

function rankLabel(merchant: string, cell: Cell): string {
  const sorted = Object.entries(cell.merchants).sort((a, b) => (b[1] - a[1]) || (a[0] < b[0] ? -1 : 1));
  const rank = sorted.findIndex(([m]) => m === merchant) + 1;
  return `entity #${rank} of ${sorted.length} (ranked by volume)`;
}

function topVolume(cell: Cell): number {
  let top = 0;
  for (const v of Object.values(cell.merchants)) top = Math.max(top, v);
  return top;
}

function topCardCount(cell: Cell): number {
  if (!cell.merchantCards) return 0;
  let top = 0;
  for (const c of Object.values(cell.merchantCards)) top = Math.max(top, c);
  return top;
}

function evaluateResidual(residual: Cell, rules: Rules): string[] {
  const failures: string[] = [];
  if (residual.nCards < rules.minCards) failures.push(R_LT_30_CARDS);
  if (nMerchants(residual) < rules.minMerchants) failures.push(R_LT_3_MERCHANTS);
  if (rules.shareMetrics.includes("volume") && shareFails(topVolume(residual), residual.nTransactions, rules)) {
    failures.push(R_TOP1_GT_75);
  }
  if (rules.shareMetrics.includes("cards") && residual.merchantCards) {
    if (shareFails(topCardCount(residual), residual.nCards, rules)) {
      failures.push(R_TOP1_GT_75);
    }
  }
  return ordered(failures);
}

function evaluate(cell: Cell, rules: Rules): LevelTrace {
  const failures: string[] = [];
  const detail: string[] = [];

  if (cell.nCards < rules.minCards) {
    failures.push(R_LT_30_CARDS);
    detail.push(`n_cards=${cell.nCards} < ${rules.minCards}`);
  }
  if (nMerchants(cell) < rules.minMerchants) {
    failures.push(R_LT_3_MERCHANTS);
    detail.push(`n_merchants=${nMerchants(cell)} < ${rules.minMerchants}`);
  }

  const shareVolume = top1Share(cell.merchants);
  if (rules.shareMetrics.includes("volume") && shareFails(topVolume(cell), cell.nTransactions, rules)) {
    failures.push(R_TOP1_GT_75);
    detail.push(
      `top-1 volume share ${fracToString(shareVolume)} = ${formatShare(shareVolume, 6)}% > ${fracToString(rules.maxShare)}`,
    );
  }

  let cardShareEvaluated = false;
  let shareCards: Frac | null = null;
  if (rules.shareMetrics.includes("cards")) {
    if (!cell.merchantCards) {
      detail.push(
        "card-share metric requested but the cell carries no per-merchant card counts; G3 was evaluated on volume alone",
      );
    } else {
      cardShareEvaluated = true;
      shareCards = maxShare(cell.merchantCards, cell.nCards);
      if (shareFails(topCardCount(cell), cell.nCards, rules)) {
        failures.push(R_TOP1_GT_75);
        detail.push(
          `top-1 card share ${fracToString(shareCards)} = ${formatShare(shareCards, 6)}% > ${fracToString(rules.maxShare)} (conservative leg: a cell fails if EITHER metric exceeds the limit)`,
        );
      }
    }
  }

  let differencingEvidence = "not_evaluated";
  if (rules.requireDifferencing) {
    differencingEvidence = isDifferencingMeasured(cell) ? "measured" : "bound";
    for (const merchant of Object.keys(cell.merchants).sort()) {
      const sub = evaluateResidual(residualCell(cell, merchant), rules);
      if (sub.length) {
        failures.push(R_G4_DIFFERENCING);
        detail.push(
          `after removing ${rankLabel(merchant, cell)}: ${sub.join("+")} (differencing attack: the merchant subtracts its own volume from the released aggregate)`,
        );
        break;
      }
    }
  }

  const finalFailures = ordered(failures);
  return {
    level: L_CELL,
    nCards: cell.nCards,
    nMerchants: nMerchants(cell),
    nTransactions: cell.nTransactions,
    top1Share: shareVolume,
    top1CardShare: shareCards,
    ok: finalFailures.length === 0,
    failures: finalFailures,
    detail,
    differencingEvidence,
    cardShareEvaluated,
  };
}

function reasonFor(failures: string[]): string {
  if (failures.length === 0) return R_OK;
  return failures.length === 1 ? failures[0] : R_MULTI;
}

/** Decide whether ONE cell may be released, and why not if it may not. */
export function gate(cell: Cell, level = L_CELL, rules: Rules = BASE_RULES, thinBase?: number): GateResult {
  if (!CASCADE_ORDER.includes(level)) throw new Error(`level must be one of ${CASCADE_ORDER.join(",")}, got ${level}`);

  if (cell.nTransactions === 0) {
    return result({
      ok: false, valueOrNone: null, reason: R_NO_DATA, level: L_LOCKED,
      detail: ["the relation is empty: an empty cell is never a pass"],
      levelsEvaluated: [level], ruleVersion: rules.ruleVersion,
    });
  }
  if (thinBase !== undefined && cell.nTransactions < thinBase) {
    return result({
      ok: false, valueOrNone: null, reason: R_THIN_BASE, level: L_LOCKED,
      detail: [`n_transactions=${cell.nTransactions} < thin_base=${thinBase}; a thin window is a display floor, not a k-anonymity failure`],
      levelsEvaluated: [level], ruleVersion: rules.ruleVersion,
    });
  }

  const trace = { ...evaluate(cell, rules), level };
  if (trace.ok) {
    return result({
      ok: true,
      valueOrNone: {
        level, nTransactions: cell.nTransactions, nCards: cell.nCards,
        nMerchants: nMerchants(cell), top1Share: trace.top1Share,
      },
      reason: R_OK, level, detail: trace.detail, trace: [trace],
      levelsEvaluated: [level], ruleVersion: rules.ruleVersion,
    });
  }
  return result({
    ok: false, valueOrNone: null, reason: reasonFor(trace.failures), level: L_LOCKED,
    failures: trace.failures, detail: trace.detail, trace: [trace],
    levelsEvaluated: [level], ruleVersion: rules.ruleVersion,
  });
}

/** Walk cell → parent → city; release the FIRST level that passes every gate. */
export function cascade(
  cellByLevel: Record<string, Cell>,
  rules: Rules = BASE_RULES,
  thinBase?: number,
): GateResult {
  const unknown = Object.keys(cellByLevel).filter((k) => !CASCADE_ORDER.includes(k)).sort();
  if (unknown.length) throw new Error(`unknown cascade levels ${unknown.join(",")}; the frozen order is ${CASCADE_ORDER.join(",")}`);
  if (!(L_CELL in cellByLevel)) throw new Error("cascade requires at least the 'cell' level");

  const trace: LevelTrace[] = [];
  const evaluated: string[] = [];
  const missing = CASCADE_ORDER.filter((level) => !(level in cellByLevel));

  for (const level of CASCADE_ORDER) {
    const cell = cellByLevel[level];
    if (!cell) continue;
    const one = gate(cell, level, rules, thinBase);
    evaluated.push(level);
    trace.push(...one.trace);
    if (one.ok) {
      return result({
        ok: true, valueOrNone: one.valueOrNone, reason: R_OK, level, detail: one.detail,
        escalated: level !== L_CELL, trace, levelsEvaluated: evaluated, levelsMissing: missing,
        ruleVersion: rules.ruleVersion,
      });
    }
    if (one.reason === R_NO_DATA || one.reason === R_THIN_BASE) {
      return result({
        ok: false, valueOrNone: null, reason: one.reason, level: L_LOCKED, detail: one.detail,
        trace, levelsEvaluated: evaluated, levelsMissing: missing, ruleVersion: rules.ruleVersion,
      });
    }
  }

  const unionFailures = ordered(trace.flatMap((t) => t.failures));
  return result({
    ok: false, valueOrNone: null, reason: R_ALL_LEVELS_FAILED, level: L_LOCKED,
    failures: unionFailures,
    detail: trace.filter((t) => !t.ok).map((t) => `${t.level}: ${t.failures.join("+")}`),
    trace, levelsEvaluated: evaluated, levelsMissing: missing, ruleVersion: rules.ruleVersion,
  });
}

// ---------------------------------------------------------------------------------------------
// The release guard
// ---------------------------------------------------------------------------------------------

/**
 * HOW THE APP CALLS IT — the single sanctioned path:
 *
 *     const cells = { cell, parent, city };                 // gated aggregates from the pipeline
 *     const record = cascade(cells, PRODUCT_RULES);
 *     assertReleased(record, PRODUCT_RULES);                // throws on an orphan release
 *     paint(record.valueOrNone);                            // null ⇒ render the suppression state
 *
 * Any number reaching a template or a transport must have come through here. A placeholder
 * value on a suppressed cell is a defect, not a fallback.
 */
export function assertReleased(record: GateResult, rules?: Rules): GateResult {
  if (!record || typeof record !== "object" || !("ok" in record)) {
    throw new ReleaseGuardError("ungated_path", "not a GateResult: it cannot have passed gate()");
  }
  if (record.seal !== SEAL) {
    throw new ReleaseGuardError("ungated_path", "record was constructed by hand, not produced by gate()/cascade()");
  }
  if (record.ok) {
    if (record.valueOrNone === null) throw new ReleaseGuardError("orphan_release", "released record without a value");
    if (!record.trace.length) throw new ReleaseGuardError("no_trace", "released record without a gate trace");
    if (record.trace[record.trace.length - 1].ok !== true) {
      throw new ReleaseGuardError("orphan_release", "the trace does not end in a passing level");
    }
    if (record.trace[record.trace.length - 1].level !== record.level) {
      throw new ReleaseGuardError("orphan_release", "released level does not match the last passing trace entry");
    }
  } else if (record.valueOrNone !== null) {
    throw new ReleaseGuardError("leak", "a suppressed record carries a value");
  }
  if (record.reason !== R_NO_DATA && record.reason !== R_THIN_BASE) {
    if (!record.trace.length) throw new ReleaseGuardError("no_trace", `reason=${record.reason} without a gate trace`);
    if (record.trace.length !== record.levelsEvaluated.length) {
      throw new ReleaseGuardError("no_trace", "trace length does not match the levels evaluated");
    }
  }
  if (rules && record.ruleVersion !== rules.ruleVersion) {
    throw new ReleaseGuardError("stale_rules", `record ruleVersion=${record.ruleVersion} != active ${rules.ruleVersion}`);
  }
  return record;
}

/** The ONLY function allowed to hand a value to a view or a transport. */
export function releaseValue(record: GateResult, rules?: Rules): ReleasedValue | null {
  assertReleased(record, rules);
  return record.valueOrNone;
}

/** Physical-consistency findings a real producer must be able to detect. Empty ⇒ coherent. */
export function plausibilityFindings(cell: Cell): string[] {
  const findings: string[] = [];
  if (cell.merchantCards) {
    for (const cards of Object.values(cell.merchantCards)) {
      if (cards > cell.nCards) {
        findings.push(`an entity holds ${cards} cards but the cell union has only ${cell.nCards}`);
      }
    }
    const total = Object.values(cell.merchantCards).reduce((a, b) => a + b, 0);
    if (Object.keys(cell.merchantCards).length === Object.keys(cell.merchants).length && total < cell.nCards) {
      findings.push(
        `per-merchant card counts sum to ${total} < the cell union ${cell.nCards}: the union of the per-merchant card sets cannot be smaller than the union`,
      );
    }
  }
  return findings;
}

/** The frozen constants, compared with the Python twin by tests/privacy/run_mirror.mjs. */
export function contractFingerprint(): Record<string, unknown> {
  return {
    rule_version: RULE_VERSION,
    min_cards: MIN_CARDS,
    min_merchants: MIN_MERCHANTS,
    max_share: fracToString(MAX_TOP1_SHARE),
    thin_base_transactions: THIN_BASE_TRANSACTIONS,
    cascade_order: CASCADE_ORDER.slice(),
    reason_codes: REASON_CODES.slice(),
  };
}
