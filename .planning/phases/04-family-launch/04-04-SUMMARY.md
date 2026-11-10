---
phase: 04-family-launch
plan: 04
subsystem: phone-pass
tags: [css, bootstrap, mobile, i18n, tests]
status: complete

requires:
  - phase: 04-family-launch
    provides: EN / CS switch and complete Czech catalogue (04-01), id="own-wishes" and Czech secrecy pass (04-03)
provides:
  - gifter/static/gifter/gifter.css (44px tap targets, wrapping main text, full-width buttons in d-grid groups below 576px)
  - Stacking action groups (d-grid gap-2 d-sm-flex flex-wrap) on every page with two or more actions
  - gifter/tests/test_phone.py (crawl EN and CS, stylesheet rules, stacking order, flex and width scans)
affects: [04-05]

actuals:
  tokens: 9000
  tasks: 3
  commits: 6
plan_head_before: 0f2cadeccc691c7db81e7114f677ad2084a79a4d
plan_head_after: 910acf89c7e2b2335d2232e3c28a0d34cc4cdb4b

key-files:
  created:
    - gifter/static/gifter/gifter.css
    - gifter/tests/test_phone.py
  modified:
    - gifter/templates/gifter/base.html
    - gifter/templates/gifter/includes/language_switch.html
    - gifter/templates/gifter/includes/owner_wish.html
    - gifter/templates/gifter/includes/member_wish.html
    - gifter/templates/gifter/my_claims.html
    - gifter/templates/gifter/event_detail.html
    - gifter/templates/gifter/wish_form.html
    - gifter/templates/gifter/wish_confirm_delete.html
    - gifter/templates/gifter/home.html
    - gifter/templates/gifter/wishlist.html

key-decisions:
  - "gifter.css sets only sizes, wrapping and alignment; a test forbids colour, background, font, order, reverse directions, url() and @import"
  - "The language switch form also wraps (class change in includes/language_switch.html, not only base.html)"

requirements-completed: [I18N-02]
---

# Phase 4 Plan 04: Phone pass on stock Bootstrap Summary

Every page now loads one small stylesheet after vendored Bootstrap that gives 44px tap targets and wrapping text, action buttons stack full width below 576px, and tests pin all of it in English and Czech.

## What was built

- **Task 1 (tracer):** gifter.css linked from base.html after Bootstrap; `.btn, .nav-link, summary, .form-check-label, footer a` get min-height 2.75rem (and `.btn` min-width 2.75rem); `main` uses overflow-wrap anywhere; buttons in `d-grid` groups are full width below 576px. Top-bar sign-out and language rows wrap. The crawl walks every GET probe of the secrecy suite plus anonymous pages, the Messenger landing, the privacy page, the cancelled-login page and a new member's empty My events, My wishlist and My claims, in both languages.
- **Task 2:** `d-grid gap-2 d-sm-flex flex-wrap` groups in owner_wish (Edit, Delete, Received; Reopen), member_wish, my_claims (including Remove from my claims), event_detail, wish_form and wish_confirm_delete, keeping the wide-screen order (a test records the order).
- **Task 3:** page headers and event list items in home.html and wishlist.html wrap; scans guarantee every `d-flex` row wraps and no width or min-width exceeds 320px.

## Verification

- Full suite: 326 tests, OK (DEBUG=1)
- `scripts/check-translations.sh`: TRANSLATIONS OK
- `SMOKE_TAG=smoke-0404 SMOKE_PORT=18104 bash scripts/container-smoke.sh`: CONTAINER SMOKE OK (stylesheet is in the production manifest)
- In-app hint line unchanged (grep count 1); no (04-04) commit touches privacy.html or locale/; `pyproject.toml` and `uv.lock` unchanged since cce7779

## Deviations from Plan

None in substance. Minor: `includes/language_switch.html` also got `flex-wrap` (the plan named base.html only) so the EN / CS form wraps. In Task 2 the templates were edited before the RED commit was made, but the RED test run was recorded as failing first, and the RED commit still precedes the implementation commit in `git log`.

## Known Stubs

None.

## Human-action items

- Real-device check (iPhone Safari, Android Chrome, Czech, about 360px): no horizontal scrolling, buttons easy to tap, long names and links wrap, EN / CS switch reachable; Messenger and Instagram in-app browsers show the open-in-browser hint (to be listed in plan 04-05's docs/dry-run.md).

## Self-Check: PASSED

Commits e4ee91f, fc2da99, 80968eb, 463ef25, 30089d2, 910acf8 exist on main; gifter.css and test_phone.py present.
