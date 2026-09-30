"""Stage 1 — INGEST: UNION ALL of the two source parts, with a disjointness proof.

WHAT THE RULE IS
----------------
The cleaned dataset ships as two parquet files that are **disjoint contiguous ranges of one
extraction**, split at `source_transaction_row` 1,177,268 / 1,177,271. They are re-read here with
`read_parquet([p1, p2])`, which is a `UNION ALL` — **never a JOIN and never a dedupe**. The union
is asserted to be disjoint on both `tran_id_raw` (the transaction key) and
`source_transaction_row` (the audit key); the assertion is the reason this module exists.

WHY IT EXISTS
-------------
`research/cleaning-lineage.md` §0.1 established that the CSV emission and the parquet emission
split the same 378,212 rows at *different* boundaries (CSV 1,179,192/1,179,230; parquet
1,177,268/1,177,271), so "part01 = first half" is false in the CSV sense. Any consumer that
assumes order, or that "helpfully" dedupes, silently changes the population. The audit's §4 gate
G4 ("`tran_id_raw` unique across both parts — 0 duplicate ids, **0 intersection** between parts")
is reproduced here as a hard assertion rather than a one-off query.

EVIDENCE COLUMNS
----------------
* `source_transaction_row` — not in the official 30-column list (challenge brief §7), so it is an
  added audit key; it is dense, unique and spans 22 – 2,345,173 across the union.
* `tran_id_raw` — the transaction key; the intersection count proves the split was clean.

The start offset of 22 is unexplained in the lineage (`INFERENCE`: an early exploratory slice, or
a non-zero `row_number()` origin). It is **reported, not repaired** — repairing it would fabricate
a source row that does not exist.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable, Sequence

import duckdb

#: File-name stems expected in `--src`, in pipeline order.
PART_STEMS: tuple[str, ...] = ("mcc5812_transactions.part01.parquet",
                               "mcc5812_transactions.part02.parquet")

#: The 72 columns of the cleaned emission, in schema order. Kept explicit so a schema drift is a
#: loud failure rather than a silent column rename.
EXPECTED_COLUMNS: tuple[str, ...] = (
    "source_transaction_row", "tran_id_raw", "tran_id_gmt_tm", "pymt_crd_acct_num_raw",
    "prod_id_pltfrm_cd_vcis", "transaction_type", "transaction_pos_entry_mode", "mrch_regn_cd",
    "mrch_regn_nm", "mrch_ctry_cd", "mrch_ctry_nm", "mrch_nm_raw", "mrch_catg_cd", "mrch_catg_nm",
    "mrch_city_nm_raw", "mrch_postal_code", "cs_tran_amt", "issr_jurn", "issr_ctry_cd",
    "issr_ctry_nm", "crd_typ_cd", "crd_typ_nm", "channel_flg", "cp_flag", "prch_mnth_id",
    "prch_dt", "myweek", "report_ctry", "lau_enr", "fua_enr", "pstl_cd_enr", "sopot_match_basis",
    "sopot_match_status", "sopot_geo_conflict", "sopot_country_status", "sopot_channel",
    "sopot_rule_version", "purchase_date", "transaction_amount", "transaction_time_gmt",
    "merchant_postal_code_normalized", "purchase_year", "purchase_month", "purchase_weekday_iso",
    "purchase_is_weekend", "purchase_date_status", "transaction_amount_status",
    "transaction_time_gmt_status", "merchant_postal_code_status", "weather_match_status",
    "weather_observed_hours", "weather_temperature_mean_c", "weather_temperature_min_c",
    "weather_temperature_max_c", "weather_wind_speed_mean_kmh", "weather_wind_speed_max_kmh",
    "weather_sunny_hours", "weather_cloudy_hours", "weather_rainy_hours",
    "weather_sunny_fraction", "weather_cloudy_fraction", "weather_rainy_fraction",
    "event_calendar_match_status", "event_listings_count", "event_single_day_listings_count",
    "event_multiday_listings_count", "event_recurring_listings_count",
    "event_nonrecurring_starts_count", "event_ids_json", "event_titles_json",
    "has_event_listings", "event_unresolved_listings_total",
)

#: Columns that must never reach a published artifact (AGENTS.md rule 5 — never publish Organiser
#: Data). `pymt_crd_acct_num_raw` is a card-account identifier and `mrch_nm_raw` is a merchant
#: name; both are read only as *cardinalities*, never emitted.
NEVER_PUBLISH: tuple[str, ...] = ("pymt_crd_acct_num_raw", "mrch_nm_raw")


def source_files(src: str | os.PathLike[str]) -> list[Path]:
    """Resolve the two part files under `src` and fail loudly if either is missing."""
    src = Path(src)
    files = [src / stem for stem in PART_STEMS]
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        raise FileNotFoundError(
            "missing source parquet part(s): " + ", ".join(missing) +
            "\nPass --src DIR pointing at the directory holding "
            "mcc5812_transactions.part01.parquet and part02.parquet.")
    return files


def sha256_file(path: str | os.PathLike[str], chunk: int = 1 << 20) -> str:
    """Streaming SHA-256 of a file (used for `source.sha256` and for the manifest cross-check)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def union_sql(files: Sequence[Path]) -> str:
    """`UNION ALL` over the parts — the only correct way to combine them.

    `read_parquet` with a list applies `union_by_name=false` and simply concatenates row groups;
    the SQL is emitted explicitly so the plan is auditable in `EXPLAIN`.
    """
    parts = ",\n       ".join(f"'{f}'" for f in files)
    return f"SELECT * FROM read_parquet([{parts}])"


def connect(threads: int | None = None) -> duckdb.DuckDBPyConnection:
    """A deterministic DuckDB connection.

    `threads` is pinned because row-group scheduling can change the *order* of results; every
    query in this pipeline is order-independent (aggregations and set operations), and pinning
    removes the last source of run-to-run variation. `preserve_insertion_order` keeps small
    result sets stable for readable console output.
    """
    con = duckdb.connect()
    n = threads if threads is not None else min(4, os.cpu_count() or 1)
    con.execute(f"SET threads={int(n)}")
    con.execute("SET preserve_insertion_order=true")
    return con


def register_raw(con: duckdb.DuckDBPyConnection, files: Sequence[Path]) -> None:
    """Materialise the union as the view `tx_raw` (stage 1 output)."""
    con.execute(f"CREATE OR REPLACE VIEW tx_raw AS {union_sql(files)}")


def check_schema(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict:
    """Assert the union still carries the 72 expected columns, in order."""
    got = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {view}").fetchall()]
    if tuple(got) != EXPECTED_COLUMNS:
        only_new = [c for c in got if c not in EXPECTED_COLUMNS]
        only_old = [c for c in EXPECTED_COLUMNS if c not in got]
        raise AssertionError(
            f"schema drift on {view}: {len(got)} columns, expected {len(EXPECTED_COLUMNS)}; "
            f"unexpected={only_new} missing={only_old}")
    return {"columns": len(got)}


def assert_disjoint(con: duckdb.DuckDBPyConnection, files: Sequence[Path]) -> dict:
    """Prove the two parts share no transaction and no source-row index.

    This is the `UNION ALL`-not-`JOIN` guard: if the parts overlapped, a union would duplicate
    rows and a join would multiply them. Both keys are tested because `tran_id_raw` is the
    business key and `source_transaction_row` is the audit key; a split that duplicated one but
    not the other would be a different, equally fatal, defect.
    """
    p1, p2 = (f"'{f}'" for f in files)
    ids_overlap, rows_overlap = con.execute(f"""
        SELECT (SELECT count(*) FROM (
                    SELECT tran_id_raw FROM read_parquet({p1})
                    INTERSECT
                    SELECT tran_id_raw FROM read_parquet({p2}))),
               (SELECT count(*) FROM (
                    SELECT source_transaction_row FROM read_parquet({p1})
                    INTERSECT
                    SELECT source_transaction_row FROM read_parquet({p2})))""").fetchone()
    assert ids_overlap == 0, f"parts overlap on tran_id_raw: {ids_overlap} shared ids"
    assert rows_overlap == 0, f"parts overlap on source_transaction_row: {rows_overlap} shared rows"
    (n1, n2) = con.execute(
        f"SELECT (SELECT count(*) FROM read_parquet({p1})), "
        f"(SELECT count(*) FROM read_parquet({p2}))").fetchone()
    return {"rows_part01": n1, "rows_part02": n2, "overlap_tran_id": ids_overlap,
            "overlap_source_row": rows_overlap}


def span(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict:
    """Row count, distinct transaction ids, source-row span and date span of the union."""
    row = con.execute(f"""
        SELECT count(*), count(DISTINCT tran_id_raw),
               min(source_transaction_row), max(source_transaction_row),
               min(purchase_date), max(purchase_date), count(DISTINCT purchase_date)
        FROM {view}""").fetchone()
    return {"rows": row[0], "distinct_tran_id": row[1], "src_row_min": row[2],
            "src_row_max": row[3], "date_min": str(row[4]), "date_max": str(row[5]),
            "distinct_days": row[6]}


def manifest(con: duckdb.DuckDBPyConnection, files: Sequence[Path],
             view: str = "tx_raw") -> dict:
    """Everything the artifact's `source` block needs, plus the schema check."""
    info = check_schema(con, view)
    info.update(assert_disjoint(con, files))
    info.update(span(con, view))
    info["files"] = [f.name for f in files]
    info["sha256"] = [sha256_file(f) for f in files]
    assert info["rows"] == info["distinct_tran_id"], (
        f"UNION ALL produced {info['rows']} rows but only {info['distinct_tran_id']} distinct "
        "tran_id_raw — the parts are not disjoint")
    return info


def mtime_iso8601(paths: Iterable[str | os.PathLike[str]], tz: str = "Europe/Warsaw") -> str:
    """A deterministic `generated` timestamp.

    WHY NOT WALL CLOCK: the artifact must be byte-identical across runs, so `generated` is derived
    from the newest source file's mtime (the moment the data last changed) rendered in the civic
    timezone the panel labels everything with. `SOURCE_DATE_EPOCH` overrides it, matching the
    reproducible-builds convention.
    """
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    env = os.environ.get("SOURCE_DATE_EPOCH")
    if env is not None and env.strip() != "":
        stamp = datetime.fromtimestamp(int(env), tz=timezone.utc)
    else:
        newest = max(os.path.getmtime(p) for p in paths)
        stamp = datetime.fromtimestamp(newest, tz=timezone.utc)
    return stamp.astimezone(ZoneInfo(tz)).replace(microsecond=0).isoformat()
