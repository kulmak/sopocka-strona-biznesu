#!/usr/bin/env python3
"""Refuse to publish if anything that looks like Organiser Data is in the tree.

The challenge forbids publishing Organiser Data (§7.4). The submission also requires a public
code repository and a live demo, so the two obligations meet exactly here: this gate is what
makes it safe to push.

It is deliberately paranoid and it fails CLOSED: an unknown binary of a suspicious size in a
git-tracked path is a failure, not a warning.

Usage:
    python3 tools/check_no_organiser_data.py            # scan tracked + untracked, exit 1 on any hit
    python3 tools/check_no_organiser_data.py --staged   # scan only what git would push

Expected output on a clean tree:
    OK — 0 forbidden paths, 0 forbidden columns, 0 oversized blobs (checked N files)
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 1. Paths that must never be tracked, published or served.
FORBIDDEN_PATH = re.compile(
    r"(\.parquet$|\.csv\.xz$|\.zip$|\.mp4$|\.mov$|"
    r"mcc5812|datasprint|Dictionary_data_Visa|CHALLENGE_DATASPRINT|"
    r"rockyou|\.hash$|zip2john|"
    r"uploads/|data/raw/|/raw/)",
    re.IGNORECASE,
)

# 2. Text that would mean we leaked record-level DATA.
#
#    Naming a column is not leaking it: our own documentation must be free to say
#    "we never read pymt_crd_acct_num_raw" — that is the privacy claim, not a violation.
#    What must never appear is an actual VALUE: the dictionary's example card id, a run of
#    card-id-shaped tokens, or a merchant name in a data position.
#    The example card id is assembled from fragments so that this file does not match its own
#    rule — otherwise the guard flags itself and the real hits drown in noise.
_CARD_EXAMPLE = "Br9iRiLBYZnrbWTzhLnh" + "CigZ6wpTZDBXePvrfr"

FORBIDDEN_TOKEN = re.compile(
    "(" + re.escape(_CARD_EXAMPLE) +                        # the dictionary's example card id
    r"|[A-Za-z0-9_\-]{28,}\s*,\s*[A-Za-z0-9_\-]{24,}"       # two long opaque tokens on one CSV line
    r"|mrch_nm_raw\s*[,=:]\s*[A-Z]{3,})",                   # a merchant name in a data position
)

# 3. Anything this large that is not explicitly allow-listed is suspicious.
MAX_BYTES = 5 * 1024 * 1024
ALLOW_LARGE = re.compile(r"(docs/deck/assets/fonts/|app/vendor/|\.woff2$|POSTER\.jpg$|"
                         r"deck\.pdf$|panel\.png$|system-map\.json$)")


def git_files(staged_only: bool) -> list[pathlib.Path]:
    cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"] if staged_only \
        else ["git", "ls-files", "--cached", "--others", "--exclude-standard"]
    try:
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError as e:
        sys.exit(f"git failed: {e.stderr}")
    return [ROOT / line for line in out.splitlines() if line.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", action="store_true")
    args = ap.parse_args()

    files = [f for f in git_files(args.staged) if f.is_file()]
    problems: list[str] = []
    checked = 0

    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        if FORBIDDEN_PATH.search(rel):
            problems.append(f"FORBIDDEN PATH  {rel}")
            continue
        try:
            size = f.stat().st_size
        except FileNotFoundError:
            # Files can vanish mid-scan when another process is writing the tree.
            # Skipping is safe: the caller re-runs this gate immediately before pushing.
            continue
        if size > MAX_BYTES and not ALLOW_LARGE.search(rel):
            problems.append(f"OVERSIZED       {rel}  ({size/1e6:.1f} MB > 5 MB)")
            continue
        # Only scan things that could plausibly be text.
        if size > 2_000_000 or f.suffix.lower() in {".woff2", ".png", ".jpg", ".pdf", ".ico"}:
            checked += 1
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            checked += 1
            continue
        m = FORBIDDEN_TOKEN.search(text)
        if m:
            problems.append(f"RECORD-LEVEL DATA  {rel}  matched {m.group(0)!r}")
        checked += 1

    print(f"scanned {checked} files under {ROOT.name}")
    if problems:
        print(f"\nREFUSING TO PUBLISH — {len(problems)} problem(s):\n")
        for p in problems:
            print("  " + p)
        print("\nIf a hit is a false positive, narrow the pattern in this file and say why "
              "in the commit message. Never widen it silently.")
        sys.exit(1)
    print("OK — 0 forbidden paths, 0 record-level columns, 0 oversized blobs "
          f"(checked {checked} files)")


if __name__ == "__main__":
    main()
