"""Stage 4/5 — FILTER: Sopot membership, the non-Sopot postcode leak, and defect **D2**.

WHAT THE RULES ARE
------------------
**(a) Sopot membership (as it was, and still is).** The original filter kept rows whose merchant
city label is Sopot: `upper(trim(mrch_city_nm_raw)) = 'SOPOT'`. There is **no postcode, geometry or
bounding-box predicate**. That is the whole of rule set `sopot-city-labels-only-v1`, and this
pipeline keeps it: the source files contain only surviving rows, so re-filtering them is a no-op
that is asserted (all 378,212 rows carry `sopot_match_basis = 'CITY_EXACT'`).

**(b) The non-Sopot postcode leak — the fix.** Because the filter never consulted the postcode,
**2,527 rows (0.668 %) carry a foreign postcode with a Sopot city label**:

| postcode | rows | presumed city |   | postcode | rows | presumed city |
|---|---:|---|---|---|---:|---|
| `20-315` | 914 | Lublin       |   | `01-221` | 114 | Warszawa |
| `70-035` | 622 | Szczecin     |   | `91-402` |  13 | Łódź |
| `02-495` | 504 | Warszawa     |   | `31-029` |   6 | Kraków |
| `62-030` | 353 | Września area|   | `01-825` |   1 | Warszawa |

These are 450–500 km from Sopot and sit inside every aggregate the dashboard computes. They are
**routed to the excluded bucket** (`codes[0]`, the `"—"` entry), not deleted: the row count stays
378,212, `sum(cnt) == rows` still holds, and the count is published as
`excluded.nonSopotPostcode` so the app can say out loud how much of the panel is not Sopot.

The companion column `sopot_geo_conflict` exists in the source and is **100 % NULL** on all
378,212 rows — the rule that should have populated it never fired. The vocabulary a real layer
should have used (`CITY_POSTCODE_MISMATCH`) is recorded here as `GEO_CONFLICT_VOCABULARY` so the
gap is documented rather than re-hidden. `81-796` (8 rows) is deliberately **kept**: it is a
Sopot-range code, merely absent from the PNA catalogue and the weather reference — a different
defect class from a Lublin postcode.

**(c) Defect D2 — the `'000000'` sentinel.** `tran_id_gmt_tm` is the GMT/UTC time in `HHMMSS`.
**38,443 rows (10.2 %)** carry the literal sentinel `'000000'`, and the original layer stamped all
of them `transaction_time_gmt_status = 'valid'` — a parse that succeeded on a value that is not a
time. Because the city's real traffic peaks at 13:00–14:00, a 10.2 % mass sitting at 00:00 GMT
moves into local 01:00/02:00 and fabricates **a phantom 02:00 spike** that the panel drew as if it
were dinner service.

THE CHOICE MADE HERE, AND WHY
.............................
The sentinel rows are **kept in `cnt`** — so `sum(cnt) == rows` reconciles and the panel's headline
transaction count stays true — but they are **routed to the excluded bucket `codes[0]`** at their
local clock hour. That is what makes them *separable*: `codes[0]` is the EXCLUDED bucket by
contract (`contracts/AGGREGATE.md`: `"codes": ["—", …]  // index 0 = EXCLUDED bucket`), so any
hourly curve drawn over `ci >= 1` drops all 38,443 of them without a second array, a second field,
or a client-side filter. They remain visible as `excluded.zeroTimecode` so the app can render the
honest state the standing rules demand: *"10,2 % transakcji nie ma godziny — poza wykresem
godzinowym"*, not a silently different curve.

The costs of that choice, stated rather than buried:
* An area's **daily** total no longer includes its un-timed rows. The trade is deliberate: a
  *shape* that is 10.2 % fabricated is worse than a *level* that is provably low, because the
  shape is what the product's "what is normal at this hour" claim rests on.
* `nat` (issuer-country mix) still counts **every** row, including these, so invariant 4
  (`sum(nat) == rows`) holds.
* 349 rows are *both* postcode-less and sentinel-bearing, so the three `excluded.*` counts overlap
  and must not be summed to predict `cnt[0]`. The exact index-0 population is reported by
  `excluded_bucket_size()`.

EVIDENCE COLUMNS
----------------
* `sopot_match_basis` = `CITY_EXACT` (100 %), `sopot_match_status` = `SUPPORTED` (100 %),
  `sopot_rule_version` = `sopot-city-labels-only-v1` (100 %) — prove which rule ran, and that it
  was city-labels-only.
* `sopot_geo_conflict` — 100 % NULL, which is the *evidence of absence* for the conflict rule.
* `merchant_postal_code_normalized` — the column the original filter never read.
* `transaction_time_gmt_status` — `'valid'` on the sentinel rows, which is exactly the bug.
"""

from __future__ import annotations

import duckdb

#: The D2 sentinel. `tran_id_gmt_tm` is `HHMMSS`, so `'000000'` is a *valid-looking* time that is
#: almost certainly a missing value: 38,443 rows land on it while hour 01:00 GMT has 569.
ZERO_TIMECODE = "000000"

#: The 8 postcodes that carry a Sopot city label but are not Sopot. Order fixed so `codes` — and
#: therefore every `cnt` index — is stable across runs and machines.
NON_SOPOT_POSTCODES: tuple[str, ...] = (
    "01-221", "01-825", "02-495", "20-315", "31-029", "62-030", "70-035", "91-402",
)

#: Rows expected on those codes (lineage §6.1). Asserted, so a source change is loud.
NON_SOPOT_ROWS = 2_527

#: The vocabulary `sopot_geo_conflict` should have carried. Recorded so the missing rule is a
#: documented gap, not an invisible one.
GEO_CONFLICT_VOCABULARY: tuple[str, ...] = (
    "CITY_POSTCODE_MISMATCH", "POSTCODE_NOT_IN_PNA", "UNKNOWN_POSTCODE",
)

#: The Sopot postcode prefix. Not a whitelist — 81-796 is in range and unknown to the PNA
#: catalogue — but the cheapest correct discriminator against Lublin/Szczecin/Warszawa codes.
SOPOT_PREFIX = "81-"


def is_sopot_code(code: str | None) -> bool:
    """True for a Sopot-range postcode. `None` is not Sopot (it is *unknown*)."""
    return bool(code) and code.startswith(SOPOT_PREFIX)


def leaked_postcodes(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict[str, int]:
    """Per-postcode counts of the city-label/postcode conflict, plus `81-796` for contrast."""
    rows = con.execute(f"""
        SELECT merchant_postal_code_normalized AS pc, count(*) AS n
        FROM {view}
        WHERE merchant_postal_code_normalized IS NOT NULL
          AND merchant_postal_code_normalized NOT LIKE '{SOPOT_PREFIX}%'
        GROUP BY 1 ORDER BY n DESC""").fetchall()
    return {pc: int(n) for pc, n in rows}


def assert_leak(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict:
    """Assert the leak is exactly the 8 known codes and 2,527 rows."""
    got = leaked_postcodes(con, view)
    assert sorted(got) == list(NON_SOPOT_POSTCODES), (
        f"non-Sopot postcode set changed: {sorted(got)} != {list(NON_SOPOT_POSTCODES)}")
    assert sum(got.values()) == NON_SOPOT_ROWS, (
        f"non-Sopot postcode rows: {sum(got.values())}, lineage says {NON_SOPOT_ROWS}")
    n_796 = con.execute(f"""
        SELECT count(*) FROM {view} WHERE merchant_postal_code_normalized = '81-796'"""
    ).fetchone()[0]
    assert n_796 == 8, f"81-796 carries {n_796} rows, lineage says 8"
    return {"by_postcode": got, "rows": sum(got.values()), "rows_81_796": int(n_796)}


def assert_sopot_basis(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict:
    """Re-assert the city-label rule over the surviving rows (stage 4 as a no-op, proven)."""
    row = con.execute(f"""
        SELECT
          sum(CASE WHEN upper(trim(mrch_city_nm_raw)) = 'SOPOT' THEN 1 ELSE 0 END),
          sum(CASE WHEN sopot_match_basis = 'CITY_EXACT' THEN 1 ELSE 0 END),
          sum(CASE WHEN sopot_rule_version = 'sopot-city-labels-only-v1' THEN 1 ELSE 0 END),
          sum(CASE WHEN sopot_geo_conflict IS NOT NULL THEN 1 ELSE 0 END),
          count(*)
        FROM {view}""").fetchone()
    n_sopot, n_basis, n_ver, n_conflict, n = (int(x) for x in row)
    assert n_sopot == n, f"{n - n_sopot} rows carry a non-Sopot city label"
    assert n_basis == n and n_ver == n
    assert n_conflict == 0, "sopot_geo_conflict is populated — the lineage says it is 100 % NULL"
    return {"rows": n, "city_label_sopot": n_sopot, "basis_city_exact": n_basis,
            "rule_version_v1": n_ver, "geo_conflict_populated": n_conflict}


def zero_timecode_stats(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict:
    """Count the D2 sentinel and show the hole it punches in the GMT hour histogram."""
    rows = con.execute(f"""
        SELECT
          sum(CASE WHEN tran_id_gmt_tm = '{ZERO_TIMECODE}' THEN 1 ELSE 0 END),
          sum(CASE WHEN tran_id_gmt_tm <> '{ZERO_TIMECODE}' AND substr(tran_id_gmt_tm,1,2) = '00'
                   THEN 1 ELSE 0 END),
          sum(CASE WHEN substr(tran_id_gmt_tm,1,2) = '01' THEN 1 ELSE 0 END),
          sum(CASE WHEN tran_id_gmt_tm = '{ZERO_TIMECODE}'
                    AND transaction_time_gmt_status <> 'valid' THEN 1 ELSE 0 END),
          count(*)
        FROM {view}""").fetchone()
    n_zero, n_h0_real, n_h1, n_flagged, n = (int(x) for x in rows)
    # The lineage's headline finding: the sentinel is *not* flagged as anything but valid.
    assert n_flagged == 0, "sentinel rows are now flagged invalid — D2's premise changed"
    return {"sentinel_rows": n_zero, "sentinel_share": round(n_zero / n, 6),
            "gmt_hour0_nonzero": n_h0_real, "gmt_hour1": n_h1, "rows": n,
            "status_flagged": n_flagged}


def excluded_predicate_sql(pc_col: str = "merchant_postal_code_normalized",
                           tm_col: str = "tran_id_gmt_tm") -> str:
    """The single predicate that decides whether a row lands in `codes[0]`.

    Three disjoint reasons, OR-ed, each with its own published count:
    no postcode · foreign postcode · no usable timecode (D2).
    """
    codes = ", ".join(f"'{c}'" for c in NON_SOPOT_POSTCODES)
    return (f"({pc_col} IS NULL OR {pc_col} IN ({codes}) OR {tm_col} = '{ZERO_TIMECODE}')")


def assert_filter(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict:
    """Run every stage-4/5 gate."""
    report = {"leak": assert_leak(con, view),
              "basis": assert_sopot_basis(con, view),
              "zero_timecode": zero_timecode_stats(con, view)}
    n = report["basis"]["rows"]
    no_pc = con.execute(f"""
        SELECT count(*) FROM {view} WHERE merchant_postal_code_normalized IS NULL"""
    ).fetchone()[0]
    both = con.execute(f"""
        SELECT count(*) FROM {view}
        WHERE merchant_postal_code_normalized IS NULL
          AND tran_id_gmt_tm = '{ZERO_TIMECODE}'""").fetchone()[0]
    report["excluded_counts"] = {
        "noPostcode": int(no_pc),
        "nonSopotPostcode": report["leak"]["rows"],
        "zeroTimecode": report["zero_timecode"]["sentinel_rows"],
        "noPostcode_and_zeroTimecode_overlap": int(both),
        "rows": n,
    }
    return report


def excluded_bucket_size(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> int:
    """Exact population of `codes[0]` — the union of the three reasons, counted once per row."""
    return int(con.execute(
        f"SELECT count(*) FROM {view} WHERE {excluded_predicate_sql()}").fetchone()[0])
