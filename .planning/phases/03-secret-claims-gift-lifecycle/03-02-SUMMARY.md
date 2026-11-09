---
phase: 03-secret-claims-gift-lifecycle
plan: 02
subsystem: claims
tags: [django, received, secrecy, test-suite, privacy-policy, smoke]

requires:
  - phase: 03-secret-claims-gift-lifecycle
    provides: Claim and Contribution models, claims.py chokepoint, My claims, test helpers (mask_csrf, without_nav, claim_state_markers)
provides:
  - wish_received and wish_reopen owner views, collapsed Received section on My wishlist
  - gifter/tests/test_secrecy.py: route guard, sentinel crawl, region check, byte-identical snapshots, uniform 404 matrix, query capture, template data check, self-sensitivity test
  - Privacy policy section "Claims and chip-ins" and corrected who-can-see statements
  - smoke check (n) for /claims/
affects: [04 launch hardening, 04 Czech catalogue (new strings)]

actuals:
  tokens: 14000
  tasks: 3
  commits: 4

plan_head_before: 31404263c05539b974c53563f8ea8e9ea861325f
plan_head_after: de6c6a452e4a8c9cd9a3d836dcda7c45d9766523
commits: 4

tech-stack:
  added: []
  patterns:
    - "Detectors (snapshot, sentinel, region) are module-level functions so the same code runs on the real app and on an injected-leak mutant"
    - "Route guard compares walk_routes(get_resolver().url_patterns) with resolve(path).route of every probe"
    - "Received and reopen write update_fields=['status'] only, so claims and updated_at stay untouched"

key-files:
  created:
    - gifter/tests/test_received.py
    - gifter/tests/test_secrecy.py
  modified:
    - gifter/views.py
    - gifter/urls.py
    - gifter/templates/gifter/wishlist.html
    - gifter/templates/gifter/includes/owner_wish.html
    - gifter/templates/gifter/privacy.html
    - gifter/tests/test_privacy.py
    - scripts/smoke.sh
    - DEPLOYMENT.md

key-decisions:
  - "Self-sensitivity runs on every suite run through a locmem template override plus a test-only context processor, not a one-time manual mutation"
  - "Snapshots run inside savepoints for GET and POST alike, each with a fresh client and force_login, so cookies and flash messages cannot differ between runs"
  - "UNREACHABLE_ROUTES stays empty: the 34 pinned admin paths plus the top-level login redirect reach every walked route"

requirements-completed: [LIFE-01, LIFE-02, LIFE-03, SECR-02]

duration: 15min
completed: 2026-11-09
status: complete
---

# Phase 3 Plan 2: Received flow, secrecy test suite and privacy update Summary

**Giftees close wishes as Received (collapsed section, Reopen), a 23-test secrecy suite proves on every deploy that Gita's pages are byte-identical with and without claims and that a deliberately injected leak is caught, and the privacy policy now says what claims store and that the giftee never sees any of it.**

## Performance

- **Duration:** about 15 min of agent time
- **Tasks:** 3 (1 tracer, 1 auto, 1 TDD)
- **Commits:** 4 (measured from the plan ledger)
- **Files:** 10 changed (1059 insertions, 17 deletions)

## Accomplishments

- `wish_received` and `wish_reopen` (POST only, owner-scoped, status-only writes). A received wish leaves every event page at once and moves into a closed `<details>` "Received (n)" section with a Reopen button, ordered by priority then newest. Claims, chip-ins and `updated_at` are never touched, so claimers see "Received" on My claims and no false "Changed since" marker after Reopen.
- `gifter/tests/test_secrecy.py` (23 tests):
  - route guard: every route string from the full resolver walk (accounts, admin, gifter.urls, named and unnamed) must be reached by a probe, with the 34 pinned admin paths; `UNREACHABLE_ROUTES` is empty and checked for staleness, reachability and shadowing;
  - sentinel crawl of every probe as the giftee (ASCII token, case-insensitive, notes holding Czech letters and HTML);
  - own-wish-region check (main element, and the "Your wishes shared here" slice), with a proof that the co-member's "Taken by Kim" is on the same page and outside the region;
  - byte-identical GET and POST snapshots after masking only CSRF values;
  - uniform 404 matrix over the six action URLs (own claimed, own unclaimed, missing wish, missing event, not her event, outsider) with a no-change check on all claim rows;
  - query capture on 13 owner probes (no SQL on the claim tables) and a template-source check (no claim identifier in any expression);
  - `test_detectors_catch_injected_owner_leak`: a locmem override adds a "Taken by" badge to the owner card; the snapshot, sentinel and region detectors each fire on the wishlist and E1 page under the override and report nothing without it.
- Sanity checks done by hand: removing the admin catch-all probe fails the route guard; a claim-dependent change in the wishlist view fails the suite (13 failures).
- Privacy policy: new "Claims and chip-ins" section, the deleted-for-everyone sentence and the completeness sentence retired, who-can-see names claimers and contributors as the exception. `PRIVACY_POLICY_UPDATED` is 2026-11-09 and the date gate exits 0.
- Smoke check (n): `/claims/` signed out redirects to the landing page. `scripts/container-smoke.sh` prints PASS (n) and CONTAINER SMOKE OK.

## Task Commits

1. **Task 1 (tracer): received, reopen, collapsed Received section** - `5cb9376` (feat)
2. **Task 2: secrecy suite** - `aba1230` (test)
3. **Task 3 RED: failing privacy tests** - `f7a4945` (test)
4. **Task 3 GREEN: privacy policy, constant bump, smoke (n), DEPLOYMENT.md** - `de6c6a4` (feat)

## TDD Gate Compliance

Task 3 has its RED `test(...)` commit (`f7a4945`, three assertion failures) before the GREEN `feat(...)` commit (`de6c6a4`). No refactor commit was needed. Tasks 1 and 2 are not marked tdd.

## Decisions Made

- The secrecy suite proves its own sensitivity on every run rather than through a manual mutation step.
- Every snapshot request uses a fresh client with `force_login` inside a savepoint (plan-checker advisory 3).
- The seven accounts/ probes come from `ALLOWED_ACCOUNTS_ROUTES` in test_lockdown (advisory 1).
- test_received also asserts "Withdrawn by the owner" is absent on a received row and "Received" absent on a withdrawn row (advisory 2).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Two draft tests consumed flash messages before asserting on them**
- **Found during:** Task 1
- **Issue:** `assertRedirects` fetched the target page and consumed "Marked as received."; the secrecy snapshot compared a page that showed the message with one that did not.
- **Fix:** `fetch_redirect_response=False` in the tracer and reopen tests; a flushing GET before the first snapshot.
- **Committed in:** 5cb9376

**Total deviations:** 1, in tests only. No production leak was found by the secrecy suite, so no participant code was changed (advisory 4 not triggered). The admin route set did not change, so ADMIN_PATHS matches the plan exactly.

## Issues Encountered

- Protected-branch commit guard flags `main`; the dispatch states `main` is expected, so commits went there. Nothing was pushed.
- `ruff` is not installed in the project venv, so no lint run was possible.

## Verification

- Full suite: 251 tests OK. `makemigrations --check` clean. `check --deploy --fail-level WARNING` exits 0. `scripts/container-smoke.sh` prints PASS (n) and CONTAINER SMOKE OK.
- `git diff --quiet -- pyproject.toml uv.lock` exits 0. Privacy date gate exits 0. `deploy.yml` unchanged (`needs: test` present, test job runs `manage.py test`).
- Acceptance greps: wish_received and wish_reopen URLs 1 each, one `<details` in wishlist.html, two `update_fields=["status"]` writes, retired phrases 0, kept phrases 1.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model (T-03-11 to T-03-17); each mitigation has a test.

## Self-Check: PASSED

All created files exist and all four task commits are ancestors of HEAD (verified below).
