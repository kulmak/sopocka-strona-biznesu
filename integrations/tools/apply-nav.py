#!/usr/bin/env python3
"""Apply the municipal navigation change to the bundled replica.

One new <li> per page, inserted immediately after the `menuItem_392` item inside
`header … .main-menu nav#mobile-menu > ul`.  This is the only navigation edit;
the offcanvas copies are NOT touched because they are cloned at runtime by
meanmenu.js from this very list (NOTES.md §2).

Depth handling: the replica's nav hrefs are document-relative, not root-relative
(`pl/partnerzy/index.html` carries `href="../../pl/rejestracja"`), so the new item
is emitted with the same `../` prefix the generator would have produced.

    index.html                      href="pl/strona-biznesu"
    pl/partnerzy/index.html         href="../../pl/strona-biznesu"

The tab highlights itself with the CMS's own `menu-wybrane` class, applied by hand
on the one page it belongs to — which is exactly what tools/build_site.py does for
every other section (NAV-DIFF.md, "Why build_site.py was not re-run").

Usage:
    python3 integrations/tools/apply-nav.py            # apply
    python3 integrations/tools/apply-nav.py --check    # verify, write nothing
    python3 integrations/tools/apply-nav.py --revert   # remove the item again
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SITE = os.path.abspath(os.path.join(REPO, "integrations", "municipal-site"))

TAB_ID = "menuItem_900"
TAB_ROUTE = "pl/strona-biznesu"
TAB_LABEL = "Strona Biznesu"
ANCHOR_ID = "menuItem_392"
NAV_MARKER = 'id="mobile-menu"'
# The tab's own page gets the CMS active-section class; every other page gets the
# same empty placeholder class the CMS writes for inactive items.
ACTIVE_PAGE = os.path.join("pl", "strona-biznesu", "index.html")

INDENT = " " * 28


def nav_item(depth, active):
    href = "../" * depth + TAB_ROUTE
    cls = "menu-wybrane" if active else " "
    return (
        f'{INDENT}<li class="{cls}" id="{TAB_ID}">'
        f'<a class="wyroznione2" href="{href}">{TAB_LABEL}</a></li>'
    )


def nav_span(html):
    """(start, end) of the header primary-nav element, or None."""
    i = html.find(NAV_MARKER)
    if i < 0:
        return None
    start = html.rfind("<nav", 0, i)
    if start < 0:
        return None
    end = html.find("</nav>", i)
    if end < 0:
        return None
    return start, end


def insert(html, depth, active):
    span = nav_span(html)
    if span is None:
        return None, "no header nav (#mobile-menu)"
    start, end = span
    if TAB_ID in html[start:end]:
        # Already there.  Keep the active-section class in sync with the page:
        # the CMS marks the current section with `menu-wybrane` on exactly one
        # page, and that page is this tab's own.
        want = "menu-wybrane" if active else " "
        pattern = re.compile(
            r'<li class="[^"]*" id="' + TAB_ID + r'">'
        )
        replacement = f'<li class="{want}" id="{TAB_ID}">'
        new_span = pattern.sub(replacement, html[start:end], count=1)
        if new_span == html[start:end]:
            return html, "already present"
        return html[:start] + new_span + html[end:], "active class set"
    anchor = html.find(ANCHOR_ID, start, end)
    if anchor < 0:
        return None, f"no {ANCHOR_ID} inside the header nav"
    close = html.find("</li>", anchor, end)
    if close < 0:
        return None, f"no closing </li> for {ANCHOR_ID}"
    cut = close + len("</li>")
    return html[:cut] + "\n" + nav_item(depth, active) + html[cut:], "inserted"


def remove(html):
    return re.sub(
        r"\n?" + re.escape(INDENT) + r'<li class="[^"]*" id="' + TAB_ID + r'">.*?</li>',
        "",
        html,
        count=1,
        flags=re.S,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify only, write nothing")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(SITE):
        sys.exit(f"bundle not found: {SITE} (run bundle-replica.py first)")

    pages = []
    for dirpath, dirnames, filenames in os.walk(SITE):
        dirnames[:] = [d for d in dirnames if d != "assets"]
        for name in filenames:
            if name.endswith(".html"):
                pages.append(os.path.join(dirpath, name))
    pages.sort()

    counts = {"inserted": 0, "already present": 0, "active class set": 0,
              "skipped (no header nav)": 0, "reverted": 0, "unchanged": 0}
    problems = []
    for path in pages:
        rel = os.path.relpath(path, SITE)
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
        depth = 0 if os.path.dirname(rel) in ("", ".") else len(os.path.dirname(rel).split(os.sep))

        if args.revert:
            new = remove(html)
            if new != html:
                counts["reverted"] += 1
                if not args.check:
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(new)
            else:
                counts["unchanged"] += 1
            continue

        if NAV_MARKER not in html:
            # A frameless document (the panel placeholder rendered inside the
            # iframe) has no municipal chrome and therefore no nav to patch.
            counts["skipped (no header nav)"] += 1
            continue

        new, status = insert(html, depth, rel == ACTIVE_PAGE)
        if status in ("inserted", "already present", "active class set"):
            counts[status] += 1
        else:
            problems.append(f"{rel}: {status}")
            continue
        if new != html and not args.check:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new)

    verb = "checked" if args.check else ("reverted" if args.revert else "patched")
    print(f"{verb} {len(pages)} pages in {SITE}")
    for k, v in counts.items():
        if v:
            print(f"  {k:16s} {v}")
    for p in problems:
        print(f"  PROBLEM {p}", file=sys.stderr)
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
