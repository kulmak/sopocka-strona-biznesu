#!/usr/bin/env python3
"""make_fixture_aggregate.py — a tiny SYNTHETIC aggregate.json for developing the panel
before pipeline/aggregate.py lands the real one.

It emits a file that satisfies contracts/aggregate.schema.json exactly, so every code path in
app/aggregate-loader.js is exercised for real. The numbers are INVENTED. The file name says so
(`aggregate.fixture.json`), source.rule_version says so, and the panel prints
"Dane testowe (fixture)" instead of "Dane rzeczywiste".

What it reproduces faithfully, because the panel's behaviour depends on it:
  * the contract's cell indexing (codes x days x hours, index 0 = EXCLUDED bucket)
  * the volume concentration measured in the parquet: 81-777 holds ~51% of all transactions
  * weekday index 1.514 (Sat) / 0.724 (Mon) - research/app-forensics.md D1
  * 38,443 sentinel-timecode rows (10.2%) landing in the EXCLUDED bucket, so D2 is exercised
  * the three contract presets, each passing all three privacy gates

Usage:
  python3 tools/make_fixture_aggregate.py                     # -> artifacts/aggregate.fixture.json
  python3 tools/make_fixture_aggregate.py --out /tmp/agg.json --seed 7
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import struct
import sys
from array import array

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "app", "data")

START = "2025-01-01"
DAYS = 546
HOURS = 24
ROWS = 378212
ZERO_TIMECODE = 38443          # measured: research/app-forensics.md D2
NON_SOPOT = 2527
NO_POSTCODE = 6431
EXCLUDED = ZERO_TIMECODE + NON_SOPOT + NO_POSTCODE

# Weekday multipliers, indexed Sunday..Saturday, normalised so their mean is 1.0.
# Anchored on the measured indices 1.514 (Sat) and 0.724 (Mon).
DOW_RAW = [0.95, 0.724, 0.80, 0.90, 1.00, 1.30, 1.514]
DOW_MEAN = sum(DOW_RAW) / 7.0
DOW = [v / DOW_MEAN for v in DOW_RAW]

# Restaurant hourly profile (MCC 5812): lunch and dinner peaks, quiet 03:00-06:00.
HOUR_SHAPE = [1.6, 0.7, 0.3, 0.15, 0.1, 0.2, 0.8, 2.0, 3.4, 4.2, 5.0, 7.4,
              11.0, 12.6, 9.0, 6.4, 6.2, 8.6, 12.4, 14.4, 12.0, 8.0, 4.6, 2.4]

PRESET_CODES = {"81-777", "81-759", "81-720", "81-706", "81-805"}


def day_shapes():
    """weekday for day index di (0 == START)."""
    import datetime
    d0 = datetime.date.fromisoformat(START)
    return [(d0 + datetime.timedelta(days=i)).weekday() for i in range(DAYS)]


def iso_day(di):
    import datetime
    return (datetime.date.fromisoformat(START) + datetime.timedelta(days=di)).isoformat()


def load_sectors():
    with open(os.path.join(DATA, "sopot-sectors.geojson"), encoding="utf-8") as fh:
        return json.load(fh)["features"]


def load_sea_km():
    path = os.path.join(DATA, "sea-km.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return {k: v["sea_km"] for k, v in json.load(fh)["codes"].items()}


def fnv(s):
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def h01(s):
    return fnv(s) / 0xFFFFFFFF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "artifacts", "aggregate.fixture.json"))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--codes", type=int, default=40, help="postcode sectors to synthesise (excl. bucket 0)")
    args = ap.parse_args()

    feats = load_sectors()
    sea = load_sea_km()
    # deterministic ordering: presets first, then by hash
    order = sorted(feats, key=lambda f: (f["properties"]["postcode"] not in PRESET_CODES,
                                         h01(f["properties"]["postcode"] + str(args.seed))))
    chosen = order[: max(args.codes, len(PRESET_CODES))]
    codes = ["—"] + [f["properties"]["postcode"] for f in chosen]
    meta_by_code = {f["properties"]["postcode"]: f["properties"] for f in chosen}
    n_codes = len(codes)

    wd = day_shapes()

    # ---- volume weights: 81-777 ~51.1% of the city, 81-759 ~9.4%, long tail for the rest
    weights = {}
    for i, pc in enumerate(codes[1:], start=1):
        base = 0.511 if pc == "81-777" else 0.094 if pc == "81-759" else 0.020 if pc in PRESET_CODES else 0.0
        if base == 0.0:
            base = 0.004 + 0.016 * h01(pc + "w" + str(args.seed))
        weights[i] = base
    tot_w = sum(weights.values())
    for i in weights:
        weights[i] /= tot_w

    n_cells = n_codes * DAYS * HOURS
    cnt = array("H", bytes(2 * n_cells))
    amt = array("H", bytes(2 * n_cells))

    # a handful of event-driven evening spikes so the hero and the event cards move
    EVENTS = {
        "2026-05-01": 1.55, "2026-05-02": 1.45, "2026-05-03": 1.30,
        "2026-05-09": 1.25, "2026-05-16": 1.20, "2026-05-23": 1.18,
        "2026-05-30": 1.28, "2026-05-31": 1.22,
        "2026-06-05": 1.16, "2026-06-12": 1.18, "2026-06-13": 1.20, "2026-06-14": 1.15,
        "2026-06-20": 1.62, "2026-06-21": 1.48, "2026-06-27": 1.30, "2026-06-28": 1.34,
    }

    body = ROWS - EXCLUDED
    shape_sum = sum(HOUR_SHAPE)
    day_totals = []
    for di in range(DAYS):
        seas = 1.0 + 0.38 * math.sin(2 * math.pi * (di - 100) / 365.0)
        day_totals.append(DOW[wd[di]] * seas)
    norm = body / sum(day_totals)

    for di in range(DAYS):
        k = iso_day(di)
        ev = EVENTS.get(k, 1.0)
        day_total = day_totals[di] * norm
        for ci in range(1, n_codes):
            pc = codes[ci]
            share = weights[ci] * day_total
            # 81-777 carries the event uplift; the tail barely notices
            ev_here = 1.0 + (ev - 1.0) * (1.0 if pc == "81-777" else 0.35 if pc == "81-759" else 0.1)
            jitter = 0.88 + 0.24 * h01(pc + k + "j")
            col = share * ev_here * jitter
            for h in range(HOURS):
                w = HOUR_SHAPE[h] / shape_sum
                # events bite hardest in the evening
                if ev != 1.0 and 18 <= h <= 22:
                    w *= 1.0 + (ev_here - 1.0) * 0.8
                v = int(round(col * w * 24 / 24))
                if v <= 0:
                    continue
                idx = (ci * DAYS + di) * HOURS + h
                cnt[idx] = v
                ticket = 62 + 46 * h01(pc + k + str(h) + "t")
                amt[idx] = max(1, int(round(v * ticket)))

    # ---- EXCLUDED bucket (index 0): the 38,443 sentinels pile into the small hours,
    #      the foreign and missing postcodes spread evenly. Excluded from every hourly curve.
    ex_shape = [3, 26, 4, 1, 1, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3]
    es = sum(ex_shape)
    for di in range(DAYS):
        for h in range(HOURS):
            v = int(round(ZERO_TIMECODE * ex_shape[h] / es / DAYS))
            if v:
                cnt[(0 * DAYS + di) * HOURS + h] = v
                amt[(0 * DAYS + di) * HOURS + h] = v * 71
    spread = NON_SOPOT + NO_POSTCODE
    for di in range(DAYS):
        per = spread // DAYS
        for h in (11, 12, 13, 19, 20):
            cnt[(0 * DAYS + di) * HOURS + h] += per // 5
            amt[(0 * DAYS + di) * HOURS + h] += (per // 5) * 88
    # integer rounding drifts; reconcile the EXCLUDED bucket to its exact total (largest remainder)
    bucket = sum(cnt[0:DAYS * HOURS])
    need = EXCLUDED - bucket
    i = 0
    while need != 0:
        idx = i % (DAYS * HOURS)
        if need > 0:
            cnt[idx] += 1
            amt[idx] += 71
            need -= 1
        elif cnt[idx] > 0:
            cnt[idx] -= 1
            amt[idx] = max(0, amt[idx] - 71)
            need += 1
        i += 1

    # ---- fix up the total to hit `body` exactly (invariant 1) and keep max cell < 65535
    have = 0
    for ci in range(1, n_codes):
        off = ci * DAYS * HOURS
        for i in range(off, off + DAYS * HOURS):
            have += cnt[i]
    drift = body - have
    step = 1 if drift > 0 else -1
    i = 0
    while drift != 0 and i < DAYS * HOURS * n_codes:
        ci = 1 + (i // (DAYS * HOURS)) % (n_codes - 1)
        idx = ci * DAYS * HOURS + (i % (DAYS * HOURS))
        if step > 0:
            cnt[idx] += 1
            amt[idx] += 81
            drift -= 1
        elif cnt[idx] > 0:
            cnt[idx] -= 1
            amt[idx] = max(0, amt[idx] - 81)
            drift += 1
        i += 1
    assert drift == 0, "could not reconcile the row total"
    assert sum(cnt[0:DAYS * HOURS]) == EXCLUDED, "EXCLUDED bucket drifted"

    max_cnt = max(cnt)
    max_amt = max(amt)
    amt_scale = 1.0
    if max_amt >= 65535:
        amt_scale = math.ceil((max_amt + 1) / 65000.0)
        for i in range(len(amt)):
            amt[i] = int(amt[i] // amt_scale)
    assert max_cnt < 65535, "Uint16 overflow in cnt"

    # ---- nationality: buckets PL DE SE NO GB OTHER, city-wide only (invariant 4)
    nat = array("I", bytes(4 * DAYS * HOURS * 6))
    nat_share = [0.831, 0.061, 0.028, 0.021, 0.024, 0.035]
    for di in range(DAYS):
        for h in range(HOURS):
            city = 0
            for ci in range(n_codes):
                city += cnt[(ci * DAYS + di) * HOURS + h]
            if not city:
                continue
            left = city
            for b in range(6):
                v = int(round(city * nat_share[b])) if b < 5 else left
                v = max(0, min(v, left))
                nat[(di * HOURS + h) * 6 + b] = v
                left -= v
            if left:
                nat[(di * HOURS + h) * 6 + 0] += left

    sum_cnt = sum(cnt)
    sum_nat = sum(nat)
    assert sum_cnt == ROWS, f"sum(cnt)={sum_cnt} != rows={ROWS}"
    assert sum_nat == ROWS, f"sum(nat)={sum_nat} != rows={ROWS}"

    # ---- codeMeta
    txn_per_code = {}
    for ci in range(1, n_codes):
        off = ci * DAYS * HOURS
        txn_per_code[codes[ci]] = sum(cnt[off:off + DAYS * HOURS])

    code_meta = {}
    for ci in range(1, n_codes):
        pc = codes[ci]
        p = meta_by_code[pc]
        txn = txn_per_code[pc]
        merchants = 241 if pc == "81-777" else 39 if pc == "81-759" else 25 if pc == "81-706" else 16 if pc == "81-720" else 12 if pc == "81-805" else max(1, int(2 + 40 * h01(pc + "m")))
        n_cards = max(1, int(txn / 2.1))
        top1 = 0.1144 if pc == "81-777" else 0.18 + 0.5 * h01(pc + "s")
        top1 = round(min(0.95, top1), 4)
        g1 = n_cards >= 30
        g2 = merchants >= 3
        g3 = top1 <= 0.75
        code_meta[pc] = {
            "name": (p.get("streets") or pc).split("; ")[0],
            "merchants": merchants,
            "transactions": txn,
            "centroid": [round(p["label"][1], 6), round(p["label"][0], 6)],
            "polygonConfidence": "observed" if p.get("support100_pct", 0) >= 90 else "inferred",
            "gates": {"g1_cards": g1, "g2_merchants": g2, "g3_share": g3, "all": g1 and g2 and g3},
            "nCards": n_cards,
            "top1Share": top1,
            "seaKm": sea.get(pc, p.get("sea_km")),
        }
    # the presets must pass every gate (contract invariant 8 and the loader rejects otherwise)
    for pc in PRESET_CODES:
        if pc in code_meta:
            m = code_meta[pc]
            m["merchants"] = max(m["merchants"], 12)
            m["nCards"] = max(m["nCards"], 4000)
            m["top1Share"] = min(m["top1Share"], 0.34)
            m["gates"] = {"g1_cards": True, "g2_merchants": True, "g3_share": True, "all": True}

    # ---- presets, exactly the three in contracts/AGGREGATE.md
    def centroid(pc):
        return code_meta[pc]["centroid"]
    presets = [
        {"id": "molo", "code": "81-777", "name": "Restauracja przy Molo",
         "lat": centroid("81-777")[0], "lng": centroid("81-777")[1],
         "why": "241 merchantów, 51,1% wolumenu"},
        {"id": "monciak", "code": "81-759", "name": "Bistro na Monciaku",
         "lat": centroid("81-759")[0], "lng": centroid("81-759")[1],
         "why": "39 merchantów, pełne 18 miesięcy"},
        {"id": "przystan", "code": "81-777", "name": "Bar na plaży",
         "lat": round(centroid("81-777")[0] - 0.0022, 6), "lng": round(centroid("81-777")[1] + 0.0016, 6),
         "why": "drugi lokal w tej samej strefie"},
    ]

    # ---- city calendar listings (fixture text, clearly generic)
    events_by_day = {}
    for k, boost in EVENTS.items():
        titles = {
            "2026-05-01": ["Majówka na Molo", "Targ rzemieślniczy, Plac Zdrojowy"],
            "2026-05-02": ["Majówka na Molo"],
            "2026-05-03": ["Koncert plenerowy, Skwer Kuracyjny"],
            "2026-05-09": ["Bieg Sopocki 10 km"],
            "2026-05-16": ["Noc Muzeów"],
            "2026-05-23": ["Koncert, Ergo Arena"],
            "2026-05-30": ["Festiwal Rzemiosła, Bohaterów Monte Cassino"],
            "2026-05-31": ["Festiwal Rzemiosła, Bohaterów Monte Cassino"],
            "2026-06-05": ["Targ Śniadaniowy — edycja wieczorna"],
            "2026-06-12": ["Festiwal Filmowy"],
            "2026-06-13": ["Festiwal Filmowy"],
            "2026-06-14": ["Festiwal Filmowy"],
            "2026-06-20": ["Koncert letni na Molo"],
            "2026-06-21": ["Noc Świętojańska"],
            "2026-06-27": ["Turniej siatkówki plażowej"],
            "2026-06-28": ["Jazz na Plaży"],
        }.get(k, [])
        if titles:
            events_by_day[k] = titles

    def b64(a):
        return base64.b64encode(a.tobytes()).decode("ascii")

    agg = {
        "ver": 4,
        "generated": "FIXTURE",
        "source": {
            "files": ["tools/make_fixture_aggregate.py"],
            "sha256": [hashlib.sha256(b"fixture").hexdigest()],
            "rule_version": "FIXTURE-synthetic-not-real-v1",
        },
        "start": START,
        "days": DAYS,
        "hours": HOURS,
        "codes": codes,
        "codeMeta": code_meta,
        "cnt": b64(cnt),
        "amt": b64(amt),
        "amtScale": amt_scale,
        "nat": b64(nat),
        "eventsByDay": events_by_day,
        "rows": ROWS,
        "excluded": {"zeroTimecode": ZERO_TIMECODE, "nonSopotPostcode": NON_SOPOT, "noPostcode": NO_POSTCODE},
        "presets": presets,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(agg, fh, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(args.out)
    print(f"wrote {args.out}  ({size/1048576:.2f} MiB)")
    print(f"  codes {n_codes} (index 0 = EXCLUDED, {sum(cnt[0:DAYS*HOURS])} rows)"
          f" · days {DAYS} · max cnt cell {max_cnt} · amtScale {amt_scale}")
    print(f"  sum(cnt)={sum_cnt} == rows={ROWS}  ·  sum(nat)={sum_nat}")
    print(f"  81-777 share {txn_per_code.get('81-777', 0)/ROWS:.1%} · 81-759 {txn_per_code.get('81-759', 0)/ROWS:.1%}")
    print("  FIXTURE — invented numbers. Not a substitute for artifacts/aggregate.json.")


if __name__ == "__main__":
    sys.exit(main())
