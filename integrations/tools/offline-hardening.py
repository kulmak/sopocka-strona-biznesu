#!/usr/bin/env python3
"""Remove every off-origin *request* from the bundled replica.

The replica is self-hosted for scripts, stylesheets and fonts — there is not a
single external <script src>, <link href>, @import or CSS url().  What it does
still carry are 154 off-origin <img src> values inherited from the CMS capture,
in four hosts:

    maps.gstatic.com       118  the red "you are here" pin in the partner map legend
    kalendarz.sopot.pl      35  event photographs on the wydarzenia pages
    sopot.bifrost.lepsze.it  2  the CMS's own upload host (absent from the mirror)
    (and nothing else)

Each is repointed at a local placeholder drawn in the replica's own palette.
Anchors (href=) are deliberately left alone: a link is not a request, and the
site's outbound links — Facebook, Instagram, Google Maps directions, partner
websites — are authentic municipal content.

Idempotent.  Run with --check to verify without writing.

Usage:
    python3 integrations/tools/offline-hardening.py
    python3 integrations/tools/offline-hardening.py --check
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SITE = os.path.abspath(os.path.join(REPO, "integrations", "municipal-site"))
ASSETS = os.path.join("assets", "mock", "offline")

PIN = "pin-red.svg"
PHOTO = "photo-placeholder.svg"

HOSTS = [
    ("maps.gstatic.com", PIN),
    ("kalendarz.sopot.pl", PHOTO),
    ("sopot.bifrost.lepsze.it", PHOTO),
]

PIN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 34" width="24" height="34" role="img" aria-label="Punkt na mapie">
  <path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 22 12 22s12-13 12-22c0-6.6-5.4-12-12-12z" fill="#d92b2b"/>
  <circle cx="12" cy="12" r="4.5" fill="#fff"/>
</svg>
"""

PHOTO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" width="640" height="360" role="img" aria-label="Zdjęcie niedostępne w wersji offline">
  <rect width="640" height="360" fill="#eceff2"/>
  <g fill="none" stroke="#9aa5b1" stroke-width="8" stroke-linecap="round" stroke-linejoin="round">
    <rect x="196" y="140" width="248" height="164" rx="18"/>
    <circle cx="320" cy="222" r="42"/>
    <path d="M262 140l20-32h76l20 32"/>
  </g>
  <rect x="0" y="330" width="640" height="30" fill="#178fd3" opacity="0.85"/>
</svg>
"""

SRC_RE = re.compile(r"""(?<![\w-])(src|data-url-grafiki)=(["'])(https?://[^"']+)\2""")
INLINE_URL_RE = re.compile(r"""url\((['"]?)(https?://[^'")]+)\1\)""")


def depth_of(rel):
    d = os.path.dirname(rel)
    return 0 if d in ("", ".") else len(d.split(os.sep))


def local_for(url, depth):
    for host, asset in HOSTS:
        if host in url:
            return "../" * depth + ASSETS.replace(os.sep, "/") + "/" + asset
    return None


def write_assets():
    outdir = os.path.join(SITE, ASSETS)
    os.makedirs(outdir, exist_ok=True)
    for name, body in ((PIN, PIN_SVG), (PHOTO, PHOTO_SVG)):
        path = os.path.join(outdir, name)
        if not os.path.isfile(path) or open(path, encoding="utf-8").read() != body:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body)
    print(f"placeholders {outdir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(SITE):
        sys.exit(f"bundle not found: {SITE}")
    if not args.check:
        write_assets()

    pages = changed = 0
    rewrites = {}
    unresolved = []
    for dirpath, dirnames, filenames in os.walk(SITE):
        for name in filenames:
            if not name.endswith(".html"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, SITE)
            depth = depth_of(rel)
            with open(path, encoding="utf-8") as fh:
                html = fh.read()
            pages += 1
            touched = False

            def swap(m):
                nonlocal touched
                attr, quote, url = m.group(1), m.group(2), m.group(3)
                local = local_for(url, depth)
                if local is None:
                    unresolved.append(f"{rel}: {url}")
                    return m.group(0)
                rewrites[url.split("/")[2]] = rewrites.get(url.split("/")[2], 0) + 1
                touched = True
                return f"{attr}={quote}{local}{quote}"

            new = SRC_RE.sub(swap, html)
            new = INLINE_URL_RE.sub(
                lambda m: f"url({m.group(1)}{local_for(m.group(2), depth) or m.group(2)}{m.group(1)})",
                new,
            )
            if new != html:
                touched = True
            if touched:
                changed += 1
                if not args.check:
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(new)

    verb = "checked" if args.check else "hardened"
    print(f"{verb} {pages} pages, {changed} rewritten")
    for host, n in sorted(rewrites.items(), key=lambda kv: -kv[1]):
        print(f"  {host:28s} {n}")
    for u in unresolved:
        print(f"  UNRESOLVED {u}", file=sys.stderr)
    if unresolved:
        sys.exit(1)


if __name__ == "__main__":
    main()
