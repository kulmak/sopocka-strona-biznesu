#!/usr/bin/env python3
"""Assemble the publishable site into _site/.

The published bundle is the ONLY thing that leaves this machine, so this script is where the
challenge's two competing obligations are reconciled:

  §4  the jury must be able to open the code repository and a working demonstration
  §7.4 Organiser Data must not be published

Everything here is either our own code, our own documentation, the municipal replica we built,
or the PRIVACY-GATED aggregate. The raw parquet never enters _site/, and neither does anything
the app does not actually need at runtime — a smaller bundle is also a faster demo.

Usage:
    python3 tools/build_site.py
    python3 tools/build_site.py --check     # verify an existing _site/ without rebuilding

Expected output on a good tree:
    _site/  10,4 MB   app  panel · aggregate 2,0 MB · deck 1,4 MB · 0 forbidden files
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "_site"
WITH_REPLICA = False   # flip with --with-replica; see the note in build()

# Files/patterns that must never reach the published bundle.
FORBIDDEN = re.compile(r"(\.parquet$|\.csv\.xz$|datasprint|mcc5812|Dictionary_data_Visa|"
                       r"rockyou|\.hash$)", re.IGNORECASE)


def copy_tree(src: pathlib.Path, dst: pathlib.Path, note: str) -> int:
    if not src.exists():
        print(f"  skip  {note:28s} (missing: {src.relative_to(ROOT)})")
        return 0
    n = 0
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(src)
        if FORBIDDEN.search(rel.as_posix()):
            print(f"  SKIP FORBIDDEN  {rel}")
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        n += 1
    size = sum(f.stat().st_size for f in dst.rglob("*") if f.is_file()) if dst.exists() else 0
    print(f"  ok    {note:28s} {n:5d} files  {size/1e6:6.2f} MB")
    return n


def build() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)

    print("assembling _site/")
    copy_tree(ROOT / "app", SITE / "app", "panel (app/)")

    # The gated aggregate is the only data file the app loads.
    agg = ROOT / "artifacts" / "aggregate.json"
    if agg.exists():
        (SITE / "artifacts").mkdir(parents=True, exist_ok=True)
        shutil.copy2(agg, SITE / "artifacts" / "aggregate.json")
        print(f"  ok    {'aggregate (gated)':28s} {1:5d} files  {agg.stat().st_size/1e6:6.2f} MB")
    else:
        print("  WARN  aggregate.json missing — the demo will not load")

    copy_tree(ROOT / "docs" / "deck", SITE / "deck", "deck + figures")

    # The municipal replica is a mirror of karta.sopot.pl. Republishing 49 MB of someone
    # else's site content in a public repository is both a copyright risk and dead weight in
    # the bundle the jury has to load, so it is EXCLUDED by default. We ship the evidence
    # instead: the screenshots of the tab, and the instructions to rebuild the replica from
    # karta-mockup.zip, which the team already has.
    shots = ROOT / "integrations" / "evidence"
    if shots.exists():
        copy_tree(shots, SITE / "evidence", "integration screenshots")
    # The chrome-only excerpt of the municipal replica: our tab page plus the minimum theme
    # assets for the header/nav/footer to render truthfully. Built by its own tool so the
    # exclusion rules live in one place.
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import build_municipal_excerpt as bx
        if bx.TAB.exists():
            bx.build()
        else:
            print(f"  skip  {'municipal tab page':28s} (not built; run integrations/tools/build-all.sh)")
    except Exception as e:  # never let the excerpt break the deploy
        print(f"  WARN  municipal excerpt failed: {e}")

    if WITH_REPLICA:
        for cand in (ROOT / "integrations" / "municipal-site", ROOT / "integrations" / "site"):
            if cand.exists():
                copy_tree(cand, SITE / "site", "municipal replica (opt-in)")
                break
    else:
        print(f"  skip  {'municipal replica':28s} (copyright + size; see integrations/NAV-DIFF.md)")

    # A landing page that works even if the replica was not built.
    (SITE / "index.html").write_text(LANDING, encoding="utf-8")

    total = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    files = sum(1 for f in SITE.rglob("*") if f.is_file())
    print(f"\n_site/  {total/1e6:.1f} MB  {files} files")


LANDING = """<!DOCTYPE html>
<html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sopocka Strona Biznesu</title>
<style>
  :root{--ground:#0B1220;--pulse:#FFB84D;--accent:#21C7B7;--ink:#F5F3EE;--ink2:#B9C0CC;--dim:#55637A;
        --line:rgba(245,243,238,.2)}
  body{margin:0;background:var(--ground);color:var(--ink);
       font-family:'Inter',system-ui,sans-serif;line-height:1.55}
  .wrap{max-width:1080px;margin:0 auto;padding:96px 32px}
  h1{font-size:64px;line-height:1.04;margin:0 0 18px;letter-spacing:-.02em}
  .strap{font-size:26px;color:var(--ink2);max-width:760px}
  .kicker{font-family:ui-monospace,monospace;font-size:15px;letter-spacing:.14em;
          text-transform:uppercase;color:var(--pulse);margin-bottom:22px}
  .cards{display:flex;gap:22px;flex-wrap:wrap;margin-top:56px}
  a.card{flex:1 1 280px;display:block;padding:28px 30px;border:1px solid var(--line);border-radius:12px;
         text-decoration:none;color:var(--ink);background:rgba(255,255,255,.04)}
  a.card:hover{border-color:var(--accent)}
  a.card b{display:block;font-size:24px;margin-bottom:8px}
  a.card span{color:var(--ink2);font-size:17px}
  .foot{margin-top:64px;padding-top:22px;border-top:1px solid var(--line);color:var(--dim);
        font-family:ui-monospace,monospace;font-size:15px}
</style></head><body><div class="wrap">
<div class="kicker">Visa Data Sprint · Public Challenge</div>
<h1>Miasto i firmy oddychają<br>tym samym rytmem</h1>
<p class="strap">Sopocka Strona Biznesu — panel przedsiębiorcy dla małych firm w Sopocie,
nowa zakładka w Karcie Sopockiej. Zbudowany na 378 212 zanonimizowanych transakcjach
kartowych (MCC 5812), bez zbierania sprzedaży firmy.</p>
<div class="cards">
  <a class="card" href="app/"><b>Panel przedsiębiorcy →</b>
     <span>Działające demo na realnych danych. Bez instalacji, bez nowej aplikacji.</span></a>
  <a class="card" href="deck/deck.pdf"><b>Prezentacja (PDF) →</b>
     <span>10 slajdów: problem, dane, dwa wnioski, model, prywatność.</span></a>
  <a class="card" href="evidence/"><b>W Karcie Sopockiej →</b>
     <span>Jak panel wygląda jako nowa zakładka serwisu miejskiego (zrzuty ekranu).</span></a>
</div>
<div class="foot">
  Dane: zanonimizowane i syntetyczne, udostępnione przez Organizatora wyłącznie na potrzeby wyzwania.<br>
  Wyniki zagregowane; grupy poniżej 30 kart, 3 podmiotów lub z podmiotem powyżej 75% udziału są wygaszane.
</div>
</div></body></html>
"""


def check() -> None:
    if not SITE.exists():
        sys.exit("_site/ missing — run without --check first")
    bad = [p.relative_to(SITE).as_posix() for p in SITE.rglob("*")
           if p.is_file() and FORBIDDEN.search(p.name)]
    if bad:
        sys.exit(f"FAIL: forbidden files in _site/: {bad}")
    if not (SITE / "artifacts" / "aggregate.json").exists():
        sys.exit("FAIL: the gated aggregate is missing — the demo would not load")
    agg = json.loads((SITE / "artifacts" / "aggregate.json").read_text())
    if agg.get("ver") != 4:
        sys.exit(f"FAIL: aggregate ver={agg.get('ver')}, expected 4")
    total = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    print(f"_site/ ok  {total/1e6:.1f} MB  aggregate ver=4  rows={agg.get('rows')}  "
          f"0 forbidden files")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--with-replica", action="store_true",
                    help="also publish the 49 MB municipal mirror (copyright + size risk)")
    args = ap.parse_args()
    global WITH_REPLICA
    WITH_REPLICA = args.with_replica
    build() if not args.check else None
    check()


if __name__ == "__main__":
    main()
