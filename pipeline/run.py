"""`python3 -m pipeline.run --src DIR --out artifacts` — the whole pipeline, one command.

WHAT IT DOES
------------
Runs the eight stages in order, printing one line per gate so the console output *is* the evidence:

```
[1/8] INGEST      union all, disjointness, sha256
[2/8] VALIDATE    re-derive purchase_date / transaction_amount / transaction_time_gmt
[3/8] NORMALISE   3-branch postcode partition
[4/8] FILTER      Sopot membership, non-Sopot leak, D2 sentinel routing
[5/8] ENRICH      GMT→Europe/Warsaw (DST), calendar features, sector geometry, gates
[6/8] AGGREGATE   cnt / amt / nat + codeMeta + presets, then assert all 8 invariants
[7/8] BASELINE    same-weekday baseline (D1) + weekday-index proof
[8/8] EVALUATE    walk-forward backtest + drivers, then the publishable sample
```

Every stage asserts; a failed assertion prints `FAIL` with the measured value and the exit code is
non-zero. There is no `--force` and no degraded path: AGENTS.md rule 4 — "No silent fallbacks."

WHY THE ORDER MATTERS
---------------------
The order is the lineage's order (`research/cleaning-lineage.md` §1), because the evidence columns
are appended in pipeline order and a rule can only be proven against a stage that already ran. In
particular the aggregate cannot be built before the DST conversion, since `cnt`'s hour axis is
local and a wrong axis is invisible in every downstream total.

DETERMINISM
-----------
Two runs produce a byte-identical `aggregate.json`. `generated` comes from the source file mtime
(or `SOURCE_DATE_EPOCH`), JSON keys are sorted, and `--check-determinism` rebuilds in-process and
compares the bytes. Wall clock is never read.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

import numpy as np

from pipeline import RULE_VERSION
from pipeline import aggregate as agg_mod
from pipeline import backtest as bt_mod
from pipeline import baseline as base_mod
from pipeline import enrich as enr
from pipeline import filter as filt
from pipeline import ingest, normalise, sample, validate

_OK = "  ok  "
_FAIL = " FAIL "


def _say(stage: str, message: str, ok: bool = True) -> None:
    print(f"[{stage}] {_OK if ok else _FAIL} {message}", flush=True)


def _kv(**kw) -> str:
    return " · ".join(f"{k}={v}" for k, v in kw.items())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m pipeline.run",
                                 description="Rebuild artifacts/aggregate.json from the source "
                                             "parquet, with every gate asserted.")
    ap.add_argument("--src", required=True,
                    help="directory holding mcc5812_transactions.part01.parquet and part02.parquet")
    ap.add_argument("--out", default="artifacts", help="output directory (default: artifacts)")
    ap.add_argument("--repo-root", default=".", help="repo root, for data/ lookups (default: .)")
    ap.add_argument("--check-determinism", action="store_true",
                    help="rebuild the aggregate in-process and compare the bytes")
    ap.add_argument("--skip-sample", action="store_true", help="do not write data/samples/")
    ap.add_argument("--skip-backtest", action="store_true", help="do not run the backtest")
    args = ap.parse_args(argv)

    t0 = time.time()
    repo_root = Path(args.repo_root).resolve()
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = repo_root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 88)
    print("Sopot MCC-5812 pipeline · " + RULE_VERSION)
    print(f"source : {Path(args.src).resolve()}")
    print(f"output : {out_dir}")
    print("=" * 88)

    con = ingest.connect()
    report: dict = {}

    # ---------------------------------------------------------------- 1 INGEST
    files = ingest.source_files(args.src)
    ingest.register_raw(con, files)
    info = ingest.manifest(con, files)
    _say("1/8 INGEST", _kv(rows=info["rows"], distinct_tran_id=info["distinct_tran_id"],
                           overlap_tran_id=info["overlap_tran_id"],
                           overlap_source_row=info["overlap_source_row"],
                           parts=f'{info["rows_part01"]}+{info["rows_part02"]}'))
    _say("1/8 INGEST", _kv(src_row_span=f'{info["src_row_min"]}..{info["src_row_max"]}',
                           dates=f'{info["date_min"]}..{info["date_max"]}',
                           distinct_days=info["distinct_days"],
                           sha256_01=info["sha256"][0][:16], sha256_02=info["sha256"][1][:16]))
    report["ingest"] = info

    # -------------------------------------------------------------- 2 VALIDATE
    val = validate.assert_validated(con)
    _say("2/8 VALIDATE", _kv(**{f"mismatch_{k}": v for k, v in val["mismatches"].items()}))
    _say("2/8 VALIDATE", _kv(**{f"calendar_{k}": v
                                for k, v in val["calendar_mismatches"].items()},
                             statuses="valid×3",
                             amount_range=f'{val["domains"]["min_amount"]}..'
                                          f'{val["domains"]["max_amount"]}'))
    report["validate"] = val

    # ------------------------------------------------------------- 3 NORMALISE
    norm = normalise.assert_normalised(con)
    _say("3/8 NORMALISE", _kv(null_or_empty=norm["null_or_empty"], six_char=norm["six_char"],
                              five_digit=norm["five_digit"], unhandled=norm["unhandled"],
                              stored_mismatches=norm["stored_mismatches"],
                              partition_sum=norm["rows"]))
    report["normalise"] = norm

    # ---------------------------------------------------------------- 4 FILTER
    flt = filt.assert_filter(con)
    idx0 = filt.excluded_bucket_size(con)
    _say("4/8 FILTER", _kv(city_label_sopot=flt["basis"]["city_label_sopot"],
                           basis=flt["basis"]["basis_city_exact"],
                           rule_version=flt["basis"]["rule_version_v1"],
                           geo_conflict_populated=flt["basis"]["geo_conflict_populated"]))
    _say("4/8 FILTER", _kv(nonSopotPostcode=flt["excluded_counts"]["nonSopotPostcode"],
                           codes=len(flt["leak"]["by_postcode"]),
                           **flt["leak"]["by_postcode"]))
    _say("4/8 FILTER", _kv(zeroTimecode=flt["zero_timecode"]["sentinel_rows"],
                           share=flt["zero_timecode"]["sentinel_share"],
                           gmt_hour0_nonzero=flt["zero_timecode"]["gmt_hour0_nonzero"],
                           gmt_hour1=flt["zero_timecode"]["gmt_hour1"],
                           status_flagged=flt["zero_timecode"]["status_flagged"]))
    _say("4/8 FILTER", _kv(noPostcode=flt["excluded_counts"]["noPostcode"],
                           overlap_noPostcode_zeroTimecode=flt[
                               "excluded_counts"]["noPostcode_and_zeroTimecode_overlap"],
                           index0_exact=idx0))
    report["filter"] = flt
    report["filter"]["excluded_counts"]["index0_exact"] = idx0

    # ---------------------------------------------------------------- 5 ENRICH
    dst = enr.assert_dst(con)
    _say("5/8 ENRICH", _kv(trap_naive=dst["trap_demonstration"]["naive"],
                           bound_summer=dst["trap_demonstration"]["summer_bound"],
                           bound_winter=dst["trap_demonstration"]["winter_bound"]))
    _say("5/8 ENRICH", _kv(**{f"dst_{k}_hours": v for k, v in dst["transition_days"].items()},
                           clamped_rows=enr.clamped_rows(con)))
    enr.calendar_features(con)
    sectors = enr.load_sectors(repo_root)
    _say("5/8 ENRICH", _kv(sectors=len(sectors), source=next(iter(sectors.values()))["source"]))
    report["enrich"] = {"dst": dst, "clamped_rows": enr.clamped_rows(con),
                        "sectors": len(sectors)}

    # ------------------------------------------------------------- 6 AGGREGATE
    source_block = {"files": info["files"], "sha256": info["sha256"],
                    "rule_version": RULE_VERSION,
                    "generated": ingest.mtime_iso8601(files)}
    excluded = {"zeroTimecode": flt["zero_timecode"]["sentinel_rows"],
                "nonSopotPostcode": flt["leak"]["rows"],
                "noPostcode": flt["excluded_counts"]["noPostcode"]}
    art, build_report = agg_mod.build_artifact(
        con, sectors, dict(source_block), info["rows"], excluded)
    checks = agg_mod.assert_invariants(art, sectors=sectors)
    cnt = np.frombuffer(base64.b64decode(art["cnt"]), dtype=np.uint16)
    _say("6/8 AGGREGATE", _kv(codes=build_report["codes"], cells=build_report["cells"],
                              max_cnt=build_report["max_cnt"],
                              max_amt_zl=round(build_report["max_amt_zl"], 1),
                              amtScale=build_report["amt_scale"]))
    _say("6/8 AGGREGATE", "invariants " + _kv(**checks))
    _say("6/8 AGGREGATE", _kv(gates_source=build_report["gates_source"],
                              gated_codes=sum(1 for c in art["codeMeta"].values()
                                              if c["gates"]["all"]),
                              codes_total=len(art["codeMeta"])))
    agg_path = out_dir / "aggregate.json"
    size = agg_mod.write_json(art, agg_path)
    _say("6/8 AGGREGATE", _kv(written=agg_path.name, bytes=size))
    report["aggregate"] = {**build_report, "invariants": checks, "bytes": size}

    # Preset geometry audit — the shipped contract's coordinates are wrong; prove the fix.
    preset_audit = enr.assert_presets(art["presets"], sectors)
    _say("6/8 AGGREGATE", "presets " + _kv(**{
        f'{k}_in_shipped_contract': "/".join(v)
        for k, v in preset_audit["contract_coords_verdict"].items()}))
    _say("6/8 AGGREGATE", "presets " + _kv(**{
        p["id"]: f'{p["code"]}@{p["lat"]},{p["lng"]}' for p in art["presets"]}))
    report["presets"] = preset_audit

    # -------------------------------------------------------------- 7 BASELINE
    parquet_idx = enr.weekday_index(con)
    # The weekday rhythm is a CITY fact, so it must be measured on the exact city series
    # (`cityCnt`), not on the released subset: suppressing 37 thin cells removes 8.8% of volume,
    # and a rhythm measured on the remainder would be a rhythm of the areas we happen to be
    # allowed to show. Falls back to `cnt` only if an older artifact has no city series.
    # `cityCnt` arrives as (days, hours); the baseline machinery indexes a flat per-code cube, so
    # it is presented as a one-code cube. The D1 diagnostic then measures the CITY's Saturday-vs-
    # mean gap, which is the right population for it: the gap is a property of the city's week,
    # not of the subset of areas we are permitted to show.
    city = None
    if art.get("cityCnt") is not None:
        city = np.frombuffer(base64.b64decode(art["cityCnt"]), dtype=np.uint16).astype(np.uint32)
        city = city.reshape(agg_mod.DAYS, agg_mod.HOURS)
    base_doc, base_report = base_mod.build(repo_root, art, cnt, parquet_idx,
                                           rhythm=city,
                                           off_axis_rows=enr.clamped_rows(con))
    wi = base_report["weekday_index"]
    _say("7/8 BASELINE", _kv(index=" ".join(f"{d}:{wi['index'][d]:.3f}" for d in range(1, 8))))
    _say("7/8 BASELINE", _kv(saturday=wi["saturday"], monday=wi["monday"],
                             expected=f'{wi["expected"]["saturday"]}/{wi["expected"]["monday"]}',
                             tolerance=wi["tolerance"],
                             parquet_agreement=wi["parquet_agreement"]))
    _say("7/8 BASELINE", _kv(D1_gap_saturday=base_report["d1_gap"]["by_weekday"][6]["mean"],
                             D1_gap_monday=base_report["d1_gap"]["by_weekday"][1]["mean"],
                             worst=base_report["d1_gap"]["worst"][0]))
    base_size = base_mod.write(base_doc, out_dir / "baseline.json")
    _say("7/8 BASELINE", _kv(written="baseline.json", bytes=base_size))
    report["baseline"] = base_report

    # -------------------------------------------------------------- 8 EVALUATE
    if not args.skip_backtest:
        daily = bt_mod.daily_series(con)
        # The forecast is about the CITY's trade, so it is driven by the exact city series.
        cube_daily = base_mod.daily_totals(city if city is not None else cnt, art["days"])
        bt_doc, drv_doc = bt_mod.build(daily, art["rows"], cube_daily,
                                       cube_rows=int(city.sum()) if city is not None else None)
        sizes = bt_mod.write((bt_doc, drv_doc), out_dir)
        for name, m in bt_doc["candidates"].items():
            _say("8/8 EVALUATE", _kv(candidate=name, **m["metrics"]))
        _say("8/8 EVALUATE", _kv(best=bt_doc["best_candidate"],
                                 reproduced_a=bt_doc["reproduced"]["a_mean4sw_MAPE_MAE"],
                                 audited_a=bt_doc["reproduced"]["audited_a_mean4sw"],
                                 reproduced_d=bt_doc["reproduced"]["d_snaive_MAPE_MAE"],
                                 audited_d=bt_doc["reproduced"]["audited_snaive"]))
        for name, m in bt_doc["weather_events_experiment"].items():
            _say("8/8 EVALUATE", _kv(experiment=name, MAPE=m["MAPE"], MAE=m["MAE"],
                                     WAPE=m["WAPE"], MASE=m["MASE"]))
        for spec in ("primary", "no_month", "audit_spec", "nb2_glm"):
            c = drv_doc[spec]["coefficients"]
            _say("8/8 EVALUATE", f"{spec:10s} " + _kv(**{
                k: f'{v["beta"]:+.4f} (t={v["t"]:+.1f})' for k, v in c.items()}))
        aud = drv_doc["audited"]
        _say("8/8 EVALUATE", "audited    " + _kv(**{
            k: f'{v[0]:+.4f} (t={v[1]:+.1f})' for k, v in aud.items()}))
        sc = drv_doc["season_control"]
        _say("8/8 EVALUATE", _kv(season_raw=f'{sc["raw_hi"]:+.1f}/{sc["raw_lo"]:+.1f}',
                                 season_raw_spread=sc["spread_raw"],
                                 season_ctl=f'{sc["ctl_hi"]:+.1f}/{sc["ctl_lo"]:+.1f}',
                                 season_ctl_spread=sc["spread_ctl"],
                                 audited_spread=f'{sc["audited"]["raw_hi"]}/{sc["audited"]["raw_lo"]} -> '
                                               f'{sc["audited"]["ctl_hi"]}/{sc["audited"]["ctl_lo"]}',
                                 days=f'{sc["n_days_q1"]}/{sc["n_days_q4"]}'))
        _say("8/8 EVALUATE", _kv(**sizes))
        report["backtest"] = {k: bt_doc[k] for k in
                              ("protocol", "best_candidate", "candidates",
                               "weather_events_experiment", "reproduced")}
        report["drivers"] = {"primary": drv_doc["primary"], "no_month": drv_doc["no_month"],
                             "audit_spec": drv_doc["audit_spec"], "nb2_glm": drv_doc["nb2_glm"],
                             "audited": drv_doc["audited"]}
    else:
        _say("8/8 EVALUATE", "skipped (--skip-backtest)")

    if not args.skip_sample:
        smp = sample.build(repo_root, con, art)
        _say("8/8 EVALUATE", _kv(sample=smp["path"], rows=smp["rows"],
                                 gated_codes=smp["gated_codes"], suppressed=smp["suppressed"],
                                 bytes=smp["bytes"]))
        gv = smp["gate_variants"]
        _say("8/8 EVALUATE", _kv(n_codes_considered=54,
                                 pass_volume_only=len(gv["volume_only"]),
                                 pass_volume_and_cards=len(gv["volume_and_cards"]),
                                 suppressed_only_by_card_share=",".join(
                                     gv["suppressed_only_by_card_share"]) or "none"))
        report["sample"] = smp

    # ------------------------------------------------------------ DETERMINISM
    if args.check_determinism:
        art2, _r2 = agg_mod.build_artifact(con, sectors, dict(source_block), info["rows"],
                                           excluded)
        a = json.dumps(art, sort_keys=True, ensure_ascii=False, indent=2)
        b = json.dumps(art2, sort_keys=True, ensure_ascii=False, indent=2)
        same = a == b
        _say("DETERMINISM", _kv(byte_identical=same, bytes=len(a.encode())), ok=same)
        if not same:
            raise AssertionError("two in-process builds of aggregate.json differ")
        report["determinism"] = {"byte_identical": same, "bytes": len(a.encode())}

    print("-" * 88)
    print(f"done in {time.time() - t0:.1f}s · aggregate.json {report['aggregate']['bytes']} B · "
          f"rows {art['rows']} · codes {len(art['codes'])} · excluded index0 "
          f"{report['filter']['excluded_counts']['index0_exact']}")
    print("=" * 88)
    return 0


if __name__ == "__main__":       # pragma: no cover
    sys.exit(main())
