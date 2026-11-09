---
phase: 03-secret-claims-gift-lifecycle
plan: 01
subsystem: claims
tags: [django, claims, secrecy, chip-in, my-claims, tdd, sqlite-race]

requires:
  - phase: 02-events-wishlists-browsing
    provides: Event, Membership, Wish, member_wish.html participant card, _member_event_or_404, navbar
provides:
  - Claim and Contribution tables (migration 0004, additive) and Wish.Status.RECEIVED
  - gifter/claims.py secrecy chokepoint and claim services (claim, chip in, purchased, release hand-over, leave, got-it, My claims)
  - Participant claim UI on event cards (Taken/Purchased badges, per-viewer names, buttons) and the My claims page
  - Test helpers mask_csrf, without_nav, CLAIM_STATE_MARKERS, claim_state_markers (reused by plan 03-02)
affects: [03-02 received flow and full secrecy suite, 04 Czech catalogue (new strings)]

actuals:
  tokens: 16000
  tasks: 3
  commits: 5

plan_head_before: 7ed5b102e32745802a48b47fe4c371dbce3842a3
plan_head_after: 561e818bcd4820a3c63405fecebac3c1cc10a11b
commits: 5

tech-stack:
  added: []
  patterns:
    - "All claim reads and writes live in gifter/claims.py; templates only receive frozen dataclasses (ClaimView, Person, MyClaimRow)"
    - "Claim.wish is a OneToOne with related_name '+': the unique constraint decides races, and Wish has no claim accessor"
    - "Participant actions resolve through one lookup that ends in a bare Http404 (uniform 404, D-15)"
    - "Owner edit bumps updated_at only when content fields changed, so share-only saves raise no Changed marker"

key-files:
  created:
    - gifter/claims.py
    - gifter/claim_views.py
    - gifter/migrations/0004_claims_and_received.py
    - gifter/templates/gifter/my_claims.html
    - gifter/tests/helpers.py
    - gifter/tests/test_claims.py
  modified:
    - gifter/models.py
    - gifter/views.py
    - gifter/urls.py
    - gifter/forms.py
    - gifter/templates/gifter/base.html
    - gifter/templates/gifter/event_detail.html
    - gifter/templates/gifter/includes/member_wish.html
    - gifter/tests/test_wishes.py
    - gifter/tests/test_lockdown.py

key-decisions:
  - "A claimer never also chips in: chip-in by the claimer is a no-op with 'You are already getting this one.'"
  - "Release hands the claim to the earliest contribution by (created_at, pk), resets status to reserved and carries that contributor's acknowledged_at over"
  - "Contributors get the Changed marker too (their own acknowledged_at), with 'Changed since you chipped in'"
  - "Owner pages are checked for claim-state copy (CLAIM_STATE_MARKERS) with the top bar removed, not for the bare word 'claim' (D-14 as amended)"

requirements-completed: [CLAM-02, CLAM-03, CLAM-04, CLAM-05, CLAM-06, CLAM-07, CLAM-08, SECR-01]

duration: 6min
completed: 2026-11-09
status: complete
---

# Phase 3 Plan 1: Secret claims, chip-in and My claims Summary

**Members claim, chip in on, purchase and release other members' wishes, with names shown only to people who share an event, a unique-constraint race decider, and a My claims page covering un-shared, withdrawn and received wishes, while the giftee's pages stay byte-identical.**

## Performance

- **Duration:** about 6 min of agent time
- **Tasks:** 3 (1 tracer, 2 TDD)
- **Commits:** 5 (measured from the plan ledger)
- **Files:** 15 changed (1425 insertions, 17 deletions)

## Accomplishments

- Migration 0004 is additive only (two CreateModel plus one AlterField widening Wish.status). `makemigrations --check` is clean and `scripts/container-smoke.sh` prints CONTAINER SMOKE OK (it applies in the production image).
- `claims.claim_views_for` raises `SecrecyViolation` for any wish the viewer owns and runs zero queries for an empty list. Names and chip-in notes pass through one `_person` rule: shown only when the viewer shares an event with that person.
- Simultaneous claims: `claim_wish` inserts and catches `IntegrityError`; a 10-round two-thread `TransactionTestCase` ends with one `claimed`, one `taken` and exactly one Claim row every round. The loser lands on `#wish-<id>` with "Someone just took it."
- Every action (claim, chip-in, purchased, release, leave, got-it) is `@require_POST`; the giftee, non-members, unshared, withdrawn and nonexistent ids all return the same 404 body. None of it writes the Wish row (`updated_at` unchanged, tested).
- My claims (`/claims/`, in the top bar) lists claims and chip-ins by user, so un-shared wishes stay, withdrawn ones show "Withdrawn by the owner" with "Remove from my claims", received ones show "Received". Order is active, withdrawn, received, newest involvement first.
- Changed marker: `wish.updated_at` later than the viewer's `acknowledged_at` shows "Changed since you claimed/chipped in" with a Got it button on both pages. A share-only owner edit no longer bumps `updated_at`.
- test_wishes' three bare-word "claim" checks were replaced by `claim_state_markers(...) == []` on pages with the top bar removed (D-14 as amended).

## Task Commits

1. **Task 1 (tracer): models, migration 0004, claims chokepoint, claim view, event-card badges, race test** - `d2fe3d9` (feat)
2. **Task 2 RED: failing tests for chip-in, purchased, release hand-over** - `e2aa077` (test)
3. **Task 2 GREEN: chip in, mark purchased, release with hand-over** - `e5b62ba` (feat)
4. **Task 3 RED: failing tests for My claims, changed marker, claim-state markers** - `e03819e` (test)
5. **Task 3 GREEN: My claims, changed marker with Got it, nav link** - `561e818` (feat)

## TDD Gate Compliance

Task 2 and Task 3 each have a RED `test(...)` commit (`e2aa077`, `e03819e`) before the GREEN `feat(...)` commit (`e5b62ba`, `561e818`). RED runs failed on assertions and missing routes (404 where 302 was expected, missing text), not on import faults. The Task 3 RED commit also carries the `helpers.py` markers and the test_wishes replacements, which are test infrastructure. No refactor commit was needed.

## Decisions Made

- A claimer cannot chip in on their own claim; a repeated claim by the claimer is a silent no-op (assumption A-01).
- Hand-over carries the new claimer's acknowledgement time over, so a marker they had as a contributor survives (A-02).
- Purchased is one-way in this phase (A-03). Releasing a purchased claim hands over as reserved.
- Contributors receive the Changed marker as well (D-08 left it to discretion).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test compared byte offsets instead of card order**
- **Found during:** Task 1
- **Issue:** `test_claiming_does_not_reorder_cards` compared `html.index` offsets, which shift when the Taken badge adds text, so it failed on a correct page.
- **Fix:** Compare the order of names only.
- **Committed in:** d2fe3d9

**2. [Rule 1 - Bug] Two draft tests were wrong**
- **Found during:** Task 3 RED/GREEN
- **Issue:** The unshared-release test logged in as Bob before Carol's 404 probe; the first visibility test on My claims did not exercise two social circles.
- **Fix:** Reordered the first, replaced the second with a Fran (E5 only) versus Bob (E1 only) scenario that checks "Taken by someone", no name leak and no note leak.
- **Committed in:** e03819e, 561e818

**Total deviations:** 2, both in tests, no scope creep. Production code matched the plan.

## Issues Encountered

- The protected-branch commit guard flags `main`; the dispatch states `main` is expected (sequential execution), so commits went there. Nothing was pushed.
- `ruff` is not installed in the project venv, so no lint run was possible.
- The tracer gate re-ran the full suite and `makemigrations --check` after Task 1 and both passed before expanding.

## Verification

- Full suite: 212 tests OK (race test stable across repeated runs). `makemigrations --check` clean. `check --deploy --fail-level WARNING` exits 0. `scripts/container-smoke.sh` prints CONTAINER SMOKE OK.
- `git diff --quiet -- pyproject.toml uv.lock` exits 0. Owner templates (`owner_wish.html`, `wishlist.html`, `wish_form.html`, `wish_confirm_delete.html`) are unchanged against 9f4196f.
- Acceptance greps: 2 CreateModel, 0 destructive operations, `related_name="+"` count 1, no bare-word claim assertions left in test_wishes.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model (T-03-01 to T-03-10). Mitigations are covered by tests: uniform 404 matrix, byte-identical giftee pages, escaped names and notes, same-host `next`, POST-only (405 on GET), Claim and Contribution not registered in admin.

## Notes for Plan 03-02

- Reuse `gifter/tests/helpers.py` (`mask_csrf`, `without_nav`, `CLAIM_STATE_MARKERS`, `claim_state_markers`). If 03-02 adds new claim-visible copy, extend the tuple.
- `Wish.Status.RECEIVED` exists and My claims already renders it; event pages and the wishlist already filter on ACTIVE, so a received wish leaves them. The owner's Received action, the Received section and Reopen are still to build.
- New strings are wrapped for translation but there is no Czech catalogue yet (Phase 4).

## Self-Check: PASSED

All created files exist and all five task commits are ancestors of HEAD (verified below).
