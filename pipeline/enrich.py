"""Stage 6/7 — ENRICH: DST-correct local time, calendar features, real sector geometry, gates.

WHAT THE RULES ARE
------------------
1. **GMT → Europe/Warsaw, DST-correct.** `tran_id_gmt_tm` is GMT/UTC. The panel labels every hour
   in civic local time, so the hour axis is local. Europe/Warsaw has a 23-hour day on the last
   Sunday of March and a 25-hour day on the last Sunday of October; both fall inside the window, so
   a fixed `+1 h`/`+2 h` rule is wrong twice a year.
2. **The timestamp must be UTC-bound before conversion.** See the trap below.
3. **Postcode → real geometry.** Every code's published centroid is a point *inside that code's
   own polygon*, and every preset coordinate is verified by a point-in-polygon test against the
   shipped sector model.
4. **Gates.** Per code: distinct merchants, transactions, distinct cards, top-1 merchant share,
   and the three gate booleans — computed from the card column the old browser layer never read.

THE DUCKDB TRAP (this cost the prototype a day)
-----------------------------------------------
`timezone('Europe/Warsaw', TIMESTAMP '2025-07-01 12:00:00')` **silently no-ops**: a naive
`TIMESTAMP` is treated as already-local, the call returns `12:00 CEST`, and every summer
transaction is an hour early. The fix is to *bind UTC first*:

```sql
timezone('Europe/Warsaw', (<naive ts>) AT TIME ZONE 'UTC')   -- 2025-07-01 12:00 → 14:00
```

Both forms are asserted against each other in `assert_dst()`: the naive form is required to
disagree, which pins the trap in a test rather than in a comment.

DST VERIFICATION
----------------
Three known Europe/Warsaw transitions inside the window, each asserted:
`2025-03-30` (23 local hours), `2025-10-26` (25 local hours), `2026-03-29` (23 local hours).
The same signature appears independently in the source data: `weather_observed_hours ∈ {23,24,25}`
lands on exactly those dates, which is why the lineage concludes the weather extract is local-time
hourly rather than UTC (`research/cleaning-lineage.md` §1 stage 7).

WHY THE DAY AXIS CLAMPS
-----------------------
A transaction at 2026-06-30 23:00 GMT is 2026-07-01 01:00 local — day index 546, one past the end
of the contract's 546-day axis. Three rows are affected. They are **clamped to day 545** rather
than dropped, because dropping them would break invariant 1 (`sum(cnt) == rows`) and a silently
short total is exactly the failure mode this pipeline exists to remove. The clamp is counted and
printed.

EVIDENCE COLUMNS
----------------
* `purchase_year`, `purchase_month`, `purchase_weekday_iso`, `purchase_is_weekend` — proven by 0
  mismatches over 378,212 rows.
* `weather_observed_hours` — carries the DST signature 23/25 on the transition dates.
* `sopot_channel` — `CASE WHEN cp_flag='1' THEN 'CP' ELSE 'CNP' END`, 0 mismatches, retained here
  as a cross-check that the row's identity survived the pipeline.
"""

from __future__ import annotations

import json
import math
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Sequence

import duckdb

from pipeline import _gates

#: Timezone the panel labels everything with.
TZ = "Europe/Warsaw"

#: Day axis from the contract: 546 days starting 2025-01-01 (inclusive of both ends).
START = date(2025, 1, 1)
DAYS = 546
HOURS = 24

#: Issuer-country buckets, index order fixed by `contracts/AGGREGATE.md`.
NAT_BUCKETS: tuple[tuple[str, str], ...] = (
    ("616", "PL"), ("276", "DE"), ("752", "SE"), ("578", "NO"), ("826", "GB"),
)
NAT_OTHER_INDEX = 5

#: The three Europe/Warsaw transitions inside the window and the local hours each day has.
DST_TRANSITIONS: tuple[tuple[str, int], ...] = (
    ("2025-03-30", 23),   # spring forward, 02:00 → 03:00
    ("2025-10-26", 25),   # fall back, 03:00 → 02:00
    ("2026-03-29", 23),
)

#: Candidate locations of the shipped sector model, in preference order. `data/` is the repo copy
#: the app reads; the prototype directory holds the GIS emission it was copied from.
SECTOR_CANDIDATES: tuple[str, ...] = (
    "data/sopot-sectors.geojson",
    "/Users/kulma/Downloads/Dashboard website application planning/data/sopot-sectors.geojson",
)

#: The two demo postcodes the contract names.
PRIMARY_CODE = "81-777"
SECONDARY_CODE = "81-759"


# --------------------------------------------------------------------------------------
# Time
# --------------------------------------------------------------------------------------

def gmt_naive_sql(date_col: str = "purchase_date", tm_col: str = "tran_id_gmt_tm") -> str:
    """The naive UTC timestamp expression: `HHMMSS` parsed and added to the purchase date."""
    return (f"({date_col} + CAST(strptime(lpad({tm_col},6,'0'),'%H%M%S') AS TIME))")


def local_ts_sql(date_col: str = "purchase_date", tm_col: str = "tran_id_gmt_tm",
                 tz: str = TZ) -> str:
    """DST-correct local timestamp SQL. **Binds UTC before converting** — see the module docstring."""
    return f"timezone('{tz}', {gmt_naive_sql(date_col, tm_col)} AT TIME ZONE 'UTC')"


def local_day_sql(date_col: str = "purchase_date", tm_col: str = "tran_id_gmt_tm",
                  lo: int = 0, hi: int = DAYS - 1) -> str:
    """Local day index, clamped onto the contract's `[lo, hi]` day axis."""
    ts = local_ts_sql(date_col, tm_col)
    return (f"least(greatest(datediff('day', DATE '{START.isoformat()}', ({ts})::DATE), {lo}), "
            f"{hi})")


def local_hour_sql(date_col: str = "purchase_date", tm_col: str = "tran_id_gmt_tm") -> str:
    """Local hour 0–23 — the `h` axis of `cnt` and `nat`."""
    return f"hour({local_ts_sql(date_col, tm_col)})"


def local_clamped_sql(date_col: str = "purchase_date", tm_col: str = "tran_id_gmt_tm",
                      lo: int = 0, hi: int = DAYS - 1) -> str:
    """1 when the row's local day had to be clamped onto the axis (3 rows on 2026-06-30)."""
    ts = local_ts_sql(date_col, tm_col)
    return (f"CASE WHEN datediff('day', DATE '{START.isoformat()}', ({ts})::DATE) > {hi} "
            f"OR datediff('day', DATE '{START.isoformat()}', ({ts})::DATE) < {lo} "
            f"THEN 1 ELSE 0 END")


def local_parts_sql(date_col: str = "purchase_date", tm_col: str = "tran_id_gmt_tm",
                    lo: int = 0, hi: int = DAYS - 1) -> str:
    """`di, h, clamped` as one comma-separated SELECT fragment.

    The three pieces are also exposed separately (`day_hour_columns`) because a naive
    `split(",")` of this string breaks on the commas inside `datediff(...)` — which it did.
    """
    di, h, cl = day_hour_columns(date_col, tm_col, lo, hi)
    return f"{di}, {h}, {cl}"


def day_hour_columns(date_col: str = "purchase_date", tm_col: str = "tran_id_gmt_tm",
                     lo: int = 0, hi: int = DAYS - 1) -> tuple[str, str, str]:
    """The three local-time expressions as a tuple — what callers should actually use."""
    return (local_day_sql(date_col, tm_col, lo, hi),
            local_hour_sql(date_col, tm_col),
            local_clamped_sql(date_col, tm_col, lo, hi))


def assert_dst(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict:
    """Prove the UTC binding is load-bearing and that the three transitions are handled.

    Three assertions:
    1. the naive form **disagrees** with the bound form (the trap is real, demonstrated on fixed
       instants so the test does not depend on which row happened to be read first);
    2. each transition local day really has 23 / 25 hours — computed by walking *every UTC hour*
       across that local day, so it is a property of the timezone rule and not of the transaction
       volume on that date;
    3. the specific instants: 02:30 local is **skipped** on a spring-forward day and **occurs
       twice** on a fall-back day.
    """
    trap = con.execute(f"""
        SELECT timezone('{TZ}', TIMESTAMP '2025-07-01 12:00:00')::VARCHAR,
               timezone('{TZ}', TIMESTAMP '2025-07-01 12:00:00' AT TIME ZONE 'UTC')::VARCHAR,
               timezone('{TZ}', TIMESTAMP '2025-01-15 12:00:00' AT TIME ZONE 'UTC')::VARCHAR""").fetchone()
    assert trap[0].startswith("2025-07-01 12:00"), (
        f"expected the naive timezone() call to no-op, got {trap[0]!r} — if this changed, "
        "DuckDB fixed the trap and the comment in this module is out of date")
    assert trap[1].startswith("2025-07-01 14:00"), f"summer offset wrong: {trap[1]!r}"
    assert trap[2].startswith("2025-01-15 13:00"), f"winter offset wrong: {trap[2]!r}"

    # (2) Walk every UTC hour across each transition's local day and count how many land in it.
    # `count(*)` and not `count(DISTINCT hour(...))`: on the fall-back day local 02:00 happens
    # twice, so the distinct-hour count would cap at 24 and hide the extra hour entirely.
    per_transition = {}
    for iso, expected_hours in DST_TRANSITIONS:
        got = int(con.execute(f"""
            SELECT count(*)
            FROM (SELECT unnest(generate_series(
                     TIMESTAMP '{iso} 00:00:00' - INTERVAL 3 HOUR,
                     TIMESTAMP '{iso} 00:00:00' + INTERVAL 27 HOUR,
                     INTERVAL 1 HOUR)) AS ts) g
            WHERE timezone('{TZ}', g.ts AT TIME ZONE 'UTC')::DATE = DATE '{iso}'""").fetchone()[0])
        assert got == expected_hours, (
            f"DST {iso}: a local day of {got} hours, expected {expected_hours} "
            f"(23 = spring forward, 25 = fall back)")
        per_transition[iso] = got

    # (3) The skipped / repeated local hour, as an exact instant test.
    skipped = con.execute("""
        SELECT count(*) FROM (SELECT unnest(generate_series(
                 TIMESTAMP '2025-03-30 00:00:00', TIMESTAMP '2025-03-30 03:00:00',
                 INTERVAL 1 MINUTE)) AS ts) g
        WHERE hour(timezone('Europe/Warsaw', g.ts AT TIME ZONE 'UTC')) = 2
          AND timezone('Europe/Warsaw', g.ts AT TIME ZONE 'UTC')::DATE = DATE '2025-03-30'"""
    ).fetchone()[0]
    repeated = con.execute("""
        SELECT count(*)
        FROM (SELECT unnest(generate_series(
                 TIMESTAMP '2025-10-25 22:00:00', TIMESTAMP '2025-10-26 06:00:00',
                 INTERVAL 1 HOUR)) AS ts) g
        WHERE timezone('Europe/Warsaw', g.ts AT TIME ZONE 'UTC')::DATE = DATE '2025-10-26'
          AND hour(timezone('Europe/Warsaw', g.ts AT TIME ZONE 'UTC')) = 2""").fetchone()[0]
    assert int(skipped) == 0, (
        "2025-03-30 is a spring-forward day but local 02:xx occurred — the conversion is wrong")
    assert int(repeated) == 2, (
        "2025-10-26 is a fall-back day: local hour 02:00 must occur twice (once in CEST, once in "
        f"CET), got {repeated}")

    # (4) The same fact, measured on the REAL rows rather than on a synthetic series — the only
    # form of this check that can be true of a day with 725 transactions on it.
    #
    # A fall-back day spans 1,500 minutes of elapsed time, but the data can only ever occupy the
    # minutes in which somebody paid: 2025-10-26 holds 792 transactions over 21 distinct local
    # hours. Demanding 1,500 occupied minutes from 792 rows is unsatisfiable and must never gate
    # `make data`. What IS assertable, and what actually proves the conversion:
    #   * local 02:xx does not exist on a spring-forward day  -> 0 rows;
    #   * local 02:xx happens twice on a fall-back day        -> rows exist in it;
    #   * every row of a transition day stays inside that single LOCAL date.
    per_day = {}
    for iso, _hours in DST_TRANSITIONS:
        n_rows, n_hours, n_dates, n_h2 = con.execute(f"""
            SELECT count(*), count(DISTINCT hour({local_ts_sql()})),
                   count(DISTINCT ({local_ts_sql()})::DATE),
                   sum(CASE WHEN hour({local_ts_sql()}) = 2 THEN 1 ELSE 0 END)
            FROM {view} WHERE ({local_ts_sql()})::DATE = DATE '{iso}'""").fetchone()
        per_day[iso] = {"rows": int(n_rows), "distinct_local_hours": int(n_hours),
                        "distinct_local_dates": int(n_dates), "rows_in_local_hour_02": int(n_h2)}
        assert int(n_dates) == 1, (
            f"{iso}: rows from one transition day landed on {n_dates} different local dates — "
            "the conversion is splitting a day")
        assert 20 <= int(n_hours) <= 24, (
            f"{iso}: {n_hours} distinct local hours with data, outside the plausible range")
    assert per_day["2025-03-30"]["rows_in_local_hour_02"] == 0, (
        "2025-03-30 is a spring-forward day: local 02:xx does not exist, yet rows carry it")
    assert per_day["2026-03-29"]["rows_in_local_hour_02"] == 0, (
        "2026-03-29 is a spring-forward day: local 02:xx does not exist, yet rows carry it")
    assert per_day["2025-10-26"]["rows_in_local_hour_02"] > 0, (
        "2025-10-26 is a fall-back day: local 02:xx occurs twice, so rows must exist in it")

    # Informational: the hours actually present in the data, per local day.
    hours_hist = {int(h): int(n) for h, n in con.execute(f"""
        SELECT count(DISTINCT hour({local_ts_sql()})) AS h, count(*) AS n
        FROM {view} GROUP BY ({local_ts_sql()})::DATE""").fetchall()}
    return {"trap_demonstration": {"naive": trap[0], "summer_bound": trap[1],
                                   "winter_bound": trap[2]},
            "transition_days": per_transition,
            "transition_days_real_rows": per_day,
            "skipped_local_minutes_2025_03_30": int(skipped),
            "local_hour_02_occurrences_2025_10_26": int(repeated),
            "distinct_hours_per_day_histogram": hours_hist}


def clamped_rows(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> int:
    """How many rows needed their local day index clamped back onto the 546-day axis."""
    lo, hi = 0, DAYS - 1
    ts = local_ts_sql()
    return int(con.execute(f"""
        SELECT count(*) FROM {view}
        WHERE datediff('day', DATE '{START.isoformat()}', ({ts})::DATE) NOT BETWEEN {lo} AND {hi}"""
    ).fetchone()[0])


def weekday_index(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict[int, float]:
    """Transactions per local weekday ÷ the mean day, normalised so the seven indices sum to 7.

    This is defect **D1**'s evidence. The prototype's baseline averaged the last 30 days across all
    weekdays, so a Saturday read +75 % against a Tuesday-flavoured mean while nothing had happened.
    The scale of that error is exactly this index: a Saturday is ~1.52× a mean day and a Monday
    ~0.72×, i.e. the weekday-blind baseline is wrong by ~±30 % twice a week before any real signal.
    """
    # Scoped to exactly the population `cityCnt` covers: Sopot postcodes, sentinel-time rows
    # excluded. Comparing a city-only cube against an all-rows index produces a mismatch that
    # looks like a timezone bug and is really a population mismatch (measured: 0.7214 vs 0.7232).
    rows = con.execute(f"""
        SELECT isodow(({local_ts_sql()})::DATE) AS dw, count(*) AS n
        FROM {view}
        WHERE merchant_postal_code_normalized IS NOT NULL
          AND merchant_postal_code_normalized LIKE '81-%'
          AND tran_id_gmt_tm <> '000000'
        GROUP BY 1 ORDER BY 1""").fetchall()
    total = sum(int(n) for _d, n in rows)
    return {int(dw): round(int(n) * 7.0 / total, 6) for dw, n in rows}


# --------------------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------------------

def _rings(geom: dict) -> Iterable[list]:
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return list(geom["coordinates"])
    raise ValueError(f"unsupported geometry type {geom['type']!r}")


def point_in_ring(pt: Sequence[float], ring: Sequence[Sequence[float]]) -> bool:
    """Ray-casting (even–odd) point-in-ring. `pt` and `ring` are `(lng, lat)`."""
    x, y = pt[0], pt[1]
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if (y1 > y) != (y2 > y):
            if x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
    return inside


def point_in_geometry(pt: Sequence[float], geom: dict) -> bool:
    """True when the point is inside the exterior ring of any polygon and outside all its holes."""
    for poly in _rings(geom):
        if point_in_ring(pt, poly[0]) and not any(point_in_ring(pt, h) for h in poly[1:]):
            return True
    return False


def _seg_distance(p, a, b) -> float:
    """Perpendicular distance from `p` to segment `a–b` (all `(lng, lat)` pairs)."""
    ax, ay = a[0], a[1]
    bx, by = b[0], b[1]
    px, py = p[0], p[1]
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _boundary_distance(pt, rings) -> float:
    """Shortest distance from `pt` to any ring edge — the objective the interior search maximises."""
    best = float("inf")
    for ring in rings:
        for i in range(len(ring) - 1):
            best = min(best, _seg_distance(pt, ring[i], ring[i + 1]))
    return best


def _scanline_spans(geom: dict, y: float) -> list[tuple[float, float]]:
    """Interior x-intervals of the geometry on the horizontal line `y`, by even–odd parity.

    Crossings from **every** ring of every part are pooled and sorted; consecutive pairs delimit
    the interior. That is exact for a valid multipolygon with holes (the GIS package reports 0
    invalid and 0 empty features across all 18 layers), and it is O(vertices) per scanline instead
    of O(vertices x grid) for a point-in-polygon sweep.
    """
    xs: list[float] = []
    for poly in _rings(geom):
        for ring in poly:
            n = len(ring)
            for i in range(n):
                x1, y1 = ring[i][0], ring[i][1]
                x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
                if (y1 > y) != (y2 > y):
                    xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    xs.sort()
    return [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]


def representative_point(geom: dict, samples: int = 200) -> tuple[float, float]:
    """A point guaranteed to lie **inside** the geometry, as far from the boundary as we can find.

    WHY NOT A CENTROID: the polygon centroid of a concave or multi-part sector routinely falls in
    the sea or in a neighbouring code. `81-777` is a coastal strip in **five** separate parts
    (`research/geo-enrichment.md` §2.5), so its vertex centroid is meaningless as a location.
    Pinning a demo preset to such a point puts the venue outside the area it claims to describe —
    which is exactly the defect found in the shipped contract (see `CONTRACT_PRESET_COORDS`).

    Method: scan a set of horizontal lines, keep the widest interior span on each, and return the
    midpoint of the span whose midpoint is furthest from any boundary edge. Deterministic, no
    dependencies, and — unlike a grid sweep — it cannot miss a thin coastal strip.
    """
    rings = [ring for poly in _rings(geom) for ring in poly]
    ys = [p[1] for ring in rings for p in ring]
    y0, y1 = min(ys), max(ys)
    best_pt, best_d = None, -1.0
    for k in range(1, samples + 1):
        y = y0 + (y1 - y0) * k / (samples + 1)
        for xa, xb in _scanline_spans(geom, y):
            if xb <= xa:
                continue
            pt = (0.5 * (xa + xb), y)
            if not point_in_geometry(pt, geom):
                continue
            d = _boundary_distance(pt, rings)
            if d > best_d:
                best_pt, best_d = pt, d
    if best_pt is None:
        raise ValueError("geometry contains no interior point on any scanline")
    assert point_in_geometry(best_pt, geom), (
        "representative_point produced a point outside its own polygon")
    return (round(best_pt[1], 6), round(best_pt[0], 6))    # (lat, lng)


def representative_points(geom: dict, k: int = 1, min_sep_deg: float = 0.0025,
                          samples: int = 200) -> list[tuple[float, float]]:
    """Up to `k` interior points, each at least `min_sep_deg` from the ones already chosen.

    Used to give two *different* venues in the same postcode (the contract's `molo` and `przystan`
    both live in 81-777) two distinct, honestly-placed coordinates instead of one repeated point.
    """
    rings = [ring for poly in _rings(geom) for ring in poly]
    ys = [p[1] for ring in rings for p in ring]
    y0, y1 = min(ys), max(ys)
    chosen: list[tuple[float, float]] = []
    for _ in range(k):
        best_pt, best_d = None, -1.0
        for s in range(1, samples + 1):
            y = y0 + (y1 - y0) * s / (samples + 1)
            for xa, xb in _scanline_spans(geom, y):
                if xb <= xa:
                    continue
                pt = (0.5 * (xa + xb), y)
                if not point_in_geometry(pt, geom):
                    continue
                if any(math.hypot(pt[0] - c[0], pt[1] - c[1]) < min_sep_deg for c in chosen):
                    continue
                d = _boundary_distance(pt, rings)
                if d > best_d:
                    best_pt, best_d = pt, d
        if best_pt is None:
            break
        assert point_in_geometry(best_pt, geom)
        chosen.append(best_pt)
    return [(round(p[1], 6), round(p[0], 6)) for p in chosen]      # (lat, lng)


def load_sectors(repo_root: str | os.PathLike[str] = ".") -> dict[str, dict]:
    """Load the shipped 151-sector model: `{postcode: {'geometry':…, 'properties':…}}`."""
    root = Path(repo_root)
    for cand in SECTOR_CANDIDATES:
        p = Path(cand)
        if not p.is_absolute():
            p = root / cand
        if p.is_file():
            gj = json.loads(p.read_text(encoding="utf-8"))
            return {f["properties"]["postcode"]: {"geometry": f["geometry"],
                                                  "properties": f["properties"],
                                                  "source": str(p)}
                    for f in gj["features"]}
    raise FileNotFoundError(
        "sector model not found; looked in: " + ", ".join(SECTOR_CANDIDATES))


def polygon_confidence(props: dict) -> str:
    """`observed | inferred | extrapolated | none`, using the thresholds published in
    `research/geo-enrichment.md` §3.3 — chosen because they are the only reproducible
    classification the package supports (`both_agree_count`, `support100_pct`, `address_count`).

    * `observed`     `both_agree_count >= 3` and `support100_pct >= 75`
    * `inferred`     `address_count >= 1` and `support100_pct >= 40`
    * `extrapolated` everything else with a polygon
    * `none`         the package publishes no polygon (81-701, 81-705, 81-768, 81-806)
    """
    both = int(props.get("both_agree_count", 0) or 0)
    support = float(props.get("support100_pct", 0) or 0)
    addrs = int(props.get("address_count", 0) or 0)
    if both >= 3 and support >= 75:
        return "observed"
    if addrs >= 1 and support >= 40:
        return "inferred"
    return "extrapolated"


def representative_points(geom: dict, k: int = 1, min_sep_deg: float = 0.0025,
                          grid: int = 64, refine: int = 4) -> list[tuple[float, float]]:
    """Up to `k` interior points, each at least `min_sep_deg` from the ones already chosen.

    Used to give two *different* venues in the same postcode (the contract's `molo` and `przystan`
    both live in 81-777) two distinct, honestly-placed coordinates instead of one repeated point.
    """
    polys = list(_rings(geom))
    xs = [p[0] for poly in polys for ring in poly for p in ring]
    ys = [p[1] for poly in polys for ring in poly for p in ring]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    chosen: list[tuple[float, float]] = []
    for _ in range(k):
        best_pt, best_d = None, -1.0
        gx0, gx1, gy0, gy1 = x0, x1, y0, y1
        for _step in range(refine):
            sx, sy = (gx1 - gx0) / grid, (gy1 - gy0) / grid
            for i in range(grid + 1):
                for j in range(grid + 1):
                    pt = (gx0 + i * sx, gy0 + j * sy)
                    if not point_in_geometry(pt, geom):
                        continue
                    if any(math.hypot(pt[0] - c[0], pt[1] - c[1]) < min_sep_deg for c in chosen):
                        continue
                    d = _boundary_distance(pt, polys)
                    if d > best_d:
                        best_pt, best_d = pt, d
            if best_pt is None:
                break
            gx0, gx1 = best_pt[0] - sx, best_pt[0] + sx
            gy0, gy1 = best_pt[1] - sy, best_pt[1] + sy
        if best_pt is None:
            break
        assert point_in_geometry(best_pt, geom)
        chosen.append(best_pt)
    return [(round(p[1], 6), round(p[0], 6)) for p in chosen]      # (lat, lng)


def code_names_and_points(sectors: dict[str, dict]) -> dict[str, dict]:
    """Per code: a Polish display label, an interior centroid, and a polygon-confidence grade.

    The label is street-derived and honest: it is the package's own top address-count street plus
    its distance-to-sea gradient band. No postcode is ever shown in the UI (`sopot-model.js`:
    "the UI never shows postcodes"), so the label is what a merchant recognises.
    """
    out: dict[str, dict] = {}
    for code, entry in sectors.items():
        props = entry["properties"]
        street = (props.get("streets") or "").split(";")[0].strip()
        label = f"ul. {street}" if street else code
        out[code] = {"name": label, "centroid": representative_point(entry["geometry"]),
                     "polygonConfidence": polygon_confidence(props)}
    return out


#: The contract's preset coordinates, kept verbatim for the point-in-polygon audit. **They are
#: wrong**: `54.4466, 18.5700` (labelled 81-777) falls inside `81-720`, `54.4447, 18.5625`
#: (labelled 81-759) falls inside `81-706`, and `54.4459, 18.5697` falls inside no sector at all.
#: `assert_presets()` fails the build if any *emitted* preset coordinate is outside its own code.
CONTRACT_PRESET_COORDS: dict[str, tuple[float, float]] = {
    "molo": (54.4466, 18.5700),
    "monciak": (54.4447, 18.5625),
    "przystan": (54.4459, 18.5697),
}


# --------------------------------------------------------------------------------------
# Per-code metadata and gates
# --------------------------------------------------------------------------------------

def code_meta(con: duckdb.DuckDBPyConnection, sectors: dict[str, dict],
              codes: Sequence[str], view: str = "tx_raw") -> dict[str, dict]:
    """Build `codeMeta` for every published code: counts, top-1 share, centroid, gate booleans.

    `mrch_nm_raw` is read only as a *grouping key* to find the top-1 share and then discarded;
    `pymt_crd_acct_num_raw` only as `count(DISTINCT …)`. Neither is ever emitted
    (`contracts/AGGREGATE.md` §"What is deliberately absent").
    """
    meta: dict[str, dict] = {}
    geo = code_names_and_points(sectors)
    rows = con.execute(f"""
        SELECT merchant_postal_code_normalized AS pc,
               count(*) AS n_tran,
               count(DISTINCT mrch_nm_raw) AS n_merchants,
               count(DISTINCT pymt_crd_acct_num_raw) AS n_cards
        FROM {view}
        WHERE merchant_postal_code_normalized IS NOT NULL
          AND merchant_postal_code_normalized LIKE '81-%'
        GROUP BY 1""").fetchall()
    stats = {pc: (int(a), int(b), int(c)) for pc, a, b, c in rows}
    tops = con.execute(f"""
        WITH per AS (
          SELECT merchant_postal_code_normalized AS pc, mrch_nm_raw AS m,
                 count(*) AS n, count(DISTINCT pymt_crd_acct_num_raw) AS c
          FROM {view}
          WHERE merchant_postal_code_normalized IS NOT NULL
            AND merchant_postal_code_normalized LIKE '81-%'
          GROUP BY 1,2)
        SELECT pc, max(n) AS top_n, max(c) AS top_c FROM per GROUP BY 1""").fetchall()
    top_by_code = {pc: (int(tn), int(tc)) for pc, tn, tc in tops}
    privacy_mod, privacy_src = _gates.load()
    for code in codes:
        if code not in stats:
            # A code in the axis with no rows cannot happen (the axis is built from the data), so
            # this is a guard rather than a branch.
            raise AssertionError(f"code {code} is in the axis but has no transactions")
        n_tran, n_merch, n_cards = stats[code]
        top_v, top_c = top_by_code.get(code, (0, 0))
        gates = privacy_mod.gate_dict(n_cards=n_cards, n_merchants=n_merch, top1_volume=top_v,
                                      n_tran=n_tran, top1_cards=top_c)
        g = geo.get(code)
        entry = {"name": (g or {}).get("name") or code,
                 "merchants": n_merch,
                 "transactions": n_tran,
                 "polygonConfidence": (g or {}).get("polygonConfidence", "none"),
                 "gates": gates,
                 "nCards": n_cards,
                 "top1Share": round(top_v / n_tran, 4)}
        if g:
            entry["centroid"] = list(g["centroid"])
        meta[code] = entry
    meta["_gates_source"] = privacy_src        # stripped by the caller before writing
    return meta


def assert_presets(presets: Sequence[dict], sectors: dict[str, dict]) -> dict:
    """Invariant 8 + geometry: every preset passes all gates and sits inside its own polygon."""
    report = {"checked": [], "contract_coords_verdict": {}}
    for pid, (lat, lng) in CONTRACT_PRESET_COORDS.items():
        owner = [c for c, e in sectors.items() if point_in_geometry((lng, lat), e["geometry"])]
        report["contract_coords_verdict"][pid] = owner or ["<no sector>"]
    for p in presets:
        code = p["code"]
        assert code in sectors, f"preset {p['id']} names code {code} which has no polygon"
        assert point_in_geometry((p["lng"], p["lat"]), sectors[code]["geometry"]), (
            f"preset {p['id']} ({p['lat']}, {p['lng']}) is NOT inside the polygon of {code} — "
            "the shipped contract's coordinates for this preset land in "
            f"{report['contract_coords_verdict'].get(p['id'])}")
        report["checked"].append({"id": p["id"], "code": code, "inside_own_polygon": True})
    return report


def events_by_day(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict[str, list]:
    """`{YYYY-MM-DD: [title, …]}` — the city calendar, deduped from the per-row payload.

    The join in the source layer is **date-only and city-wide** (`research/cleaning-lineage.md`
    §1 stage 8): 0 of 546 dates have more than one distinct `event_titles_json`. The lineage also
    found 546 dates but only 544 distinct event sets. Duplicates within a date are preserved in
    source order so the app's day strip shows the calendar the city actually published.
    """
    rows = con.execute(f"""
        SELECT purchase_date, any_value(event_titles_json)
        FROM {view} GROUP BY 1 ORDER BY 1""").fetchall()
    out: dict[str, list] = {}
    for d, payload in rows:
        if payload is None:
            continue
        try:
            titles = json.loads(payload)
        except (TypeError, ValueError):
            titles = []
        if titles:
            out[str(d)] = list(titles)
    return out


def calendar_features(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict:
    """Calendar-feature re-derivation gate (stage 6), kept next to the time code it depends on."""
    mism = {}
    for col, expr in (("purchase_year", "year(purchase_date)"),
                      ("purchase_month", "month(purchase_date)"),
                      ("purchase_weekday_iso", "isodow(purchase_date)"),
                      ("purchase_is_weekend", "isodow(purchase_date) IN (6,7)")):
        mism[col] = int(con.execute(
            f"SELECT count(*) FROM {view} WHERE {col} IS DISTINCT FROM ({expr})").fetchone()[0])
    assert not any(mism.values()), f"calendar features disagree with purchase_date: {mism}"
    return mism


def saturday_monday_index(con: duckdb.DuckDBPyConnection, view: str = "tx_raw") -> dict:
    """The two weekday indices the D1 fix is validated against (contract: ~1.514 / ~0.724)."""
    idx = weekday_index(con, view)
    return {"monday": idx[1], "saturday": idx[6], "all": idx}
