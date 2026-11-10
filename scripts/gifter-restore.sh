#!/usr/bin/env bash
# Restore a Gifter backup (OPS-06, D-11). Runs on the Bombur host as the deploy user;
# installed as /usr/local/bin/gifter-restore.sh next to gifter-backup.sh.
#
#   gifter-restore.sh BACKUP            dry run: validate only, change nothing
#   gifter-restore.sh BACKUP --yes      replace the live database (safety copy first)
#   gifter-restore.sh --drill BACKUP    restore into a throwaway container on a fresh
#                                       volume; production is never touched
#
# Settings (environment): CONTAINER=gifter-web  DEST=/home/deploy/backups/gifter
# A backup is refused (and nothing changes) unless PRAGMA integrity_check says ok and it
# has a django_migrations table. No mode prints claims, chip-ins or notes, or counts of
# them: the operator is also a giftee. The drill reports users, events and wishes only.
set -euo pipefail
umask 077

CONTAINER="${CONTAINER:-gifter-web}"
DEST="${DEST:-/home/deploy/backups/gifter}"
export DEST
HERE="$(dirname "$(readlink -f "$0")")"

usage() {
  echo "usage: $0 BACKUP [--yes] | $0 --drill BACKUP" >&2
  exit 2
}

MODE=""
FILE=""
case "${1:-}" in
  --drill) [ $# -eq 2 ] || usage; MODE=drill; FILE="$2" ;;
  "") usage ;;
  -*) usage ;;
  *)
    FILE="$1"
    case "${2:-}" in
      "") MODE=dry ;;
      --yes) [ $# -eq 2 ] || usage; MODE=yes ;;
      *) usage ;;
    esac
    ;;
esac

UPLOAD="/tmp/gifter-restore-$$.sqlite3"
TARGET="$CONTAINER"
DRILL=""

cleanup() {
  docker exec "$TARGET" rm -f "$UPLOAD" >/dev/null 2>&1 || true
  if [ -n "$DRILL" ]; then
    docker rm -f "$DRILL" >/dev/null 2>&1 || true
    docker volume rm -f "$DRILL" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

wait_migrated() { # wait_migrated CONTAINER SECONDS
  for _ in $(seq 1 "$2"); do
    if docker exec "$1" python manage.py migrate --check >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  echo "FAIL $1 did not pass migrate --check within $2 s" >&2
  exit 1
}

validate() { # upload FILE into TARGET and check it
  [ -r "$FILE" ] || { echo "FAIL $FILE is not an intact Gifter backup: not readable" >&2; exit 1; }
  docker exec -i "$TARGET" sh -c "cat > $UPLOAD" < "$FILE"
  local check tables
  check="$(docker exec "$TARGET" sqlite3 "$UPLOAD" "PRAGMA integrity_check;" 2>&1 || true)"
  if [ "$check" != "ok" ]; then
    echo "FAIL $FILE is not an intact Gifter backup: integrity check says '$(echo "$check" | head -n 1)'" >&2
    exit 1
  fi
  tables="$(docker exec "$TARGET" sqlite3 "$UPLOAD" \
    "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='django_migrations';" 2>&1 || true)"
  if [ "$tables" != "1" ]; then
    echo "FAIL $FILE is not an intact Gifter backup: no django_migrations table" >&2
    exit 1
  fi
}

replace_database() { # online restore into TARGET's live database, then restart
  docker exec "$TARGET" sqlite3 -cmd ".timeout 20000" /app/data/db.sqlite3 ".restore $UPLOAD"
  local check
  check="$(docker exec "$TARGET" sqlite3 /app/data/db.sqlite3 "PRAGMA integrity_check;" 2>&1 || true)"
  [ "$check" = "ok" ] || { echo "FAIL integrity check of the restored database: $check" >&2; exit 1; }
  docker restart "$TARGET" >/dev/null
  wait_migrated "$TARGET" 90
}

case "$MODE" in
  dry)
    validate
    echo "DRY RUN OK $FILE is an intact Gifter backup; nothing was restored. Repeat with --yes to replace the database in $CONTAINER."
    ;;
  yes)
    validate
    SAFETY_OUT="$(PREFIX=pre-restore CONTAINER="$CONTAINER" DEST="$DEST" bash "$HERE/gifter-backup.sh")" \
      || { echo "FAIL could not save a safety copy; the live database was not touched" >&2; exit 1; }
    SAFETY="$(echo "$SAFETY_OUT" | sed -n 's/^BACKUP OK //p' | tail -n 1)"
    [ -n "$SAFETY" ] || { echo "FAIL no safety copy path; the live database was not touched" >&2; exit 1; }
    replace_database
    echo "RESTORE OK $FILE restored into $CONTAINER; safety copy $SAFETY (remove it once the site is verified)"
    ;;
  drill)
    IMAGE="$(docker inspect -f '{{.Config.Image}}' "$CONTAINER")"
    DRILL="gifter-drill-$$"
    docker volume create "$DRILL" >/dev/null
    docker run -d --name "$DRILL" -v "$DRILL:/app/data" \
      -e SECRET_KEY="$(od -An -tx1 -N32 /dev/urandom | tr -d ' \n')" \
      -e GOOGLE_CLIENT_ID=drill -e GOOGLE_CLIENT_SECRET=drill -e PUBLIC_HOSTS=localhost \
      "$IMAGE" >/dev/null
    TARGET="$DRILL"
    wait_migrated "$TARGET" 90
    validate
    replace_database
    COUNTS="$(docker exec "$TARGET" python manage.py shell -v 0 -c \
      "from django.contrib.auth import get_user_model; from gifter.models import Event, Wish; print('COUNTS', get_user_model().objects.count(), Event.objects.count(), Wish.objects.count())" \
      | sed -n 's/^COUNTS //p' | tail -n 1)"
    read -r U E W <<<"$COUNTS"
    [ -n "${W:-}" ] || { echo "FAIL could not count rows in the drill container" >&2; exit 1; }
    echo "DRILL OK $FILE: $U users, $E events, $W wishes"
    ;;
esac
