---
phase: 02-events-wishlists-browsing
plan: 02
subsystem: wishes
tags: [django, wishes, sharing, links, soft-delete, privacy, tdd]

requires:
  - phase: 02-events-wishlists-browsing
    provides: Event, Membership, event page, navbar, BootstrapFormMixin, privacy page (plan 02-01)
provides:
  - Wish reshaped (owner, priority, links, status, events M2M; claim columns removed) via migration 0003
  - My wishlist, add, edit and soft-delete wish views with validated, normalized links
  - Explicit per-event sharing (checkboxes, pre-ticked for new wishes) and Share all my wishes here
  - Event page with the viewer's own shared wishes (owner view) and one card per other member (participant view)
  - Privacy policy section for wishes and the soft delete
affects: [phase 3 claims (member_wish.html is the only wish template to extend)]

actuals:
  tokens: 21000
  tasks: 3
  commits: 5

plan_head_before: 0b9cd41739b7698b6df0d6a9f7f8a444c47fc938
plan_head_after: b84dd338fe82c054d98094b7fa817b3f4da869a1
commits: 5

tech-stack:
  added: []
  patterns:
    - "Owner and participant wish markup live in separate templates (owner_wish.html, member_wish.html)"
    - "Edit saves with update_fields excluding status, so a racing delete is never undone"
    - "normalize_links checks the scheme on the raw line before any https:// prefix"
    - "Sharing is only ever an explicit Wish.events row; there is no implicit visibility"

key-files:
  created:
    - gifter/migrations/0003_wish_owner_status_sharing.py
    - gifter/templates/gifter/wishlist.html
    - gifter/templates/gifter/wish_form.html
    - gifter/templates/gifter/wish_confirm_delete.html
    - gifter/templates/gifter/includes/owner_wish.html
    - gifter/templates/gifter/includes/member_wish.html
    - gifter/tests/test_wishes.py
  modified:
    - gifter/models.py
    - gifter/forms.py
    - gifter/views.py
    - gifter/urls.py
    - gifter/templates/gifter/base.html
    - gifter/templates/gifter/event_detail.html
    - gifter/templates/gifter/privacy.html
    - gifter/tests/test_privacy.py
    - DEPLOYMENT.md
    - .planning/phases/01-google-sign-in-live/01-REVIEW-DISPOSITION.md

key-decisions:
  - "Links are a newline-separated normalized TextField, not a link table"
  - "Delete is a soft delete (status withdrawn); share rows are kept and every listing filters on status"
  - "PRIVACY_POLICY_UPDATED stays 2026-11-08: that is the execution date, so the date gate exits 0"

requirements-completed: [WISH-01, WISH-02, WISH-03, WISH-04, CLAM-01]

coverage:
  - id: D1
    description: "Add a wish with name, optional description, priority and any number of links; shown on My wishlist"
    requirement: WISH-01
    verification:
      - kind: unit
        ref: "gifter/tests/test_wishes.py#WishCrudTests, NormalizeLinksTests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Edit and idempotent soft delete; withdrawn wishes vanish everywhere; other users get 404"
    requirement: WISH-02
    verification:
      - kind: unit
        ref: "gifter/tests/test_wishes.py#WishCrudTests"
        status: pass
    human_judgment: false
  - id: D3
    description: "Per-event sharing via owner-scoped checkboxes, pre-ticked, never implicit, forged ids rejected"
    requirement: WISH-03
    verification:
      - kind: unit
        ref: "gifter/tests/test_wishes.py#TracerTests"
        status: pass
    human_judgment: false
  - id: D4
    description: "Share all is POST-only, idempotent, local to one event, active wishes only"
    requirement: WISH-04
    verification:
      - kind: unit
        ref: "gifter/tests/test_wishes.py#ShareAllTests"
        status: pass
    human_judgment: false
  - id: D5
    description: "Event page groups other members' shared active wishes by person in priority/newest order; non-members get 404"
    requirement: CLAM-01
    verification:
      - kind: unit
        ref: "gifter/tests/test_wishes.py#TracerTests, WishCrudTests, ShareAllTests"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-11-08
status: complete
---

# Phase 2 Plan 2: Wishlists, sharing into events, and browsing Summary

**Wish reshaped with owner, priority, validated links, soft-delete status and an explicit events M2M (no claim columns), plus My wishlist, edit/delete, per-event sharing with Share all, and event-page cards where members browse each other's wishes.**

## Performance

- **Duration:** about 12 min of agent time
- **Tasks:** 3 (1 tracer, 2 TDD)
- **Commits:** 5 (measured from the plan ledger)
- **Files:** 17 changed (929 insertions, 24 deletions)

## Accomplishments

- Migration 0003 renames `user` to `owner` (a real RenameField), drops `claimed_by` and `is_active`, adds priority, links, status, events and updated_at. Closes WR-06 and IN-06.
- `normalize_links` rejects `javascript:`, `data:`, `mailto:` and `ftp:` on the raw line, accepts `alza.cz:8080/x` as host plus port, lowercases only scheme and host, de-duplicates and reports every bad line.
- Owner pages render no claim data (tests assert no `claim` field name on Wish and no `claim` text on /wishes/ and /wishes/new/).
- `event_share_all` is `require_POST`, resolves the event through `_member_event_or_404`, and uses an idempotent `event.wishes.add`; the post-join callout reuses it.
- Privacy policy now covers wishes, sharing and "Gifter keeps a copy" of deleted wishes, without mentioning claims or chip-ins.

## Task Commits

1. **Task 1 (tracer): reshape Wish, add wishes shared into events, member cards** - `1483a89` (feat)
2. **Task 2 RED: failing tests for links, edit and soft delete** - `3cace3d` (test)
3. **Task 2 GREEN: validated links, edit, soft delete** - `fd94bb2` (feat)
4. **Task 3 RED: failing tests for share-all, own section, privacy text** - `d253bca` (test)
5. **Task 3 GREEN: share all, own wishes section, privacy, docs, ledger** - `b84dd33` (feat)

## TDD Gate Compliance

Task 2 and Task 3 each have a RED `test(...)` commit (`3cace3d`, `d253bca`) before the GREEN `feat(...)` commit (`fd94bb2`, `b84dd33`). RED runs failed on assertion mismatches (for example 404 where 200/302 was expected, missing text), not on import or fixture faults. For Task 2 the `normalize_links` import is deferred into a thin test helper so the module loads and the unit tests fail with ImportError only for the function that does not exist yet, while the view tests failed on assertions. No refactor commit was needed.

## Decisions Made

- Links are one newline-separated TextField (D-06 needs only a textarea and normalized storage).
- Delete is soft: `status=withdrawn`, shares kept, all listings filter by status.
- The pre-tick of events on a new wish was implemented in Task 1 (rather than Task 2) because the tracer's tests exercise the form; behavior is unchanged.
- `PRIVACY_POLICY_UPDATED` left at 2026-11-08 (the execution date); the date gate exits 0.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan names the dropped columns `claimer`, actual column is `claimed_by`**
- **Found during:** Task 1
- **Issue:** The plan calls the field "claimer" in places; the real columns were `claimed_by` and `is_active`.
- **Fix:** Migration removes `claimed_by` and `is_active` as the plan intends.
- **Committed in:** 1483a89

**2. [Rule 1 - Bug] Netloc lowercasing in the first draft of normalize_links was a no-op**
- **Found during:** Task 2 (before the first GREEN run)
- **Issue:** `urlsplit(...).hostname` is already lowercase, so comparing it to its lowercase never fired.
- **Fix:** Lowercase `host_port` after `rpartition("@")`, keeping userinfo as typed.
- **Committed in:** fd94bb2

**Total deviations:** 2, no scope creep.

## Issues Encountered

- The protected-branch commit guard flags `main`; the dispatch states `main` is expected (sequential execution), so commits were made there. Nothing was pushed.
- `ruff` is not installed in the project venv, so no lint run was possible.
- The checkpoint-free tracer gate: `<verify>` was re-run end to end (full suite, makemigrations check) after the tracer and passed before expanding.

## Verification

- Full suite: 157 tests OK. `makemigrations --check` clean. `check --deploy --fail-level WARNING` clean. `scripts/container-smoke.sh` prints CONTAINER SMOKE OK (migration 0003 applies in the image).
- `git diff --quiet -- pyproject.toml uv.lock` exits 0. Policy-date gate exits 0.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model; T-02-09 to T-02-17 mitigations are covered by tests.

## Self-Check: PASSED

All created files exist and all five task commits are ancestors of HEAD (verified).
