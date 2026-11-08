---
phase: 01-google-sign-in-live
plan: 07
subsystem: auth
tags: [allauth, url-allowlist, adapters, admin-lockdown, promote-staff, gap-closure]
status: complete

requires:
  - phase: 01-google-sign-in-live
    provides: "01-01 Google sign-in, 01-02 login redirects and lockdown tests, 01-06 privacy page, pipeline hardening and smoke (h)/(i)"
provides:
  - "web/urls.py explicit allowlist: exactly seven accounts/ routes; One Tap token, connections page, legacy aliases, inactive page and all email/password/code/session routes are 404"
  - "gifter.adapters.AccountAdapter (inactive account -> landing with message) and SocialAccountAdapter (process=connect refused, connect redirect -> home)"
  - "Admin: SocialApp and SocialToken unregistered; SocialAccount and EmailAddress view/delete only, make_verified removed; Wish and claim models never registered"
  - "promote_staff resolves through a Google-verified email, prints the Google uid, refuses unknown/unverified/non-Google/ambiguous matches"
  - "scripts/smoke.sh checks (j) One Tap 404 and (k) connections 404"
  - "01-REVIEW-DISPOSITION.md: all 15 findings dispositioned, open: 0"
affects: [01-08, phase-02, phase-03]

actuals:
  tokens: 8000
  tasks: 2
  commits: 4

plan_head_before: c42c09de0bba652ebaa8930a39d674685a233417
plan_head_after: 4481bc06d3f193961f81dd173d55bd42703ddeaa
commits: 4

tech-stack:
  added: []
  patterns:
    - "Third-party URLconf is allowlisted route by route; a URL-table test fails on any added accounts/ route"
    - "Admin models for identity data are re-registered as view/delete-only subclasses; delete stays so user deletion cascades"
    - "Import allauth admin modules explicitly before unregistering (gifter is first in INSTALLED_APPS)"

key-files:
  created:
    - gifter/adapters.py
  modified:
    - web/urls.py
    - web/settings.py
    - gifter/admin.py
    - gifter/management/commands/promote_staff.py
    - gifter/tests/test_lockdown.py
    - scripts/smoke.sh
    - DEPLOYMENT.md
    - .planning/phases/01-google-sign-in-live/01-REVIEW-DISPOSITION.md

key-decisions:
  - "accounts/login/ keeps the to_landing redirect but is now named account_login, so allauth's own reverse() calls land on the Google landing page with next preserved"
  - "Delete permission is kept on the read-only admins: Django blocks deleting a User if a registered related model denies delete"
  - "WR-02 recorded as deferred (partial): 01-06 found bombur-deploy declares no workflow_call secrets, so secrets: inherit stays"

requirements-completed: [AUTH-01, AUTH-03]

coverage:
  - id: D1
    description: "Only the seven allowlisted accounts/ routes resolve; allauth upgrade or edit adding another fails a test"
    requirement: AUTH-01
    verification:
      - kind: test
        ref: "gifter/tests/test_lockdown.py#AccountsUrlTableTests.test_accounts_routes_are_exactly_the_allowlist"
        status: pass
    human_judgment: false
  - id: D2
    description: "One Tap token POST, connections page, social aliases, inactive page and email/password/code/session routes are 404 for anonymous and signed-in visitors"
    requirement: AUTH-01
    verification:
      - kind: test
        ref: "gifter/tests/test_lockdown.py#AccountsUrlTableTests"
        status: pass
      - kind: command
        ref: "bash scripts/container-smoke.sh -> PASS (j), PASS (k)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Inactive account, connect attempt and email conflict all end on real pages (no 500); GET google login never redirects to Google"
    requirement: AUTH-03
    verification:
      - kind: test
        ref: "gifter/tests/test_lockdown.py#AdapterFlowTests"
        status: pass
    human_judgment: false
  - id: D4
    description: "Superuser cannot reach SocialApp/SocialToken pages; Social accounts and Email addresses are view/delete only; user deletion still works; Wish not registered"
    requirement: AUTH-01
    verification:
      - kind: test
        ref: "gifter/tests/test_lockdown.py#AdminLockdownTests"
        status: pass
    human_judgment: false
  - id: D5
    description: "promote_staff promotes only a single Google-verified match and prints the Google uid; refuses unknown, non-Google, unverified, ambiguous"
    requirement: AUTH-01
    verification:
      - kind: test
        ref: "gifter/tests/test_lockdown.py#PromoteStaffTests"
        status: pass
    human_judgment: false
  - id: D6
    description: "Review dispositions recorded: WR-01/03/04/05 fixed, WR-02 deferred as partial, remainder deferred with target phase"
    requirement: AUTH-01
    verification:
      - kind: command
        ref: "grep -c '^open: 0$' and grep -c 'disposition: open' on 01-REVIEW-DISPOSITION.md -> 1 and 0"
        status: pass
    human_judgment: false
---

# Phase 1 Plan 07: Google is the only door, enforced Summary

**The accounts/ URL table is an explicit seven-route allowlist pinned by a test, two small allauth adapters keep removed routes from causing 500s, the admin shows Google identity data read-only, and promote_staff trusts only a Google-verified email and prints the Google uid.**

## Performance

- **Duration:** about 10 min wall clock for the agent run
- **Started:** 2026-11-08T17:43Z
- **Completed:** 2026-11-08T17:51Z (clock of the executing session)
- **Tasks:** 2 (tracer, TDD)
- **Files:** 1 created, 8 modified

## Accomplishments

- Replaced the wholesale allauth include with seven explicit routes; `accounts/login/` is `account_login` (redirect to landing, keeps `next`).
- `AccountAdapter.respond_user_inactive` and `SocialAccountAdapter.pre_social_login` / `get_connect_redirect_url` wired via settings; three mocked-Google round trips (inactive, connect, email conflict) end on real pages.
- Admin lockdown: no SocialApp/SocialToken, read-only SocialAccount/EmailAddress without `make_verified`; deleting a user with a Google account still works.
- `promote_staff` rewritten; the old User.email-only behaviour is now refused.
- Tracer gate (yolo/end-of-phase): `<verify>` re-run end to end (targeted tests, full suite, container smoke with PASS (a) to (k)) before expanding to Task 2.
- Final gate: 72 tests OK, `makemigrations --check` clean, `check --deploy --fail-level WARNING` clean (1 silenced), container smoke `CONTAINER SMOKE OK`.

## Task Commits

1. **Task 1 (tracer): allowlist, adapters, tests, smoke (j)/(k)** - `e63bc0e` (feat)
2. **Task 2 RED: admin lockdown and promote_staff tests, 12 failing** - `04ea411` (test)
3. **Task 2 GREEN: admin and promote_staff** - `a5226be` (feat)
4. **Task 2: DEPLOYMENT.md and review dispositions** - `4481bc0` (docs)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Smoke insertion point**
- **Found during:** Task 1
- **Issue:** The plan says to add (j) and (k) "before the client_id line", but in the current script the `client_id` echo sits inside check (g); there is no separate trailing client_id line.
- **Fix:** Added (j) and (k) after (i), before `SMOKE OK`, which matches the intent (SMOKE OK stays last).
- **Files modified:** scripts/smoke.sh
- **Commit:** e63bc0e

**2. [Rule 3 - Blocking] `ruff` not available in the project environment**
- **Found during:** final gate
- **Issue:** `uv run ruff` fails to spawn (not a dependency); lint could not run.
- **Fix:** None; kept imports in isort order by hand. Not part of the plan's verify commands.

**Total deviations:** 2 (both Rule 3, no scope change).

## Notes for later phases

- **Phase 3:** claim and contribution models must stay out of the admin (or be registered without giftee-visible claim data); `test_dangerous_and_secret_models_are_not_registered` pins Wish only and should grow with each such model.
- **Phase 2:** if invite links ever need a route under `accounts/`, update `ALLOWED_ACCOUNTS_ROUTES` in `gifter/tests/test_lockdown.py` (and `web/urls.py` docstring).
- **Plan 01-08:** smoke checks (j) and (k) run live against https://gifter.remesh.cz; after deploy, check the uid printed by `promote_staff` against `/gifter-admin/socialaccount/socialaccount/`.

## Known Stubs

None.

## Threat Flags

None. T-01-37 to T-01-42 are mitigated as planned; no new surface beyond the plan's threat model.

## Issues Encountered

None.

## Next Phase Readiness

Ready for 01-08 (deploy, publish, human checks). Nothing was pushed.

## Self-Check: PASSED

- Created file exists: gifter/adapters.py
- Commits reachable from HEAD: e63bc0e, 04ea411, a5226be, 4481bc0
- Full suite 72 tests OK; makemigrations clean; check --deploy clean; container smoke PASS (a) to (k), CONTAINER SMOKE OK
