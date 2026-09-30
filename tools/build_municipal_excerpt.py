#!/usr/bin/env python3
"""Publish a chrome-only excerpt of the municipal replica, so a juror can open the new tab
inside the city's real frame — without republishing 31 MB of the city's article images.

We do not republish karta.sopot.pl. What ships is our own page plus the minimum theme assets
needed for the header, navigation and footer to render as they really are. Everything else —
article galleries, partner logos, the mirrored page tree — stays out, and
`integrations/tools/build-all.sh` rebuilds the full replica locally from karta-mockup.zip.

Usage:
    python3 tools/build_municipal_excerpt.py            # writes _site/site/
    python3 tools/build_municipal_excerpt.py --check
"""
from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "integrations" / "municipal-site"
TAB = SRC / "pl" / "strona-biznesu" / "index.html"
OUT = ROOT / "_site" / "site"

# Theme directories the header/footer/nav genuinely need. `res/` (31 MB of article imagery)
# and `snapshots/` are deliberately absent.
KEEP_DIRS = ["cmsCSS", "cmsJS", "css", "js", "assets", "cmsImages", "adminImages", "vendor"]
ASSET_REF = re.compile(r'(?:src|href)="([^"?#]+)"')


def collect_refs(html: str, base: pathlib.Path, seen: set[pathlib.Path]) -> None:
    """Follow local references one level deep — enough for chrome, cheap to reason about."""
    for ref in ASSET_REF.findall(html):
        if ref.startswith(("http", "//", "data:", "mailto:", "tel:", "#")):
            continue
        p = (base / ref).resolve()
        if p.is_file() and p not in seen and SRC in p.parents:
            seen.add(p)
        elif p.is_dir():
            continue


def build() -> None:
    if not TAB.exists():
        sys.exit(f"missing the tab page: {TAB.relative_to(ROOT)} — run integrations/tools/build-all.sh")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    copied: list[pathlib.Path] = []
    for d in KEEP_DIRS:
        src = SRC / d
        if not src.is_dir():
            continue
        dst = OUT / d
        shutil.copytree(src, dst)
        copied += [p for p in dst.rglob("*") if p.is_file()]

    # The tab page itself, at the same relative depth it has in the replica.
    tab_dst = OUT / "pl" / "strona-biznesu" / "index.html"
    tab_dst.parent.mkdir(parents=True, exist_ok=True)
    html = TAB.read_text(encoding="utf-8")

    # Point the iframe at the published panel and make the tab link a no-op (we ship one page).
    html = re.sub(r'(<iframe[^>]*\ssrc=")[^"]*"', r'\1../../app/"', html, count=1)
    html = html.replace('href="../../app/index.html"', 'href="../../app/"')

    # A banner that says plainly what this is. A mockup must never read as the live city site.
    banner = ('<div style="background:#0B1220;color:#F5F3EE;font:14px/1.5 Inter,system-ui,sans-serif;'
              'padding:10px 20px;text-align:center">Makieta integracji — kopia serwisu miejskiego '
              'na potrzeby prototypu. Tab „Strona Biznesu” prowadzi do działającego panelu. '
              '<span style="color:#B9C0CC">Integration mockup — a replica used for prototyping; '
              'the “Strona Biznesu” tab opens the working panel.</span></div>')
    html = html.replace("<body", "<body", 1)
    m = re.search(r"<body[^>]*>", html)
    if m:
        html = html[:m.end()] + banner + html[m.end():]
    tab_dst.write_text(html, encoding="utf-8")
    copied.append(tab_dst)

    # The loader probes the panel at a DOMAIN-ROOT path ("/app/"), which is correct inside the
    # replica but WRONG on a GitHub Pages project site, where the app lives under
    # /<repo>/app/. Left alone, the deploy would silently fall back to "panel w przygotowaniu".
    loader = OUT / "assets" / "mock" / "strona-biznesu.js"
    if loader.exists():
        js = loader.read_text(encoding="utf-8")
        # Point straight at the panel, not at app/index.html: that wrapper renders municipal
        # chrome and then iframes the panel itself, so the tab would nest two frames deep and
        # show a landing rather than the data.
        js = js.replace('var PANEL_URL = "/app/";', 'var PANEL_URL = "../../../app/panel.html";')
        js = js.replace('var PANEL_PROBE = "/app/index.html";',
                        'var PANEL_PROBE = "../../../app/index.html";')
        loader.write_text(js, encoding="utf-8")
        print("  rewrote the panel probe to a relative path (GitHub Pages project sites)")

    total = sum(p.stat().st_size for p in copied)
    print(f"  wrote _site/site/  {len(copied)} files  {total/1e6:.2f} MB")
    print(f"  excluded: res/ (article imagery), snapshots/, and the mirrored page tree")
    print(f"  tab page: {(tab_dst.relative_to(ROOT))}")


def check() -> None:
    tab = OUT / "pl" / "strona-biznesu" / "index.html"
    if not tab.exists():
        sys.exit("FAIL: the tab page is not in _site/site/")
    html = tab.read_text(encoding="utf-8")
    if "app/" not in html:
        sys.exit("FAIL: the tab page does not point at the panel")
    if "Makieta integracji" not in html:
        sys.exit("FAIL: the mockup banner is missing — a replica must not read as the live site")
    loader = OUT / "assets" / "mock" / "strona-biznesu.js"
    if loader.exists() and '"/app/"' in loader.read_text(encoding="utf-8"):
        sys.exit("FAIL: the panel probe is still a domain-root path — it 404s on a project site")
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"_site/site/ ok  {size/1e6:.2f} MB  (chrome-only excerpt, banner present)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if not args.check:
        build()
    check()


if __name__ == "__main__":
    main()
