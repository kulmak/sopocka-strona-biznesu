"""The publishable sample — what the public repo ships *instead of* the raw parquet.

WHAT THE RULE IS
----------------
`data/samples/sample.csv` is a **k-anonymised aggregate**, never a row sample. Nothing in it can be
traced to a card, a merchant or a transaction. The construction, in order:

1. **Only gated codes.** A postcode is included only if it passes all three privacy gates over the
   whole period (≥30 distinct cards, ≥3 distinct merchant descriptors, ≤75 % top-1 share). With
   this data that is 18 of 62 codes carrying 90.7 % of volume; the other 44 are absent entirely,
   so the sample cannot be differenced against the panel to recover a suppressed cell.
2. **Aggregated to postcode × day.** The finest published grain is one row per (postcode, date).
   No hour, no card, no merchant, no transaction id — so the hourly curve, which is the panel's
   product, cannot be reconstructed from it.
3. **k = 3 on the row.** A (postcode, day) row is dropped unless it carries ≥3 transactions *and*
   ≥3 distinct merchants. Rows that thin are exactly the rows from which a single venue's day
   could be read off.
4. **Amounts rounded to whole złoty** and counts left exact, so the sample is *useful* for
   re-deriving the driver regression and the weekday profile without being *re-identifying*.
5. **The D2 sentinel is split out, not hidden.** `transactions` counts every row for that
   code-day; `transactions_dated` counts only the rows that carry a real timecode. Publishing both
   keeps the 10.2 % hole visible in the sample instead of quietly shrinking the totals.

WHY IT EXISTS
-------------
AGENTS.md rule 5 — "Never publish Organiser Data. Public artifacts are the privacy-gated aggregate
only. The raw parquet never enters git, never gets served, never lands in a public bucket." The
public repo still needs a data file a reader can open: this is it. It is deliberately *not* the
parquet, not a subsample of the parquet, and not `aggregate.json` (which is a UI artifact keyed to
a byte layout and is orders of magnitude larger).

WHAT THIS FILE IS NOT
---------------------
It is **not** an anonymisation of individuals in the k-anonymity sense of generalising a record
table until each record is indistinguishable from k−1 others; there are no records to generalise.
It is an aggregate release whose cells are all above the same thresholds the panel enforces, which
is the stronger property for this data. The distinction is stated rather than blurred.

EVIDENCE
--------
`data/samples/sample-manifest.json` records the row count, the sha256 of the CSV, the gated codes,
the suppression counters and the exact thresholds — so a reader can re-derive the file from the
source parquet and check it, without the source parquet being published.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Sequence

import duckdb

from pipeline import _gates
from pipeline.enrich import TZ

#: Minimum transactions and merchants on a published (postcode, day) row.
MIN_ROW_TRANSACTIONS = 3
MIN_ROW_MERCHANTS = 3

#: Columns of `sample.csv`, in order. Every one is an aggregate or a city-level covariate.
COLUMNS: tuple[str, ...] = (
    "postcode", "date", "weekday_iso", "month",
    "transactions", "transactions_dated", "amount_pln", "merchants",
    "temperature_mean_c", "rainy_fraction", "wind_speed_mean_kmh", "event_listings_count",
)


def gated_codes(con: duckdb.DuckDBPyConnection, view: str = "tx_raw",
                codes: Sequence[str] | None = None) -> tuple[list[str], dict]:
    """Codes that pass all three gates over the whole period, plus the per-code evidence.

    Two readings of "all three gates" are computed, because they disagree on exactly one code:

    * the **challenge brief's** rule — ≥30 cards, ≥3 merchants, ≤75 % of *volume*: 18 codes pass;
    * the **harness spec's** default (`Rules.share_metrics = ('volume','cards')`): 17 pass.

    `81-740` holds 72.2 % of its volume in one merchant but 78.5 % of its distinct cards, so it
    passes the first and fails the second. The stricter reading is the one used here (it is the
    specification the privacy engineer's module is being written to), and the difference is
    published rather than resolved silently.
    """
    privacy_mod, source = _gates.load()
    rows = con.execute(f"""
        WITH per AS (
          SELECT merchant_postal_code_normalized AS pc, mrch_nm_raw AS m,
                 count(*) AS n, count(DISTINCT pymt_crd_acct_num_raw) AS c
          FROM {view}
          WHERE merchant_postal_code_normalized LIKE '81-%'
          GROUP BY 1,2),
        agg AS (
          SELECT pc, count(*) AS n_merch, sum(n) AS n_tran, max(n) AS top_v, max(c) AS top_c
          FROM per GROUP BY 1),
        cards AS (
          SELECT merchant_postal_code_normalized AS pc,
                 count(DISTINCT pymt_crd_acct_num_raw) AS n_cards
          FROM {view} WHERE merchant_postal_code_normalized LIKE '81-%' GROUP BY 1)
        SELECT agg.pc, agg.n_merch, agg.n_tran, agg.top_v, agg.top_c, cards.n_cards
        FROM agg JOIN cards USING (pc) ORDER BY agg.pc""").fetchall()
    keep, evidence, volume_only, strict_only = [], {}, set(), set()
    for pc, n_merch, n_tran, top_v, top_c, n_cards in rows:
        g_vol = privacy_mod.gate_dict(n_cards=int(n_cards), n_merchants=int(n_merch),
                                      top1_volume=int(top_v), n_tran=int(n_tran),
                                      top1_cards=0)
        g = privacy_mod.gate_dict(n_cards=int(n_cards), n_merchants=int(n_merch),
                                  top1_volume=int(top_v), n_tran=int(n_tran),
                                  top1_cards=int(top_c))
        evidence[pc] = {"gates": g, "gates_volume_only": g_vol, "n_cards": int(n_cards),
                        "n_merchants": int(n_merch), "n_transactions": int(n_tran),
                        "top1_share": round(int(top_v) / int(n_tran), 4),
                        "top1_card_share": round(int(top_c) / max(int(n_cards), 1), 4)}
        if g_vol["all"]:
            volume_only.add(pc)
        if g["all"]:
            strict_only.add(pc)
        if g["all"] and (codes is None or pc in set(codes)):
            keep.append(pc)
    return sorted(keep), {
        "source": source,
        "per_code": evidence,
        "passed_volume_only": sorted(volume_only),
        "passed_volume_and_cards": sorted(strict_only),
        "suppressed_only_by_card_share": sorted(volume_only - strict_only),
        "n_codes_considered": len(rows),
    }


def rows_for(con: duckdb.DuckDBPyConnection, codes: Sequence[str],
             view: str = "tx_raw") -> list[list]:
    """One aggregate row per (gated postcode, day), with the k-anonymity suppression applied."""
    if not codes:
        return []
    code_list = ", ".join(f"'{c}'" for c in codes)
    raw = con.execute(f"""
        SELECT merchant_postal_code_normalized AS pc, purchase_date AS d,
               count(*) AS n,
               sum(CASE WHEN tran_id_gmt_tm <> '000000' THEN 1 ELSE 0 END) AS n_dated,
               sum(transaction_amount)::DOUBLE AS zl,
               count(DISTINCT mrch_nm_raw) AS n_merch,
               any_value(weather_temperature_mean_c)::DOUBLE AS temp,
               any_value(weather_rainy_fraction)::DOUBLE AS rain,
               any_value(weather_wind_speed_mean_kmh)::DOUBLE AS wind,
               any_value(event_listings_count)::INT AS ev
        FROM {view}
        WHERE merchant_postal_code_normalized IN ({code_list})
        GROUP BY 1,2 ORDER BY 1,2""").fetchall()
    out = []
    for pc, d, n, n_dated, zl, n_merch, temp, rain, wind, ev in raw:
        if int(n) < MIN_ROW_TRANSACTIONS or int(n_merch) < MIN_ROW_MERCHANTS:
            continue
        out.append([pc, str(d), (d.isoweekday() if hasattr(d, "isoweekday") else ""),
                    int(str(d)[5:7]), int(n), int(n_dated), int(round(float(zl or 0.0))),
                    int(n_merch),
                    None if temp is None else round(float(temp), 1),
                    None if rain is None else round(float(rain), 4),
                    None if wind is None else round(float(wind), 2),
                    None if ev is None else int(ev)])
    return out


def write_sample(con: duckdb.DuckDBPyConnection, codes_axis: Sequence[str] | None = None,
                 out_dir: str | Path = "data/samples", view: str = "tx_raw",
                 repo_root: str | Path = ".") -> dict:
    """Write `sample.csv` + `sample-manifest.json` + `README.md`; return the report.

    `out_dir` is explicit so the CLI (`make sample`) and the pipeline (`make data`) share one
    implementation instead of two that drift.
    """
    root = Path(repo_root)
    out_dir = Path(out_dir)
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    codes, gate_evidence = gated_codes(con, view, codes=codes_axis)
    rows = rows_for(con, codes, view)
    code_list = ", ".join(f"'{c}'" for c in codes) if codes else "''"
    gated_pairs = con.execute(f"""
        SELECT count(*) FROM (
          SELECT merchant_postal_code_normalized AS pc, purchase_date AS d
          FROM {view} WHERE merchant_postal_code_normalized IN ({code_list}) GROUP BY 1,2)"""
    ).fetchone()[0]
    ungated_pairs = con.execute(f"""
        SELECT count(*) FROM (
          SELECT merchant_postal_code_normalized AS pc, purchase_date AS d
          FROM {view} WHERE merchant_postal_code_normalized LIKE '81-%'
            AND merchant_postal_code_normalized NOT IN ({code_list}) GROUP BY 1,2)"""
    ).fetchone()[0]

    csv_path = out_dir / "sample.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLUMNS)
        w.writerows(rows)
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()

    manifest = {
        "file": "sample.csv",
        "sha256": digest,
        "rows": len(rows),
        "columns": list(COLUMNS),
        "grain": "postcode x day (aggregate, not a row sample)",
        "timezone": TZ,
        "gated_codes": codes,
        "n_gated_codes": len(codes),
        "thresholds": {"min_cards": 30, "min_merchants": 3, "max_top1_share": 0.75,
                       "min_row_transactions": MIN_ROW_TRANSACTIONS,
                       "min_row_merchants": MIN_ROW_MERCHANTS},
        "suppression": {
            "code_day_pairs_in_gated_codes": int(gated_pairs),
            "published": len(rows),
            "suppressed_below_k": int(gated_pairs) - len(rows),
            "code_day_pairs_in_non_gated_codes": int(ungated_pairs),
        },
        "gate_variants": {
            "passed_volume_only": gate_evidence["passed_volume_only"],
            "passed_volume_and_cards": gate_evidence["passed_volume_and_cards"],
            "suppressed_only_by_card_share": gate_evidence["suppressed_only_by_card_share"],
            "n_codes_considered": gate_evidence["n_codes_considered"],
            "note": ("AGENTS.md records '18 of 62 postcodes pass all three gates' — that is the "
                     "challenge brief's volume-only reading. Under the privacy harness's default "
                     "share_metrics=('volume','cards') 17 pass; 81-740 holds 72.2 % of volume but "
                     "78.5 % of distinct cards in one merchant. The stricter reading is used."),
        },
        "absent_by_construction": ["pymt_crd_acct_num_raw", "mrch_nm_raw", "tran_id_raw",
                                   "tran_id_gmt_tm", "hour", "any per-transaction record"],
        "gates_source": gate_evidence["source"],
        "per_code": gate_evidence["per_code"],
        "note": ("Gated codes only; every published row has >= 3 transactions and >= 3 distinct "
                 "merchants. Re-run `python3 -m pipeline.run` to regenerate from the source "
                 "parquet. The raw parquet is never published."),
    }
    (out_dir / "sample-manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    (out_dir / "README.md").write_text(_README.format(
        rows=len(rows), codes=len(codes), sha=digest[:16],
        pairs=int(gated_pairs), suppressed=int(gated_pairs) - len(rows)), encoding="utf-8")
    return {"path": str(csv_path), "bytes": csv_path.stat().st_size, "rows": len(rows),
            "sha256": digest, "gated_codes": len(codes),
            "gated_codes_list": codes,
            "gate_variants": {"volume_only": gate_evidence["passed_volume_only"],
                              "volume_and_cards": gate_evidence["passed_volume_and_cards"],
                              "suppressed_only_by_card_share":
                                  gate_evidence["suppressed_only_by_card_share"]},
            "suppressed": int(gated_pairs) - len(rows)}


_README = """# `data/samples/` — the publishable sample

**This directory never contains the raw parquet.** It contains `sample.csv`, a k-anonymised
aggregate that is safe to publish, and the manifest that lets a reader check it.

| | |
|---|---|
| Rows | {rows} |
| Grain | one row per **postcode × day** |
| Codes | {codes} (only those passing all three privacy gates) |
| Suppressed rows | {suppressed} of {pairs} code-day pairs (below k = 3 transactions or 3 merchants) |
| SHA-256 (first 16) | `{sha}…` |

## What is in it

`postcode, date, weekday_iso, month, transactions, transactions_dated, amount_pln, merchants,
temperature_mean_c, rainy_fraction, wind_speed_mean_kmh, event_listings_count`

## What is deliberately absent

Card identifiers, merchant names, transaction identifiers, **times of day**, and any per-transaction
record. The hourly curve — the panel's actual product — cannot be reconstructed from this file.

## Why `transactions_dated`

10.2 % of the source rows carry the sentinel timecode `'000000'` (defect D2). `transactions` counts
every row for that code-day; `transactions_dated` counts only the rows with a real timecode. Both
are published so the hole is visible instead of silently shrinking the totals.

## Regenerating

```sh
python3 -m pipeline.run --src <DIR with mcc5812_transactions.part0*.parquet> --out artifacts
```

The manifest records the sha256 of the CSV, so a diff is a one-line check.
"""


def build(repo_root: str | Path, con: duckdb.DuckDBPyConnection, agg: dict,
          view: str = "tx_raw") -> dict:
    """Entry point used by `pipeline/run.py`: writes into `<repo_root>/data/samples`."""
    return write_sample(con, codes_axis=agg["codes"][1:], out_dir="data/samples",
                        view=view, repo_root=repo_root)


def _main(argv: list[str] | None = None) -> int:
    """`python3 -m pipeline.sample --src DIR --out data/samples` — the `make sample` target.

    Regenerating the sample alone is useful when only the gate thresholds change: it re-reads the
    parquet, re-evaluates every gate through whatever module `pipeline._gates.load()` returns, and
    rewrites `sample.csv` + `sample-manifest.json` + `README.md`. It never touches the raw data.
    """
    import argparse
    from pipeline import ingest

    ap = argparse.ArgumentParser(prog="python3 -m pipeline.sample")
    ap.add_argument("--src", default="/Users/kulma/Downloads",
                    help="directory holding mcc5812_transactions.part0*.parquet")
    ap.add_argument("--out", default="data/samples", help="output directory")
    ap.add_argument("--repo-root", default=".", help="repo root for data/ lookups")
    args = ap.parse_args(argv)

    root = Path(args.repo_root).resolve()
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    con = ingest.connect()
    ingest.register_raw(con, ingest.source_files(args.src))
    info = write_sample(con, out_dir=out, repo_root=root)
    print(f"wrote {out}/sample.csv · {info['rows']} rows · {info['bytes']} B · "
          f"{info['gated_codes']} gated codes · sha256 {info['sha256'][:16]}…")
    return 0


if __name__ == "__main__":       # pragma: no cover
    raise SystemExit(_main())
