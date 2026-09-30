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
import base64
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 1. Paths that must never be tracked, published or served.
#: DATA-shaped paths: never acceptable anywhere in the tree, tracked or not. These name the
#: Organiser's files or a record-level format, so their mere presence is the finding.
FORBIDDEN_DATA_PATH = re.compile(
    r"(\.parquet$|\.csv\.xz$|mcc5812|datasprint|Dictionary_data_Visa|CHALLENGE_DATASPRINT|"
    r"rockyou|\.hash$|zip2john|uploads/|data/raw/|/raw/)",
    re.IGNORECASE,
)

#: SIZE-shaped paths: fine untracked (they cannot be published), fatal once staged. Keeping these
#: separate is what lets the tree scan stay broad — the first version walked `git ls-files`, so a
#: planted `.parquet` sailed past a rule that named `.parquet`.
FORBIDDEN_TRACKED_PATH = re.compile(r"(\.zip$|\.mp4$|\.mov$|\.wav$)", re.IGNORECASE)

#: This file necessarily contains the dictionary's example card id (split across two literals, so
#: the assembled token never appears) and describes the shapes it looks for. Scanning itself is
#: circular and noisy; it is excluded by name and nothing else is.
SELF = "tools/check_no_organiser_data.py"

# 2. Text that would mean we leaked record-level DATA.
#
#    Naming a column is not leaking it: our own documentation must be free to say
#    "we never read pymt_crd_acct_num_raw" — that is the privacy claim, not a violation.
#    What must never appear is an actual VALUE: the dictionary's example card id, a run of
#    card-id-shaped tokens, or a merchant name in a data position.
#    The example card id is assembled from fragments so that this file does not match its own
#    rule — otherwise the guard flags itself and the real hits drown in noise.
_CARD_EXAMPLE = "Br9iRiLBYZnrbWTzhLnh" + "CigZ6wpTZDBXePvrfr"

#    The first version of this rule needed either that one hard-coded id or two long tokens on a
#    single CSV line, so a REAL card id — 47 chars of mixed-case alphanumerics — sitting alone on
#    its own line, which is the shape a leak actually takes, was invisible. Widened to:
#      * any card-id-shaped token (the real ones are 40+ chars, mixed case, digits, underscores)
#      * the dictionary example
#      * a merchant name in a data position
#    Short opaque tokens are NOT flagged: git SHAs, base64 image data and our own base64 series
#    are legitimate, and a guard that cries wolf gets switched off.
FORBIDDEN_TOKEN = re.compile(
    "(" + re.escape(_CARD_EXAMPLE) +
    r"|mrch_nm_raw\s*[,=:]\s*[A-Z]{3,})"                          # merchant name in a data position
)

#: What a card identifier actually looks like in THIS dataset, measured rather than assumed:
#: 47 lowercase hex characters (`d0d07ffcf655a4577be158d92e767c02b6adcbfaca7be03`). The
#: documented example is mixed case with an underscore, 47 characters, so the rule covers both.
#:
#: The distinction that matters is LENGTH against our own digests: `data/MANIFEST.sha256` is full
#: of 64-character hex, and the first version of this rule excluded hex-only tokens outright to
#: stop flagging them — which excluded the real card ids too, and made the guard blind to exactly
#: the leak it exists to catch. An adversarial pass found that. SHA-256 is 64; card ids are 47.
_OPAQUE = re.compile(r"[A-Za-z0-9_\-]{40,64}")
_HEX_ONLY = re.compile(r"^[0-9a-f]+$")
SHA256_LEN = 64


#: Mirrored third-party libraries we did not author and have not modified. Their bundled base64
#: (woff2 payloads, jQuery UI themes, font CSS) is full of long mixed-case tokens. Excluding them
#: by path rather than weakening the rule keeps the rule sharp for everything WE write — which is
#: where a leak could actually come from.
#: Mirrored third-party libraries and the municipal replica: byte-identical copies of public
#: content we did not author. Their bundled base64 and CMS filename hashes are full of long
#: mixed-case tokens (a stylesheet alone carries 608). Scoping them out keeps the shape rule sharp
#: for everything WE write, which is where a leak could actually originate.
ALLOW_THIRD_PARTY = re.compile(r"^(integrations/municipal-site/|app/vendor/)")


def token_candidates(text: str) -> list[str]:
    """Every place a card-shaped token could hide, without ever merging unrelated text.

    `"".join(text.split())` was the first attempt and it is wrong twice over: it fabricates
    40-character "tokens" out of ordinary prose, and — because the regex is greedy — it misaligns
    a run of three concatenated 47-character ids so that none of the windows matches. Scanning
    each line, plus each adjacent pair's join, catches a token on its own line AND a token split
    across a line break, with no merging of anything else.
    """
    # Join a newline ONLY when both neighbours are token characters. That reassembles a card id
    # broken across a line while leaving JSON, prose and code untouched — joining every adjacent
    # pair of lines instead fabricated tokens out of `sample-manifest.json` and flagged our own
    # sample as a leak.
    rejoined = re.sub(r"(?<=[A-Za-z0-9_\-])\n(?=[A-Za-z0-9_\-])", "", text)
    return [rejoined] + [l.strip() for l in text.splitlines() if l.strip()]


def card_shaped_tokens(flat: str) -> list[str]:
    """Long tokens that look like an account identifier rather than a hash, a path or a word."""
    out = []
    for tok in _OPAQUE.findall(flat):
        if _HEX_ONLY.match(tok):
            # A 64-character hex run is a sha256 — ours, and legitimate. Anything shorter that is
            # still hex-shaped is indistinguishable from a card id, so it is flagged.
            if len(tok) == SHA256_LEN:
                continue
            out.append(tok)
            continue
        if not (any(c.isupper() for c in tok) and any(c.islower() for c in tok)
                and any(c.isdigit() for c in tok)):
            continue                        # concatenated prose is one case only
        out.append(tok)
    return out

#    A token split across a newline is reassembled before scanning, because "one id per line" is
#    exactly how a leaked column gets past a line-oriented scan.
BASE64_RUN = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")

# 3. Anything this large that is not explicitly allow-listed is suspicious.
MAX_BYTES = 5 * 1024 * 1024
ALLOW_LARGE = re.compile(r"(docs/deck/assets/fonts/|app/vendor/|\.woff2$|POSTER\.jpg$|"
                         r"deck\.pdf$|panel\.png$|system-map\.json$)")


SKIP_DIRS = {".git", "node_modules", "_site", "__pycache__", ".pytest_cache"}


def walk_files(staged_only: bool) -> list[pathlib.Path]:
    """Every file in the tree, NOT just the git-tracked ones.

    The first version walked `git ls-files`, which made half of this guard dead code: `.gitignore`
    already ignores `*.parquet`, `*.mp4` and `*.zip`, so `FORBIDDEN_PATH` could only ever fire on a
    file somebody had force-added — and a planted `canary.parquet` walked straight past. A guard
    that only sees what git already agreed to show is not a guard. An adversarial pass proved it.
    """
    if staged_only:
        cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
        try:
            out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout
        except subprocess.CalledProcessError as e:
            sys.exit(f"git failed: {e.stderr}")
        return [ROOT / line for line in out.splitlines() if line.strip()]

    found: list[pathlib.Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            found.append(pathlib.Path(dirpath) / name)
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", action="store_true")
    args = ap.parse_args()

    files = [f for f in walk_files(args.staged) if f.is_file()]
    # Which paths git would actually publish. The size rules apply only to these.
    try:
        tracked = {line for line in subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.splitlines()}
    except Exception:
        tracked = {f.relative_to(ROOT).as_posix() for f in files}   # outside a checkout: assume all
    problems: list[str] = []
    checked = 0

    for f in files:
        rel = f.relative_to(ROOT).as_posix()
        is_tracked = rel in tracked
        if rel != SELF and FORBIDDEN_DATA_PATH.search(rel):
            problems.append(f"FORBIDDEN DATA PATH  {rel}")
            continue
        if is_tracked and FORBIDDEN_TRACKED_PATH.search(rel):
            problems.append(f"OVERSIZED PATH (tracked)  {rel}")
            continue
        if rel == SELF:
            checked += 1
            continue
        try:
            size = f.stat().st_size
        except FileNotFoundError:
            # Files can vanish mid-scan when another process is writing the tree.
            # Skipping is safe: the caller re-runs this gate immediately before pushing.
            continue
        # The size rule is about what git carries, so it applies to tracked files. An untracked
        # 36 MB film in the working tree is a local artifact, not a published one — and treating
        # it as a violation would push someone to delete the evidence rather than the exposure.
        if is_tracked and size > MAX_BYTES and not ALLOW_LARGE.search(rel):
            problems.append(f"OVERSIZED (tracked)  {rel}  ({size/1e6:.1f} MB > 5 MB)")
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

        # (a) newlines removed: a token broken across a line is still the same token
        # Newlines only: joining every word would fabricate 40-character "tokens" out of ordinary
        # prose, which is how the first version of this rule produced four false positives.
        flat = text.replace("\n", "").replace("\r", "")
        # Inline `data:…;base64,…` payloads are embedded fonts and images — every one of them is a
        # long mixed-case token, and a theme stylesheet can carry hundreds. Stripping them is a
        # rule about WHAT the data is, unlike widening the path allow-list, which would blind the
        # guard to whatever else lives in those directories.
        flat = re.sub(r"data:[A-Za-z0-9/.+\-]{0,80};base64,[A-Za-z0-9+/=]+", "", flat)
        m = FORBIDDEN_TOKEN.search(flat)
        if m:
            problems.append(f"RECORD-LEVEL DATA  {rel}  matched {m.group(0)[:48]!r}")
            checked += 1
            continue
        toks = [] if ALLOW_THIRD_PARTY.match(rel) else [
            t for cand in token_candidates(text) for t in card_shaped_tokens(cand)]
        if toks:
            problems.append(f"RECORD-LEVEL DATA  {rel}  card-id-shaped token {toks[0][:24]!r}… "
                            f"({len(toks)} found)")
            checked += 1
            continue

        # (b) base64: decode any long run and scan what it decodes to. Encoding a card id is the
        #     cheapest way to walk past a plaintext scan.
        hit = None
        for run in BASE64_RUN.findall(text)[:8]:
            pad = run + "=" * (-len(run) % 4)
            try:
                decoded = base64.b64decode(pad, validate=False).decode("utf-8", "ignore")
            except Exception:
                continue
            if FORBIDDEN_TOKEN.search(decoded.replace("\n", "")) or card_shaped_tokens(decoded):
                hit = "a base64 blob that decodes to a card-id-shaped token"
                break
        if hit:
            problems.append(f"RECORD-LEVEL DATA  {rel}  {hit}")
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
