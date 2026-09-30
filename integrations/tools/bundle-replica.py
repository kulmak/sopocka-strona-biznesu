#!/usr/bin/env python3
"""Bundle the karta.sopot.pl replica into a self-contained, repo-sized demo copy.

Source (READ-ONLY, never modified):  ../karta-mockup/site/
Destination (owned by the municipal integrator): integrations/municipal-site/

What it does
------------
1. Copies every page of the replica tree, so no link in the demo 404s and the
   navigation diff in integrations/NAV-DIFF.md is a genuine whole-site diff.
2. Re-encodes every raster image through Pillow:
     * CMYK JPEGs are converted to sRGB and their embedded ICC profile is
       dropped.  The replica carries print-ready uploads whose ~590 KB FOGRA39
       profile dwarfs the 81 KB of actual image data; browsers render CMYK JPEG
       inconsistently anyway.
     * images are downsampled to --max-edge / --max-edge-png on the long edge.
     * JPEG is re-encoded progressive; PNG stays PNG (references are never
       rewritten, so the file format must not change).
   A file is only replaced when the re-encode is genuinely smaller.
3. Drops two things that no page requests:
     snapshots/                22 MB of build-time verification captures
     assets/visit/fonts/*.ttf  3.7 MB of TrueType fallbacks; every @font-face
                               offers woff2 first and Chrome never asks for ttf

The nav insertion is a separate, auditable step (integrations/tools/apply-nav.py)
so that the diff stays reviewable on its own.

Usage:
    python3 integrations/tools/bundle-replica.py [--max-edge 640] [--force]
"""
import argparse
import io
import os
import re
import shutil
import sys
import time

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.abspath(os.path.join(REPO, "..", "karta-mockup", "site"))
DST = os.path.abspath(os.path.join(REPO, "integrations", "municipal-site"))

RASTER = {".jpg", ".jpeg", ".png"}
SKIP_DIRS = {"snapshots"}


def human(n):
    return f"{n / 1e6:.1f} MB"


def keep(name):
    """False for files that no page or stylesheet ever requests."""
    if name == ".DS_Store":
        return False
    if name.endswith(".ttf"):          # @font-face offers woff2 first
        return False
    return True


REF_RE = re.compile(r"""(?:res|cmsImages|adminImages)/[^"'\s)]+""")
BIG_SOURCE_EDGE = 1200        # originals this large are full-bleed art, not thumbnails


def hero_assets():
    """Site-root-relative paths of large images the homepage paints full-bleed.

    Everything else in res/ is a partner logo or a gallery thumbnail shown at
    card size, so the aggressive cap costs nothing visible there; the homepage
    hero does get looked at, so it keeps its resolution.
    """
    out = set()
    index = os.path.join(SRC, "index.html")
    if not os.path.isfile(index):
        return out
    html = open(index, encoding="utf-8", errors="replace").read()
    for ref in set(REF_RE.findall(html)):
        ref = ref.rstrip(".,;:")
        p = os.path.join(SRC, ref)
        if not os.path.isfile(p) or os.path.splitext(ref)[1].lower() not in RASTER:
            continue
        try:
            with Image.open(p) as im:
                if max(im.size) >= BIG_SOURCE_EDGE:
                    out.add(ref)
        except Exception:
            pass
    return out


def optimize(path, ext, max_edge, max_edge_png, quality, big=False):
    """Re-encode in place if that produces a smaller file. Returns (before, after)."""
    if big:
        max_edge = max(max_edge, 1920)
        max_edge_png = max(max_edge_png, 1920)
    before = os.path.getsize(path)
    try:
        im = Image.open(path)
        im.load()
    except Exception as exc:                      # unreadable: leave untouched
        print(f"  ! cannot read {path}: {exc}", file=sys.stderr)
        return before, before

    has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    buf = io.BytesIO()
    try:
        if ext == ".png" and has_alpha:
            out = im.convert("RGBA")
            out.thumbnail((max_edge_png, max_edge_png), Image.LANCZOS)
            out.save(buf, "PNG", optimize=True)
        elif ext == ".png":
            out = im.convert("RGB")
            out.thumbnail((max_edge_png, max_edge_png), Image.LANCZOS)
            out.save(buf, "PNG", optimize=True)
        else:
            out = im if im.mode == "RGB" else im.convert("RGB")
            out.thumbnail((max_edge, max_edge), Image.LANCZOS)
            out.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    except Exception as exc:
        print(f"  ! cannot encode {path}: {exc}", file=sys.stderr)
        return before, before

    after = buf.tell()
    if after < before:
        with open(path, "wb") as fh:
            fh.write(buf.getvalue())
        return before, after
    return before, before


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-edge", type=int, default=640,
                    help="max long edge for JPEG (default 640)")
    ap.add_argument("--max-edge-png", type=int, default=420,
                    help="max long edge for PNG (default 420)")
    ap.add_argument("--jpeg-quality", type=int, default=70)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(SRC):
        sys.exit(f"source replica not found: {SRC}")
    if os.path.exists(DST):
        if not args.force:
            sys.exit(f"destination exists: {DST} (pass --force to rebuild)")
        shutil.rmtree(DST)
    os.makedirs(DST, exist_ok=True)

    t0 = time.time()
    copied = pages = skipped = 0
    bytes_in = bytes_out = 0
    jobs = []
    for dirpath, dirnames, filenames in os.walk(SRC):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel = os.path.relpath(dirpath, SRC)
        outdir = DST if rel == "." else os.path.join(DST, rel)
        os.makedirs(outdir, exist_ok=True)
        for name in filenames:
            if not keep(name):
                skipped += 1
                continue
            s, d = os.path.join(dirpath, name), os.path.join(outdir, name)
            if not os.path.isfile(s):
                continue
            shutil.copy2(s, d)
            copied += 1
            bytes_in += os.path.getsize(s)
            bytes_out += os.path.getsize(s)
            if name.endswith(".html"):
                pages += 1
            ext = os.path.splitext(name)[1].lower()
            if ext in RASTER:
                jobs.append((d, ext, os.path.relpath(d, DST)))

    heroes = hero_assets()
    saved = 0
    for d, ext, rel in jobs:
        before, after = optimize(d, ext, args.max_edge, args.max_edge_png,
                                 args.jpeg_quality, big=rel in heroes)
        bytes_out += after - before
        saved += before - after

    print(f"source      {SRC}")
    print(f"destination {DST}")
    print(f"copied      {copied} files ({pages} pages), skipped {skipped}")
    print(f"images      {len(jobs)} re-encoded, saved {human(saved)}")
    print(f"hero art    {len(heroes)} homepage images kept at up to 1920px")
    print(f"size        {human(bytes_in)} -> {human(bytes_out)}")
    print(f"elapsed     {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
