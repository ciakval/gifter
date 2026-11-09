---
phase: 03-secret-claims-gift-lifecycle
verified: 2026-11-09T19:30:00Z
status: gaps_found
score: 4/5 must-haves verified
covered_files:
  - ".planning/phases/03-secret-claims-gift-lifecycle/03-01-PLAN.md"
  - ".planning/phases/03-secret-claims-gift-lifecycle/03-01-SUMMARY.md"
  - ".planning/phases/03-secret-claims-gift-lifecycle/03-02-PLAN.md"
  - ".planning/phases/03-secret-claims-gift-lifecycle/03-02-SUMMARY.md"
  - "gifter/admin.py"
  - "gifter/claim_views.py"
  - "gifter/claims.py"
  - "gifter/migrations/0004_claims_and_received.py"
  - "gifter/models.py"
  - "gifter/templates/gifter/includes/member_wish.html"
  - "gifter/templates/gifter/includes/owner_wish.html"
  - "gifter/templates/gifter/my_claims.html"
  - "gifter/templates/gifter/privacy.html"
  - "gifter/templates/gifter/wishlist.html"
  - "gifter/tests/test_claims.py"
  - "gifter/tests/test_received.py"
  - "gifter/tests/test_secrecy.py"
  - "gifter/urls.py"
  - "gifter/views.py"
covered_digest: "v4:sha256:63eb0474e9da6acb658f197ee84e21b398950c7eb59b2d9e44066f268405366d"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "From no page, URL, error message, ordering or timestamp can the giftee tell whether their wishes are claimed (ROADMAP SC4, SECR-01)"
    status: failed
    reason: "The Django admin delete-confirmation page for a User lists every Claim and Contribution that would cascade, rendered as 'Claim: <wish name>' (Claim.__str__ returns wish.name), even though Claim and Contribution are deliberately not registered in the admin. The author is staff and also a giftee, so the author can learn that a claim exists on their own wish, and which user made it. Probed with a staff giftee: /gifter-admin/gifter/user/<claimer pk>/delete/ shows 'Claims: 1 ... Claim: <the giftee's wish name>' (names the claimer in the heading and URL, so who and what). /gifter-admin/gifter/user/<own pk>/delete/ shows 'Wishs: 1 ... Claims: 1 ... Claim: <wish name>'. The 'delete selected users' action on the user list renders the same page. Not caught by the suite: the sentinel crawl and the admin probes run as a non-staff giftee (bounced), and the only admin test checks registration, not what the User delete page cascades."
    artifacts:
      - path: "gifter/admin.py"
        issue: "User is registered with the stock UserAdmin, so has_delete_permission is True and the delete confirmation (and delete_selected action) enumerates related Claim/Contribution rows of unregistered models."
      - path: "gifter/models.py"
        issue: "Claim.__str__ and Contribution.__str__ return the wish name, which the admin deletion summary prints."
    missing:
      - "Disable user deletion in the admin (UserAdmin.has_delete_permission returning False, and drop the delete_selected action), or override get_deleted_objects so Claim and Contribution never appear. Note ReadOnlySocialAccountAdmin comment says delete must stay allowed for cascades; revisit it."
      - "Add a staff-giftee test: request /gifter-admin/gifter/user/<claimer>/delete/, /gifter-admin/gifter/user/<own>/delete/ and the delete_selected action as a staff giftee with claims on their wishes, and assert the wish name and 'Claim' never appear (or that the response is 403/404/redirect)."
      - "Extend the sentinel crawl / byte-identical snapshots to run once as a staff giftee."
deferred: []
human_verification:
  - test: "Two real people claim the same wish at the same moment on phones"
    expected: "Exactly one gets 'You are getting this one.'; the other lands back on the event card at #wish-<id> with 'Someone just took it.' and the card shows Taken"
    why_human: "The code side passes (unique OneToOne constraint plus IntegrityError handling, covered by a two-thread TransactionTestCase). A real two-device race on the production Gunicorn and SQLite stack, and the phone layout of the claim, chip-in and Release buttons, can only be seen live."
  - test: "Giftee walk-through on production after deploy"
    expected: "As the giftee (not staff) click through My wishlist, event page, wish edit, Received section and the privacy page while a friend claims and chips in on your wishes; nothing on any of them changes or reveals anything"
    why_human: "Final confidence check of the core promise in the real environment, with real sessions and the deployed image."
---

# Phase 3: Secret Claims & Gift Lifecycle Verification Report

**Phase Goal:** Members can coordinate who buys what (claim, chip in, mark purchased) and giftees can close wishes once received. A giftee never learns who claimed or contributed, and automated tests enforce this.
**Verified:** 2026-11-09
**Status:** gaps_found
**Re-verification:** No, initial verification

## Goal Achievement

The coordination features and the received flow are implemented, wired and tested. The test suite is green (251 tests), and I could not find a leak on any participant or owner page, URL, error, ordering or timestamp. One leak exists through a channel the suite does not cover: the Django admin user-delete confirmation, which a staff giftee (the author) can open. It violates the core promise literally, so the phase is `gaps_found` until it is closed. The fix is small.

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A member can claim a wish; every other non-giftee viewer sees it as taken in every event; names only to viewers who share an event with that person; second simultaneous claimer sees "someone just took it" | VERIFIED | `claims.claim_wish` relies on `Claim.wish` OneToOne plus `IntegrityError` (claims.py). `event_detail` builds the per-viewer `ClaimView` through `claim_views_for`, names go through `_person` with `co_member_ids`. `member_wish.html` renders Taken/Purchased and "Taken by someone". `wish_claim` flashes "Someone just took it." on `TAKEN`. Two-thread race test `ClaimRaceTests` (TransactionTestCase) passes in my full run. |
| 2 | Chip in with optional note; claimer can mark purchased or release (earliest contributor takes over); My claims lists everything across events | VERIFIED | `chip_in` (get_or_create, unique claim+user, note max 200), `mark_purchased`, `release_claim` hands over to earliest `(created_at, pk)` contribution and deletes that row, `my_claims_for` queries Claim/Contribution by user (so un-shared, withdrawn, received stay listed). URLs `claims/`, `claims/<pk>/purchased|release|leave|got-it/` all `@require_POST` except the list. Nav link present. Covered by test_claims.py (687 lines, all green). |
| 3 | Claimer sees when the owner edited the wish after the claim, and when the owner withdrew it | VERIFIED | `_claim_view.changed` compares `wish.updated_at` to the claimer's or contributor's `acknowledged_at`; `wish_edit` bumps `updated_at` only when name, description, priority or links changed; `wish_delete` withdraws, and `my_claims_for` returns `state == "withdrawn"` rows ("Withdrawn by the owner" plus "Remove from my claims"). "Got it" calls `acknowledge`. |
| 4 | From no page, URL, error message, ordering or timestamp can the giftee tell whether their wishes are claimed; sentinel crawl, owner-page diff and uniform-404 tests run in CI and block deploys | FAILED (BLOCKER) | Pages, URLs, errors, ordering and timestamps all pass my independent probes (below), and the suite plus the deploy gate exist. But the staff giftee can read claim existence and the claimer's identity through the admin user-delete confirmation page (see Gaps). The suite does not detect it, so "automated tests enforce this" is also not fully true for that channel. |
| 5 | Giftee marks a wish received; it leaves every list and moves into a collapsed Received section without revealing the giver; giftee can reopen | VERIFIED | `wish_received` / `wish_reopen` (owner path, `update_fields=["status"]`, no claim import, claims untouched). `wishlist.html` renders `<details>` without `open`, ordered by priority then newest. `event_detail` and `claim_views._participant_wish_or_404` filter to ACTIVE, so received wishes leave event pages and cannot be claimed; My claims shows "Received". test_received.py green. |

**Score:** 4/5 roadmap truths verified. The 14 plan-level truths and the 4 prohibitions below were also checked; only the admin channel fails.

### Plan prohibitions (must_haves.prohibitions)

| Prohibition | Tier | Result |
|-------------|------|--------|
| Owner-facing pages/templates MUST NOT load or render claim data; Wish exposes no claim accessor | test | HOLDS. `Claim.wish` has `related_name="+"`; `OwnerQueryTests`, `OwnerTemplateSourceTests` and `SelfSensitivityTests` pass; owner templates contain no claim data (read `owner_wish.html`, `wishlist.html`). |
| Claim endpoints MUST NOT answer anyone without visibility with anything but one uniform 404 | test | HOLDS. I POSTed claim/chip-in/purchased/release/got-it/leave as a giftee on own wish, nonexistent wish, nonexistent event: one distinct response (404, identical body). |
| Names and notes MUST NOT be shown to a viewer who shares no event with that person | test | HOLDS. `_person` blanks name and note unless `is_you` or in `co_member_ids`; covered in test_claims. |
| Claim/Contribution MUST NOT be registered in admin; no money fields | test | HOLDS in the narrow sense (not registered, no amount field), but the unregistered models still leak through the User delete page. This is the gap above. |

### Independent leak probes (beyond the suite)

| Channel | Probe | Result |
|---------|-------|--------|
| Ordering of giftee's wishes | Code read: `wishlist`/`event_detail` order by `priority, -created_at, -pk` only | No claim data in ordering. OK |
| Timestamps | claim, chip-in, purchased, release, got-it, received, reopen never save Wish with `updated_at`; probe: `wish.updated_at` unchanged after claims on it | OK |
| Counts | Owner pages never query claim tables (`OwnerQueryTests`); event page counts members/wishes only | OK |
| Error messages / 404 vs other codes | Giftee POST on own wish vs nonexistent: identical 404 body; GET on action URLs is 405 for everyone alike (before any lookup) | OK |
| Privacy page | Static, reads two constants; text promises "never sees any of this", which is currently false for the admin channel | OK until the gap is closed |
| My claims for a giftee who also claims elsewhere | Anna claims Bob's wish while Carol claims and Bob chips in on Anna's wish: Anna's /claims/ shows only BOBWISH, not ANNAWISH, Carol or Bob's note; `my_claims_for` also excludes own wishes | OK |
| Event page for that giftee | Own-wish region shows plain owner card; no claim markers | OK |
| Django admin (staff giftee) | User delete confirmation and delete_selected action | LEAK (see Gaps) |

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `gifter/models.py` (Claim, Contribution, Wish.Status.RECEIVED) | VERIFIED | Substantive, OneToOne unique claim, unique (claim, user). |
| `gifter/migrations/0004_claims_and_received.py` | VERIFIED, additive | Operations: AlterField on wish.status choices (`sqlmigrate` prints `(no-op)`), CreateModel Claim, CreateModel Contribution. No RemoveField, DeleteModel, RunPython or data rewrite; safe for live data. `makemigrations --check --dry-run` reports no changes. |
| `gifter/claims.py` | VERIFIED | The only claim read/write point; `claim_views_for` raises `SecrecyViolation` for own wishes. |
| `gifter/claim_views.py` | VERIFIED | All actions `@require_POST`, uniform `Http404`. |
| `member_wish.html`, `my_claims.html`, `owner_wish.html`, `wishlist.html`, `privacy.html` | VERIFIED | Wired from `event_detail`, `my_claims`, `wishlist`, `privacy`. |
| `gifter/tests/test_secrecy.py`, `test_claims.py`, `test_received.py` | VERIFIED as present and passing | Route guard, sentinel crawl, own-wish region, byte-identical snapshots, 404 matrix, query capture, self-sensitivity. Blind spot: no staff-giftee/admin coverage. |

### Key Links

| From | To | Status |
|------|----|--------|
| event_detail -> claims.claim_views_for (participant list only, viewer excluded) | WIRED |
| claim_views -> claims services via `_participant_wish_or_404` | WIRED |
| wishlist/owner_wish.html -> `wish_received` / `wish_reopen` | WIRED |
| base.html nav -> `my_claims` | WIRED |
| `.github/workflows/deploy.yml`: `test` job runs `manage.py test` (whole suite incl. secrecy) -> `build-and-push` has `needs: test` -> `deploy-production` has `needs: build-and-push` | WIRED (ROADMAP SC4 gate present) |

### Behavioral Spot-Checks and Probes

| Check | Command | Result | Status |
|-------|---------|--------|--------|
| Full test suite | `DEBUG=1 uv run python manage.py test` | Ran 251 tests, OK (includes the threaded race test) | PASS |
| Migrations current | `DEBUG=1 uv run python manage.py makemigrations --check --dry-run` | "No changes detected", exit 0 | PASS |
| Migration SQL | `manage.py sqlmigrate gifter 0004` | One no-op, two CREATE TABLE plus indexes, no ALTER/DROP | PASS |
| Container smoke | `bash scripts/container-smoke.sh` | Checks (a)-(n) PASS including (n) `/claims/` signed-out redirect, "CONTAINER SMOKE OK", exit 0 | PASS |
| Admin leak probe (temporary test, removed) | staff giftee GET `/gifter-admin/gifter/user/<pk>/delete/` | Page contains "Claim: <wish name>" and "Claims: 1" | FAIL |

Probe execution (Step 7c): the phase declares no `probe-*.sh` scripts; the smoke script above stands in and passed.

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| CLAM-02 | 03-01 | SATISFIED | claim_wish + race test + "Someone just took it." |
| CLAM-03 | 03-01 | SATISFIED | Taken badge in every event; `co_member_ids` name rule |
| CLAM-04 | 03-01 | SATISFIED | chip_in with 200-char note |
| CLAM-05 | 03-01 | SATISFIED | release_claim hand-over |
| CLAM-06 | 03-01 | SATISFIED | mark_purchased, Purchased badge |
| CLAM-07 | 03-01 | SATISFIED | my_claims_for across events and states |
| CLAM-08 | 03-01 | SATISFIED | changed marker, Withdrawn state, Got it |
| SECR-01 | 03-01, 03-02 | BLOCKED (partial) | Holds on all pages, URLs, errors, ordering, timestamps; broken through the admin user-delete page for a staff giftee |
| SECR-02 | 03-02 | SATISFIED as written (sentinel crawl, byte-identical diff, uniform 404), but the crawl does not cover a staff giftee, which is why SECR-01's gap was missed | 
| LIFE-01 | 03-02 | SATISFIED | wish_received |
| LIFE-02 | 03-02 | SATISFIED | wish_reopen |
| LIFE-03 | 03-02 | SATISFIED | collapsed `<details>` Received section |

All 12 requirement IDs in the phase are claimed by a plan frontmatter and match REQUIREMENTS.md (no orphans; CLAM-01 belongs to Phase 2).

### Anti-Patterns Found

None. No TBD/FIXME/XXX in files touched by the phase; no stubs; no empty implementations.

### Human Verification Required

1. **Simultaneous claim on two phones.** Test: two people press "I'll get this" on the same wish at once. Expected: one wins, the other sees "Someone just took it." Why human: the code path and a threaded test pass; a real two-device race on production needs live check. Not a gap.
2. **Giftee walk-through on production** after deploy, as a non-staff giftee while friends claim.

### Gaps Summary

One gap (BLOCKER for SC4 / SECR-01): the admin user-delete confirmation exposes `Claim: <wish name>` rows (and `Contribution:` rows) to staff. Because the author is both staff and a giftee, the core promise is violated for the author. Root cause: stock `UserAdmin` allows delete, and Django's deletion summary prints every cascading object even for unregistered models. Fix: disable user delete in the admin (or filter the deletion summary), update the `ReadOnlySocialAccountAdmin` docstring that relies on delete, and add a staff-giftee test that requests the delete URLs and the delete_selected action and asserts no claim text appears. The suite's route guard already lists the admin delete paths, so the simplest durable guard is to run one probe pass as a staff giftee with claims on their wishes.

Nothing was deployed or pushed. Production still runs phase 2 (7dd6a6a); this fix should land before phase 3 ships.

---

_Verified: 2026-11-09_
_Verifier: Claude (gsd-verifier)_
