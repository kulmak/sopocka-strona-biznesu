"""Stage 2 — VALIDATE: re-derive the three typed columns and assert 0 mismatches.

WHAT THE RULE IS
----------------
Three raw VARCHAR columns were parsed into typed columns by the original pipeline. The rule is
recovered exactly by re-running the parse over all 378,212 rows and comparing to the stored
cleaned column:

| Derived               | Expression                                                        | Mismatches |
|-----------------------|-------------------------------------------------------------------|-----------:|
| `purchase_date`       | `CAST(prch_dt AS DATE)`                                            |          0 |
| `transaction_amount`  | `CAST(cs_tran_amt AS DECIMAL(38,10))`                              |          0 |
| `transaction_time_gmt`| `CAST(strptime(lpad(tran_id_gmt_tm,6,'0'),'%H%M%S') AS TIME)`      |          0 |

WHY IT EXISTS
-------------
This is the gate that separates "the columns are probably fine" from "the columns are provably the
raw values, re-parsed". Without it the whole downstream aggregate rests on an unrecorded DuckDB
run — the exact failure the audit names as the most damaging finding. A non-zero mismatch here is
not a warning; it means the cleaned columns were edited after parsing and every number built on
them is unsourced.

Note on `lpad(...,6,'0')`: the raw `tran_id_gmt_tm` is *always* exactly 6 characters in this
extract (audit gate G12), so the `lpad` is a no-op that is kept anyway because it is the documented
expression and a future extract with a 5-character value would otherwise parse as `0H:MM:SS`
silently — the same class of bug as the `'000000'` sentinel.

EVIDENCE COLUMNS
----------------
`purchase_date_status`, `transaction_amount_status`, `transaction_time_gmt_status` — all three
carry the single value `valid` on 100 % of rows. Those statuses assert *that* a parse happened;
the 0-mismatch comparison below asserts *what* the parse was. Both are needed: a status column with
one possible value is unfalsifiable on its own (`research/cleaning-lineage.md` §6.4 attack 4).

Also validated here: the date span (546 days, 2025-01-01 → 2026-06-30, no gaps), the amount domain
(0 < amount, min 0.0276, max 41,308.92) and the calendar features (`purchase_year`,
`purchase_month`, `purchase_weekday_iso`, `purchase_is_weekend`), plus the two corroborating raw
keys `prch_mnth_id` (YYYYMM) and `myweek` (ISO year + week) that were verified-but-not-replaced.
"""

from __future__ import annotations

import duckdb

#: The re-derivation expressions, verbatim from `research/cleaning-lineage.md` §3.1.
REDERIVATIONS: dict[str, str] = {
    "purchase_date": "CAST(prch_dt AS DATE)",
    "transaction_amount": "CAST(cs_tran_amt AS DECIMAL(38,10))",
    "transaction_time_gmt": "CAST(strptime(lpad(tran_id_gmt_tm,6,'0'),'%H%M%S') AS TIME)",
}

#: Calendar features, proven by 0 mismatches (stage 6 of the lineage).
CALENDAR_FEATURES: dict[str, str] = {
    "purchase_year": "year(purchase_date)::SMALLINT",
    "purchase_month": "month(purchase_date)::TINYINT",
    "purchase_weekday_iso": "isodow(purchase_date)::TINYINT",
    "purchase_is_weekend": "isodow(purchase_date) IN (6,7)",
}

#: Constants asserted against the lineage, with the §-reference that measured them.
EXPECTED: dict[str, object] = {
    "rows": 378_212,
    "distinct_days": 546,
    "date_min": "2025-01-01",
    "date_max": "2026-06-30",
    "min_amount": 0.0276,
    "max_amount": 41_308.92,
    "distinct_codes_normalised": 62,
    "distinct_merchants": 347,
    "distinct_cards": 160_127,
}


def _count(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    return int(con.execute(sql).fetchone()[0])


def rederive(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict[str, int]:
    """Count mismatches between each stored cleaned column and its re-derivation.

    `IS DISTINCT FROM` is used rather than `<>` so that a NULL on either side counts as a
    mismatch instead of silently evaluating to NULL (which would drop the row from the count).
    """
    out: dict[str, int] = {}
    for col, expr in REDERIVATIONS.items():
        out[col] = _count(con, f"""
            SELECT count(*) FROM {view}
            WHERE ({col}) IS DISTINCT FROM ({expr})""")
    return out


def rederive_calendar(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict[str, int]:
    """Same for the four calendar features and the two corroborating raw week keys."""
    out: dict[str, int] = {}
    for col, expr in CALENDAR_FEATURES.items():
        out[col] = _count(con, f"""
            SELECT count(*) FROM {view} WHERE ({col}) IS DISTINCT FROM ({expr})""")
    # prch_mnth_id = YYYYMM and myweek = ISO year + 'W' + ISO week: the lineage verified both
    # against purchase_date (0 mismatches, including the 2025/2026 week-year rollover) but the
    # original layer never asserted them itself.
    out["prch_mnth_id"] = _count(con, f"""
        SELECT count(*) FROM {view}
        WHERE prch_mnth_id IS DISTINCT FROM strftime(purchase_date,'%Y%m')""")
    out["myweek"] = _count(con, f"""
        SELECT count(*) FROM {view}
        WHERE myweek IS DISTINCT FROM (strftime(purchase_date,'%G')||'W'||lpad(strftime(purchase_date,'%V'),2,'0'))""")
    return out


def status_vocabularies(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict[str, list]:
    """Distinct values of the parse status columns — each must be exactly `['valid']`."""
    out: dict[str, list] = {}
    for col in ("purchase_date_status", "transaction_amount_status",
                "transaction_time_gmt_status"):
        out[col] = [r[0] for r in con.execute(
            f"SELECT DISTINCT {col} FROM {view} ORDER BY 1").fetchall()]
    return out


def domains(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict:
    """Numeric domains the lineage measured (gates G6–G12, G18, G19)."""
    row = con.execute(f"""
        SELECT count(*),
               count(DISTINCT purchase_date), min(purchase_date), max(purchase_date),
               min(transaction_amount)::DOUBLE, max(transaction_amount)::DOUBLE,
               sum(CASE WHEN purchase_date IS NULL THEN 1 ELSE 0 END),
               sum(CASE WHEN transaction_amount <= 0 THEN 1 ELSE 0 END),
               sum(CASE WHEN length(tran_id_gmt_tm) <> 6 THEN 1 ELSE 0 END),
               count(DISTINCT mrch_nm_raw), count(DISTINCT pymt_crd_acct_num_raw),
               count(DISTINCT merchant_postal_code_normalized),
               count(DISTINCT mrch_postal_code)
        FROM {view}""").fetchone()
    return {"rows": row[0], "distinct_days": row[1], "date_min": str(row[2]),
            "date_max": str(row[3]), "min_amount": round(row[4], 4),
            "max_amount": round(row[5], 2), "null_purchase_date": row[6],
            "nonpositive_amount": row[7], "bad_timecode_length": row[8],
            "distinct_merchants": row[9], "distinct_cards": row[10],
            "distinct_codes_normalised": row[11], "distinct_codes_raw": row[12]}


def assert_validated(con: duckdb.DuckDBPyConnection, view: str = "tx_raw",
                     strict_literals: bool = True) -> dict:
    """Run every stage-2 gate and return a report. Raises on any failure.

    `strict_literals` pins the measured constants from the lineage (row count, 62 raw postcodes,
    347 merchants, 160 127 cards). It is on by default: a silent change in any of them means the
    source moved under the pipeline and every published number is stale.
    """
    report: dict = {"mismatches": rederive(con, view),
                    "calendar_mismatches": rederive_calendar(con, view),
                    "statuses": status_vocabularies(con, view),
                    "domains": domains(con, view)}
    bad = {k: v for k, v in report["mismatches"].items() if v}
    assert not bad, f"re-derivation mismatches (stored column != re-derived): {bad}"
    bad_cal = {k: v for k, v in report["calendar_mismatches"].items() if v}
    assert not bad_cal, f"calendar re-derivation mismatches: {bad_cal}"
    for col, vals in report["statuses"].items():
        assert vals == ["valid"], f"{col} domain is {vals}, expected ['valid']"
    d = report["domains"]
    assert d["null_purchase_date"] == 0 and d["nonpositive_amount"] == 0
    assert d["bad_timecode_length"] == 0, "tran_id_gmt_tm is not uniformly 6 characters"
    if strict_literals:
        for key, want in EXPECTED.items():
            got = d.get(key)
            assert got == want, f"{key}: measured {got!r}, lineage says {want!r}"
        assert abs(d["min_amount"] - EXPECTED["min_amount"]) < 5e-4
        assert abs(d["max_amount"] - EXPECTED["max_amount"]) < 5e-3
    return report
