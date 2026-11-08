---
phase: 02-events-wishlists-browsing
plan: 01
subsystem: events
tags: [django, events, membership, invite-links, allauth, privacy, tdd]

requires:
  - phase: 01-google-sign-in-live
    provides: Google sign-in, LoginRequiredMiddleware, landing page with next, deployment smoke scripts
provides:
  - Event and Membership models (migration 0002), invite token per event
  - My events list, event creation, event page with collapsible members list and invite link box
  - /invite/<token>/ confirm-and-join flow (no join on GET), session fallback, signed-in safe-next on landing
  - Navbar (Events, Sign out) and BootstrapFormMixin / EventForm
  - Privacy policy section for events, members and invite links
affects: [02-02 wishes and sharing, phase 3 claims]

actuals:
  tokens: 11400
  tasks: 2
  commits: 3

plan_head_before: 27bb04038e35ec8da844834e464b82dd9dc2295a
plan_head_after: 77d14ba636cb8662e08f1ef1e7165e29f2ef2598
commits: 3

tech-stack:
  added: []
  patterns:
    - "_member_event_or_404: one code path for non-member and missing id, identical 404 bodies"
    - "Anonymous invite hits store the token in the session and redirect_to_login for every token"
    - "display_name never falls back to the (email-derived) username"

key-files:
  created:
    - gifter/forms.py
    - gifter/migrations/0002_event_membership.py
    - gifter/templates/gifter/event_form.html
    - gifter/templates/gifter/event_detail.html
    - gifter/templates/gifter/invite.html
    - gifter/templates/gifter/includes/form_field.html
    - gifter/tests/test_events.py
  modified:
    - gifter/models.py
    - gifter/views.py
    - gifter/urls.py
    - gifter/templates/gifter/base.html
    - gifter/templates/gifter/home.html
    - gifter/templates/gifter/privacy.html
    - gifter/tests/test_auth.py
    - gifter/tests/test_privacy.py
    - scripts/smoke.sh

key-decisions:
  - "Event.created_by is SET_NULL so account deletion never blocks on events"
  - "Landing never follows a next that points into the admin, to avoid a redirect loop with the admin's login redirect"
  - "PRIVACY_POLICY_UPDATED stays 2026-11-08: that is the execution date, so the bump is a no-op and the date gate passes"

requirements-completed: [EVNT-01, EVNT-02, EVNT-03, EVNT-04, EVNT-05]

coverage:
  - id: D1
    description: "Signed-in user creates an event and sees it in My events and on its page with members"
    requirement: EVNT-01
    verification:
      - kind: unit
        ref: "gifter/tests/test_events.py#EventCreateTests, MyEventsTests, EventDetailTests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every member sees a copyable absolute invite link"
    requirement: EVNT-02
    verification:
      - kind: unit
        ref: "gifter/tests/test_events.py#InviteTests.test_every_member_sees_the_invite_link"
        status: pass
    human_judgment: false
  - id: D3
    description: "Invite round trip through Google lands on a confirm page; only POST joins; previews join nobody"
    requirement: EVNT-03
    verification:
      - kind: unit
        ref: "gifter/tests/test_events.py#InviteTests, InviteRoundTripTests"
        status: pass
      - kind: integration
        ref: "bash scripts/container-smoke.sh (checks l, m)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Members list by display name only; non-members get the same 404 as a missing id"
    requirement: EVNT-04
    verification:
      - kind: unit
        ref: "gifter/tests/test_events.py#EventDetailTests"
        status: pass
    human_judgment: false
  - id: D5
    description: "/events/ orders by date (undated last), name, pk and lists only own events"
    requirement: EVNT-05
    verification:
      - kind: unit
        ref: "gifter/tests/test_events.py#MyEventsTests"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-11-08
status: complete
---

# Phase 2 Plan 1: Events and invite links Summary

**Event and Membership models with a member-only event page, My events list, an invite link every member can copy, and a /invite/<token>/ confirm page that joins only on an explicit POST (with a signed-out Google round trip and a session fallback).**

## Performance

- **Duration:** about 8 min of agent time
- **Started:** 2026-11-08T19:12:00Z
- **Completed:** 2026-11-08
- **Tasks:** 2
- **Files modified:** 16 (code and tests)

## Accomplishments

- Event creation, My events ordering, collapsible members list in join order, navbar with Sign out POST form.
- Invite flow: anonymous visits (including preview bots) get an identical redirect for every token and see no event data; signed-in visitors confirm via POST, idempotent; already-members get an "already in" page.
- `/events/` forwards once to a pending invite if `next` was lost; landing follows a safe same-site `next` for signed-in visitors (IN-08).
- Privacy policy and smoke checks (l) and (m) updated; container smoke passes with migration 0002.

## Task Commits

1. **Task 1: tracer, create event / My events / event page** - `65c2dde` (feat)
2. **Task 2 RED: failing invite, fallback, safe-next and privacy tests** - `ab75c87` (test)
3. **Task 2 GREEN: invite flow, fallback, safe next, privacy, smoke** - `77d14ba` (feat)

## TDD Gate Compliance

RED commit `ab75c87` precedes GREEN commit `77d14ba`. RED evidence for target `gifter.tests.test_events.InviteTests.test_post_joins_once_and_is_idempotent` classified `RED_EVIDENCE_OK` (unittest format, 1 failure on `404 != 302`). Semantic assessment: the target ran and failed on the planned assertion because the `/invite/<token>/` route did not exist yet, not because of a syntax, import or fixture fault. 12 tests failed in the full RED run, all assertion failures.

## Decisions Made

- `Event.created_by` uses SET_NULL so deleting an account never blocks on events.
- Anonymous invite requests store the token and redirect for every token, so validity cannot be probed.
- `PRIVACY_POLICY_UPDATED` unchanged at 2026-11-08 (execution date); the policy-date gate exits 0.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Landing safe-next caused an admin redirect loop**
- **Found during:** Task 2 (full suite after GREEN)
- **Issue:** The admin sends signed-in non-staff users to `/gifter-admin/login/?next=/gifter-admin/`, which redirects to `/?next=/gifter-admin/`. With the new IN-08 behaviour landing followed `next` back to the admin: infinite loop (`test_lockdown.AdminAccessTests.test_non_staff_bounced_without_loop` failed).
- **Fix:** Landing does not follow a `next` that starts with `reverse("admin:index")`; it goes home. Added a test.
- **Files modified:** gifter/views.py, gifter/tests/test_events.py
- **Committed in:** 77d14ba

**2. [Rule 1 - Bug] `_` shadowed gettext in the invite view**
- **Found during:** Task 2 GREEN
- **Issue:** `_, created = get_or_create(...)` rebound the gettext alias, raising `TypeError` on the success message.
- **Fix:** Renamed to `_membership`.
- **Committed in:** 77d14ba

**3. [Test correction] "already member has no join form" assertion matched the navbar's POST form**
- **Fix:** Asserted absence of the `btn-lg` Join button instead.
- **Committed in:** 77d14ba

**Total deviations:** 2 auto-fixed bugs and 1 test correction. No scope creep.

## Issues Encountered

- The protected-branch commit guard flags `main`. The dispatch states main is the expected branch (`branching_strategy=none`, sequential execution), so commits were made on main without changing any configuration. Nothing was pushed.
- `ruff` is not installed in the project venv, so no lint run was possible.

## Known Stubs

None. Plan 02-02 wish sections are marked by a template comment on the event page only.

## Threat Flags

None beyond the plan's threat model. Mitigations T-02-01 to T-02-06 are covered by tests.

## Self-Check: PASSED

Created files and commits verified (see below); full suite 113 tests OK, `makemigrations --check` clean, `check --deploy` clean, container smoke prints PASS (l), PASS (m), CONTAINER SMOKE OK, `pyproject.toml` and `uv.lock` unchanged, policy-date gate exits 0.
