#!/usr/bin/env bash
# Build the production image and prove it behaves as it will on Bombur:
# non-root, nothing secret baked in, HTTPS redirect, proxy-aware OAuth URI,
# WhiteNoise static files, SQLite (WAL) data surviving container replacement.
#
#   bash scripts/container-smoke.sh        (SMOKE_PORT defaults to 18000)
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE="gifter:smoke"
PORT="${SMOKE_PORT:-18000}"
HOST_NAME="gifter.remesh.cz"
NAME_A="gifter-smoke-a-$$"
NAME_B="gifter-smoke-b-$$"
NAME_S="gifter-smoke-static-$$"
DATA_DIR="$(mktemp -d)"
WORK_DIR="$(mktemp -d)"
SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"

cleanup() {
  docker rm -f "$NAME_A" "$NAME_B" "$NAME_S" >/dev/null 2>&1 || true
  # The container wrote as uid 1000; remove through a throwaway container if needed.
  rm -rf "$DATA_DIR" "$WORK_DIR" 2>/dev/null || true
}
trap cleanup EXIT

pass() { echo "PASS $1"; }
fail() { echo "FAIL $1" >&2; exit 1; }

echo "Building $IMAGE ..."
docker build -q -t "$IMAGE" . >/dev/null

# (a) static image checks ----------------------------------------------------
check="$(docker run --rm --name "$NAME_S" --entrypoint sh "$IMAGE" -c '
  echo "uid=$(id -u)"
  if [ -e /app/.env ]; then echo "env=present"; else echo "env=absent"; fi
  echo "datafiles=$(ls -A /app/data | wc -l)"
  echo "sqlite=$(find /app -name "*.sqlite3" | wc -l)"
  python -c "import django; print(\"django=%d.%d\" % django.VERSION[:2])"
')"
echo "$check" | grep -qx 'uid=1000' || fail "(a) image does not run as uid 1000 ($check)"
echo "$check" | grep -qx 'env=absent' || fail "(a) /app/.env exists in the image"
echo "$check" | grep -qx 'datafiles=0' || fail "(a) /app/data is not empty in the image"
echo "$check" | grep -qx 'sqlite=0' || fail "(a) a .sqlite3 file is baked into the image"
echo "$check" | grep -qx 'django=6.1' || fail "(a) Django is not 6.1 ($check)"
pass "(a) image: uid 1000, no .env, empty /app/data, no SQLite file, Django 6.1"

# (b) start container A ------------------------------------------------------
chmod 777 "$DATA_DIR"

run_container() { # run_container NAME
  docker run -d --name "$1" -p "127.0.0.1:$PORT:8000" -v "$DATA_DIR:/app/data" \
    -e SECRET_KEY="$SECRET" -e PUBLIC_HOSTS="$HOST_NAME" \
    -e GOOGLE_CLIENT_ID=smoke-client-id -e GOOGLE_CLIENT_SECRET=smoke-secret \
    "$IMAGE" >/dev/null
}

wait_for_port() { # wait_for_port NAME
  for _ in $(seq 1 30); do
    if curl -s -o /dev/null -H "Host: $HOST_NAME" "http://127.0.0.1:$PORT/"; then return 0; fi
    sleep 1
  done
  docker logs "$1" >&2 || true
  fail "container $1 did not answer on port $PORT within 30 s"
}

run_container "$NAME_A"
wait_for_port "$NAME_A"
pass "(b) container A answers on 127.0.0.1:$PORT"

# (c) plain HTTP is redirected to https --------------------------------------
code="$(curl -s -o /dev/null -D "$WORK_DIR/c.head" -w '%{http_code}' -H "Host: $HOST_NAME" "http://127.0.0.1:$PORT/")"
loc="$(grep -i '^location:' "$WORK_DIR/c.head" | head -n 1 | sed -E 's/^[^:]*:[[:space:]]*//; s/\r$//')"
[ "$code" = "301" ] || fail "(c) plain HTTP returned $code, expected 301"
[ "$loc" = "https://$HOST_NAME/" ] || fail "(c) redirect Location was '$loc', expected https://$HOST_NAME/"
pass "(c) plain HTTP gets 301 to https://$HOST_NAME/"

# (d) HTTP contract behind a simulated proxy ---------------------------------
bash scripts/smoke.sh "http://127.0.0.1:$PORT" "$HOST_NAME"

# (e) persistence across container replacement -------------------------------
docker exec "$NAME_A" python manage.py shell -c \
  "from django.contrib.auth import get_user_model; get_user_model().objects.create(username='smoke-persist')" \
  >/dev/null
docker rm -f "$NAME_A" >/dev/null
run_container "$NAME_B"
wait_for_port "$NAME_B"
docker exec "$NAME_B" python manage.py shell -c \
  "from django.contrib.auth import get_user_model; import sys; sys.exit(0 if get_user_model().objects.filter(username='smoke-persist').exists() else 1)" \
  || fail "(e) smoke-persist user did not survive container replacement"
docker logs "$NAME_B" 2>&1 | grep -q 'No migrations to apply' \
  || fail "(e) second start did not log 'No migrations to apply'"
mode="$(docker exec "$NAME_B" python -c \
  "import sqlite3; print(sqlite3.connect('/app/data/db.sqlite3').execute('PRAGMA journal_mode').fetchone()[0])")"
[ "$mode" = "wal" ] || fail "(e) journal_mode is '$mode', expected wal"
pass "(e) user survived replacement, second start had no migrations to apply, journal_mode=wal"

echo "CONTAINER SMOKE OK"
