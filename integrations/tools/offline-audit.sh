#!/usr/bin/env bash
# Offline audit: what in the integration still names an off-origin URL.
#
# The demo must be servable with no network at all. This separates *requests*
# (src=, url(), @import, iframe src — things a browser fetches) from *links*
# (href= — things a user may click) and from text, and exits non-zero if any
# request survives.
#
# Usage: bash integrations/tools/offline-audit.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
SITE=integrations/municipal-site

echo "== off-origin REQUESTS (must be 0) =="
REQ=0
# `[^-a-zA-Z0-9_]src=` so that the replica's own `data-mock-embed-src`
# placeholder marker — which google-stubs.js renders as a local notice — is not
# mistaken for a fetchable attribute.
for pat in '(^|[^-a-zA-Z0-9_])src="https?://' "(^|[^-a-zA-Z0-9_])src='https?://" 'url\((https?:)?//' '@import[^;]*https?://' 'data-background="https?://'; do
    n=$(grep -rEo "$pat" "$SITE" --include='*.html' --include='*.css' --include='*.js' 2>/dev/null | wc -l | tr -d ' ')
    printf '  %-34s %s\n' "$pat" "$n"
    REQ=$((REQ + n))
done
echo "  TOTAL REQUESTS: $REQ"

echo
echo "== the one known non-request marker =="
grep -rEoh 'data-mock-embed-src="[^"]*"' "$SITE" --include='*.html' | sort -u | cut -c1-120
echo "  (a data- attribute on a local placeholder div; nothing fetches it)"

echo
echo "== links and text naming an off-origin URL (informational) =="
echo -n "  href=\"http(s)://...\"   : "
grep -rEo 'href="https?://' "$SITE" --include='*.html' | wc -l | tr -d ' '
echo -n "  bare URLs in body text : "
grep -rEo '(^|[^"'"'"'=])https?://[a-z0-9.-]+' "$SITE" --include='*.html' | wc -l | tr -d ' '
echo -n "  in JS string literals  : "
grep -rEo 'https?://[a-z0-9.-]+' "$SITE" --include='*.js' | wc -l | tr -d ' '
echo -n "  xmlns / schema (not a URL fetch): "
grep -rEo 'https?://(www\.)?w3\.org[^"'"'"' )]*' "$SITE" --include='*.html' --include='*.svg' | wc -l | tr -d ' '

echo
echo "== distinct off-origin hosts named anywhere =="
grep -rEoh 'https?://[a-z0-9.-]+' "$SITE" --include='*.html' --include='*.css' --include='*.js' \
  | sed 's|https\?://||' | sort | uniq -c | sort -rn | head -20

echo
echo "== local placeholder assets (replacements for what was off-origin) =="
ls -la "$SITE/assets/mock/offline/" 2>/dev/null

echo
echo "== the mandated OpenStreetMap exception =="
grep -rn 'openstreetmap' "$SITE" --include='*.html' | cut -c1-160

echo
if [ "$REQ" -ne 0 ]; then
    echo "FAIL: $REQ off-origin request pattern(s) remain"
    exit 1
fi
echo "PASS: no request in $SITE can leave 127.0.0.1"
