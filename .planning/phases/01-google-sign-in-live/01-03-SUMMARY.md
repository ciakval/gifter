---
phase: 01-google-sign-in-live
plan: 03
subsystem: auth
tags: [in-app-browser, landing, clipboard, django-templates, i18n]

requires:
  - phase: 01-google-sign-in-live
    provides: "01-01 landing view/template, base.html blocks, test conventions"
provides:
  - "is_in_app_browser(user_agent) pure detection for Messenger, Facebook, Instagram, TikTok, LinkedIn, Snapchat and Android WebView"
  - "Landing view context in_app, copy_url, force_url; ?force=1 escape hatch keeps next"
  - "Plain-language open-in-your-browser hint card (numbered steps, Copy link button, read-only link field, Continue anyway) replacing the Google form in in-app browsers"
  - "gifter/static/gifter/landing.js copy-link behaviour with select-input fallback"
affects: [01-05, phase-02]

actuals:
  tokens: 6500
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "URLs carrying user input are built in the view with reverse + urlencode, never string concatenation"
    - "First-party static JS loaded with defer only on the page branch that needs it; no inline scripts"

key-files:
  created:
    - gifter/inapp.py
    - gifter/static/gifter/landing.js
    - gifter/tests/test_inapp.py
  modified:
    - gifter/views.py
    - gifter/templates/gifter/landing.html

key-decisions:
  - "Hint replaces the Google form entirely (form absent from HTML) with an always-present Continue anyway link, so a detection false positive never locks anyone out"
  - "No intent:// deep link; copy-link plus manual steps only (per research)"

patterns-established:
  - "UA matrix tests use realistic full user agent strings; clipboard behaviour is left to real-phone UAT"

requirements-completed: [OPS-04]

coverage:
  - id: D1
    description: "In-app browsers (Messenger, Facebook, Instagram, TikTok, LinkedIn, Snapchat, Android WebView) get the hint instead of the Google form; Chrome, Safari, Firefox, empty and missing user agents get the normal button"
    requirement: OPS-04
    verification:
      - kind: unit
        ref: "gifter/tests/test_inapp.py#IsInAppBrowserTests, LandingHintTests"
        status: pass
    human_judgment: false
  - id: D2
    description: "next survives the copied link and Continue anyway; force=1 shows the normal form; payloads in next are escaped"
    requirement: OPS-04
    verification:
      - kind: unit
        ref: "gifter/tests/test_inapp.py#LandingHintTests.test_next_survives_in_link_and_continue_anyway, test_continue_anyway_shows_normal_form, test_script_payload_in_next_is_escaped"
        status: pass
    human_judgment: false
  - id: D3
    description: "Hint copy is plain language without technical jargon"
    requirement: OPS-04
    verification:
      - kind: unit
        ref: "gifter/tests/test_inapp.py#LandingHintTests.test_hint_has_no_jargon"
        status: pass
    human_judgment: false
  - id: D4
    description: "Copy link button carries the absolute landing URL, script loads deferred only on the hint page"
    requirement: OPS-04
    verification:
      - kind: unit
        ref: "gifter/tests/test_inapp.py#CopyLinkTests"
        status: pass
    human_judgment: false
  - id: D5
    description: "Real in-app browsers (Messenger/Instagram on real phones) match the UA tokens, the menu wording is accurate, and the Copy link button actually copies"
    verification: []
    human_judgment: true
    rationale: "UA tokens and menu wording are research assumptions and clipboard behaviour has no JS test runner; confirmed on real phones in plan 01-05 UAT"

duration: 4 min
completed: 2026-10-18
plan_head_before: 6cfc03577975e51e750f44e9ef01043b2aa11415
plan_head_after: 6341fa0a1e8ac4d007ec8764ec0401a20484f98a
commits: 2
status: complete
---

# Phase 1 Plan 03: Relatives who open Gifter inside a chat app are told how to get in Summary

**Server-side in-app browser detection that swaps the Google button for a plain-language open-in-your-browser card (numbered steps, one-tap Copy link, read-only link field, Continue anyway escape), with next preserved everywhere.**

## Performance

- **Duration:** 4 min
- **Tasks:** 2
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments

- Messenger, Facebook, Instagram, TikTok, LinkedIn, Snapchat and Android WebView visitors no longer see a Google button that Google would refuse.
- Continue anyway (`?force=1`) always shows the normal sign-in button, so a false positive costs one tap.
- Copy link copies the absolute landing URL (including `next`) and falls back to selecting the read-only field.

## Task Commits

1. **Task 1: hint instead of the Google form** - `42c759f` (feat)
2. **Task 2: Copy link button** - `6341fa0` (feat)

**Plan metadata:** committed separately (docs: complete plan).

## Files Created/Modified

- `gifter/inapp.py` - `IN_APP_UA_RE`, `is_in_app_browser()`
- `gifter/views.py` - landing computes `in_app`, `copy_url`, `force_url` via reverse + urlencode
- `gifter/templates/gifter/landing.html` - in_app branch, Copy link button, deferred script in `extra_body`
- `gifter/static/gifter/landing.js` - clipboard copy with select fallback
- `gifter/tests/test_inapp.py` - 14 tests (UA matrix, view cases, escaping, jargon, copy button)

## Decisions Made

- Form is entirely absent from the hint page; the escape hatch is the Continue anyway link (T-01-15).
- WhatsApp and Google app browsers are intentionally not matched.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Commits are on `main` (branching_strategy none, sequential executor), as in plans 01-01 and 01-02.
- Full suite is 41 tests (27 prior plus 14 new), all passing; `makemigrations --check --dry-run` reports no changes.

## User Setup Required

None.

## Known Stubs

None.

## Threat Flags

None - T-01-14 (reflected next/force) and T-01-15 (false positive lockout) are mitigated and covered by tests.

## Next Phase Readiness

- UA tokens, menu wording and the Copy link button must be checked on real phones in plan 01-05's live UAT (human judgment item D5).
- Phase 2 invite links land on this page for anonymous users, so the hint covers them too.

## Self-Check: PASSED

- Files exist: gifter/inapp.py, gifter/static/gifter/landing.js, gifter/tests/test_inapp.py, gifter/views.py, gifter/templates/gifter/landing.html
- Commits 42c759f and 6341fa0 are ancestors of HEAD
- All acceptance criteria re-run and pass; `DEBUG=1 uv run python manage.py test` (41 tests) OK

---
*Phase: 01-google-sign-in-live*
*Completed: 2026-10-18*
