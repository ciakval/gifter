---
phase: 04-family-launch
plan: 05
subsystem: launch-hardening
tags: [healthz, hsts, cache-control, deploy, docs]
status: complete

requires:
  - phase: 04-family-launch
    provides: route inventories and Czech catalogue (04-01), backups docs (04-02), secrecy suite in Czech (04-03), phone pass (04-04)
provides:
  - Public /healthz (ok or 503 unavailable) and health_path /healthz on the bombur-deploy call
  - SignedInNoStoreMiddleware (Cache-Control private, no-store for signed-in responses)
  - One-year HSTS fixed in settings
  - docs/dry-run.md (Czech family message, checklist, real-device checks, launch order, record)
affects: []

actuals:
  tokens: 12000
  tasks: 3
  commits: 6
plan_head_before: f5f71de5deb4d5d2fa731ae5f374883b339b4a84
plan_head_after: e2900a106c0afeac752447e7ea08c1ca43b08356

key-files:
  created:
    - gifter/middleware.py
    - gifter/tests/test_ops.py
    - docs/dry-run.md
  modified:
    - gifter/views.py
    - gifter/urls.py
    - web/settings.py
    - .env.example
    - scripts/smoke.sh
    - .github/workflows/deploy.yml
    - gifter/tests/test_secrecy.py
    - gifter/tests/test_lockdown.py
    - DEPLOYMENT.md

key-decisions:
  - "HSTS is the literal 31536000 in settings so the old 3600 line in the server .env cannot lower it"
  - "healthz route has no trailing slash (APPEND_SLASH would answer 301 to the deploy check)"

requirements-completed: [OPS-05]
---

# Phase 4 Plan 05: Health check, launch hardening and the family dry-run kit Summary

/healthz plus health_path make every deploy prove the live site answers, HSTS is a fixed one year, signed-in pages are never cached, and docs/dry-run.md hands the author a ready Czech message and launch order.

## What was built

- **Task 1 (tracer):** `healthz` view (login_not_required, require_safe, never_cache, SELECT 1 ping, plain-text body, no cookie), route `healthz`, entries in the secrecy probes and PUBLIC_ROUTES, smoke check (p), `health_path: /healthz` in deploy.yml.
- **Task 2:** middleware after AuthenticationMiddleware; HSTS 31536000 + includeSubDomains in code, HSTS variable removed from .env.example, smoke check (b) requires max-age=31536000.
- **Task 3:** docs/dry-run.md (quotes the catalogue's Czech labels, test enforced; asks for words not screenshots of event pages or My claims) and DEPLOYMENT.md catch-up (translations, health check, HSTS, privacy bullet, no-store, healthz, dry-run pointer). The 04-04 real-device checks (iPhone Safari, Android Chrome at about 360px in Czech, Messenger/Instagram in-app hint) are in the dry-run doc.

## Deploy workflow consistency

`ciakval/bombur-deploy` tag `v1` (the ref gifter calls) declares the `health_path` input and its Health check step curls `<url><health_path>` up to 20 times, so the next push to main deploys with the check. gifter passes `url: https://gifter.remesh.cz` and `health_path: /healthz`; `secrets: inherit` unchanged.

## Verification

- Full suite: 335 tests OK (DEBUG=1); `check-translations.sh`: TRANSLATIONS OK; `makemigrations --check`: no changes; `check --deploy --fail-level WARNING`: passes
- `bash scripts/container-smoke.sh`: PASS (b) with max-age=31536000, PASS (o), PASS (p), CONTAINER SMOKE OK
- With SECURE_HSTS_SECONDS=3600 in the environment, settings print `31536000 True`
- No (04-05) commit touches privacy.html or locale/

## Deviations from Plan

None. The privacy date gate script was not re-run separately because privacy.html and locale/ are untouched by this plan.

## Known Stubs

None.

## Human-action items

- Push main and watch the deploy health check; run `bash scripts/smoke.sh https://gifter.remesh.cz`.
- Real-device checks, send the message, run the dry-run by about 22 Nov and fill the record table in docs/dry-run.md (launch order is in that file).

## Self-Check: PASSED

Commits f4df225, 1d318f6, a6c2733, e2900a1 and the test commits exist on main; files above present.
