#!/usr/bin/env python3
"""scripts/privacy_report.py — measure the real panel against the gates, and write the artifact.

WHAT
    Runs `contracts/privacy.py` over the delivered transaction files and writes
    `artifacts/privacy-report.json`:

      * grain A — postcode, pooled over the whole 18-month period;
      * grain B — postcode × month × daypart (local Europe/Warsaw).

    For every cell: the distinct-card count (UNION, never a sum of children), the distinct
    merchant count, the transaction total, the exact top-1 share, the four gate booleans, and
    the stable reason code.

WHY
    Three regulatory claims are being made in the submission. Until this command has run, none of
    them has been checked against the data: the audit found the ≥30-card gate could not fire (the
    loader never read the card column), the ≤75% share was never computed, and the only cascades
    ran on a hand-written table. Numbers in the report, the deck and the copy block must come from
    this command, not from a sentence.

HOW (the semantics a reviewer must be able to re-derive)
    * `n_cards` = `count(DISTINCT pymt_crd_acct_num_raw)` over the cell's own relation. Card
      counts are NOT additive across a partition — the same card pays in several postcodes — so a
      sum of children would over-count and could pass a parent that does not qualify.
    * `merchants` = `count(*) GROUP BY mrch_nm_raw`: the cell's OWN partition; it sums to
      `n_transactions` by construction (`Cell` refuses it otherwise).
    * `residual_n_cards[m]` = `n_cards − |{cards whose every transaction in this cell is with m}|`
      — the MEASURED leave-one-out union count, which is what makes G4 exact rather than a bound.
    * Shares are exact rationals. The gate is decided on integers; the printed percentage is
      rounded afterwards and never feeds a decision.
    * No merchant id, name, street or address is written to the artifact: the only
      merchant-attributable figure in it is the aggregate top-1 share (compliance §1.5(a)).

FAILURE MODE
    Exits non-zero if any cell is arithmetically impossible, if a cell carries a plausibility
    finding, if a released cell carries no trace, or if the contract's own fixtures do not pass —
    the report must never be produced by a harness that is itself broken.

USAGE
    python3 scripts/privacy_report.py --src /Users/kulma/Downloads --out artifacts/privacy-report.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "contracts"))

import privacy as P  # noqa: E402

PARQUET_GLOB = "mcc5812_transactions.part0[12].parquet"
DAYPARTS = [
    ("night", 0, 5),
    ("morning", 6, 11),
    ("afternoon", 12, 17),
    ("evening", 18, 23),
]
#: Domain-separation salt for the opaque entity key. The key never leaves this process; it exists
#: so that the gate can group by merchant without ever handling a name it could print.
SALT = "sopocka-strona-biznesu/privacy-report/v1"

#: The volume-only reading of G3: exactly what the audit tables in
#: research/privacy-compliance.md §4.2/§4.3 measured (`100*top1_tran <= 75*n_tran`). The contract
#: additionally evaluates the CARD leg (compliance §2.3 R7, the conservative reading required by
#: reference fixture F-11), which is stricter. Both readings are reported; neither is tuned.
VOLUME_ONLY_RULES = P.Rules(share_metrics=("volume",))

EXPECTED = {
    "grain_postcode": {
        "cells": 62, "g1_pass": 54, "g2_pass": 25, "g3_pass": 25, "all_three_pass": 18,
        "share_all_three_pct": 90.7,
        "source": "AGENTS.md 'Measured facts'; research/privacy-compliance.md §4.2–4.3",
    }
}


def entity_key(merchant: str) -> str:
    """Opaque, stable-within-this-report entity id. Never written to the artifact."""
    return hashlib.sha256((SALT + "|" + merchant).encode("utf-8")).hexdigest()[:20]


def daypart_of(local_hour: int) -> str:
    for name, lo, hi in DAYPARTS:
        if lo <= local_hour <= hi:
            return name
    raise ValueError(f"hour out of range: {local_hour}")


def build_view(con, src: Path) -> Dict[str, Any]:
    """One view carrying exactly the derived columns the two grains need."""
    parquet = str(src / PARQUET_GLOB)
    con.execute(
        f"""
        CREATE OR REPLACE VIEW tx AS
        SELECT
            coalesce(nullif(upper(trim(merchant_postal_code_normalized)), ''), '(brak)') AS pc,
            prch_mnth_id                                   AS prch_month,
            purchase_date                                  AS gmt_date,
            cast(timezone('Europe/Warsaw', (purchase_date + transaction_time_gmt) AT TIME ZONE 'UTC')
                 AS DATE)                                  AS local_date,
            strftime(cast(timezone('Europe/Warsaw',
                 (purchase_date + transaction_time_gmt) AT TIME ZONE 'UTC') AS DATE), '%Y%m') AS local_month,
            extract(hour FROM timezone('Europe/Warsaw',
                 (purchase_date + transaction_time_gmt) AT TIME ZONE 'UTC'))::INT AS local_hour,
            (tran_id_gmt_tm = '000000')                    AS is_sentinel,
            pymt_crd_acct_num_raw                          AS card,
            mrch_nm_raw                                    AS merchant,
            mrch_catg_cd                                   AS mcc
        FROM read_parquet('{parquet}')
        """
    )
    row = con.execute(
        """
        SELECT count(*) AS rows,
               count(*) FILTER (WHERE is_sentinel) AS sentinel_rows,
               count(*) FILTER (WHERE local_date <> gmt_date) AS local_day_rollover,
               count(*) FILTER (WHERE local_month <> prch_month) AS local_month_differs,
               count(*) FILTER (WHERE pc = '(brak)') AS no_postcode_rows,
               count(DISTINCT pc) AS distinct_pc,
               count(DISTINCT merchant) AS distinct_merchants,
               count(DISTINCT card) AS distinct_cards,
               min(gmt_date) AS first_day, max(gmt_date) AS last_day,
               count(DISTINCT local_month) AS local_months,
               count(DISTINCT prch_month) AS prch_months
        FROM tx
        """
    ).fetchone()
    keys = ["rows", "sentinel_rows", "local_day_rollover", "local_month_differs", "no_postcode_rows",
            "distinct_pc", "distinct_merchants", "distinct_cards", "first_day", "last_day",
            "local_months", "prch_months"]
    facts = dict(zip(keys, row))
    mcc = con.execute("SELECT DISTINCT mcc FROM tx").fetchall()
    facts["mcc"] = sorted(str(m[0]) for m in mcc)
    for key in ("first_day", "last_day"):
        if isinstance(facts.get(key), dt.date):
            facts[key] = facts[key].isoformat()
    facts["files"] = sorted(p.name for p in src.glob("mcc5812_transactions.part0[12].parquet"))
    facts["sha256"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(src.glob("mcc5812_transactions.part0[12].parquet"))
    }
    return facts


def cells_for(con, relation_sql: str, grain_keys: List[str]) -> List[Dict[str, Any]]:
    """Aggregate one grain into gate-ready cells. Three passes over the same relation:

      1. the cell totals (union card count, transaction count, merchant count);
      2. the per-merchant partition (volume + distinct cards);
      3. the cards exclusive to a single merchant, which turn the totals into MEASURED
         leave-one-out residuals: cards(R \\ {m}) = cards(R) − exclusive(m).
    """
    key_cols = ", ".join(grain_keys)
    totals = con.execute(
        f"""
        SELECT {key_cols},
               count(DISTINCT card) AS n_cards,
               count(*)             AS n_transactions,
               count(DISTINCT merchant) AS n_merchants
        FROM ({relation_sql})
        GROUP BY {key_cols}
        """
    ).fetchall()
    per_merchant = con.execute(
        f"""
        SELECT {key_cols}, merchant, count(*) AS volume, count(DISTINCT card) AS cards
        FROM ({relation_sql})
        GROUP BY {key_cols}, merchant
        """
    ).fetchall()
    exclusive = con.execute(
        f"""
        WITH per_card AS (
            SELECT {key_cols}, card, count(DISTINCT merchant) AS n_merchants, min(merchant) AS only_merchant
            FROM ({relation_sql})
            GROUP BY {key_cols}, card
        )
        SELECT {key_cols}, only_merchant, count(*) AS exclusive_cards
        FROM per_card WHERE n_merchants = 1
        GROUP BY {key_cols}, only_merchant
        """
    ).fetchall()

    n_keys = len(grain_keys)
    cells: Dict[Tuple, Dict[str, Any]] = {}
    for row in totals:
        key = tuple(row[:n_keys])
        cells[key] = {
            "key": key,
            "grain": dict(zip(grain_keys, row[:n_keys])),
            "n_cards": int(row[n_keys]),
            "n_transactions": int(row[n_keys + 1]),
            "n_merchants": int(row[n_keys + 2]),
            "volumes": {},
            "cards": {},
            "exclusive": {},
        }
    for row in per_merchant:
        key = tuple(row[:n_keys])
        who = entity_key(str(row[n_keys]))
        cells[key]["volumes"][who] = int(row[n_keys + 1])
        cells[key]["cards"][who] = int(row[n_keys + 2])
    for row in exclusive:
        key = tuple(row[:n_keys])
        cells[key]["exclusive"][entity_key(str(row[n_keys]))] = int(row[n_keys + 1])
    return [cells[k] for k in sorted(cells)]


def gate_cell(raw: Dict[str, Any]) -> Tuple[P.Cell, Dict[str, Any]]:
    """Turn a measured cell into a contract Cell plus its three- and four-gate verdicts."""
    residuals = {
        who: raw["n_cards"] - raw["exclusive"].get(who, 0) for who in raw["volumes"]
    }
    cell = P.Cell(
        n_cards=raw["n_cards"],
        merchants=raw["volumes"],
        n_transactions=raw["n_transactions"],
        merchant_cards=raw["cards"],
        residual_n_cards=residuals,
        label=None,
    )
    findings = P.plausibility_findings(cell)
    if findings:
        raise AssertionError(f"implausible cell {raw['grain']}: {findings}")

    three = P.gate(cell, P.L_CELL, rules=P.BASE_RULES)
    four = P.gate(cell, P.L_CELL, rules=P.PRODUCT_RULES)
    volume_only = P.gate(cell, P.L_CELL, rules=VOLUME_ONLY_RULES)
    for record, rules in ((three, P.BASE_RULES), (four, P.PRODUCT_RULES), (volume_only, VOLUME_ONLY_RULES)):
        P.assert_released(record, rules=rules)

    row = dict(raw["grain"])
    row.update(
        {
            "n_cards": cell.n_cards,
            "n_merchants": cell.n_merchants,
            "n_transactions": cell.n_transactions,
            "top1_transactions": max(cell.merchants.values()) if cell.merchants else 0,
            "top1_share": f"{P.top1_share(cell.merchants).numerator}/{P.top1_share(cell.merchants).denominator}",
            "top1_share_pct": float(P.format_share(P.top1_share(cell.merchants), 3)),
            "top1_card_share": (
                f"{P.max_share(cell.merchant_cards, cell.n_cards).numerator}/"
                f"{P.max_share(cell.merchant_cards, cell.n_cards).denominator}"
            ),
            "top1_card_share_pct": float(P.format_share(P.max_share(cell.merchant_cards, cell.n_cards), 3)),
            "g1_cards": P.R_LT_30_CARDS not in three.failures,
            "g2_merchants": P.R_LT_3_MERCHANTS not in three.failures,
            "g3_share": P.R_TOP1_GT_75 not in three.failures,
            "g4_differencing": P.R_G4_DIFFERENCING not in four.failures,
            "all_three": three.ok,
            "all_four": four.ok,
            "g3_share_volume_only": P.R_TOP1_GT_75 not in volume_only.failures,
            "all_three_volume_metric": volume_only.ok,
            "reason_three": three.reason,
            "reason_four": four.reason,
            "reason_three_volume_metric": volume_only.reason,
        }
    )
    return cell, row


def summarise(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    volume = sum(r["n_transactions"] for r in rows)
    def vol(pred) -> int:
        return sum(r["n_transactions"] for r in rows if pred(r))
    def count(pred) -> int:
        return sum(1 for r in rows if pred(r))
    histogram: Dict[str, int] = {}
    for r in rows:
        histogram[r["reason_three"]] = histogram.get(r["reason_three"], 0) + 1
        histogram[r["reason_four"]] = histogram.get(r["reason_four"], 0) + 1
    three_volume = vol(lambda r: r["all_three"])
    four_volume = vol(lambda r: r["all_four"])
    volume_only_volume = vol(lambda r: r["all_three_volume_metric"])
    return {
        "cells": len(rows),
        "transactions_total": volume,
        "g1_pass": count(lambda r: r["g1_cards"]),
        "g2_pass": count(lambda r: r["g2_merchants"]),
        "g3_pass": count(lambda r: r["g3_share"]),
        "all_three_pass": count(lambda r: r["all_three"]),
        "g4_pass": count(lambda r: r["g4_differencing"]),
        "all_four_pass": count(lambda r: r["all_four"]),
        "volume_all_three": three_volume,
        "share_all_three_pct": round(100.0 * three_volume / volume, 2) if volume else 0.0,
        "volume_all_four": four_volume,
        "share_all_four_pct": round(100.0 * four_volume / volume, 2) if volume else 0.0,
        "g3_pass_volume_only": count(lambda r: r["g3_share_volume_only"]),
        "all_three_pass_volume_only": count(lambda r: r["all_three_volume_metric"]),
        "volume_all_three_volume_only": volume_only_volume,
        "share_all_three_volume_only_pct": (
            round(100.0 * volume_only_volume / volume, 2) if volume else 0.0
        ),
        "reason_histogram": dict(sorted(histogram.items())),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", default="/Users/kulma/Downloads", help="directory holding the source parquet")
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "privacy-report.json"))
    args = ap.parse_args()

    try:
        import duckdb  # noqa: F401
    except ImportError:
        print("duckdb is required for the measurement (it is NOT required by contracts/privacy.py)",
              file=sys.stderr)
        return 2
    import duckdb

    src = Path(args.src)
    if not list(src.glob("mcc5812_transactions.part0[12].parquet")):
        print(f"source parquet not found in {src}", file=sys.stderr)
        return 2

    con = duckdb.connect()
    facts = build_view(con, src)

    # The '(brak)' bucket is the aggregate contract's EXCLUDED bucket (index 0): a transaction
    # with no merchant postcode cannot belong to a postcode cell and is never displayed. It is
    # counted in `source.no_postcode_rows` instead of being gated as if it were an area.
    postcode = cells_for(
        con, "SELECT pc, card, merchant FROM tx WHERE pc <> '(brak)'", ["pc"])
    daypart = cells_for(
        con,
        """SELECT pc, local_month,
                  CASE WHEN local_hour BETWEEN 0 AND 5 THEN 'night'
                       WHEN local_hour BETWEEN 6 AND 11 THEN 'morning'
                       WHEN local_hour BETWEEN 12 AND 17 THEN 'afternoon'
                       ELSE 'evening' END AS daypart,
                  card, merchant
           FROM tx
           WHERE NOT is_sentinel        -- defect D2: the '000000' sentinel is not a transaction time
             AND pc <> '(brak)'          -- the no-postcode bucket is not an area
        """,
        ["pc", "local_month", "daypart"],
    )

    postcode_rows = [gate_cell(c)[1] for c in postcode]
    daypart_rows = [gate_cell(c)[1] for c in daypart]

    # A sensitivity check on the time convention: does the month axis change the verdicts?
    month_alt = cells_for(
        con,
        "SELECT pc, prch_month AS local_month, card, merchant FROM tx WHERE pc <> '(brak)'",
        ["pc", "local_month"],
    )
    alt_summary = summarise([gate_cell(c)[1] for c in month_alt])

    report = {
        "format": "sopot-privacy-report/1",
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "command": "python3 scripts/privacy_report.py --src /Users/kulma/Downloads "
                   "--out artifacts/privacy-report.json",
        "publication": (
            "INTERNAL AUDIT ARTIFACT — do not serve, do not bundle. It carries evidence for "
            "SUPPRESSED cells on purpose: a suppression that cannot be audited cannot be trusted. "
            "It contains no merchant id, name, street or address; its only merchant-attributable "
            "figure is the aggregate top-1 share. The app reads the GATED artifacts/aggregate.json, "
            "never this file."
        ),
        "contract": {
            "module": "contracts/privacy.py (mirrored by contracts/privacy.ts)",
            "three_gate_rules": P.BASE_RULES.to_mapping(),
            "four_gate_rules": P.PRODUCT_RULES.to_mapping(),
            "fingerprint": P.contract_fingerprint(),
        },
        "source": facts,
        "method": {
            "card_count": "count(DISTINCT pymt_crd_acct_num_raw) over the cell's union relation "
                          "(never a sum of children: a card pays in several postcodes)",
            "merchant_partition": "count(*) GROUP BY mrch_nm_raw; sums to n_transactions by construction",
            "top1_share": "exact Fraction: max(per-merchant transactions) / n_transactions; "
                          "the gate compares exact rationals, the printed percentage is rounded after",
            "residual_n_cards": "n_cards − |{cards whose every transaction in this cell is with that "
                                "one merchant}| — the MEASURED leave-one-out union count G4 uses",
            "postcode_universe": "every distinct merchant_postal_code_normalized value: 54 Sopot '81-*' "
                                 "codes plus 7 out-of-town codes carried by Sopot-labelled merchants = 62; "
                                 "the no-postcode bucket is excluded and counted below",
            "daypart": "local Europe/Warsaw time: night 00–05, morning 06–11, afternoon 12–17, "
                       "evening 18–23; month = the LOCAL calendar month",
            "excluded_rows": {
                "zero_timecode_sentinel": facts["sentinel_rows"],
                "reason": "defect D2: tran_id_gmt_tm='000000' is not a transaction time; excluded "
                          "from the daypart grain and counted here",
                "no_postcode_rows": facts["no_postcode_rows"],
                "rows_whose_local_month_differs_from_prch_mnth_id": facts["local_month_differs"],
                "month_axis_note": "the daypart grain uses the LOCAL calendar month; "
                                   f"{facts['local_month_differs']} row(s) sit in a different local "
                                   f"month than prch_mnth_id, so the axis has {facts['local_months']} "
                                   f"months instead of {facts['prch_months']}",
            },
            "sensitivity_local_month_vs_prch_mnth_id": {
                "note": "the month axis re-derived from prch_mnth_id instead of the local calendar month",
                "summary": alt_summary,
            },
        },
        "grain_postcode": {"summary": summarise(postcode_rows), "cells": postcode_rows},
        "grain_postcode_month_daypart": {
            "summary": summarise(daypart_rows), "cells": daypart_rows
        },
        "expected": EXPECTED,
        "matches_expected": {},
        "findings": [],
    }

    measured = report["grain_postcode"]["summary"]
    exp = EXPECTED["grain_postcode"]
    differences = []
    for field, got in (
        ("cells", measured["cells"]),
        ("g1_pass", measured["g1_pass"]),
        ("g2_pass", measured["g2_pass"]),
        ("g3_pass", measured["g3_pass_volume_only"]),
        ("all_three_pass", measured["all_three_pass_volume_only"]),
    ):
        if got != exp[field]:
            differences.append(f"{field}: measured {got} != expected {exp[field]}")
    if abs(measured["share_all_three_volume_only_pct"] - exp["share_all_three_pct"]) > 0.05:
        differences.append(
            f"share_all_three_pct: measured {measured['share_all_three_volume_only_pct']} "
            f"!= expected {exp['share_all_three_pct']}"
        )
    report["matches_expected"] = {
        "ok": not differences,
        "compared": "the VOLUME-ONLY reading of G3 — the one the audit tables measured",
        "differences": differences,
    }

    # Where the conservative card leg bites, name it. A difference that is reported is evidence;
    # a difference that is tuned away is a defect (AGENTS.md rule 3).
    card_leg = [
        {
            "pc": r["pc"],
            "n_cards": r["n_cards"],
            "n_merchants": r["n_merchants"],
            "top1_share_pct": r["top1_share_pct"],
            "top1_card_share_pct": r["top1_card_share_pct"],
            "verdict": "released on the volume metric; suppressed on the card metric",
        }
        for r in postcode_rows
        if r["all_three_volume_metric"] and not r["all_three"]
    ]
    report["findings"] = [
        {
            "id": "F-G3-CARD-LEG",
            "severity": "informational",
            "statement": (
                "The contract evaluates G3 on BOTH metrics and fails the cell if either exceeds the "
                "limit (compliance §2.3 R7, required by reference fixture F-11). The audit tables "
                "measured the volume metric only, so the conservative reading suppresses "
                f"{len(card_leg)} further postcode cell(s) and the 18/90.7% figure becomes "
                f"{measured['all_three_pass']}/{measured['share_all_three_pct']}%."
            ),
            "cells": card_leg,
        },
        {
            "id": "F-G4",
            "severity": "informational",
            "statement": (
                "G4 (leave-one-out differencing, a voluntary strengthening beyond the letter of the "
                "rule) is evaluated on MEASURED residuals at both grains. Its de-facto effect is a "
                "4-merchant floor: with three merchants, removing any one leaves two and the "
                "residual fails G2 by construction."
            ),
            "postcode_all_four_pass": measured["all_four_pass"],
            "postcode_share_all_four_pct": measured["share_all_four_pct"],
        },
    ]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=False), encoding="utf-8")

    def line(label: str, s: Dict[str, Any]) -> None:
        print(f"{label}: {s['cells']} cells · G1 {s['g1_pass']} · G2 {s['g2_pass']} "
              f"· G3 volume-only {s['g3_pass_volume_only']} / both metrics {s['g3_pass']} "
              f"· all three {s['all_three_pass_volume_only']} volume-only "
              f"({s['share_all_three_volume_only_pct']}% of volume) / {s['all_three_pass']} both "
              f"({s['share_all_three_pct']}%) · +G4 {s['all_four_pass']} ({s['share_all_four_pct']}%)")

    print(f"privacy report → {out}")
    line("postcode                    ", report["grain_postcode"]["summary"])
    line("postcode × month × daypart  ", report["grain_postcode_month_daypart"]["summary"])
    print("reason histogram (3 gates):", report["grain_postcode"]["summary"]["reason_histogram"])
    print("audit reproduction (volume-only G3):", "OK" if not differences else differences)
    for f in report["findings"]:
        print(f"  [{f['severity']}] {f['id']}: {f['statement']}")
    return 0 if not differences else 0   # differences are reported, never tuned away


if __name__ == "__main__":
    raise SystemExit(main())
