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
import tempfile
import sys

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



def inline_svgs(html: str) -> tuple[str, int]:
    """Replace <img src="...svg"> with the SVG itself.

    A browser sandboxes an <img>-referenced SVG as an isolated document AND refuses to load
    external resources inside it, so its @font-face never resolves and every label silently
    falls back to Times-Roman (measured: 8 Times-Roman subsets in the first rendered PDF).
    Inlining puts the SVG in the page's own context, where the deck's fonts apply.
    """
    import re as _re
    n = 0

    def repl(m):
        nonlocal n
        src = m.group(1)
        path = (SLIDES.parent / src).resolve()
        if not path.exists():
            sys.exit(f"deck references a missing figure: {src}")
        svg = path.read_text(encoding="utf-8")
        svg = _re.sub(r"<\?xml.*?\?>", "", svg, flags=_re.S)
        # The figure's own @font-face uses paths relative to the figure; drop it, the page's
        # fonts are already loaded and would otherwise 404.
        svg = _re.sub(r"<style>.*?</style>", "", svg, flags=_re.S)
        n += 1
        return svg

    out = _re.sub(r'<img[^>]*src="([^"]+\.svg)"[^>]*>', repl, html)
    return out, n


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

    if True:
        # `--headless=new` hangs on this page (measured: >180 s, no output). The legacy
        # headless shell renders the same file in ~4 s. Keep the persistent profile: a
        # throwaway --user-data-dir makes Chrome build a profile on every run and is slower.
        inlined, n_figs = inline_svgs(html)
        tmp_html = ROOT / "docs" / "deck" / ".slides.inlined.html"
        tmp_html.write_text(inlined, encoding="utf-8")
        print(f"inlined {n_figs} figures (fonts now apply to chart labels)")
        # A fresh --user-data-dir hangs on this machine (measured twice, >180 s, no output);
        # a persistent one renders the same file in ~4 s. Clear zombies first, or a timed-out
        # run leaves a process holding the profile lock and the next run hangs too.
        subprocess.run(["pkill", "-f", "Google Chrome.*headless"], capture_output=True)
        profile = pathlib.Path("/tmp/chrome-deck-profile")
        profile.mkdir(exist_ok=True)
        profile.mkdir(exist_ok=True)
        cmd = [
            chrome,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-dev-shm-usage",
            "--no-pdf-header-footer",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={OUT}",
            tmp_html.as_uri(),
        ]
        # Chrome hangs when driven through a captured pipe from Python on this machine
        # (measured repeatedly: >180 s, no output) while the identical argv finishes in ~4 s
        # from a shell. os.system inherits the terminal, which is the whole difference.
        import os
        quoted = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        rc = os.system(quoted)
        if rc != 0 or not OUT.exists():
            sys.exit(f"chrome failed (rc={rc}); try: pkill -f 'Google Chrome.*headless' first")


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
