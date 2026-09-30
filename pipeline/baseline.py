"""Defect **D1** — the same-weekday-matched baseline, and the proof that it matters.

WHAT THE RULE IS
----------------
For a target cell *(code, day, hour)* the baseline ("zwykle") is the mean of the **same
`purchase_weekday_iso`** over the trailing four weeks:

```
B(code, di, h) = mean( cnt[code, di - 7k, h] )   for k = 1..4
```

Not the mean of the last 30 days, which is what the prototype computed
(`sopot-model.js:206`: `avg()` sums `dd = di-30 … di-1` with no weekday control).

WHY IT EXISTS
-------------
`AGENTS.md` defect D1: *"Baseline averages all weekdays; a no-event Saturday reads +75 %."* The
weekday-blind mean is not a mild approximation — it is a systematic bias whose size is exactly the
weekday index of the day being read. Measured over all 378,212 rows in local time:

| | Nd | Pn | Wt | Śr | Cz | Pt | Sb |
|---|---:|---:|---:|---:|---:|---:|---:|
| index (this build) | 1.361 | **0.723** | 0.729 | 0.738 | 0.852 | 1.072 | **1.520** |
| contract expectation | — | **0.724** | — | — | — | — | **1.514** |

Against a flat 30-day mean, a Saturday is read ~52 % high and a Monday ~28 % low **before any real
deviation exists** — which is precisely how a quiet Saturday gets sold to a restaurateur as an
event effect. The assertion below pins both extremes.

WHY THE APP COMPUTES IT FROM `cnt`, NOT FROM THIS FILE
------------------------------------------------------
`contracts/AGGREGATE.md` §"What the app must do": *"Compute the weekday-matched baseline from `cnt`
in the client (defect D1): for a target (code, hour) the baseline is the mean of the same
`purchase_weekday_iso` over the trailing 4 weeks, not the mean of all days."* The day index is in
`cnt`'s indexing, so `isodow(start + di)` is derivable client-side with no extra payload. This
module therefore provides (a) the reference implementation used for validation, (b) the assertions
that fix its behaviour, and (c) `artifacts/baseline.json` — a compact per-(code, weekday, hour)
table the app can use for the pre-load state, replacing the `Dane przykładowe` fabrication
(AGENTS.md rule 4: "No silent fallbacks").

EVIDENCE
--------
The weekday index itself is the evidence column: it is derivable two independent ways — from the
stored `purchase_weekday_iso` in the parquet, and from the local-day axis inside `cnt` — and
`assert_weekday_index()` requires both to agree. If they ever diverge, the hour/DST conversion has
broken and every per-hour curve in the panel is wrong.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

import numpy as np

from pipeline.enrich import DAYS, HOURS, START

#: The contract's expected weekday index for the two extremes (see `AGENTS.md` and
#: `contracts/AGGREGATE.md`). Tolerance ±0.01 — tight enough to catch an offset error, loose enough
#: to survive a legitimate re-derivation from a slightly different axis.
EXPECTED_INDEX: dict[str, float] = {"monday": 0.724, "saturday": 1.514}
INDEX_TOLERANCE = 0.01

#: Trailing same-weekday occurrences averaged into the baseline.
MATCHED_WEEKS = 4


def weekday_of(di: int, start: date = START) -> int:
    """ISO weekday (1=Mon … 7=Sun) of day index `di`. This is the client-side derivation."""
    return (start + timedelta(days=int(di))).isoweekday()


def daily_totals(cnt: np.ndarray, days: int = DAYS) -> np.ndarray:
    """City-wide daily counts from the published cube (sum over codes and hours)."""
    return cnt.reshape(-1, days, HOURS).sum(axis=(0, 2)).astype(np.float64)


def weekday_index_from_cube(cnt: np.ndarray, days: int = DAYS) -> dict[int, float]:
    """Weekday index computed **from `cnt`** — the artifact the app actually reads."""
    daily = daily_totals(cnt, days)
    idx = np.array([weekday_of(d) for d in range(days)])
    total = daily.sum()
    return {w: round(float(daily[idx == w].sum()) * 7.0 / total, 6) for w in range(1, 8)}


def matched_baseline(cnt: np.ndarray, ci: int, di: int, h: int, days: int = DAYS,
                     weeks: int = MATCHED_WEEKS, hours: int = HOURS) -> float | None:
    """Reference implementation of the D1 baseline. `None` when there is no full history.

    Returning `None` rather than `0.0` is deliberate: the prototype's `avg()` returns `[0,0]` when
    no in-range history exists, which silently turns "no history" into a `+0 %` readout
    (`model-audit.md` §3g). A missing baseline must be visibly missing.
    """
    vals = []
    for k in range(1, weeks + 1):
        dd = di - 7 * k
        if dd < 0 or dd >= days:
            continue
        vals.append(int(cnt[(ci * days + dd) * hours + h]))
    if len(vals) < weeks:
        return None
    return float(np.mean(vals))


def weekday_blind_baseline(cnt: np.ndarray, ci: int, di: int, h: int, days: int = DAYS,
                           window: int = 30, hours: int = HOURS) -> float | None:
    """The D1 *defect*, implemented so its size can be measured rather than asserted rhetorically."""
    lo = max(0, di - window)
    if lo >= di:
        return None
    return float(np.mean(cnt.reshape(-1, days, hours)[ci, lo:di, h]))


def measure_d1_gap(cnt: np.ndarray, codes: Sequence[str], days: int = DAYS,
                   hours: int = HOURS, sample_days: int = 120,
                   min_matched: float = 3.0) -> dict:
    """Quantify how far the weekday-blind baseline is from the matched one.

    Reported as the distribution of `blind / matched - 1` over every published code, all 24 hours
    and a uniform sample of days, plus the value split by weekday — which is where the bias is
    visible as a *pattern* rather than as noise.

    `min_matched` drops cells whose matched baseline is below 3 transactions: with a base of 1, a
    single extra transaction is a +100 % "gap" and the ratio is meaningless. Those cells are also
    exactly the ones the panel must refuse to print (AGENTS.md defect D4), so including them here
    would let the D4 population flatter the D1 measurement.
    """
    n_codes = len(codes)
    by_weekday: dict[int, list[float]] = {w: [] for w in range(1, 8)}
    step = max(1, (days - 35) // sample_days)
    worst = (0.0, None)
    skipped = 0
    for di in range(35, days, step):
        w = weekday_of(di)
        for ci in range(n_codes):
            for h in range(hours):
                m = matched_baseline(cnt, ci, di, h, days, hours=hours)
                b = weekday_blind_baseline(cnt, ci, di, h, days, hours=hours)
                if not m or m < min_matched or b is None:
                    skipped += 1
                    continue
                rel = b / m - 1.0
                by_weekday[w].append(rel)
                if abs(rel) > abs(worst[0]):
                    worst = (rel, {"code": codes[ci], "di": di, "hour": h})
    summary = {}
    for w, vals in by_weekday.items():
        if vals:
            arr = np.array(vals)
            summary[w] = {"n": len(vals), "mean": round(float(arr.mean()), 4),
                          "p05": round(float(np.percentile(arr, 5)), 4),
                          "p95": round(float(np.percentile(arr, 95)), 4)}
    return {"by_weekday": summary, "worst": [round(worst[0], 4), worst[1]],
            "min_matched": min_matched, "skipped_thin_cells": skipped}


def baseline_table(cnt: np.ndarray, codes: Sequence[str], days: int = DAYS,
                   hours: int = HOURS) -> dict:
    """Per-(code, weekday, hour) mean count over the whole period — the publishable fallback table.

    It is *not* the matched baseline (that is per-day); it is the weekday-and-hour profile the
    panel can draw before the cube finishes decoding, so the pre-load state shows real structure
    instead of invented numbers.
    """
    cube = cnt.reshape(len(codes), days, hours)
    out: dict[str, dict] = {}
    for ci, code in enumerate(codes):
        per_weekday = {}
        for w in range(1, 8):
            dis = [d for d in range(days) if weekday_of(d) == w]
            block = cube[ci][dis, :]                    # (n_days, 24)
            per_weekday[str(w)] = [round(float(v), 3) for v in block.mean(axis=0)]
        out[code] = per_weekday
    return out


def assert_weekday_index(cnt: np.ndarray, parquet_index: dict[int, float] | None = None,
                         days: int = DAYS, off_axis_rows: int = 0,
                         rhythm: np.ndarray | None = None) -> dict:
    """Assert the Sat/Mon extremes against the contract, and cube-vs-parquet agreement.

    The cube is keyed by *local* day; the parquet column is keyed by `purchase_date`. They differ
    only for the rows whose local date rolls past 2026-06-30 (3 rows, clamped back to day 545), so
    the agreement tolerance is `7 * off_axis_rows / total` rather than zero — an exact-equality
    test here would be a test of the clamp, not of the timezone conversion.
    """
    # `rhythm` is the exact CITY series when the released cube has suppressed cells removed.
    # The weekday shape is a city fact; measuring it on the released subset would describe the
    # areas we are allowed to show rather than the city.
    idx = weekday_index_from_cube(rhythm if rhythm is not None else cnt, days)
    sat, mon = idx[6], idx[1]
    assert abs(sat - EXPECTED_INDEX["saturday"]) <= INDEX_TOLERANCE, (
        f"Saturday index {sat} is not within ±{INDEX_TOLERANCE} of "
        f"{EXPECTED_INDEX['saturday']}")
    assert abs(mon - EXPECTED_INDEX["monday"]) <= INDEX_TOLERANCE, (
        f"Monday index {mon} is not within ±{INDEX_TOLERANCE} of {EXPECTED_INDEX['monday']}")
    if parquet_index is not None:
        total = float((rhythm if rhythm is not None else cnt).sum())
        tol = 7.0 * off_axis_rows / total + 1e-6 if off_axis_rows else 1e-6
        for w in range(1, 8):
            assert abs(parquet_index[w] - idx[w]) <= tol, (
                f"weekday {w}: cube says {idx[w]}, parquet says {parquet_index[w]} "
                f"(tolerance {tol:.2e} allows for {off_axis_rows} off-axis rows) — the local-day "
                "axis in cnt disagrees with the stored purchase_weekday_iso")
    return {"index": idx, "saturday": sat, "monday": mon,
            "expected": EXPECTED_INDEX, "tolerance": INDEX_TOLERANCE,
            "parquet_agreement": parquet_index is not None,
            "parquet_index": parquet_index, "off_axis_rows": off_axis_rows}


def build(repo_root: str | Path, agg: dict, cnt: np.ndarray,
          parquet_index: dict[int, float] | None = None,
          off_axis_rows: int = 0, rhythm: np.ndarray | None = None) -> tuple[dict, dict]:
    """Assemble `artifacts/baseline.json` and the console report."""
    codes = agg["codes"]
    check = assert_weekday_index(cnt, parquet_index, off_axis_rows=off_axis_rows, rhythm=rhythm)
    gap = measure_d1_gap(cnt, codes)
    doc = {
        "ver": 1,
        "generated": agg["generated"],
        "start": agg["start"],
        "days": agg["days"],
        "hours": agg["hours"],
        "estimand": (f"mean of the last {MATCHED_WEEKS} same-weekday occurrences of the same "
                     "local hour"),
        "defect": "D1",
        "why": ("A weekday-blind 30-day mean reads a Saturday ~52% high and a Monday ~28% low "
                "before any real deviation. The app must compute this baseline from cnt."),
        "weekdayIndex": {str(k): v for k, v in check["index"].items()},
        "d1Gap": {"byWeekday": {str(k): v for k, v in gap["by_weekday"].items()},
                  "worst": gap["worst"],
                  "note": "blind / matched - 1, over all published codes x 24 h x sampled days"},
        "profile": baseline_table(cnt, codes),
    }
    report = {"weekday_index": check, "d1_gap": gap}
    return doc, report


def write(doc: dict, path: str | Path) -> int:
    from pipeline.aggregate import write_json
    return write_json(doc, path)
