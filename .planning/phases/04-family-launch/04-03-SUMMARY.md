---
phase: 04-family-launch
plan: 03
subsystem: privacy-and-secrecy
tags: [privacy, i18n, czech, secrecy, tests]
status: complete

requires:
  - phase: 04-family-launch
    provides: Czech catalogue and language switch (04-01), nightly-backups-since marker writer (04-02)
provides:
  - /privacy/ covering the language cookie and one-off copies (always) and nightly backups (gated on the marker)
  - gifter.views.NIGHTLY_BACKUPS_MARKER and _nightly_backups_since() (fail closed)
  - Czech pass of the whole secrecy suite plus a Czech-really guard
affects: [04-04, 04-05]

actuals:
  tokens: 14000
  tasks: 2
  commits: 4
plan_head_before: aac911061402721025a24db7f09318b90b28a10c
plan_head_after: 703c9b3957e32aa4168cd928f370f4d30f33c09d

key-files:
  created: []
  modified:
    - gifter/views.py
    - gifter/templates/gifter/privacy.html
    - gifter/templates/gifter/event_detail.html
    - gifter/tests/test_privacy.py
    - gifter/tests/test_secrecy.py
    - gifter/tests/helpers.py
    - locale/cs/LC_MESSAGES/django.po
    - locale/cs/LC_MESSAGES/django.mo

key-decisions:
  - "Nightly-backup and 14-day sentences render only while DATA_DIR/nightly-backups-since holds a strict YYYY-MM-DD date; read on every request, fail closed"
  - "Own-wish region on the event page is found by id=\"own-wishes\", not by English heading text"
  - "Czech wording of the language cookie avoids gendered forms (jazyk zvoleny prepinacem EN / CS)"

requirements-completed: [I18N-01]
---

# Phase 4 Plan 03: A truthful privacy policy in both languages, and the secrecy suite in Czech Summary

The privacy page now truthfully covers the language cookie and one-off maintenance copies, and describes nightly backups only from the first real nightly backup on. The whole secrecy suite passes a second time in Czech.

## What was built

- **Task 1 (tracer):** `privacy` view reads `DATA_DIR/nightly-backups-since` per request (`_nightly_backups_since()`, strict regex plus `date.fromisoformat`, any OSError or ValueError gives None). "Last updated" is the later of `PRIVACY_POLICY_UPDATED` (bumped to 2026-11-10) and the marker date. privacy.html: the cookie paragraph lists four kinds (language cookie, up to a year), a one-off copy sentence is always shown, and the two nightly-backup/14-day sentences sit inside `{% if nightly_backups_since %}` blocks. Czech translations added to the .po and the .mo recompiled in the same commit. Tests use a temporary DATA_DIR and cover absent, present, unusable, per-request, Last updated and Czech completeness.
- **Task 2:** Czech subclasses of SentinelCrawl, OwnWishRegion, ByteIdentical, UniformNotFound, SelfSensitivity, Chokepoint and StaffGiftee tests under `override_settings(LANGUAGE_CODE="cs")`; `CzechPassIsReallyCzechTests` guard; `helpers.CLAIM_STATE_MSGIDS` / `czech_claim_state_markers()` so `claim_state_markers()` checks English and Czech wording; `id="own-wishes"` on the event page heading, and `own_wish_regions` uses it.

## Verification

- `scripts/check-translations.sh`: TRANSLATIONS OK
- Full suite: 313 tests, OK
- Privacy date gate: exits 0; gate-placement check: exits 0
- `git diff --quiet cce7779 -- pyproject.toml uv.lock gifter/migrations`: clean

## Deviations from Plan

None in substance. Minor: the Czech completeness test allows an explicit `SAME_IN_CZECH = ("Cookies",)` because that heading is identical in Czech. No Czech claim-state marker appeared in an own-wish region, so no claim-side wording had to change in the .po. The per-plan commit ledger file for 04-03 did not exist, so `plan_head_before` is the HEAD after plan 04-02 (aac9110).

## Known Stubs

None.

## Human-action items

- A Czech-speaking relative should read the Czech privacy copy (including the three new sentences) during the dry-run.
- After deploy and installing the backup timer (DEPLOYMENT.md), confirm /privacy/ shows no nightly-backup sentence before the first nightly backup and shows them after it.

## Self-Check: PASSED

Commits 5ad76b8, 1e62afe, adb18ff, 703c9b3 exist on main; modified files present.
