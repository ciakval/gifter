---
phase: 01-google-sign-in-live
plan: 02
subsystem: auth
tags: [django-admin, django-allauth, redirects, management-command, templates]

requires:
  - phase: 01-google-sign-in-live
    provides: "01-01 tracer: landing/home URL names, gifter/base.html, gifter.User, allauth Google-only settings"
provides:
  - "accounts/login/ and gifter-admin/login/ redirect to the landing page with the query string (next) preserved"
  - "Django admin at gifter-admin/ (User registered, Gifter admin header); /admin/ is 404"
  - "promote_staff EMAIL management command (staff + superuser, never creates users or sets passwords)"
  - "allauth layout override and friendly Google error / cancelled pages with Try again links to the landing page"
  - "test_lockdown and test_allauth_pages test modules"
affects: [01-03, 01-04, 01-05]

actuals:
  tokens: 4200
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Login redirect routes are listed before the allauth and admin includes (route order is load-bearing)"
    - "login_not_required wraps RedirectView so LoginRequiredMiddleware does not redirect the redirect"
    - "Single-line allauth/layouts/base.html override re-skins every allauth page"

key-files:
  created:
    - gifter/management/__init__.py
    - gifter/management/commands/__init__.py
    - gifter/management/commands/promote_staff.py
    - gifter/templates/allauth/layouts/base.html
    - gifter/templates/socialaccount/authentication_error.html
    - gifter/templates/socialaccount/login_cancelled.html
    - gifter/tests/test_lockdown.py
    - gifter/tests/test_allauth_pages.py
  modified:
    - web/urls.py
    - gifter/admin.py

key-decisions:
  - "No SocialApp registration in admin; Google credentials stay settings-only (avoids MultipleObjectsReturned)"
  - "allauth layout override is just {% extends 'gifter/base.html' %}: all blocks stock allauth fills (head_title, content, extra_head, extra_body, body) already exist in gifter/base.html, so no changes to gifter/base.html were needed"

patterns-established:
  - "Tests for redirects with next compare unquote()d Location because LoginRequiredMiddleware percent-encodes next"

requirements-completed: [AUTH-01, AUTH-03]

coverage:
  - id: D1
    description: "Google is the only way in: /accounts/signup/, /accounts/password/reset/, /admin/, /login/ are 404; /accounts/login/ and /gifter-admin/login/ redirect to landing keeping next; POST to accounts/login/ signs nobody in"
    requirement: AUTH-01
    verification:
      - kind: unit
        ref: "gifter/tests/test_lockdown.py#LoginRedirectTests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Staff user reaches /gifter-admin/; anonymous and non-staff users end on landing/home in a finite redirect chain"
    requirement: AUTH-01
    verification:
      - kind: unit
        ref: "gifter/tests/test_lockdown.py#AdminAccessTests"
        status: pass
    human_judgment: false
  - id: D3
    description: "GET /accounts/logout/ shows a confirmation and never signs out; only POST does"
    requirement: AUTH-01
    verification:
      - kind: unit
        ref: "gifter/tests/test_lockdown.py#LogoutTests"
        status: pass
    human_judgment: false
  - id: D4
    description: "promote_staff makes the matching user (case-insensitive email) staff and superuser; unknown email raises CommandError"
    requirement: AUTH-01
    verification:
      - kind: unit
        ref: "gifter/tests/test_lockdown.py#PromoteStaffTests"
        status: pass
    human_judgment: false
  - id: D5
    description: "Sign-out confirmation, Google error and cancelled pages render in Gifter's layout without allauth's stock Menu, with Try again links to /"
    requirement: AUTH-03
    verification:
      - kind: unit
        ref: "gifter/tests/test_allauth_pages.py#AllauthPageTests"
        status: pass
    human_judgment: false
  - id: D6
    description: "Visual quality of the unstyled allauth sign-out form (allauth element tags render plain HTML inside Bootstrap container)"
    verification: []
    human_judgment: true
    rationale: "No test asserts visual appearance; check on a phone in plan 01-05 live UAT"

duration: 4 min
completed: 2026-10-18
plan_head_before: c6fd675b3385a97164ae7364bb7eb997ebc2dbb4
plan_head_after: 1003a8d37bc1dcb771c7578519714dfaa8a1b85c
commits: 2
status: complete
---

# Phase 1 Plan 02: Google is the only door Summary

**Password-style entry points closed or redirected to the Google landing page (query string kept), a Google-only admin at gifter-admin/ with a promote_staff command, and allauth's sign-out, error and cancel pages re-skinned through gifter/base.html with Try again links.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-10-18T11:09Z (approx)
- **Completed:** 2026-10-18T11:13Z
- **Tasks:** 2
- **Files modified:** 10 (8 created, 2 modified)

## Accomplishments

- accounts/login/ and gifter-admin/login/ bounce to `/` keeping `?next=`; both routes precede the allauth and admin includes.
- Admin only reachable by staff signed in through Google; non-staff land on /events/ with no loop.
- promote_staff gives the author a way to become staff without any password account.
- allauth dead ends read as Gifter and always offer a way back to sign-in.

## Task Commits

1. **Task 1: Close every non-Google door and add a Google-only admin** - `191ce2f` (feat)
2. **Task 2: allauth pages look like Gifter and lead back to sign-in** - `1003a8d` (feat)

**Plan metadata:** committed separately (docs: complete plan).

## Files Created/Modified

- `web/urls.py` - to_landing redirect, ordered routes, admin at gifter-admin/
- `gifter/admin.py` - User registered with UserAdmin, "Gifter admin" header/title (translatable)
- `gifter/management/commands/promote_staff.py` - email-based staff promotion
- `gifter/templates/allauth/layouts/base.html` - extends gifter/base.html
- `gifter/templates/socialaccount/{authentication_error,login_cancelled}.html` - friendly pages with Try again
- `gifter/tests/test_lockdown.py`, `gifter/tests/test_allauth_pages.py` - 14 new tests (27 in the full suite)

## Decisions Made

- Left SocialApp unregistered in admin; credentials live only in settings.
- allauth layout override needed no extra blocks: gifter/base.html already provides every block the stock layouts fill.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test expected unencoded next in the redirect chain**
- **Found during:** Task 1 (first test run)
- **Issue:** LoginRequiredMiddleware redirects anonymous /gifter-admin/ to `/?next=%2Fgifter-admin%2F`, so the literal comparison in my test failed. The behavior itself is correct (the landing view decodes next).
- **Fix:** Compare `unquote()` of the final redirect URL.
- **Files modified:** gifter/tests/test_lockdown.py (before commit, no extra commit)
- **Verification:** test_lockdown passes

---

**Total deviations:** 1 auto-fixed (1 test-expectation bug)
**Impact on plan:** None.

## Issues Encountered

- Commits are on `main` (branching_strategy none, sequential executor), same as plan 01-01.
- The unstyled allauth `element` tags (h1, p, button) render as plain HTML inside the Bootstrap container; the sign-out button has no btn classes. Acceptable for now, flagged for the phone check in 01-05.

## User Setup Required

None.

## Known Stubs

None.

## Threat Flags

None - no new surface beyond the plan's threat model (T-01-10 to T-01-13 mitigated and tested).

## Next Phase Readiness

- Ready for 01-03 (in-app browser hint) and 01-04 (deploy) in the same wave; this plan touches none of their files.
- Operators promote the author with `python manage.py promote_staff EMAIL` after the first Google sign-in (document in plan 01-04's DEPLOYMENT.md; never add a Social application row in admin).

## Self-Check: PASSED

- Files exist: web/urls.py, gifter/admin.py, gifter/management/commands/promote_staff.py, gifter/templates/allauth/layouts/base.html, gifter/templates/socialaccount/authentication_error.html, gifter/templates/socialaccount/login_cancelled.html, gifter/tests/test_lockdown.py, gifter/tests/test_allauth_pages.py
- Commits 191ce2f and 1003a8d are ancestors of HEAD
- All acceptance criteria re-run and pass; `DEBUG=1 uv run python manage.py test` (27 tests) OK; `makemigrations --check --dry-run` prints "No changes detected"

---
*Phase: 01-google-sign-in-live*
*Completed: 2026-10-18*
