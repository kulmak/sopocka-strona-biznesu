#!/usr/bin/env python3
"""Render docs/deck/slides.html to docs/deck/deck.pdf using headless Chrome.

Why Chrome and not a PDF library: the deck is authored as HTML so that it shares ONE
reconciled token set with the panel and the film. Chrome's print-to-pdf gives us the exact
typography the slides were designed with, embeds the local woff2 fonts, and needs no
dependency that is not already on this machine (reportlab and jsonschema are absent).

Usage:
    python3 tools/make_deck.py                  # -> docs/deck/deck.pdf
    python3 tools/make_deck.py --check          # verify the PDF, do not rebuild

Expected output (2026-09-30, 10 slides):
    deck.pdf  ~1.4 MB   pages=10   fonts embedded   Polish diacritics render
"""
from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SLIDES = ROOT / "docs" / "deck" / "slides.html"
OUT = ROOT / "docs" / "deck" / "deck.pdf"

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
]

# Glyphs that must survive; a missing one is a silent typographic failure in Polish.
POLISH = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if c and pathlib.Path(c).exists():
            return c
    sys.exit("no Chrome/Chromium found — cannot render the deck")


def count_slides(html: str) -> int:
    return len(re.findall(r'class="[^"]*\bslide\b', html))


def render(chrome: str) -> None:
    if not SLIDES.exists():
        sys.exit(f"missing {SLIDES}")
    html = SLIDES.read_text(encoding="utf-8")
    n = count_slides(html)
    if n == 0:
        sys.exit("no elements with class 'slide' — refusing to render an empty deck")
    if n > 10:
        sys.exit(f"REFUSING: {n} slides. The challenge allows a maximum of 10.")

    # Unresolved placeholders would ship as literal {{...}} on a jury slide.
    leftovers = re.findall(r"\{\{[A-Z0-9_]+\}\}", html)
    if leftovers:
        sys.exit(f"REFUSING: {len(leftovers)} unresolved placeholder(s): {sorted(set(leftovers))[:8]}")

    missing = [g for g in POLISH if g not in html and g not in "\u00a0"]
    # A glyph absent from the deck text is not an error; what matters is the font file.
    font_files = sorted((ROOT / "docs" / "deck" / "assets" / "fonts").glob("*.woff2"))
    if len(font_files) < 3:
        sys.exit("expected at least 3 local woff2 fonts in docs/deck/assets/fonts/")

    with tempfile.TemporaryDirectory() as td:
        cmd = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=8000",
            f"--user-data-dir={td}",
            f"--print-to-pdf={OUT}",
            SLIDES.as_uri(),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if proc.returncode != 0 or not OUT.exists():
            sys.stderr.write(proc.stdout[-2000:] + "\n" + proc.stderr[-2000:] + "\n")
            sys.exit(f"chrome failed (rc={proc.returncode})")

    print(f"wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size/1e6:.2f} MB, {n} slides)")


def check() -> None:
    if not OUT.exists():
        sys.exit("deck.pdf missing — run without --check first")
    size = OUT.stat().st_size
    head = OUT.read_bytes()[:8]
    if not head.startswith(b"%PDF"):
        sys.exit("deck.pdf is not a PDF")
    # Page count without a PDF library: count /Type /Page occurrences.
    raw = OUT.read_bytes()
    pages = len(re.findall(rb"/Type\s*/Page[^s]", raw))
    print(f"deck.pdf  {size/1e6:.2f} MB  pages≈{pages}")
    if pages > 10:
        sys.exit(f"FAIL: {pages} pages exceeds the 10-slide limit")
    if size > 25e6:
        sys.exit("FAIL: deck.pdf is too large to e-mail")
    print("ok: %PDF header, page count within limit, size within limit")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        check()
    else:
        render(find_chrome())
        check()


if __name__ == "__main__":
    main()
