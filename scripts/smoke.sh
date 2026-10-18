#!/usr/bin/env bash
# HTTP contract smoke test for a running Gifter.
#
#   scripts/smoke.sh BASE_URL [HOST]
#
# With HOST, every request carries "Host: HOST" and "X-Forwarded-Proto: https"
# (simulating Caddy in front of a local container). Without it, BASE_URL is
# tested as-is (e.g. https://gifter.remesh.cz).
set -euo pipefail

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
  echo "usage: $0 BASE_URL [HOST]" >&2
  exit 2
fi

BASE="${1%/}"
HOST="${2:-}"
if [ -n "$HOST" ]; then
  ORIGIN="https://$HOST"
  PROXY_HEADERS=(-H "Host: $HOST" -H "X-Forwarded-Proto: https")
else
  ORIGIN="$BASE"
  PROXY_HEADERS=()
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

pass() { echo "PASS $1"; }
fail() { echo "FAIL $1" >&2; exit 1; }

# curl wrapper: get HEAD_FILE BODY_FILE PATH -> prints the HTTP status code
get() {
  curl -sS -o "$2" -D "$1" -w '%{http_code}' "${PROXY_HEADERS[@]}" "$BASE$3"
}

header() { # header FILE NAME -> value of the first matching header (case-insensitive)
  grep -i "^$2:" "$1" | head -n 1 | sed -E "s/^[^:]*:[[:space:]]*//; s/\r$//" || true
}

# (a) landing page with the Google sign-in form
code="$(get "$TMP/a.head" "$TMP/a.body" /)"
[ "$code" = "200" ] || fail "(a) GET / returned $code, expected 200"
grep -q 'action="/accounts/google/login/"' "$TMP/a.body" \
  || fail '(a) landing page lacks action="/accounts/google/login/"'
pass "(a) GET / is 200 and carries the Google sign-in form"

# (b) HSTS
hsts="$(header "$TMP/a.head" strict-transport-security)"
case "$hsts" in
  *includeSubDomains*) pass "(b) Strict-Transport-Security: $hsts" ;;
  *) fail "(b) Strict-Transport-Security missing includeSubDomains (got: '${hsts:-none}')" ;;
esac

# (c) protected page redirects to the landing page with next preserved
code="$(get "$TMP/c.head" "$TMP/c.body" /events/)"
loc="$(header "$TMP/c.head" location)"
[ "$code" = "302" ] || fail "(c) GET /events/ returned $code, expected 302"
case "$loc" in
  "/?next=/events/" | "$ORIGIN/?next=/events/" | "$BASE/?next=/events/") pass "(c) GET /events/ redirects to $loc" ;;
  *) fail "(c) GET /events/ Location was '$loc', expected /?next=/events/" ;;
esac

# (d) old password login is gone, and DEBUG is off
code="$(get "$TMP/d.head" "$TMP/d.body" /login/)"
[ "$code" = "404" ] || fail "(d) GET /login/ returned $code, expected 404"
if grep -q 'Using the URLconf' "$TMP/d.body"; then
  fail "(d) 404 page is Django's debug page: DEBUG is on"
fi
pass "(d) GET /login/ is a plain 404 (DEBUG off)"

# (e) default admin path is gone
code="$(get "$TMP/e.head" "$TMP/e.body" /admin/)"
[ "$code" = "404" ] || fail "(e) GET /admin/ returned $code, expected 404"
pass "(e) GET /admin/ is 404"

# (f) vendored static file served without login
code="$(get "$TMP/f.head" "$TMP/f.body" /static/vendor/bootstrap/bootstrap.min.css)"
[ "$code" = "200" ] || fail "(f) static Bootstrap CSS returned $code, expected 200"
pass "(f) static Bootstrap CSS is served anonymously"

# (g) OAuth start: POST with CSRF token -> redirect to Google with the right redirect_uri
csrf_cookie="$(grep -i '^set-cookie: *csrftoken=' "$TMP/a.head" | head -n 1 \
  | sed -E 's/^[^=]*=([^;]*).*/\1/; s/\r$//' || true)"
csrf_form="$(grep -o 'name="csrfmiddlewaretoken" value="[^"]*"' "$TMP/a.body" | head -n 1 \
  | sed -E 's/.*value="([^"]*)"/\1/' || true)"
[ -n "$csrf_cookie" ] || fail "(g) no csrftoken cookie in the landing page response"
[ -n "$csrf_form" ] || fail "(g) no csrfmiddlewaretoken in the landing page form"
code="$(curl -sS -o "$TMP/g.body" -D "$TMP/g.head" -w '%{http_code}' "${PROXY_HEADERS[@]}" \
  -H "Cookie: csrftoken=$csrf_cookie" -H "Referer: $ORIGIN/" -H "Origin: $ORIGIN" \
  --data-urlencode "csrfmiddlewaretoken=$csrf_form" --data-urlencode "next=/events/" \
  "$BASE/accounts/google/login/")"
loc="$(header "$TMP/g.head" location)"
[ "$code" = "302" ] || fail "(g) POST /accounts/google/login/ returned $code, expected 302"
case "$loc" in
  https://accounts.google.com/*) ;;
  *) fail "(g) Location does not start with https://accounts.google.com/ (got: $loc)" ;;
esac
case "$loc" in
  *code_challenge_method=S256*) ;;
  *) fail "(g) Location lacks code_challenge_method=S256 (PKCE)" ;;
esac
expected_uri="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1] + "/accounts/google/login/callback/", safe=""))' "$ORIGIN")"
case "$loc" in
  *"redirect_uri=$expected_uri"*) ;;
  *) fail "(g) Location lacks redirect_uri=$expected_uri (got: $loc)" ;;
esac
client_id="$(printf '%s' "$loc" | sed -E 's/.*[?&]client_id=([^&]*).*/\1/')"
echo "client_id=$client_id"
pass "(g) OAuth start redirects to Google with redirect_uri $ORIGIN/accounts/google/login/callback/"

echo "SMOKE OK"
