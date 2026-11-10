#!/usr/bin/env bash
# Czech catalogue gate (Phase 4, D-03). Fails when `makemessages -l cs` leaves an untranslated
# or fuzzy entry, or when the committed django.mo does not match django.po.
#
#   bash scripts/check-translations.sh
#
# Needs GNU gettext (msgattrib, msgfmt) and uv. The committed .po is restored on exit, so the
# check never leaves the tree modified.
set -euo pipefail

cd "$(dirname "$0")/.."
PO=locale/cs/LC_MESSAGES/django.po
MO=locale/cs/LC_MESSAGES/django.mo

TMP="$(mktemp -d)"
cp "$PO" "$TMP/committed.po"
trap 'cp "$TMP/committed.po" "$PO"; rm -rf "$TMP"' EXIT

DEBUG=1 uv run python manage.py makemessages -l cs --no-obsolete --add-location=file \
  --ignore=staticfiles --ignore=data >/dev/null 2>&1 \
  || { echo "FAIL makemessages did not run" >&2; exit 1; }

untranslated="$(msgattrib --untranslated --no-obsolete "$PO")"
if [ -n "$untranslated" ]; then
  echo "FAIL untranslated entries:" >&2
  echo "$untranslated" >&2
  exit 1
fi

fuzzy="$(msgattrib --only-fuzzy --no-obsolete "$PO")"
if [ -n "$fuzzy" ]; then
  echo "FAIL fuzzy entries:" >&2
  echo "$fuzzy" >&2
  exit 1
fi

# The committed .po (not the makemessages-rewritten one) is what the .mo must match.
msgfmt --check -o "$TMP/fresh.mo" "$TMP/committed.po" \
  || { echo "FAIL msgfmt --check rejected $PO" >&2; exit 1; }

python3 - "$MO" "$TMP/fresh.mo" <<'PY' || { echo "FAIL django.mo does not match django.po: run compilemessages -l cs --ignore=.venv" >&2; exit 1; }
import gettext, sys

def catalog(path):
    with open(path, "rb") as handle:
        return gettext.GNUTranslations(handle)._catalog

sys.exit(0 if catalog(sys.argv[1]) == catalog(sys.argv[2]) else 1)
PY

echo "TRANSLATIONS OK"
