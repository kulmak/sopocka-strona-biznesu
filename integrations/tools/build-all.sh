#!/usr/bin/env bash
# Rebuild the whole municipal integration from the read-only replica.
#
# Order matters: the page builder regenerates pl/strona-biznesu/index.html from
# its donor, so the augmentation and navigation passes must run after it.
#
#   ../karta-mockup/site/            READ-ONLY source, never touched
#   integrations/municipal-site/     the deliverable
#
# Usage: bash integrations/tools/build-all.sh
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "== 1/4 bundle the replica (images re-encoded, snapshots dropped)"
python3 integrations/tools/bundle-replica.py --force

echo "== 2/4 remove every off-origin request"
python3 integrations/tools/offline-hardening.py

echo "== 3/4 build the Strona Biznesu tab page"
python3 integrations/tools/build-tab-page.py

echo "== 4/4 load the augmentation on every page, then insert the nav item"
python3 integrations/tools/apply-augmentation.py
python3 integrations/tools/apply-nav.py

echo
echo "== verify (all three must be no-ops)"
python3 integrations/tools/apply-augmentation.py --check
python3 integrations/tools/apply-nav.py --check
python3 integrations/tools/offline-hardening.py --check
