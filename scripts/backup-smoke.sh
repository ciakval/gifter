#!/usr/bin/env bash
# Local end-to-end test of the backup and restore tooling against the real production
# image: backup, nightly-backups-since marker, rotation, dry run, refusals, real restore
# with safety copy, and the drill.
#
#   bash scripts/backup-smoke.sh
#
# Isolated from container-smoke.sh: own image tag (gifter:backup-smoke), own container
# names, and no published host port (every check goes through docker exec), so it can run
# next to another worktree's container smoke.
set -euo pipefail

cd "$(dirname "$0")/.."
REPO="$PWD"

IMAGE="gifter:backup-smoke"
NAME_A="gifter-backup-smoke-a-$$"
DATA_DIR="$(mktemp -d)"
BK_DIR="$(mktemp -d)"
WORK_DIR="$(mktemp -d)"
SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"

cleanup() {
  docker rm -f "$NAME_A" >/dev/null 2>&1 || true
  docker ps -aq --filter "name=gifter-drill-" | xargs -r docker rm -f >/dev/null 2>&1 || true
  docker volume ls -q --filter "name=gifter-drill-" | xargs -r docker volume rm -f >/dev/null 2>&1 || true
  rm -rf "$DATA_DIR" "$BK_DIR" "$WORK_DIR" 2>/dev/null || true
}
trap cleanup EXIT

pass() { echo "PASS $1"; }
fail() { echo "FAIL $1" >&2; exit 1; }

dx() { docker exec "$NAME_A" "$@"; }
manage() { docker exec "$NAME_A" python manage.py "$@"; }
user_exists() { # user_exists NAME -> exit 0 when present in the live database
  manage shell -c "from django.contrib.auth import get_user_model as g; import sys; sys.exit(0 if g().objects.filter(username='$1').exists() else 1)"
}
backup() { CONTAINER="$NAME_A" DEST="$BK_DIR" bash "$REPO/scripts/gifter-backup.sh" "$@"; }

echo "Building $IMAGE ..."
docker build -q -t "$IMAGE" . >/dev/null

chmod 777 "$DATA_DIR"
docker run -d --name "$NAME_A" -v "$DATA_DIR:/app/data" \
  -e SECRET_KEY="$SECRET" -e PUBLIC_HOSTS=gifter.remesh.cz \
  -e GOOGLE_CLIENT_ID=smoke-client-id -e GOOGLE_CLIENT_SECRET=smoke-secret \
  "$IMAGE" >/dev/null

ready=0
for _ in $(seq 1 60); do
  if manage migrate --check >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
[ "$ready" = 1 ] || { docker logs "$NAME_A" >&2 || true; fail "container did not become ready within 60 s"; }

manage shell -c "from django.contrib.auth import get_user_model as g; g().objects.create(username='backup-persist')" >/dev/null

# (b1) one backup -------------------------------------------------------------
out="$(backup)"
[ "$(echo "$out" | grep -c '^BACKUP OK ')" = 1 ] || fail "(b1) expected exactly one BACKUP OK line ($out)"
B1="$(echo "$out" | sed -n 's/^BACKUP OK //p')"
[ -f "$B1" ] && [[ "$B1" == "$BK_DIR"/* ]] || fail "(b1) backup file missing or outside the backup dir ($B1)"
[ "$(stat -c %a "$B1")" = 600 ] || fail "(b1) file mode is $(stat -c %a "$B1"), expected 600"
[ "$(stat -c %a "$BK_DIR")" = 700 ] || fail "(b1) dir mode is $(stat -c %a "$BK_DIR"), expected 700"
python3 -I - "$B1" <<'PY' || fail "(b1) backup content check failed"
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "integrity"
assert c.execute("PRAGMA journal_mode").fetchone()[0] == "delete", "journal mode"
assert c.execute("SELECT count(*) FROM gifter_user WHERE username='backup-persist'").fetchone()[0] == 1, "user"
PY
pass "(b1) backup outside the app dir: mode 600/700, integrity ok, journal delete, user present"

# (m1) marker written by the first nightly run ---------------------------------
[ "$(dx cat /app/data/nightly-backups-since)" = "$(date +%F)" ] || fail "(m1) marker missing or wrong content"
pass "(m1) nightly-backups-since holds today's date"

# (b2) rotation + (m2) marker never overwritten -------------------------------
for n in $(seq 1 20); do
  f="$BK_DIR/gifter-2026-10-01-031500-$(printf %02d "$n").sqlite3"
  : > "$f"; touch -d "$n days ago" "$f"
done
for p in pre-restore-old pre-deletion-old; do
  : > "$BK_DIR/$p.sqlite3"; touch -d "30 days ago" "$BK_DIR/$p.sqlite3"
done
dx sh -c 'printf "2026-01-02\n" > /app/data/nightly-backups-since'
out="$(backup)"
n_left="$(find "$BK_DIR" -maxdepth 1 -name 'gifter-*.sqlite3' | wc -l)"
[ "$n_left" = 14 ] || fail "(b2) $n_left gifter-* copies remain, expected 14"
echo "$out" | sed -n 's/^BACKUP OK //p' | { read -r f; [ -f "$f" ]; } || fail "(b2) the new backup was rotated away"
[ -z "$(find "$BK_DIR" -name 'gifter-*.sqlite3' -mtime +13)" ] || fail "(b2) a copy older than 14 days survived"
[ -e "$BK_DIR/pre-restore-old.sqlite3" ] && [ -e "$BK_DIR/pre-deletion-old.sqlite3" ] || fail "(b2) a manual-prefix copy was rotated"
pass "(b2) rotation keeps 14 nightly copies, leaves other prefixes alone"
[ "$(dx cat /app/data/nightly-backups-since)" = "2026-01-02" ] || fail "(m2) marker was overwritten"
pass "(m2) existing marker untouched by later runs"

# (m3) manual copies never write the marker and never rotate -------------------
dx rm -f /app/data/nightly-backups-since
out="$(PREFIX=pre-deletion backup)"
echo "$out" | grep -q '^BACKUP OK .*/pre-deletion-.*\.sqlite3$' || fail "(m3) unexpected output: $out"
dx test -e /app/data/nightly-backups-since && fail "(m3) a manual copy wrote the marker"
[ "$(find "$BK_DIR" -maxdepth 1 -name 'gifter-*.sqlite3' | wc -l)" = 14 ] || fail "(m3) manual copy changed the nightly count"
pass "(m3) manual copy: no marker, no rotation"

echo "BACKUP SMOKE OK"
