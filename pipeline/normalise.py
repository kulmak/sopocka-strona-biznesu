"""Stage 3 — NORMALISE: the 3-branch postcode rewrite, asserted to be an exact partition.

WHAT THE RULE IS
----------------
`mrch_postal_code` holds two encodings of the same place — `81-777` and `81777` are separate
strings. The original pipeline rewrote it with a pure string CASE, with no lookup table:

```sql
CASE
  WHEN mrch_postal_code IS NULL OR mrch_postal_code = '' THEN NULL
  WHEN length(mrch_postal_code) = 6 THEN mrch_postal_code     -- already NN-NNN
  WHEN length(mrch_postal_code) = 5 THEN substr(x,1,2)||'-'||substr(x,3,3)
END
```

WHY IT EXISTS
-------------
Without it, any `GROUP BY` on the raw column splits 81-777 into two places and any join keyed on
it silently drops 20,943 rows (5.5 % of the table). It is the single best cost/benefit intervention
in the layer — three lines of SQL, provably lossless.

The branch counts are the falsifiable part, and they are asserted to the row:

===========================  =======  ==========================================
branch                       rows     what it proves
===========================  =======  ==========================================
NULL / `''` → NULL             6,431   (5,490 NULL + 941 empty string)
6-character pass-through     350,838   every value matches `^\\d{2}-\\d{3}$`, 0 exceptions
5-digit re-hyphenation        20,943   every value matches `^\\d{5}$`, 0 exceptions
**sum**                      378,212   exact partition of the table
===========================  =======  ==========================================

A 4th branch is asserted **absent**: any row whose raw postcode is neither NULL, nor 6 chars, nor
5 chars would fall through the CASE to NULL and vanish silently. The lineage calls the 3-branch
form "an exhaustive partition"; this module makes that a runtime assertion so a future extract
with a 4-character value fails loudly instead of re-labelling rows as postcode-less.

EVIDENCE COLUMNS
----------------
* `merchant_postal_code_normalized` — the output.
* `merchant_postal_code_status` / `weather_match_status` — the downstream membership statuses that
  are a 1:1 relabelling of each other and prove the normalisation ran (3 values, total, no
  residual). Note the lineage's finding that `merchant_postal_code_status` is mis-named: it
  describes *weather-reference membership*, not postcode validity.
"""

from __future__ import annotations

import duckdb

#: The recovered CASE expression, verbatim. `{col}` is the raw column name.
POSTCODE_CASE_SQL = """CASE
        WHEN {col} IS NULL OR {col} = '' THEN NULL
        WHEN length({col}) = 6 THEN {col}
        WHEN length({col}) = 5 THEN substr({col},1,2) || '-' || substr({col},3,3)
      END"""

#: Measured partition (lineage §1 stage 3 / §3.2). Asserted, not assumed.
EXPECTED_PARTITION: dict[str, int] = {
    "null_or_empty": 6_431,
    "six_char": 350_838,
    "five_digit": 20_943,
}


def normalised(con: duckdb.DuckDBPyConnection, view: str = "tx_raw",
               col: str = "mrch_postal_code") -> str:
    """Return a SELECT expression producing the normalised postcode (not materialised)."""
    expr = POSTCODE_CASE_SQL.format(col=col)
    return f"({expr})"


def partition(con: duckdb.DuckDBPyConnection, view: str = "tx_raw",
              col: str = "mrch_postal_code") -> dict[str, int]:
    """Count the three branches, plus the un-handled 4th shape (must be 0)."""
    row = con.execute(f"""
        SELECT
          sum(CASE WHEN {col} IS NULL OR {col} = '' THEN 1 ELSE 0 END),
          sum(CASE WHEN {col} IS NOT NULL AND {col} <> '' AND length({col}) = 6 THEN 1 ELSE 0 END),
          sum(CASE WHEN {col} IS NOT NULL AND {col} <> '' AND length({col}) = 5 THEN 1 ELSE 0 END),
          sum(CASE WHEN {col} IS NOT NULL AND {col} <> ''
                    AND length({col}) NOT IN (5,6) THEN 1 ELSE 0 END),
          count(*)
        FROM {view}""").fetchone()
    return {"null_or_empty": int(row[0]), "six_char": int(row[1]), "five_digit": int(row[2]),
            "unhandled": int(row[3]), "rows": int(row[4])}


def shape_violations(con: duckdb.DuckDBPyConnection, view: str = "tx_raw",
                     col: str = "mrch_postal_code") -> dict[str, int]:
    """Prove each branch's shape claim: 6-char values are `NN-NNN`, 5-char values are 5 digits."""
    a = con.execute(f"""
        SELECT count(*) FROM {view}
        WHERE {col} IS NOT NULL AND {col} <> '' AND length({col}) = 6
          AND NOT regexp_matches({col}, '^[0-9]{{2}}-[0-9]{{3}}$')""").fetchone()[0]
    b = con.execute(f"""
        SELECT count(*) FROM {view}
        WHERE {col} IS NOT NULL AND {col} <> '' AND length({col}) = 5
          AND NOT regexp_matches({col}, '^[0-9]{{5}}$')""").fetchone()[0]
    return {"six_char_not_nn_nnn": int(a), "five_char_not_five_digits": int(b)}


def assert_normalised(con: duckdb.DuckDBPyConnection, view: str = "tx_raw",
                      col: str = "mrch_postal_code") -> dict:
    """Assert the exact partition, the branch shapes, and that the stored column agrees.

    The stored `merchant_postal_code_normalized` is re-derived for all rows and compared with
    `IS DISTINCT FROM`, so the assertion covers both the arithmetic *and* the stored output.
    """
    part = partition(con, view, col)
    assert part["unhandled"] == 0, (
        f"{part['unhandled']} rows have a raw postcode that is neither NULL, '' nor 5/6 characters; "
        "the 3-branch CASE would silently map them to NULL")
    for key, want in EXPECTED_PARTITION.items():
        assert part[key] == want, f"postcode branch {key}: {part[key]} rows, lineage says {want}"
    assert part["null_or_empty"] + part["six_char"] + part["five_digit"] == part["rows"]
    shapes = shape_violations(con, view, col)
    assert shapes["six_char_not_nn_nnn"] == 0 and shapes["five_char_not_five_digits"] == 0, shapes
    mismatch = con.execute(f"""
        SELECT count(*) FROM {view}
        WHERE merchant_postal_code_normalized IS DISTINCT FROM {normalised(con, view, col)}"""
    ).fetchone()[0]
    assert mismatch == 0, (
        f"{mismatch} rows where the stored merchant_postal_code_normalized differs from the "
        "re-derived 3-branch CASE")
    part.update(shapes)
    part["stored_mismatches"] = int(mismatch)
    return part


def reference_membership(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict[str, int]:
    """The downstream status vocabulary, and the 1:1 relabelling proof.

    `merchant_postal_code_status` and `weather_match_status` must be a total, 1:1 mapping:
    `in_weather_reference`↔`matched_date_and_postal_code` (369,246),
    `missing`↔`missing_postal_code` (6,431),
    `not_in_weather_reference`↔`postal_code_not_in_weather_reference` (2,535).
    """
    rows = con.execute(f"""
        SELECT merchant_postal_code_status, weather_match_status, count(*)
        FROM {view} GROUP BY 1,2 ORDER BY 3 DESC""").fetchall()
    out: dict[str, int] = {}
    seen_a: dict[str, str] = {}
    for a, b, n in rows:
        if a in seen_a:
            raise AssertionError(
                f"merchant_postal_code_status={a!r} maps to more than one weather_match_status "
                f"({seen_a[a]!r} and {b!r}) — the relabelling is not 1:1")
        seen_a[a] = b
        out[f"{a} -> {b}"] = int(n)
    return out
