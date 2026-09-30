#!/usr/bin/env python3
"""Load the replica-only augmentation on every page.

`integrations/municipal-site/assets/mock/strona-biznesu.css` carries one global
rule that every header needs — the eighth nav item fits on one line only because
of it (see integrations/NAV-DIFF.md §"Does the eighth item wrap?") — so the
stylesheet has to reach all 165 pages, not just the tab.

It is inserted immediately after `assets/mock/mock.css`, which NOTES.md names as
the replica's own augmentation point, so it stays the last stylesheet on the page
and can therefore only add.  The script is injected on the tab page alone.

Idempotent.  Usage:
    python3 integrations/tools/apply-augmentation.py
    python3 integrations/tools/apply-augmentation.py --check
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SITE = os.path.abspath(os.path.join(REPO, "integrations", "municipal-site"))

CSS_NAME = "strona-biznesu.css"
JS_NAME = "strona-biznesu.js"
# Exact end-of-tag markers.  A marker must include the tag's closing ">", or the
# insertion lands inside the element and the injected <script> is parsed as
# script TEXT instead of as an element (which also breaks the anchor script).
ANCHOR_CSS = 'assets/mock/mock.css">'
ANCHOR_JS = 'assets/mock/mock.js"></script>'
CSS_LINK = 'assets/mock/strona-biznesu.css">'
JS_LINK = 'assets/mock/strona-biznesu.js"></script>'

TAB_PAGE = os.path.join("pl", "strona-biznesu", "index.html")


def prefix_of(rel):
    """Document-relative prefix, matching the replica's own convention.

    The generator writes `./assets/...` at the site root and `../assets/...`
    below it; staying byte-identical keeps the diff minimal.
    """
    d = os.path.dirname(rel)
    if d in ("", "."):
        return "./"
    return "../" * len(d.split(os.sep))


def inject_after(html, marker, present_marker, snippet):
    """Insert `snippet` on its own line immediately after `marker`.

    `marker` is a complete end-of-tag string, so the cut point is unambiguous.
    If `present_marker` is already in the document the snippet is not repeated.
    """
    if present_marker in html:
        return html, False
    i = html.find(marker)
    if i < 0:
        return html, False
    cut = i + len(marker)
    return html[:cut] + "\n        " + snippet + html[cut:], True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(SITE):
        sys.exit(f"bundle not found: {SITE}")

    pages = css_added = js_added = 0
    missing_css = []
    for dirpath, dirnames, filenames in os.walk(SITE):
        for name in filenames:
            if not name.endswith(".html"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, SITE)
            with open(path, encoding="utf-8") as fh:
                html = fh.read()
            pages += 1
            prefix = prefix_of(rel)
            new = html

            css_link = f'<link rel="stylesheet" href="{prefix}assets/mock/{CSS_NAME}">'
            new, added = inject_after(new, ANCHOR_CSS, CSS_LINK, css_link)
            if added:
                css_added += 1
            elif CSS_LINK not in new:
                missing_css.append(rel)

            if rel == TAB_PAGE:
                js_link = f'<script src="{prefix}assets/mock/{JS_NAME}"></script>'
                new, added = inject_after(new, ANCHOR_JS, JS_LINK, js_link)
                if added:
                    js_added += 1

            if new != html and not args.check:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(new)

    verb = "checked" if args.check else "augmented"
    print(f"{verb} {pages} pages: css link on {css_added}, panel script on {js_added}")
    for m in missing_css:
        print(f"  NO CSS ANCHOR {m}", file=sys.stderr)
    if missing_css:
        sys.exit(1)


if __name__ == "__main__":
    main()
