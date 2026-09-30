#!/usr/bin/env python3
"""Generate every figure the deck uses, as SVG, from the transaction parquet.

Why a script and not hand-drawn art: the deck must introduce NO number that is not produced by
a command (AGENTS.md rule 2). Each function here states its own SQL, writes one SVG, and prints
the numbers it drew — so the deck's slide numbers can be copied from this script's stdout.

Usage:
    python3 tools/figures.py                 # -> docs/deck/assets/figures/*.svg
    python3 tools/figures.py --print-values  # only print the numbers, draw nothing

Expected output (2026-09-30, 378,212 rows, MCC 5812):
    hourly_profile.svg   peak hour 14, 45.8% of trade in 11:00-15:00
    zero_timecode.svg    phantom 02:00 spike when the '000000' sentinel is included
    season_control.svg   raw event spread 59.8pp -> 9.0pp after month x weekday control
    privacy_funnel.svg   62 postcodes -> 54 (cards) -> 25 (merchants) -> 18 (all three); 90.7% of volume
"""
from __future__ import annotations

import argparse
import pathlib

import duckdb

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIGS = ROOT / "docs" / "deck" / "assets" / "figures"
SRC = "/Users/kulma/Downloads"
PARTS = f"['{SRC}/mcc5812_transactions.part01.parquet','{SRC}/mcc5812_transactions.part02.parquet']"

# The reconciled token set. Amber = money moving. Teal = the service. No third hue in the data layer.
INK, INK2, DIM = "#F5F3EE", "#B9C0CC", "#55637A"
AMBER, TEAL, GROUND = "#FFB84D", "#21C7B7", "#0B1220"
LINE = "rgba(245,243,238,0.28)"


def con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


def hourly_profile(c: duckdb.DuckDBPyConnection) -> tuple[list[int], int, float]:
    """Local hour histogram, DST-correct, sentinel rows excluded.

    GMT -> Europe/Warsaw via ICU on a UTC-bound timestamp. The trap this avoids: binding a
    naive timestamp silently no-ops, which is how the 10.2% '000000' sentinel became a
    phantom 02:00 surge in the original panel.
    """
    rows = c.execute(f"""
        select date_part('hour', timezone('Europe/Warsaw',
                   (purchase_date + transaction_time_gmt)::TIMESTAMP AT TIME ZONE 'UTC'))::int h,
               count(*) n
        from read_parquet({PARTS})
        where transaction_time_gmt is not null and tran_id_gmt_tm <> '000000'
        group by 1 order by 1
    """).fetchall()
    counts = [0] * 24
    for h, n in rows:
        counts[int(h) % 24] = int(n)
    total = sum(counts)
    lunch = sum(counts[11:16])
    return counts, max(range(24), key=lambda h: counts[h]), 100.0 * lunch / total


def hourly_with_sentinel(c: duckdb.DuckDBPyConnection) -> list[int]:
    """Same histogram but keeping the '000000' rows — this is defect D2 made visible."""
    rows = c.execute(f"""
        select date_part('hour', timezone('Europe/Warsaw',
                   (purchase_date + transaction_time_gmt)::TIMESTAMP AT TIME ZONE 'UTC'))::int h,
               count(*) n
        from read_parquet({PARTS})
        where transaction_time_gmt is not null
        group by 1 order by 1
    """).fetchall()
    counts = [0] * 24
    for h, n in rows:
        counts[int(h) % 24] = int(n)
    return counts


# An <img>-referenced SVG is an ISOLATED document: the page's @font-face never reaches it,
# so without this block every label silently falls back to Times-Roman. Paths are relative to
# the SVG's own location.
FACE = """<style>
@font-face{font-family:'Inter';src:url('../fonts/inter-0.woff2') format('woff2');font-weight:400}
@font-face{font-family:'Inter';src:url('../fonts/inter-1.woff2') format('woff2');font-weight:500}
@font-face{font-family:'JetBrains Mono';src:url('../fonts/jetbrains-mono-0.woff2') format('woff2');font-weight:500}
</style>"""

# ---------------------------------------------------------------- drawing helpers

def _scale(vals: list[float], lo: float, hi: float, out_lo: float, out_hi: float):
    span = (hi - lo) or 1.0
    return [out_lo + (v - lo) / span * (out_hi - out_lo) for v in vals]


def profile_svg(counts: list[int], peak: int, lunch_share: float) -> str:
    W, H = 1180, 430
    L, R, T, B = 64, 24, 40, 58
    n = 24
    bw = (W - L - R) / n
    top = max(counts) or 1
    bars = []
    for h, v in enumerate(counts):
        hgt = (v / top) * (H - T - B)
        x = L + h * bw + 1.5
        y = H - B - hgt
        is_peak = h == peak
        fill = AMBER if is_peak else TEAL
        op = "1" if is_peak else "0.55"
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw-3:.1f}" height="{hgt:.1f}" '
                    f'fill="{fill}" opacity="{op}" rx="1.5"/>')
    # the 11:00-15:00 window the headline names
    x0, x1 = L + 11 * bw, L + 16 * bw
    span = (f'<rect x="{x0:.1f}" y="{T-14}" width="{x1-x0:.1f}" height="{H-T-B+14:.1f}" '
            f'fill="{AMBER}" opacity="0.07"/>'
            f'<line x1="{x0:.1f}" y1="{T-14}" x2="{x0:.1f}" y2="{H-B}" stroke="{AMBER}" opacity="0.35"/>'
            f'<line x1="{x1:.1f}" y1="{T-14}" x2="{x1:.1f}" y2="{H-B}" stroke="{AMBER}" opacity="0.35"/>')
    ticks = "".join(
        f'<text x="{L + h*bw + bw/2:.1f}" y="{H-B+24}" fill="{DIM}" font-size="17" '
        f'text-anchor="middle" font-family="JetBrains Mono">{h:02d}</text>' for h in range(0, 24, 2))
    grid = "".join(f'<line x1="{L}" y1="{H-B-(f)*(H-T-B)}" x2="{W-R}" y2="{H-B-(f)*(H-T-B)}" '
                   f'stroke="{LINE}" stroke-width="0.5"/>' for f in (0.25, 0.5, 0.75))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
            f'{FACE}'
            f'<rect width="{W}" height="{H}" fill="{GROUND}"/>{grid}{span}{"".join(bars)}{ticks}'
            f'<text x="{L}" y="{T-20}" fill="{INK2}" font-size="18" font-family="Inter">'
            f'Transakcje MCC 5812 wg godziny (czas polski)</text>'
            f'<text x="{x0+6:.1f}" y="{T-20}" fill="{AMBER}" font-size="17" font-family="JetBrains Mono">'
            f'{lunch_share:.1f}% w godz. 11-15</text>'
            f'<text x="{W-R}" y="{T-20}" fill="{AMBER}" font-size="17" font-family="JetBrains Mono" '
            f'text-anchor="end">szczyt {peak:02d}:00</text>'
            f'</svg>')


def sentinel_svg(excl: list[int], incl: list[int]) -> str:
    W, H = 1180, 360
    L, R, T, B = 64, 24, 46, 52
    top = max(incl) or 1
    bw = (W - L - R) / 24
    out = []
    for h in range(24):
        for counts, fill, op, dx in ((incl, DIM, "0.55", 0), (excl, TEAL, "1", 0)):
            hgt = (counts[h] / top) * (H - T - B)
            x = L + h * bw + 2 + dx
            out.append(f'<rect x="{x:.1f}" y="{H-B-hgt:.1f}" width="{bw/2-2:.1f}" height="{hgt:.1f}" '
                       f'fill="{fill}" opacity="{op}" rx="1"/>')
        hgt = (excl[h] / top) * (H - T - B)
        out.append(f'<rect x="{L + h*bw + bw/2:.1f}" y="{H-B-hgt:.1f}" width="{bw/2-2:.1f}" '
                   f'height="{hgt:.1f}" fill="{TEAL}" rx="1"/>')
    spike = incl.index(max(incl))
    x = L + spike * bw
    callout = (f'<line x1="{x+bw/2:.1f}" y1="{T+6}" x2="{x+bw/2:.1f}" y2="{H-B-max(incl)/top*(H-T-B):.1f}" '
               f'stroke="{AMBER}" stroke-dasharray="4 3"/>'
               f'<text x="{x+bw+12:.1f}" y="{T+22}" fill="{AMBER}" font-size="19" font-family="JetBrains Mono">'
               f'02:00 = {(100*max(incl)/sum(incl)):.0f}% wierszy bez znacznika czasu</text>')
    ticks = "".join(f'<text x="{L + h*bw + bw/2:.1f}" y="{H-B+26}" fill="{DIM}" font-size="17" '
                    f'text-anchor="middle" font-family="JetBrains Mono">{h:02d}</text>' for h in range(0, 24, 2))
    lg = (f'<rect x="{L}" y="{T-22}" width="14" height="14" fill="{DIM}" opacity="0.55"/>'
          f'<text x="{L+22}" y="{T-10}" fill="{INK2}" font-size="17" font-family="Inter">'
          f'z znacznikiem 000000 (błędnie „valid")</text>'
          f'<rect x="{L+430}" y="{T-22}" width="14" height="14" fill="{TEAL}"/>'
          f'<text x="{L+452}" y="{T-10}" fill="{INK2}" font-size="17" font-family="Inter">'
          f'po wyłączeniu — prawdziwy profil</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
            f'{FACE}'
            f'<rect width="{W}" height="{H}" fill="{GROUND}"/>{lg}{"".join(out)}{callout}{ticks}</svg>')


def season_control_svg(raw_hi: float, raw_lo: float, ctl_hi: float, ctl_lo: float) -> str:
    W, H = 1180, 330
    L, R, T, B = 190, 150, 58, 54
    span = max(abs(raw_hi), abs(raw_lo)) * 1.15
    y = lambda v: H / 2 - (v / span) * (H - T - B) / 2
    zero = H / 2

    def row(label, hi, lo, colour, yy):
        x_hi, x_lo = L + 260, L + 480
        return (f'<text x="{L-24}" y="{yy+6}" fill="{INK2}" font-size="20" font-family="Inter" '
                f'text-anchor="end">{label}</text>'
                f'<line x1="{x_hi}" y1="{y(hi):.1f}" x2="{x_lo}" y2="{y(lo):.1f}" stroke="{colour}" '
                f'stroke-width="3"/>'
                f'<circle cx="{x_hi}" cy="{y(hi):.1f}" r="9" fill="{colour}"/>'
                f'<circle cx="{x_lo}" cy="{y(lo):.1f}" r="9" fill="{colour}"/>'
                f'<text x="{x_lo+22}" y="{y(hi)+7:.1f}" fill="{colour}" font-size="22" '
                f'font-family="JetBrains Mono">+{hi:.1f}%</text>'
                f'<text x="{x_lo+22}" y="{y(lo)+7:.1f}" fill="{colour}" font-size="22" '
                f'font-family="JetBrains Mono">{lo:.1f}%</text>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
            f'{FACE}'
            f'<rect width="{W}" height="{H}" fill="{GROUND}"/>'
            f'<line x1="{L+260}" y1="{zero}" x2="{W-R}" y2="{zero}" stroke="{LINE}"/>'
            f'{row("Dni z największą liczbą wydarzeń vs najmniejszą — bez kontroli", raw_hi, raw_lo, AMBER, 118)}'
            f'{row("To samo, po kontroli miesiąc × dzień tygodnia", ctl_hi, ctl_lo, TEAL, 232)}'
            f'<text x="{L+260}" y="{H-14}" fill="{INK}" font-size="21" font-family="JetBrains Mono">'
            f'rozstęp {(raw_hi-raw_lo):.1f} pp → {(ctl_hi-ctl_lo):.1f} pp</text>'
            f'</svg>')


def privacy_funnel_svg(total: int, g1: int, g2: int, all3: int, vol_share: float) -> str:
    W, H = 1180, 400
    steps = [("Wszystkie kody pocztowe Sopotu", total, DIM),
             ("≥ 30 kart", g1, INK2),
             ("≥ 3 podmioty", g2, TEAL),
             ("wszystkie trzy bramki", all3, AMBER)]
    L, T, BH, GAP = 60, 74, 54, 22
    maxw = W - L - 340
    out = []
    for i, (label, v, colour) in enumerate(steps):
        w = maxw * v / total
        yy = T + i * (BH + GAP)
        out.append(f'<rect x="{L}" y="{yy}" width="{w:.1f}" height="{BH}" fill="{colour}" '
                   f'opacity="{0.35 + 0.2*i:.2f}" rx="3"/>'
                   f'<text x="{L+14}" y="{yy+BH/2+8}" fill="{GROUND if i>1 else INK}" font-size="23" '
                   f'font-family="Inter" font-weight="600">{label}</text>'
                   f'<text x="{maxw+L+22}" y="{yy+BH/2+9}" fill="{colour}" font-size="27" '
                   f'font-family="JetBrains Mono">{v} / {total}</text>')
    out.append(f'<text x="{L}" y="{T-26}" fill="{AMBER}" font-size="26" font-family="JetBrains Mono">'
               f'{vol_share:.1f}% wolumenu transakcji leży w obszarach, które przechodzą wszystkie trzy bramki</text>')
    out.append(f'<text x="{L}" y="{H-26}" fill="{DIM}" font-size="19" font-family="Inter">'
               f'Bramki: ≥30 kart · ≥3 podmioty · żaden podmiot powyżej 75% grupy. Ciemne obszary są celowe, nie brakujące.</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
            f'{FACE}'
            f'<rect width="{W}" height="{H}" fill="{GROUND}"/>{"".join(out)}</svg>')


# ---------------------------------------------------------------- measurement

def measure(c: duckdb.DuckDBPyConnection) -> dict:
    out: dict = {}
    counts, peak, lunch = hourly_profile(c)
    out["hourly"] = counts
    out["peak_hour"] = peak
    out["lunch_share"] = lunch
    out["hourly_with_sentinel"] = hourly_with_sentinel(c)

    out["zero_timecode"] = c.execute(
        f"select count(*) from read_parquet({PARTS}) where tran_id_gmt_tm = '000000'").fetchone()[0]
    out["rows"] = c.execute(f"select count(*) from read_parquet({PARTS})").fetchone()[0]

    # privacy funnel
    per = f"""
        with per as (select merchant_postal_code_normalized pc, mrch_nm_raw m, count(*) n
                     from read_parquet({PARTS}) where merchant_postal_code_normalized is not null
                     group by 1,2),
             agg as (select pc, sum(n) tot, count(*) merchants, max(n) top1 from per group by 1),
             cards as (select merchant_postal_code_normalized pc,
                              count(distinct pymt_crd_acct_num_raw) cards
                       from read_parquet({PARTS}) where merchant_postal_code_normalized is not null
                       group by 1)
        select count(*),
               sum(case when c.cards>=30 then 1 else 0 end),
               sum(case when a.merchants>=3 then 1 else 0 end),
               sum(case when c.cards>=30 and a.merchants>=3 and a.top1*1.0/a.tot<=0.75 then 1 else 0 end),
               100.0*sum(case when c.cards>=30 and a.merchants>=3 and a.top1*1.0/a.tot<=0.75 then a.tot else 0 end)/sum(a.tot)
        from agg a join cards c using(pc)
    """
    t, g1, g2, all3, vol = c.execute(per).fetchone()
    out.update(privacy_total=int(t), g1=int(g1), g2=int(g2), all3=int(all3), vol_share=float(vol))

    # dominant postcode
    out["top_code"], out["top_code_n"], out["top_share"] = c.execute(f"""
        select merchant_postal_code_normalized, count(*) n,
               100.0*count(*)/(select count(*) from read_parquet({PARTS}))
        from read_parquet({PARTS}) where merchant_postal_code_normalized is not null
        group by 1 order by n desc limit 1""").fetchone()

    out["merchants"] = c.execute(
        f"select count(distinct mrch_nm_raw) from read_parquet({PARTS})").fetchone()[0]
    out["cards"] = c.execute(
        f"select count(distinct pymt_crd_acct_num_raw) from read_parquet({PARTS})").fetchone()[0]
    return out


# Season-control numbers come from the driver regression, which the pipeline owns.
# Until artifacts/drivers.json exists these fall back to the audited values and SAY SO.
def season_numbers() -> tuple[float, float, float, float, bool]:
    import json
    p = ROOT / "artifacts" / "drivers.json"
    if p.exists():
        d = json.loads(p.read_text())
        s = d.get("season_control", {})
        if {"raw_hi", "raw_lo", "ctl_hi", "ctl_lo"} <= s.keys():
            return s["raw_hi"], s["raw_lo"], s["ctl_hi"], s["ctl_lo"], True
    return 32.9, -26.9, 4.7, -4.3, False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print-values", action="store_true")
    args = ap.parse_args()
    FIGS.mkdir(parents=True, exist_ok=True)
    c = con()
    m = measure(c)

    raw_hi, raw_lo, ctl_hi, ctl_lo, from_artifact = season_numbers()

    if args.print_values:
        print(f"rows                    {m['rows']:,}")
        print(f"zero-timecode rows      {m['zero_timecode']:,} ({100*m['zero_timecode']/m['rows']:.1f}%)")
        print(f"peak hour               {m['peak_hour']:02d}:00")
        print(f"share 11-15             {m['lunch_share']:.1f}%")
        print(f"distinct merchants      {m['merchants']}")
        print(f"distinct cards          {m['cards']:,}")
        print(f"postcodes               {m['privacy_total']}")
        print(f"  pass >=30 cards       {m['g1']}")
        print(f"  pass >=3 merchants    {m['g2']}")
        print(f"  pass all three        {m['all3']}")
        print(f"  volume share in those {m['vol_share']:.1f}%")
        print(f"top postcode            {m['top_code']} {m['top_code_n']:,} ({m['top_share']:.1f}%)")
        src = "artifacts/drivers.json" if from_artifact else "AUDIT VALUES (drivers.json absent)"
        print(f"season control          raw {raw_hi}/{raw_lo} ctl {ctl_hi}/{ctl_lo}  [{src}]")
        return

    (FIGS / "hourly_profile.svg").write_text(
        profile_svg(m["hourly"], m["peak_hour"], m["lunch_share"]), encoding="utf-8")
    (FIGS / "zero_timecode.svg").write_text(
        sentinel_svg(m["hourly"], m["hourly_with_sentinel"]), encoding="utf-8")
    (FIGS / "season_control.svg").write_text(
        season_control_svg(raw_hi, raw_lo, ctl_hi, ctl_lo), encoding="utf-8")
    (FIGS / "privacy_funnel.svg").write_text(
        privacy_funnel_svg(m["privacy_total"], m["g1"], m["g2"], m["all3"], m["vol_share"]),
        encoding="utf-8")
    emitted = list(FIGS.glob("*.svg"))
    generic = [f.name for f in emitted
               if 'font-family="sans"' in f.read_text() or 'font-family="mono"' in f.read_text()]
    if generic:
        raise SystemExit(f"REFUSING: generic font families in {generic} — they render as Times")
    missing_face = [f.name for f in emitted if "@font-face" not in f.read_text()]
    if missing_face:
        raise SystemExit(f"REFUSING: no embedded @font-face in {missing_face} — an <img> SVG "
                         "cannot see the page's fonts and would fall back to a serif")
    print(f"wrote {len(emitted)} figures to {(FIGS).relative_to(ROOT)} (fonts embedded)")
    if not from_artifact:
        print("WARNING: season_control.svg used audited fallback values — "
              "re-run after the pipeline writes artifacts/drivers.json")


if __name__ == "__main__":
    main()
