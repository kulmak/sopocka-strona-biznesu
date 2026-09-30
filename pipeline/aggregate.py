"""Stage 9 — EMIT: build `artifacts/aggregate.json` v4 and assert every contract invariant.

WHAT THE RULE IS
----------------
The browser used to read 26 MB of parquet (pure-JS ZSTD decode + IndexedDB cache): 2.9–5.6 s cold,
23–28 s on a 10 Mbit/s link, and for the first 1.4–2.7 s it displayed **fabricated** numbers
labelled `Dane przykładowe`. `aggregate.json` replaces that with one precomputed, privacy-gated
file this pipeline can prove correct before writing.

THE THREE ARRAYS
----------------
```
cnt[ (ci * days + di) * 24 + h ]                      Uint16Array, base64
amt[ (ci * days + di) * 24 + h ]                      Uint16Array, WHOLE złoty, base64
nat[ (di * 24 + h) * 6 + bucket ]                     Uint32Array, base64
```
* `ci` — index into `codes`; **index 0 is the EXCLUDED bucket** (`"—"`).
* `di` — day index, `0 == 2025-01-01`, `545 == 2026-06-30`.
* `h` — local hour 0–23 in Europe/Warsaw, DST-corrected (see `pipeline/enrich.py`).
* `bucket` — issuer country: `0=PL 1=DE 2=SE 3=NO 4=GB 5=OTHER`.

Indexing is byte-for-byte the contract's. The app depends on it, so the indexing is asserted
against a hand-computed probe in `tests/pipeline/test_invariants.py`, not merely commented.

THE EXCLUDED BUCKET (index 0)
-----------------------------
Rows with no postcode, a foreign postcode, **or** the D2 `'000000'` sentinel land in `codes[0]`.
They stay inside `cnt`, so `sum(cnt) == rows` and the headline total is honest; they are outside
every `ci >= 1` curve, so no per-area or city view is contaminated by the phantom 02:00 spike.
`excluded.zeroTimecode` publishes the sentinel count so the app can say why the hourly total and
the headline total differ.

ENCODING NOTES THE APP MUST MATCH
---------------------------------
* Base64 is the raw little-endian byte image of the typed array (`array.tobytes()`), which is what
  `new Uint16Array(buffer)` expects on every platform that runs the panel.
* `amt` holds **whole złoty**. `amtScale` is raised only if a single cell would overflow Uint16
  (`> 65535`); with this data it stays `1`, so no precision is lost. If it ever rises, the app must
  multiply decoded values by `amtScale`, and the artifact says so — no silent rescale.
* `cnt`'s max cell is asserted `< 65535`. Invariant 5 exists because a silent `Uint16` wraparound
  would turn a busy hour into a small number that still *looks* plausible.

DETERMINISM
-----------
`json.dump(..., sort_keys=True, ensure_ascii=False)` plus a `generated` stamp derived from the
source mtime (or `SOURCE_DATE_EPOCH`) — never wall clock. Two runs produce byte-identical files;
`tests/pipeline/test_invariants.py` proves it by running the builder twice in one process.

EVIDENCE COLUMN
---------------
`rows` is `count(*)` over the union, and invariant 1 (`sum(cnt) == rows`) is the reconciliation
gate the original layer never had ("No artifact records 'expected 378,212, got 378,212'" —
`research/cleaning-lineage.md` §4.2). Here the number is *asserted by the pipeline*, not inferred
from the files.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Sequence

import duckdb
import numpy as np

from pipeline import RULE_VERSION, enrich, filter as filt
from pipeline.enrich import DAYS, HOURS, NAT_BUCKETS, NAT_OTHER_INDEX, START

#: Index 0 of `codes` — the contract's EXCLUDED bucket.
EXCLUDED_LABEL = "—"

#: Contract version. The app refuses anything else.
VER = 5

#: Presets, exactly as `contracts/AGGREGATE.md` specifies them: the codes, the ids, the display
#: names and the `why` strings are the contract's. Only `lat`/`lng` are recomputed — see
#: `pipeline/enrich.py::CONTRACT_PRESET_COORDS` for the audit that shows the shipped coordinates
#: land in the wrong postcode (54.4466,18.5700 → 81-720; 54.4447,18.5625 → 81-706; and
#: 54.4459,18.5697 → no sector at all).
PRESET_SPECS: tuple[dict, ...] = (
    {"id": "molo", "code": "81-777", "name": "Restauracja przy Molo",
     "why": "241 merchantów, 51.1% wolumenu", "point": 0},
    {"id": "monciak", "code": "81-759", "name": "Bistro na Monciaku",
     "why": "39 merchantów, pełne 18 miesięcy", "point": 0},
    {"id": "przystan", "code": "81-777", "name": "Bar na plaży",
     "why": "drugi lokal w tej samej strefie", "point": 1},
)


def b64(arr: np.ndarray) -> str:
    """Little-endian byte image of a typed array, base64-encoded (ASCII, no newlines)."""
    return base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode("ascii")


def code_axis(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> list[str]:
    """`codes` = `['—'] + sorted(Sopot postcodes)`, index 0 being the excluded bucket.

    Sorted, so the index of every code — and therefore every `cnt` offset — is identical on every
    machine and on every run. The 8 foreign postcodes are deliberately absent: they are *in* the
    data but *out* of the axis, which is what routes them to index 0.
    """
    rows = con.execute(f"""
        SELECT DISTINCT merchant_postal_code_normalized AS pc FROM {view}
        WHERE pc IS NOT NULL AND pc LIKE '{filt.SOPOT_PREFIX}%' ORDER BY pc""").fetchall()
    return [EXCLUDED_LABEL] + [r[0] for r in rows]


def build_arrays(con: duckdb.DuckDBPyConnection, codes: Sequence[str], view: str = "tx_raw"):
    """Fill `cnt`, `amt` (raw złoty) and `nat` from one grouped pass each.

    `ci` is resolved by a LEFT JOIN onto a VALUES table so an excluded row lands on index 0: the
    excluded predicate nulls the code *before* the join, which is why no `COALESCE(..., 0)` on a
    real code is needed (a code can never silently absorb the excluded mass).
    """
    n_codes = len(codes)
    values = ", ".join(f"('{c}', {i})" for i, c in enumerate(codes) if i > 0)
    di, h, _clamped = enrich.day_hour_columns()
    excluded = filt.excluded_predicate_sql()
    con.execute(f"CREATE OR REPLACE TEMP TABLE code_axis(code VARCHAR, idx INTEGER)")
    con.execute(f"INSERT INTO code_axis VALUES {values}")

    cells = con.execute(f"""
        SELECT COALESCE(a.idx, 0) AS ci, {di} AS di, {h} AS h,
               count(*) AS n, sum(transaction_amount)::DOUBLE AS zl
        FROM {view} t
        LEFT JOIN code_axis a
               ON a.code = CASE WHEN {excluded} THEN NULL
                                ELSE t.merchant_postal_code_normalized END
        GROUP BY 1,2,3""").fetchall()

    cnt = np.zeros(n_codes * DAYS * HOURS, dtype=np.uint16)
    zl = np.zeros(n_codes * DAYS * HOURS, dtype=np.float64)
    for ci, d, hh, n, amount in cells:
        p = (int(ci) * DAYS + int(d)) * HOURS + int(hh)
        cnt[p] += int(n)
        zl[p] += float(amount or 0.0)

    nat = np.zeros(DAYS * HOURS * 6, dtype=np.uint32)
    nat_cells = con.execute(f"""
        SELECT {di} AS di, {h} AS h,
               CASE issr_ctry_cd {''.join(f" WHEN '{c}' THEN {i}" for i, (c, _n) in enumerate(NAT_BUCKETS))}
                    ELSE {NAT_OTHER_INDEX} END AS b,
               count(*) AS n
        FROM {view} GROUP BY 1,2,3""").fetchall()
    for d, hh, b, n in nat_cells:
        nat[(int(d) * HOURS + int(hh)) * 6 + int(b)] += int(n)
    return cnt, zl, nat


def whole_zloty(zl: np.ndarray, limit: int = 65535) -> tuple[np.ndarray, float]:
    """Round złoty sums to whole units and choose the smallest safe `amtScale`.

    Invariant 6: a cell above 65535 would wrap silently in `Uint16Array`. Rather than clip (which
    would destroy the busiest — i.e. most interesting — cell), the scale is raised and published.
    """
    peak = float(zl.max(initial=0.0))
    scale = max(1.0, float(np.ceil(peak / limit))) if peak > limit else 1.0
    scaled = np.rint(zl / scale)
    if scaled.max(initial=0.0) > limit:                     # rounding can nudge one cell over
        scale = max(scale, float(np.ceil(scaled.max() / limit)))
        scaled = np.rint(zl / scale)
    assert scaled.max(initial=0.0) <= limit, "amtScale still overflows Uint16"
    return scaled.astype(np.uint16), scale


def presets_with_real_points(sectors: dict[str, dict]) -> list[dict]:
    """Build the three presets with coordinates **inside** their own postcode polygon.

    Two presets share `81-777` (the contract asks for a second venue in the same zone); they get
    two distinct interior points rather than the same coordinate twice, so the map draws two
    venues and not one stacked on itself.
    """
    out = []
    cache: dict[str, list[tuple[float, float]]] = {}
    for spec in PRESET_SPECS:
        code = spec["code"]
        if code not in cache:
            cache[code] = enrich.representative_points(sectors[code]["geometry"], k=2)
        pts = cache[code]
        lat, lng = pts[min(spec["point"], len(pts) - 1)]
        out.append({"id": spec["id"], "code": code, "name": spec["name"],
                    "lat": lat, "lng": lng, "why": spec["why"]})
    return out


def build_artifact(con: duckdb.DuckDBPyConnection, sectors: dict[str, dict],
                   source_block: dict, rows: int, excluded: dict,
                   view: str = "tx_raw") -> tuple[dict, dict]:
    """Build the artifact dict plus a report of every invariant it satisfied."""
    codes = code_axis(con, view)
    cnt, zl, nat = build_arrays(con, codes, view)

    meta_all = enrich.code_meta(con, sectors, codes[1:], view)

    # ---------------------------------------------------------------------------------------
    # THE RELEASE GATE. Everything above computes; this is the only place that decides what
    # leaves the machine, and it is deliberately the last step before the artifact is built.
    #
    # The challenge's binding rule is per-cell: an analysis or a presentation of a result may
    # only be made on a group covering >=30 distinct cards, with >=3 entities and no entity
    # above 75% of the group. A per-postcode hourly series IS a presentation of that cell's
    # result, so a cell that fails the gates must not carry one — and must not carry the
    # counts either, because "81-814: 1 transakcja, 1 karta, 1 podmiot" is exactly the
    # identification the rule forbids, whether or not a chart is drawn from it.
    #
    # What survives for a suppressed cell: its code, its name, its polygon provenance and WHICH
    # gate failed, so the map can render it honestly dark with a reason. What does not survive:
    # the hourly series, the amount series, and every count or share behind the verdict.
    # ---------------------------------------------------------------------------------------
    gated = {c for c, e in meta_all.items()
             if c != "_gates_source" and isinstance(e, dict) and e.get("gates", {}).get("all")}
    suppressed = [c for c in codes[1:] if c not in gated]

    # City totals are computed BEFORE suppression: the city as a whole is a single group of
    # 371k transactions, 347 entities and a 5.7% top-1 share, so it passes the gates and its
    # totals are publishable. Keeping them separate is what lets us suppress the parts without
    # lying about the whole.
    blocks = DAYS * HOURS
    city_cnt = cnt.reshape(len(codes), blocks)[1:].sum(axis=0).astype(np.uint32)
    city_amt = zl.reshape(len(codes), blocks)[1:].sum(axis=0)

    idx = {c: i for i, c in enumerate(codes)}
    suppressed_volume = int(sum(int(cnt[idx[c] * blocks:(idx[c] + 1) * blocks].sum())
                               for c in suppressed))
    for c in suppressed:
        i = idx[c]
        cnt[i * blocks:(i + 1) * blocks] = 0
        zl[i * blocks:(i + 1) * blocks] = 0.0

    # amt is derived AFTER zeroing so the scale is computed on what actually ships.
    amt, amt_scale = whole_zloty(zl)

    for c in suppressed:
        e = meta_all[c]
        for k in ("merchants", "transactions", "nCards", "top1Share"):
            e.pop(k, None)
        e["suppressed"] = True
        e["why"] = e.get("gates", {}).get("reason") or "gates"

    gates_source = meta_all.pop("_gates_source")
    code_meta = {k: v for k, v in meta_all.items() if k in set(codes)}
    presets = presets_with_real_points(sectors)

    art = {
        "ver": VER,
        "generated": source_block.pop("generated"),
        "source": source_block,
        "start": START.isoformat(),
        "days": DAYS,
        "hours": HOURS,
        "codes": list(codes),
        "codeMeta": code_meta,
        "cnt": b64(cnt),
        "amt": b64(amt),
        "amtScale": amt_scale,
        "nat": b64(nat),
        # Exact city totals, INCLUDING the suppressed cells. Without these the app could only
        # sum the released codes and would silently under-report the city by the suppressed
        # volume — the kind of quiet wrongness this artifact exists to avoid.
        "cityCnt": b64(city_cnt.astype(np.uint16) if city_cnt.max() < 65535 else city_cnt),
        "cityAmt": b64(city_amt.astype(np.uint16) if city_amt.max() < 65535 else city_amt),
        "cityAmtScale": amt_scale,
        "released": {"codes": len(gated), "suppressed": len(suppressed),
                     "codesInAxis": len(codes) - 1,
                     "suppressedVolume": suppressed_volume,
                     "note": ("Suppressed cells carry no series and no counts. `cityCnt` still "
                              "includes them, so the city total stays exact while the parts stay "
                              "unidentifiable. sum(cnt) + suppressedVolume == rows.")},
        "eventsByDay": enrich.events_by_day(con, view),
        "rows": int(rows),
        "excluded": excluded,
        "presets": presets,
    }
    report = {
        "codes": len(codes),
        "cells": int(cnt.size),
        "max_cnt": int(cnt.max(initial=0)),
        "max_amt_zl": float(zl.max(initial=0.0)),
        "suppressed_volume": int(art.get("released", {}).get("suppressedVolume", 0)),
        "amt_scale": amt_scale,
        "gates_source": gates_source,
        "array_bytes": {"cnt": int(cnt.nbytes), "amt": int(amt.nbytes), "nat": int(nat.nbytes)},
    }
    return art, report


def assert_invariants(art: dict, cnt: np.ndarray | None = None,
                      amt: np.ndarray | None = None, nat: np.ndarray | None = None,
                      sectors: dict[str, dict] | None = None) -> dict:
    """Assert the eight invariants of `contracts/AGGREGATE.md` §"Invariants".

    Decoded from the base64 that will be written — not from the in-memory arrays — so a serialisation
    bug cannot pass the gate that exists to catch serialisation bugs.
    """
    codes = art["codes"]
    days, hours, rows = art["days"], art["hours"], art["rows"]
    c = np.frombuffer(base64.b64decode(art["cnt"]), dtype=np.uint16)
    a = np.frombuffer(base64.b64decode(art["amt"]), dtype=np.uint16)
    n = np.frombuffer(base64.b64decode(art["nat"]), dtype=np.uint32)

    checks: dict[str, object] = {}
    # 1. every row lands exactly once, excluded rows in index 0
    checks["1_sum_cnt_eq_rows"] = int(c.sum())
    # The released series cannot sum to `rows` any more: the suppressed cells carry no series
    # by design. The honest form of the reconciliation keeps the suppressed volume in the
    # equation instead of quietly dropping it, and `cityCnt` carries the exact whole.
    supp = int(art.get("released", {}).get("suppressedVolume", 0))
    assert int(c.sum()) + supp == rows, (
        f"sum(cnt)={int(c.sum())} + suppressed={supp} != rows={rows} — the released series and "
        "the suppressed volume must together account for every row")
    # 2. array lengths
    assert len(c) == len(a) == len(codes) * days * hours, "cnt/amt length mismatch"
    checks["2_len_cnt_amt"] = len(c)
    # 3. nat length
    assert len(n) == days * hours * 6, f"len(nat)={len(n)} != {days*hours*6}"
    checks["3_len_nat"] = len(n)
    # 4. nat reconciles to the same row count
    assert int(n.sum()) == rows, f"sum(nat)={int(n.sum())} != rows={rows}"
    checks["4_sum_nat_eq_rows"] = int(n.sum())
    # 5. Uint16 safety on counts
    assert int(c.max(initial=0)) < 65535, f"max(cnt)={int(c.max())} would wrap Uint16"
    checks["5_max_cnt"] = int(c.max(initial=0))
    # 6. Uint16 safety on whole-złoty amounts, with the published scale
    assert int(a.max(initial=0)) < 65535, f"max(amt)={int(a.max())} would wrap Uint16"
    checks["6_max_amt_scaled"] = int(a.max(initial=0))
    checks["6_amtScale"] = art["amtScale"]
    # 7. codeMeta ↔ codes consistency
    axis = [x for x in codes if x != EXCLUDED_LABEL]
    assert set(art["codeMeta"]) == set(axis), (
        "codeMeta keys and codes are not the same set: "
        f"missing={sorted(set(axis)-set(art['codeMeta']))} extra={sorted(set(art['codeMeta'])-set(axis))}")
    checks["7_codes_with_meta"] = len(axis)
    # 8. every preset's code passes all privacy gates
    for p in art["presets"]:
        assert p["code"] in art["codeMeta"], f"preset {p['id']} names unknown code {p['code']}"
        g = art["codeMeta"][p["code"]]["gates"]
        assert g["g1_cards"] and g["g2_merchants"] and g["g3_share"] and g["all"], (
            f"preset {p['id']} (code {p['code']}) fails the privacy gates: {g}")
    checks["8_presets_passed_gates"] = len(art["presets"])
    # Geometry: every preset coordinate must sit inside its own code's polygon. Not a contract
    # invariant, but it is the defect this build corrects, so it is asserted next to the others.
    if sectors is not None:
        for p in art["presets"]:
            assert enrich.point_in_geometry((p["lng"], p["lat"]), sectors[p["code"]]["geometry"]), (
                f"preset {p['id']} ({p['lat']},{p['lng']}) is outside the polygon of {p['code']}")
        checks["8b_presets_inside_own_polygon"] = len(art["presets"])
    return checks


def validate_against_schema(art: dict, schema_path: str | Path) -> list[str]:
    """A dependency-free structural check of the frozen schema.

    `jsonschema` is **not installed** in this environment (`python3 -c "import jsonschema"` →
    ModuleNotFoundError), so the subset of JSON Schema the contract uses — `required`, `const`,
    `type`, `enum`, `pattern`, `minItems/maxItems`, `additionalProperties: false` — is implemented
    here in ~40 lines. It is deliberately narrow: it checks *this* schema, and a widened schema
    would need this to be widened too.
    """
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    problems: list[str] = []

    def check(node, sch, path):
        t = sch.get("type")
        if t == "object":
            if not isinstance(node, dict):
                problems.append(f"{path}: expected object"); return
            for req in sch.get("required", []):
                if req not in node:
                    problems.append(f"{path}: missing required key {req!r}")
            props = sch.get("properties", {})
            if sch.get("additionalProperties") is False:
                for k in node:
                    if k not in props:
                        problems.append(f"{path}: unexpected key {k!r}")
            for k, v in node.items():
                if k in props:
                    check(v, props[k], f"{path}.{k}")
                elif isinstance(sch.get("additionalProperties"), dict):
                    check(v, sch["additionalProperties"], f"{path}.{k}")
        elif t == "array":
            if not isinstance(node, list):
                problems.append(f"{path}: expected array"); return
            if "minItems" in sch and len(node) < sch["minItems"]:
                problems.append(f"{path}: {len(node)} items < minItems {sch['minItems']}")
            if "maxItems" in sch and len(node) > sch["maxItems"]:
                problems.append(f"{path}: {len(node)} items > maxItems {sch['maxItems']}")
            for i, v in enumerate(node):
                check(v, sch.get("items", {}), f"{path}[{i}]")
        elif t == "string":
            if not isinstance(node, str):
                problems.append(f"{path}: expected string"); return
            import re
            if "pattern" in sch and not re.search(sch["pattern"], node):
                problems.append(f"{path}: {node!r} does not match {sch['pattern']!r}")
        elif t == "integer":
            if not isinstance(node, int) or isinstance(node, bool):
                problems.append(f"{path}: expected integer, got {type(node).__name__}")
        elif t == "number":
            if not isinstance(node, (int, float)) or isinstance(node, bool):
                problems.append(f"{path}: expected number")
        if "const" in sch and node != sch["const"]:
            problems.append(f"{path}: {node!r} != const {sch['const']!r}")
        if "enum" in sch and node not in sch["enum"]:
            problems.append(f"{path}: {node!r} not in {sch['enum']}")
        if "minimum" in sch and isinstance(node, (int, float)) and node < sch["minimum"]:
            problems.append(f"{path}: {node} < minimum {sch['minimum']}")
        if "exclusiveMinimum" in sch and isinstance(node, (int, float)) and node <= sch["exclusiveMinimum"]:
            problems.append(f"{path}: {node} <= exclusiveMinimum {sch['exclusiveMinimum']}")
        if "maximum" in sch and isinstance(node, (int, float)) and node > sch["maximum"]:
            problems.append(f"{path}: {node} > maximum {sch['maximum']}")

    check(art, schema, "$")
    return problems


def write_json(obj: dict, path: str | Path) -> int:
    """Write deterministic UTF-8 JSON (sorted keys, 2-space indent) and return the byte size."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2)
    p.write_text(text + "\n", encoding="utf-8")
    return len((text + "\n").encode("utf-8"))
