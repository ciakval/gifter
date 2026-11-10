---
phase: 04-family-launch
plan: 02
subsystem: ops
tags: [sqlite, backup, restore, systemd, docker]
status: complete

requires:
  - phase: 01-foundation
    provides: production image, SQLite WAL data dir, Bombur deploy layout
provides:
  - sqlite3 tool in the production image
  - scripts/gifter-backup.sh (online backup, rotation, nightly-backups-since marker)
  - scripts/gifter-restore.sh (dry run, --yes with safety copy, --drill)
  - systemd service and timer (nightly 03:15 Europe/Prague)
  - scripts/backup-smoke.sh local end-to-end proof
  - DEPLOYMENT.md "Backups and restore", restore drill record, deletion steps on the new tooling
affects: [04-03 privacy view reads the nightly-backups-since marker, 04-05 dry-run kit]

actuals:
  tokens: 14000
  tasks: 3
  commits: 3
plan_head_before: 30ac14fcd4f4f07330481cc52589801358d4f248
plan_head_after: d2e0d457889fe04298787b3683bdcd8dc6a43ea9

tech-stack:
  added: ["Debian sqlite3 package (image only)"]
  patterns:
    - "Backup and restore run sqlite3 inside the container via docker exec, so file ownership never matters"
    - "Smoke scripts use their own image tag, container names and no published port"

key-files:
  created:
    - scripts/gifter-backup.sh
    - scripts/gifter-restore.sh
    - scripts/backup-smoke.sh
    - scripts/systemd/gifter-backup.service
    - scripts/systemd/gifter-backup.timer
  modified:
    - Dockerfile
    - scripts/container-smoke.sh
    - DEPLOYMENT.md

key-decisions:
  - "Marker nightly-backups-since written once by the first PREFIX=gifter success; manual prefixes never write it"
  - "Drill prints users, events and wishes only; no mode prints claims, chip-ins or notes"

requirements-completed: [OPS-06]

duration: 25min
completed: 2026-11-10
---

# Phase 4 Plan 02: Nightly backups and a proven restore Summary

Nightly online SQLite backups (VACUUMed, integrity-checked, 600 files in a 700 directory outside the app dir, 14-day / 14-copy rotation) plus a restore tool with dry run, safety-copied `--yes` restore and a throwaway-container drill, all proven locally against the real image.

## What was built

- **Task 1:** `sqlite3` added to the image; `gifter-backup.sh`; `backup-smoke.sh`; `SMOKE_TAG` override in `container-smoke.sh` (default unchanged). Note: the backup script was written with rotation and the marker already in place, so Task 1's commit contains them; Task 2's commit added the restore script and the restore checks.
- **Task 2:** `gifter-restore.sh` (validate: integrity_check ok plus django_migrations; dry run; `--yes` with `pre-restore` safety copy, online `.restore`, restart, migrate check; `--drill`). Smoke checks b1, m1, b2, m2, m3, r1 to r4 all pass.
- **Task 3:** systemd units (verified with `systemd-analyze`), DEPLOYMENT.md section with install commands, marker check, drill record table, real restore, manual copies; delete_user steps now use `PREFIX=pre-deletion`, VACUUM, `gifter-restore.sh`, and state the 14-day statement.

## Verification

- `bash scripts/backup-smoke.sh`: all of PASS (b1) (m1) (b2) (m2) (m3) (r1) (r2) (r3) (r4), "BACKUP SMOKE OK"
- `SMOKE_TAG=smoke-0402 SMOKE_PORT=18102 bash scripts/container-smoke.sh`: "CONTAINER SMOKE OK"
- Units verify: "UNITS OK"
- `DEBUG=1 uv run python manage.py test`: 283 tests OK
- No change to pyproject.toml, uv.lock, gifter/ or web/ since the plan start.

## Deviations from Plan

None - plan executed as written (apart from the Task 1/2 split of the backup script noted above). Minor: `shell -v 0` used in smoke and drill to suppress the Django "objects imported automatically" banner.

## Human-action items (Bombur, cannot be done here)

1. Deploy the image from this phase, then install and run the first backup (commands in DEPLOYMENT.md "One-time install on Bombur"):
   ```sh
   scp -P 10022 scripts/gifter-backup.sh scripts/gifter-restore.sh scripts/systemd/gifter-backup.service scripts/systemd/gifter-backup.timer ciakval@bombur.remesh.cz:/tmp/
   ssh -p 10022 ciakval@bombur.remesh.cz 'sudo install -m 755 /tmp/gifter-backup.sh /tmp/gifter-restore.sh /usr/local/bin/ && sudo install -m 644 /tmp/gifter-backup.service /tmp/gifter-backup.timer /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now gifter-backup.timer && sudo systemctl start gifter-backup.service && sudo journalctl -u gifter-backup -n 5 --no-pager && sudo -u deploy ls -l /home/deploy/backups/gifter'
   ssh -p 10022 ciakval@bombur.remesh.cz 'sudo -u deploy docker exec gifter-web cat /app/data/nightly-backups-since'
   ```
2. Restore drill before 1 Dec 2026, then record the line in DEPLOYMENT.md "Restore drill record" and STATE:
   ```sh
   ssh -p 10022 ciakval@bombur.remesh.cz 'sudo -u deploy /usr/local/bin/gifter-restore.sh --drill /home/deploy/backups/gifter/<newest file>'
   ```

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

Files present (scripts/gifter-backup.sh, gifter-restore.sh, backup-smoke.sh, systemd units, DEPLOYMENT.md); commits e7312fc, c756c03, d2e0d45 exist on main.
