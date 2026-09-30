# PRIVACY — the three rules, the gate, and what it does not do

Every published figure is an aggregate that passed four gates, and a group that fails them is **never shown
with a number**: the panel escalates to a larger area that passes, or renders a named suppression reason. The
rules come verbatim from challenge §3 („Oczekiwany rezultat”); the gate lives in one module
(`contracts/privacy.py`, mirrored by `contracts/privacy.ts`). **This is k-anonymity with a suppression gate, not differential privacy** — §10 states the difference.

## 1. Reproduce

```sh
python3 scripts/privacy_report.py --src /Users/kulma/Downloads --out artifacts/privacy-report.json

# 62 cells · G1 54 · G2 25 · all three 18 (volume) / 17 (volume AND cards) · all four 11
make check                       # the full suite; the privacy leg is #privacy_suite_passed
```

## 2. The rules, verbatim

Challenge §7's §3 block, quoted in `contracts/PRIVACY-COPY.md` and in the gate's module docstring: 
> „analizy i prezentacje wyników powinny być prowadzone wyłącznie na grupach obejmujących co najmniej
> 30 kart; każda grupa porównawcza powinna obejmować co najmniej 3 podmioty/graczy, przy czym udział
> żadnego z nich nie może przekraczać 75% analizowanej grupy.”
>
> „Rozwiązanie nie powinno umożliwiać identyfikacji pojedynczych użytkowników, kart, transakcji ani
> podmiotów.”

> Analyses may be carried out **only on groups covering at least 30 cards**; each comparison group must cover
> **at least 3 entities/players**, and **no single one may exceed 75%** of the group. The solution must not
> permit identification of individual users, cards, transactions or entities.

**30 means 30 distinct cards** (`pymt_crd_acct_num_raw`) — never cardholders, never transactions. `≥` and `≤`
are inclusive: 30 cards pass, 29 fail; 75.000000% passes and 75.000025% fails. Shares are therefore exact `fractions.Fraction`, formatted to a decimal only *after* the decision.

## 3. The predicates

For a cell `R`, with `cards`, `entities`, `vol`, and `top1` = the largest entity's transactions:

```
G1  cards(R) >= 30                     G3  for m in {volume, cards}: 100*top1_m <= 75*total_m G2  entities(R) >= 3                   G4  for every e: G1,G2,G3 hold for R \ {e}
```

`G3` is checked on **both** metrics and a cell fails if *either* exceeds the limit — the conservative reading
of a rule that says „udział” without naming the metric, whose cost §7 measures. `G4` is **voluntary**: the challenge does not ask for it, and our copy labels it a strengthening.

## 4. How we enforce them

| Rule | Enforced in | Test | Failure |
|---|---|---|---|
| G1 ≥ 30 cards | `privacy.py::_core_failures` | `test_boundary_thresholds` (29 fails, 30 passes) | suppress `lt_30_cards` |
| G2 ≥ 3 entities | same function | same test (2 fails, 3 passes) | suppress `lt_3_merchants` |
| G3 ≤ 75% | same function, exact `Fraction` | `test_display_rounding_never_moves_a_cell` | suppress `top1_gt_75` |
| G4 differencing | `residual_cell` → `_evaluate_residual` | `test_g4_leave_one_out_differencing` | suppress `g4_differencing` |
| several at once | `_reason_for` | `test_multi_failure_reports_every_gate` | suppress `multi` |
| the release path | `assert_released` | `test_release_guard_refuses_orphan_values` | **raise**, never warn |

`gate()` returns `no_data` for an empty relation and `thin_base` below **12** transactions (`#thin_base_transactions`) — a **readability** floor, not a privacy gate, so the UI never says „too few
cards” when the cause was a thin window. A suppressed record cannot carry a value and a released record cannot carry a reason: the types make both unrepresentable.

## 5. The cascade

```
  cell ──pass?──► release at "cell"     reason codes (9, no others): ok · lt_30_cards · top1_gt_75
    │ fail                               · lt_3_merchants · multi · g4_differencing · thin_base ▼                                    · no_data · all_levels_failed
  parent ─pass?─► release at "parent"    escalated=true; the label names the ancestor │ fail ▼
  city ──pass?──► release at "city"      „Dane dla obszaru {kod}, nie dla Twojego lokalu.” │ fail ▼ locked ─► no number: „Analiza zablokowana · żadna grupa nie spełnia progów: {reason}”
```

`cascade_order=(cell,parent,city)`; `locked` is terminal (`#privacy_cascade_order`,
`#privacy_reason_codes`). Escalation is **not** an exemption: the ancestor must independently satisfy every
gate. An unknown level key **raises** rather than being skipped, and missing levels are listed in `levels_missing` — so no view can claim a check it never ran.

## 6. G4 — the differencing test, and the attack it prevents

**The attack.** The merchant reading the panel is *inside* every comparison cell we show her. Given a released
area total and her own till she subtracts herself out and holds the complement. A cell with 3 entities and a
74% top-1 share passes the letter of the rule and still leaks: the dominant merchant removes its own known
volume and recovers the union of the other two as a 26% residual. With three merchants, removing any one leaves two — so **G4's de-facto effect is a four-merchant floor**.
`residual_cell(cell, merchant)` builds `R \ {merchant}` and re-runs G1–G3; removing a non-member **raises**
rather than producing a larger, more-compliant residual. Card counts use the measured leave-one-out union
where available, else the sound lower bound `cards − volume`, which can only over-suppress. 

## 7. What we measured

At the postcode grain, over the **62** cells of the audited universe — 54 Sopot `81-*` codes plus the 8 out-of-town codes Sopot-labelled merchants carry (`#privacy_matches_audit`):
| Gate | Cells | Volume | Claim |
|---|---:|---:|---|
| G1 (≥30 cards) / G2 (≥3 entities) | **54** / **25** | — | `#gate_g1_cards`, `#gate_g2_merchants` |
| G3 volume only / volume **and** cards | **25** / **24** | — | `#privacy_g3_volume_only`, `#privacy_g3_both_metrics` |
| all three, **as the shipped artifact applies them** | **17** | **89.95%** | `#released_codes`, `#gate_volume_share` |
| all three, volume-only reading (not shipped) | 18 | 90.69% | `#privacy_summary_volume_only` |
| all three, conservative reading | **17** | **89.95%** | `#privacy_all_three_strict`, `#privacy_share_strict` |
| all four (G1–G4) | **11** | **87.7%** | `#privacy_g4_pass`, `#privacy_share_all_four` |

The pipeline enforces the same verdicts as a **release gate** on the artifact it ships: of the 54 Sopot cells
in the axis, **17 leave with a series** and **37 with nothing but their name and their failure reason**,
carrying **33,197** transactions that stay inside the exact city series `cityCnt` (`#released_codes`,
`#suppressed_codes`, `#suppressed_volume`, `#city_cnt_sum`). A suppressed cell is not merely undrawn — its counts are absent from the file.

**The single difference between 18 and 17 is `81-740`**: released on a **72.2%** volume share, suppressed on a
**78.5%** card share (`#privacy_single_difference`) — one merchant is volume-light and card-heavy. We ship the
conservative reading and report 18 as the audit's. At postcode × month × daypart, **393 of 2,003** cells pass
all three carrying **83.44%** of volume (`#privacy_daypart_pass`, `#privacy_daypart_share`); the 18 passing
postcodes hold **19.0%** of Sopot's **3,767** address points (`#address_share_passing18`). 

## 8. The two planes, in the words the panel uses

**Plane A** is the merchant's own acquirer/POS feed with consent: one subject, her own till, *not* a
k-anonymity group. **Plane B** is the anonymised comparison panel: many subjects, gated. They are never
blended into one number, and a Plane A figure is never derived from the pooled panel — finding the merchant's
own volume inside the panel is exactly the re-identification attempt the challenge forbids. 
> **Porównanie branżowe.** Te liczby to agregat wszystkich restauracji w wybranym obszarze i okresie, liczony z
> panelu transakcji kartą. Publikujemy je tylko wtedy, gdy grupa obejmuje co najmniej 30 unikalnych kart i co
> najmniej 3 podmioty, a udział żadnego podmiotu nie przekracza 75%. Stosujemy dodatkowo test różnicowy: grupa
> musi spełniać progi także po odjęciu dowolnego jednego podmiotu. Twoja własna sprzedaż nie jest odejmowana
> ani dodawana do tej liczby.

The Plane A disclosure (*„Twoje dane.”* … *„Możesz je w każdej chwili wyłączyć.”*), the EN rendering of both,
and one sentence per reason code are in `contracts/PRIVACY-COPY.md` §4. Every Plane B number carries *„Dane
dla obszaru **{kod}**, nie dla Twojego lokalu.”* in the same visual block as the number — not a footnote. 

## 9. Non-vacuity: the gate can fail, and we proved it

`tests/privacy/test_nonvacuous.py` perturbs each threshold, requires the check constraining it to **fail**,
reverts, and requires the check to **pass**: **31** tests in the privacy suite, **12** in the non-vacuity
suite, **18** reference fixtures, and the TypeScript mirror agreeing with the Python gate on **23 fixture
cases** (`#privacy_suite_passed`, `#privacy_nonvacuous_passed`, `#privacy_fixtures`, `#privacy_mirror_parity`).
Loosening the thresholds flips exactly six fixtures; tightening them flips six others. Transcript: `tests/privacy/nonvacuous-evidence.txt`.

## 10. What this is not

- **Not differential privacy.** k-anonymity bounds *one released cell*; DP bounds a *sequence of queries*
  against a budget. We have no budget, no noise mechanism, no composition guarantee. A merchant who knows her
  own volume can still difference herself out of a released area total, and reads across months and dayparts
  can narrow a competitor's range. **G4 narrows that attack; it does not close it.**
- **Not protection against an attacker holding the raw feed.** Anyone with the parquet can count what they
  like; the gate governs what *we publish*, not what anyone else can compute.
- **Not record-level anonymisation, and not a legal opinion.** There are no records to generalise, and
  compliance is a judgement for the Organiser, not for us. 

## 11. Known limitations

- **G4 is off in the letter-of-the-rule profile and on in the shipped one.** `BASE_RULES` has
  `requireDifferencing=False`, for the 18 reference fixtures and the boundary tests; `PRODUCT_RULES` has it on
  under a different `rule_version`, and `assert_released` raises `stale_rules` if a record produced under one
  is displayed under the other. - **The gate is enforced at the gate, not at a network boundary.** It stops a number reaching a renderer; it
  does not stop an analyst re-running the pipeline with the thresholds edited.
- **The card-share leg of G3 is skipped when per-merchant card counts are missing.** The gate then evaluates
  volume alone and records that in its trace; it never silently claims the conservative reading.
- **`81-740` sits exactly on the boundary that leg exists for**, so the 17-vs-18 choice is a judgement between
  two defensible readings; both appear in `docs/EVALUATION.md` §5.
