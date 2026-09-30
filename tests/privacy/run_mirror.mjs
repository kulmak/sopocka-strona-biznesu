/**
 * tests/privacy/run_mirror.mjs — behavioural parity check for the browser mirror.
 *
 * WHAT
 *     Runs `contracts/privacy.ts` against the SAME `tests/privacy/fixtures.json` the Python
 *     contract is tested against, field by field (ok, level, reason, escalated, failures,
 *     trace_failures, levels_missing, differencing evidence), and optionally compares the
 *     contract fingerprint with the one `contracts/privacy.py` just printed.
 *
 * WHY
 *     Two implementations of one gate drift silently. The prototype is the cautionary tale: the
 *     browser aggregated and the model suppressed, and neither checked the card column. Here a
 *     divergence is a build failure, not a bug report.
 *
 * HOW
 *     `node tests/privacy/run_mirror.mjs [python-fingerprint.json]`
 *     Exit 0 = mirror agrees. Exit 1 = divergence (printed with the failing fields).
 *     Node ≥ 23 executes the .ts file directly by stripping types; no build step, no deps.
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..", "..");
const P = await import(join(repo, "contracts", "privacy.ts"));

const fixtures = JSON.parse(readFileSync(join(here, "fixtures.json"), "utf8"));
const baseRules = fixtures.rules;

function rulesFor(caseSpec, differencing) {
  const merged = { ...baseRules, ...(caseSpec.rules_override ?? {}) };
  if (differencing !== undefined) merged.requireDifferencing = differencing;
  return P.rulesFromMapping(merged);
}

function cellFromSpec(spec) {
  return P.makeCell({
    nCards: spec.n_cards,
    merchants: { ...spec.merchants },
    nTransactions: spec.n_transactions,
    merchantCards: spec.merchant_cards ?? null,
    residualNCards: spec.residual_n_cards ?? null,
  });
}

function runCase(caseSpec, rules) {
  const levels = Object.entries(caseSpec.levels);
  const thin = caseSpec.thin_base ? baseRules.thinBaseTransactions : undefined;
  if (levels.length === 1) {
    const [level, spec] = levels[0];
    return P.gate(cellFromSpec(spec), level, rules, thin);
  }
  const cells = {};
  for (const [level, spec] of levels) cells[level] = cellFromSpec(spec);
  return P.cascade(cells, rules, thin);
}

function compare(caseSpec, got, expect) {
  const errs = [];
  if ("ok" in expect && got.ok !== expect.ok) errs.push(`ok ${got.ok} != ${expect.ok}`);
  if ("level" in expect && got.level !== expect.level) errs.push(`level ${got.level} != ${expect.level}`);
  if ("reason" in expect && got.reason !== expect.reason) errs.push(`reason ${got.reason} != ${expect.reason}`);
  if ("escalated" in expect && got.escalated !== expect.escalated) {
    errs.push(`escalated ${got.escalated} != ${expect.escalated}`);
  }
  if ("failures" in expect) {
    const a = [...got.failures].sort().join(",");
    const b = [...expect.failures].sort().join(",");
    if (a !== b) errs.push(`failures [${got.failures}] != [${expect.failures}]`);
  }
  if ("trace_failures" in expect) {
    const gotTrace = got.trace.map((t) => t.failures.join(",")).join("|");
    const expTrace = expect.trace_failures.map((f) => f.join(",")).join("|");
    if (gotTrace !== expTrace) errs.push(`trace_failures ${gotTrace} != ${expTrace}`);
  }
  if ("levels_missing" in expect) {
    const gotMissing = [...got.levelsMissing].sort().join(",");
    const expMissing = [...expect.levels_missing].sort().join(",");
    if (gotMissing !== expMissing) errs.push(`levels_missing ${gotMissing} != ${expMissing}`);
  }
  if ("detail_contains" in expect && !got.detail.some((d) => d.includes(expect.detail_contains))) {
    errs.push(`detail does not name ${expect.detail_contains}`);
  }
  if ("trace_differencing_evidence" in expect) {
    const mode = got.trace.length ? got.trace[got.trace.length - 1].differencingEvidence : null;
    if (mode !== expect.trace_differencing_evidence) {
      errs.push(`differencing_evidence ${mode} != ${expect.trace_differencing_evidence}`);
    }
  }
  return errs;
}

let checked = 0;
const failures = [];
for (const group of ["cases", "cascade_cases", "g4_cases"]) {
  for (const caseSpec of fixtures[group]) {
    checked += 1;
    const errs = compare(caseSpec, runCase(caseSpec, rulesFor(caseSpec)), caseSpec.expect);
    if (caseSpec.expect_without_thin_base) {
      const alt = P.gate(cellFromSpec(caseSpec.levels.cell), "cell", rulesFor(caseSpec), undefined);
      errs.push(...compare(caseSpec, alt, caseSpec.expect_without_thin_base).map((e) => `without_thin_base: ${e}`));
    }
    if (caseSpec.expect_without_differencing) {
      const alt = runCase(caseSpec, rulesFor(caseSpec, false));
      errs.push(
        ...compare(caseSpec, alt, caseSpec.expect_without_differencing).map((e) => `without_differencing: ${e}`),
      );
    }
    if (errs.length) failures.push({ id: caseSpec.id, errors: errs });
  }
}

// The guard rails must behave the same way too.
const guardChecks = [];
function expectThrow(name, fn, code) {
  try {
    fn();
    guardChecks.push(`${name}: expected a throw, got none`);
  } catch (err) {
    const got = err && err.code ? err.code : err && err.name;
    if (code && got !== code) guardChecks.push(`${name}: expected ${code}, got ${got}`);
  }
}
const releasedCell = P.makeCell({ nCards: 30, merchants: { E1: 10, E2: 10, E3: 10 }, nTransactions: 30 });
const released = P.gate(releasedCell, "cell", P.BASE_RULES);
guardChecks.push(
  ...(P.releaseValue(released, P.BASE_RULES) === released.valueOrNone ? [] : ["releaseValue did not return the value"]),
);
const suppressed = P.gate(P.makeCell({ nCards: 29, merchants: { E1: 10, E2: 10, E3: 10 }, nTransactions: 30 }), "cell", P.BASE_RULES);
if (P.releaseValue(suppressed, P.BASE_RULES) !== null) guardChecks.push("a suppressed cell released a value");
expectThrow("hand-built record", () => P.assertReleased({
  ok: true, valueOrNone: released.valueOrNone, reason: "ok", level: "cell", failures: [], detail: [],
  escalated: false, trace: [], levelsEvaluated: [], levelsMissing: [], ruleVersion: P.RULE_VERSION, seal: null,
}), "ungated_path");
expectThrow("stale rules", () => P.assertReleased(released, P.PRODUCT_RULES), "stale_rules");
expectThrow("impossible cell", () => P.makeCell({ nCards: 30, merchants: { E1: 10, E2: 10 }, nTransactions: 100 }), "CellError");
expectThrow("float threshold", () => P.rulesFromMapping({ ...baseRules, maxShare: 0.75 }), "RulesError");
expectThrow("residual below the bound", () =>
  P.makeCell({ nCards: 900, merchants: { E1: 700, E2: 250 }, nTransactions: 950, residualNCards: { E1: 100 } }), "CellError");

// Fingerprint parity with the Python contract, when the caller hands one over.
const fingerprintArg = process.argv[2];
if (fingerprintArg) {
  const py = JSON.parse(readFileSync(fingerprintArg, "utf8"));
  const ts = P.contractFingerprint();
  for (const key of Object.keys(py)) {
    const a = JSON.stringify(py[key]);
    const b = JSON.stringify(ts[key]);
    if (a !== b) guardChecks.push(`fingerprint.${key}: python ${a} != ts ${b}`);
  }
}

if (failures.length || guardChecks.length) {
  console.error("MIRROR DIVERGENCE — contracts/privacy.ts does not match contracts/privacy.py");
  for (const f of failures) console.error(`  ${f.id}: ${f.errors.join("; ")}`);
  for (const g of guardChecks) console.error(`  guard: ${g}`);
  process.exit(1);
}
console.log(
  `mirror ok: ${checked} fixture cases and ${7} guard checks agree with contracts/privacy.py` +
    (fingerprintArg ? ", fingerprint identical" : ", fingerprint not compared"),
);
