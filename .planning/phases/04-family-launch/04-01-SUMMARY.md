---
phase: 04-family-launch
plan: 01
subsystem: i18n
tags: [django, gettext, czech, set_language, locale]
status: complete

requires:
  - phase: 01-foundation
    provides: LocaleMiddleware, LANGUAGES en/cs, wrapped UI strings
provides:
  - EN / CS switch (POST to set_language, cookie only) in the top bar and the signed-out footer
  - Complete Czech catalogue (.po plus committed .mo) with three-form plurals
  - scripts/check-translations.sh catalogue gate, run in the CI test job
  - Smoke check (o): Czech landing page for Accept-Language cs
affects: [04-03 privacy policy and Czech secrecy pass, 04-04 phone pass, 04-05 dry-run kit]

actuals:
  tokens: 48000
  tasks: 2
  commits: 4
plan_head_before: ca3e707
plan_head_after: 51682b7e2f1719d1a6f65df762a08153012cc500

tech-stack:
  added: []
  patterns:
    - "Language is a per-browser cookie (django_language), never a user or session field"
    - "Public routes are pinned in test_lockdown.PUBLIC_ROUTES and probed in test_secrecy"
    - ".mo is committed; CI gate proves it equals the .po"

key-files:
  created:
    - locale/cs/LC_MESSAGES/django.po
    - locale/cs/LC_MESSAGES/django.mo
    - scripts/check-translations.sh
    - gifter/templates/gifter/includes/language_switch.html
    - gifter/tests/test_i18n.py
  modified:
    - web/urls.py
    - web/settings.py
    - gifter/templates/gifter/base.html
    - scripts/smoke.sh
    - .github/workflows/deploy.yml
    - gifter/tests/test_secrecy.py
    - gifter/tests/test_lockdown.py
    - gifter/tests/test_inapp.py

key-decisions:
  - "Three-form Czech Plural-Forms header (D-03), proven equal to Django's cs categories for every integer 0..1000 (A-03)"
  - ".mo files are committed, not compiled in the image: no gettext in the Dockerfile; CI gate keeps them in sync"
  - "Claim-side Czech wording (zamluveno, koupeno, přispět, pořídím) deliberately shares no word with owner pages (obdrženo, znovu otevřít) for the plan 04-03 own-wish check"
  - "Informal 'ty' tone; present tense or noun phrases instead of gendered past forms"

requirements-completed: [I18N-01]

duration: 40min
completed: 2026-11-10
---

# Phase 4 Plan 01: Czech everywhere, with an EN / CS switch Summary

An EN / CS switch (cookie only, one year, HttpOnly, SameSite Lax, Secure in production) on every page, browser-language default via Accept-Language, a fully translated Czech catalogue with three-form plurals, and a CI gate that refuses an incomplete or stale catalogue.

## Accomplishments

- `i18n/setlang/` routes to Django's `set_language` (wrapped in `login_not_required`), so signed-out visitors can switch from the landing page. Open redirects fall back to `/`, unknown or missing languages set no cookie.
- One shared include renders the switch: in `#gifter-nav` when signed in, in the footer when signed out. `<html lang>` now comes from `get_current_language` (it always said `en` before).
- All 172 msgids translated, including privacy page as it stands, the in-app browser hint, `Claim %(pk)s`, `Contribution %(pk)s`, three plural forms for member count and wish-share message.
- `scripts/check-translations.sh` fails on untranslated or fuzzy entries, `msgfmt --check` errors, or a `.mo` that differs from the `.po`; it runs in the CI test job after installing gettext, ahead of build and deploy.
- Smoke check (o) and the container smoke prove the Czech catalogue ships in the image.

## Verification

- Full suite: 283 tests OK (264 before). `makemigrations --check` clean. `check --deploy --fail-level WARNING` passes.
- Production settings print `True True 31536000 Lax` for the language cookie.
- `bash scripts/check-translations.sh` prints `TRANSLATIONS OK`. Sensitivity run by hand: emptied msgstr gives `FAIL untranslated entries`, a fuzzy flag gives `FAIL fuzzy entries`, an edited `.po` with the old `.mo` gives `FAIL django.mo does not match django.po`; all exit 1. The `.po` was restored each time.
- `bash scripts/container-smoke.sh`: `PASS (o)` and `CONTAINER SMOKE OK`.
- `pyproject.toml`, `uv.lock`, `Dockerfile` and migrations unchanged versus ca3e707.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plural test could not read Django's cs Plural-Forms from the .po**
- **Found during:** Task 2 (RED run)
- **Issue:** Django's cs header wraps onto two .po lines, so the regex found nothing.
- **Fix:** Read the equation from Django's compiled cs `django.mo` via `GNUTranslations.info()`.
- **Files modified:** gifter/tests/test_i18n.py
- **Commit:** 737c1bc

**2. [Rule 1 - Bug] Test literal leaked into Gifter's catalogue**
- **Found during:** Task 2, first gate run
- **Issue:** The literal `ngettext("%(num)d minute", ...)` in test_i18n.py was picked up by makemessages as an untranslated Gifter msgid, so the gate (correctly) failed.
- **Fix:** Pass the msgids through local variables in the test.
- **Files modified:** gifter/tests/test_i18n.py
- **Commit:** 51682b7

**3. [Rule 3 - Placement] Switch include lives under `includes/`**
- The plan said "an include or a block"; the template directory already has an `includes/` folder, so the file is `gifter/templates/gifter/includes/language_switch.html`.

Pre-commit protected-branch assertion: the run was dispatched sequentially on `main` by the orchestrator, so commits went to `main` as instructed. Nothing was pushed.

## Known Stubs

None.

## Threat Flags

None. The only new surface is `i18n/setlang/` (T-04-01, T-04-02 mitigated and tested).

## Notes for later plans

- Do not push `main` until plan 04-03 lands: `/privacy/` must describe the language cookie first, and the secrecy suite should run in Czech.
- Czech copy was written by Claude; a Czech-speaking relative should review it in the dry-run.
- Plan 04-03 adds new privacy sentences; add and translate them in the `.po`, recompile, and run `scripts/check-translations.sh`.

## Self-Check: PASSED

All created files exist; commits 2cc755c, f715a35, 737c1bc, 51682b7 are ancestors of HEAD.
