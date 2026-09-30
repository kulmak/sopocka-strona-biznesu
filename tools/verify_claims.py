#!/usr/bin/env python3
"""Re-derive every published number and fail if any of them is no longer true.

This is the enforcement arm of AGENTS.md rule 2 ("no number without a command"). The deck, the
README and the poster may not introduce a figure that is not in `docs/claims.json`, and every
figure in that file carries the command that produces it. Running this script re-runs all of
them and compares.

It is deliberately a whole-document check, not a spot check: a submission whose numbers drift
between the pipeline and the slides is worse than one with fewer numbers.

Usage:
    python3 tools/verify_claims.py              # verify every claim
    python3 tools/verify_claims.py --list       # show the ledger without running it
    python3 tools/verify_claims.py --only rows  # verify one claim

Expected output on a good tree:
    PASS  rows              378212
    PASS  peak_hour         14
    ...
    27/27 claims verified
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDGER = ROOT / "docs" / "claims.json"


def normalise(s: str) -> str:
    """Collapse the thousand-separator and spacing variants we use across documents."""
    s = s.replace("\u00a0", " ").replace("\u202f", " ")
    s = re.sub(r"(?<=\d)[ \u00a0](?=\d{3}\b)", "", s)   # 378 212 -> 378212
    return re.sub(r"\s+", "", s)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", default=None)
    args = ap.parse_args()

    if not LEDGER.exists():
        sys.exit(f"missing {LEDGER.relative_to(ROOT)} — every published number needs a row")

    claims = json.loads(LEDGER.read_text(encoding="utf-8"))
    if args.only:
        claims = [c for c in claims if c["id"] == args.only]
        if not claims:
            sys.exit(f"no claim with id {args.only!r}")

    if args.list:
        for c in claims:
            print(f"{c['id']:24s} {str(c['value']):>14s}  used in: {', '.join(c.get('used_in', []))}")
        return

    failures: list[str] = []
    for c in claims:
        try:
            proc = subprocess.run(c["cmd"], shell=True, cwd=ROOT, capture_output=True,
                                  text=True, timeout=300)
        except subprocess.TimeoutExpired:
            failures.append(f"{c['id']}: command timed out")
            print(f"FAIL  {c['id']:24s} (timeout)")
            continue
        # WHOLE-TOKEN match, not a substring. A plain `in` test let a doctored "1378212"
        # satisfy the claim "378212", and let "0" be satisfied by "10" — the harness could
        # certify a wrong number, which is worse than having no harness. The value must appear
        # not adjacent to another digit or a decimal point, so it works inside labelled output
        # like `rows=189106` while refusing `1378212`.
        haystack = normalise(proc.stdout + "\n" + proc.stderr)
        needle = normalise(str(c["value"]))
        # Guard only the ENDS THAT ARE DIGITS. A labelled value like `share=83.44%` sits flush
        # against the previous label (`pass=393share=...`), so an unconditional lookbehind would
        # reject it; the guard exists to stop `0` matching `10`, which only needs to apply when
        # the needle itself begins or ends with a digit.
        left = r"(?<![\d.])" if needle[:1].isdigit() else ""
        right = r"(?![\d])" if needle[-1:].isdigit() else ""
        pattern = re.compile(left + re.escape(needle) + right)
        matched = bool(pattern.search(haystack))
        if not matched and c.get("artifact"):
            art = ROOT / c["artifact"]
            if art.exists() and art.stat().st_size < 40_000_000:
                blob = art.read_text(encoding="utf-8", errors="ignore")
                matched = bool(pattern.search(normalise(blob))) or \
                          ('"' + str(c["value"]) + '"') in blob
        if matched:
            print(f"PASS  {c['id']:24s} {c['value']}")
        else:
            failures.append(f"{c['id']}: expected {c['value']!r}, not found — cmd: {c['cmd'][:90]}")
            print(f"FAIL  {c['id']:24s} {c['value']}  NOT FOUND")

    print()
    if failures:
        print(f"{len(failures)} of {len(claims)} claims FAILED:\n")
        for f in failures:
            print("  " + f)
        print("\nEither the number moved (update docs/claims.json AND every document that uses it) "
              "or the command is stale. Never delete a row to make this pass.")
        sys.exit(1)
    print(f"{len(claims)}/{len(claims)} claims verified")


if __name__ == "__main__":
    main()
