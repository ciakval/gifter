#!/usr/bin/env bash
# Online backup of Gifter's SQLite database (OPS-06, D-09, D-10).
#
# Runs on the Bombur host as the deploy user (docker group); installed as
# /usr/local/bin/gifter-backup.sh and started nightly by gifter-backup.timer.
# sqlite3 runs INSIDE the gifter-web container (docker exec), so the app keeps running
# and file ownership (container uid 1000) never matters. The copy is VACUUMed, switched
# to rollback-journal mode (one self-contained file) and integrity-checked before it is
# kept. Output: $DEST/$PREFIX-YYYY-MM-DD-HHMMSS.sqlite3, directory 700, file 600.
#
# Settings (environment): CONTAINER=gifter-web DEST=/home/deploy/backups/gifter KEEP=14
#   PREFIX=gifter (lowercase letters and dashes; use another prefix for manual copies,
#   which are never rotated and never write the marker).
#
# Rotation (PREFIX gifter only): copies older than KEEP days are deleted, then all but
# the KEEP newest.
#
# Marker (PREFIX gifter only): the first successful nightly run writes the one-line file
# nightly-backups-since (YYYY-MM-DD) into the container's /app/data. It switches on the
# nightly-backup sentences of /privacy/ (plan 04-03) and is written once, never
# overwritten.
set -euo pipefail
umask 077

CONTAINER="${CONTAINER:-gifter-web}"
DEST="${DEST:-/home/deploy/backups/gifter}"
KEEP="${KEEP:-14}"
PREFIX="${PREFIX:-gifter}"

[[ "$KEEP" =~ ^[1-9][0-9]*$ ]] || { echo "FAIL KEEP must be a positive integer" >&2; exit 2; }
[[ "$PREFIX" =~ ^[a-z-]+$ ]] || { echo "FAIL PREFIX must be lowercase letters and dashes" >&2; exit 2; }

mkdir -p "$DEST"
chmod 700 "$DEST"

STAMP="$(date +%Y-%m-%d-%H%M%S)"
OUT="$DEST/$PREFIX-$STAMP.sqlite3"
TMP="/tmp/gifter-backup-$$-$STAMP.sqlite3"

cleanup() {
  docker exec "$CONTAINER" rm -f "$TMP" >/dev/null 2>&1 || true
  rm -f "$OUT.partial" 2>/dev/null || true
}
trap cleanup EXIT

docker exec "$CONTAINER" sqlite3 -cmd ".timeout 20000" /app/data/db.sqlite3 ".backup $TMP"
docker exec "$CONTAINER" sqlite3 "$TMP" "PRAGMA journal_mode=DELETE; VACUUM;" >/dev/null
CHECK="$(docker exec "$CONTAINER" sqlite3 "$TMP" "PRAGMA integrity_check;" 2>&1 || true)"
if [ "$CHECK" != "ok" ]; then
  echo "FAIL integrity check of the new backup: $CHECK" >&2
  exit 1
fi

docker exec "$CONTAINER" cat "$TMP" > "$OUT.partial"
mv "$OUT.partial" "$OUT"
chmod 600 "$OUT"

if [ "$PREFIX" = "gifter" ]; then
  # Marker: only when absent; write to a temporary name, then rename.
  if ! docker exec "$CONTAINER" sh -c '
    m=/app/data/nightly-backups-since
    [ -e "$m" ] && exit 0
    printf "%s\n" "$1" > "$m.tmp" && mv "$m.tmp" "$m"
  ' sh "$(date +%F)"; then
    echo "FAIL could not write the nightly-backups-since marker" >&2
    exit 1
  fi

  # Rotation: by age, then by count. Safe under pipefail when nothing matches.
  find "$DEST" -maxdepth 1 -type f -name 'gifter-*.sqlite3' -mtime +$((KEEP - 1)) -delete
  { find "$DEST" -maxdepth 1 -type f -name 'gifter-*.sqlite3' -printf '%f\n' || true; } \
    | sort | head -n -"$KEEP" | while read -r old; do rm -f "$DEST/$old"; done || true
fi

echo "BACKUP OK $OUT"
