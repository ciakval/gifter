---
phase: 03-secret-claims-gift-lifecycle
verified: 2026-11-09T21:00:00Z
status: human_needed
score: 5/5 must-haves verified
covered_files:
  - ".planning/phases/03-secret-claims-gift-lifecycle/03-01-PLAN.md"
  - ".planning/phases/03-secret-claims-gift-lifecycle/03-01-SUMMARY.md"
  - ".planning/phases/03-secret-claims-gift-lifecycle/03-02-PLAN.md"
  - ".planning/phases/03-secret-claims-gift-lifecycle/03-02-SUMMARY.md"
  - ".planning/phases/03-secret-claims-gift-lifecycle/03-03-PLAN.md"
  - ".planning/phases/03-secret-claims-gift-lifecycle/03-03-SUMMARY.md"
  - "DEPLOYMENT.md"
  - "gifter/admin.py"
  - "gifter/claim_views.py"
  - "gifter/claims.py"
  - "gifter/management/commands/delete_user.py"
  - "gifter/migrations/0004_claims_and_received.py"
  - "gifter/models.py"
  - "gifter/templates/gifter/includes/member_wish.html"
  - "gifter/templates/gifter/includes/owner_wish.html"
  - "gifter/templates/gifter/my_claims.html"
  - "gifter/templates/gifter/privacy.html"
  - "gifter/templates/gifter/wishlist.html"
  - "gifter/tests/test_claims.py"
  - "gifter/tests/test_lockdown.py"
  - "gifter/tests/test_received.py"
  - "gifter/tests/test_secrecy.py"
  - "gifter/urls.py"
  - "gifter/views.py"
covered_digest: "v4:sha256:0225568ec38d99681bc43103b20d867b57580ed808d2377f1a81ce5a44234f95"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "From no page, URL, error message, ordering or timestamp can the giftee tell whether their wishes are claimed (ROADMAP SC4, SECR-01): admin user-delete confirmation leaked Claim rows to a staff giftee"
  gaps_remaining: []
  regressions: []
deferred: []
human_verification:
  - test: "Two real people claim the same wish at the same moment on phones"
    expected: "Exactly one gets 'You are getting this one.'; the other lands back on the event card at #wish-<id> with 'Someone just took it.' and the card shows Taken"
    why_human: "The code side passes (unique OneToOne constraint plus IntegrityError handling, covered by a two-thread TransactionTestCase). A real two-device race on the production Gunicorn and SQLite stack, and the phone layout of the claim, chip-in and Release buttons, can only be seen live."
  - test: "Giftee walk-through on production after deploy"
    expected: "As the giftee (not staff) click through My wishlist, event page, wish edit, Received section and the privacy page while a friend claims and chips in on your wishes; nothing on any of them changes or reveals anything. Then, as the staff author, open the admin user list and a user's change page and confirm there is no Delete button, no bulk action, and that a user's delete URL answers 403."
    why_human: "Final confidence check of the core promise in the real environment with real sessions and the deployed image. Nothing from phase 3 has been pushed or deployed (production runs phase 2 at 7dd6a6a)."
---

# Phase 3: Secret Claims & Gift Lifecycle Verification Report

**Phase Goal:** Members can coordinate who buys what (claim, chip in, mark purchased) and giftees can close wishes once received. A giftee never learns who claimed or contributed, and automated tests enforce this.
**Verified:** 2026-11-09
**Status:** human_needed (all automated checks pass; two live-only checks remain)
**Re-verification:** Yes, after gap-closure plan 03-03

## Goal Achievement

The previous gap (the Django admin user-delete confirmation listing `Claim: <wish name>` rows to a staff giftee) is closed, and I could not find any other staff-reachable channel. I re-probed the original leak and then a wider set of admin surfaces independently, comparing the staff giftee's responses with and without claims on her wishes. No response differed. The full suite (264 tests), the migration check and the container smoke all pass. Plans 03-01 and 03-02 are unchanged in app code since the previous verification (`git diff 38eadd8 HEAD` touches only `gifter/admin.py`, `gifter/models.py` `__str__` bodies, and the new `delete_user` command outside tests), so the earlier VERIFIED truths stand.

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A member can claim a wish; every other non-giftee viewer sees it as taken in every event; names only to co-members; second simultaneous claimer sees "someone just took it" | VERIFIED | Unchanged since previous verification; `ClaimRaceTests` (two-thread) and test_claims.py pass in my full run. |
| 2 | Chip in with optional note; claimer can mark purchased or release (earliest contributor takes over); My claims lists everything across events | VERIFIED | Unchanged; test_claims.py green. |
| 3 | Claimer sees when the owner edited the wish after the claim, and when the owner withdrew it | VERIFIED | Unchanged; covered by test_claims.py. |
| 4 | From no page, URL, error message, ordering or timestamp can the giftee (staff or not) tell whether their wishes are claimed; sentinel crawl, owner-page diff and uniform-404 tests run in CI and block deploys | VERIFIED | Staff giftee probes (below) show no difference with vs without claims. `StaffGifteeTests` now runs the byte-identical snapshot pass as a staff giftee over `staff_probes(fx)` (all routes plus admin user, identity, group pages, bulk-delete POSTs on four lists, a filter probe per `User._meta.related_objects`, content-type shortcut ids 1-8), with a permanent sensitivity test that patches the admin fixes out and requires findings. Deploy gate unchanged (test job -> build-and-push -> deploy-production). |
| 5 | Giftee marks a wish received; it leaves every list and moves into a collapsed Received section without revealing the giver; giftee can reopen | VERIFIED | Unchanged; test_received.py green. |

**Score:** 5/5 roadmap truths verified; 0 behavior-unverified.

### 03-03 plan must-haves and prohibitions

| Must-have | Result | Evidence |
|-----------|--------|----------|
| Staff giftee gets one uniform 403 on any user delete URL (including nonexistent id); POST deletes nothing | VERIFIED | `GifterUserAdmin.has_delete_permission` returns False (admin.py). My probe: GET and POST `{"post":"yes"}` on gita, kim, sam delete URLs: 403, identical with and without claims. |
| No bulk delete action on the user list; forged `delete_selected` POST deletes nothing and shows no claim data | VERIFIED | Forged `delete_selected`, `make_verified` and unknown actions with all pks, one pk and none, on all four admin lists: no with/without-claims difference. |
| Reverse-relation list filters refused (400); built-in filters and search still work | VERIFIED | `lookup_allowed` refuses a first segment that is `auto_created and not concrete`. `test_reverse_relation_filters_are_refused_and_builtin_filters_work` passes. My probe of about 45 extra query strings across the user, SocialAccount, EmailAddress and Group lists (two- and three-hop lookups such as `user__claims__isnull`, `groups__user__claims__isnull`, `socialaccount__user__claims__isnull`, `wishes__claim__isnull`, ordering `o=`, `_facets`, `e`, `all`, `_changelist_filters`) gave zero with/without-claims differences. |
| Byte-identical staff responses over the full probe set | VERIFIED | Test `test_every_staff_giftee_response_is_byte_identical_with_and_without_claims` passes (part of 264). `last_login` removed at the source by disconnecting `update_last_login`, no new masks. |
| Cascade invariant over every registered ModelAdmin | VERIFIED | `test_admin_deletes_that_reach_claim_data_are_denied` uses `NestedObjects`; passes and asserts User is among reaching models. |
| `Claim.__str__` / `Contribution.__str__` without the wish name | VERIFIED | models.py returns `gettext("Claim %(pk)s")` and `gettext("Contribution %(pk)s")`; `grep` for `return self.(claim.)?wish.name` = 0; `test_claim_and_contribution_str_never_name_the_wish` passes. |
| SocialAccount and EmailAddress admins view only | VERIFIED | `has_add/change/delete_permission` False on both (3 `has_delete_permission` defs in admin.py). Lockdown tests pass. |
| `delete_user` command: dry run default, output independent of claims, discards `delete()` counts, refuses last active staff | VERIFIED | Read the command: counts discarded, only username/display name/email printed; last-staff guard raises "Nobody was deleted." in dry run and `--yes`. `DeleteUserCommandTests` pass. |
| DEPLOYMENT.md deletion steps, pre-deletion copy removed after verification, "removed or rotated", shell-deletion warning | VERIFIED | Day-2 "Delete someone's account (data request)" present (steps 1-5); greps: `delete_user` 5, `pre-deletion copy` 4, `removed or rotated` 1, `view and delete only` 0. |
| WR-04 supersession recorded, WR-04 stays fixed | VERIFIED | Row matches `^| WR-04 | warning | fixed | 01-07; ... superseded by 03-03 for SECR-01`; frontmatter `disposition: fixed` count 1. |
| No migration added, privacy.html unchanged | VERIFIED | `git diff --quiet 38eadd8 -- gifter/templates/gifter/privacy.html gifter/migrations pyproject.toml uv.lock` exits 0; `makemigrations --check --dry-run` reports "No changes detected". |
| Sensitivity test proves the staff pass can fail | VERIFIED | `test_staff_pass_catches_a_reopened_admin_leak` passes on every run (patches `GifterUserAdmin.has_delete_permission` / `lookup_allowed`). Summary documents a justified deviation (also patches the identity admins' delete permission, which are a second protective layer). |

Prohibitions: (1) admin MUST NOT render claim rows or claim-dependent responses for staff: HOLDS (probes below, cascade invariant). (2) `delete_user` MUST NOT print counts: HOLDS (read the command, test asserts no digits). (3) No migration / no privacy.html change: HOLDS (diff-quiet).

### Independent staff-giftee leak probes (beyond the suite)

I wrote a temporary test (since deleted; `git status` shows only the two pre-existing unstaged `.planning` files) that reused the suite's `Fixture`, `snapshot` (redirect chain, status, flashed messages, CSRF-masked body) with staff and superuser Gita, with and without claims, Google identity rows and a Group:

| Channel | Probe | Result |
|---------|-------|--------|
| User delete pages (own, claimer, contributor) GET and POST | 403 each | Identical with/without claims. |
| `delete_selected` and other actions on user, SocialAccount, EmailAddress, Group lists, three pk selections | forged POSTs | Identical. |
| List filters (reverse relations, two- and three-hop, ordering, facets, popup, changelist_filters) on all four lists | about 45 queries x 4 lists | Identical; first-hop reverse relations answer 400. |
| Admin index (recent actions), user history and change pages, add page, `_popup`/`_to_field=id` | GET | Identical. |
| Group delete and change pages | GET | Identical (cascade reaches only the user-group through rows). |
| Autocomplete endpoint for user, claim, wish, socialaccount, group fields | GET | Identical (claim/wish are unregistered, so no results). |
| Unregistered models (`gifter/claim`, `wish`, `contribution`, `event`, `membership`, `admin/logentry`) | GET | 404 each. |
| LogEntry / history | No code creates LogEntry rows about claims; claims are never written through the admin. | No channel. |
| App views as staff | grep: no `is_staff` branching in app views (only an admin-next redirect guard). | Staff sees the same pages as non-staff. |

Info only (not a secrecy gap): `?_to_field=claims` on the user list raises an `AttributeError` in Django's `to_field_allowed` (a Django bug when the name is a reverse relation). It is a 500 regardless of whether claims exist, so it is not a claim oracle. Production DEBUG is off.

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `gifter/admin.py` (`GifterUserAdmin`, view-only identity admins) | VERIFIED | Substantive and registered (`admin.site.register(User, GifterUserAdmin)` x1). |
| `gifter/models.py` (`__str__` changes) | VERIFIED | No state change, no migration. |
| `gifter/management/commands/delete_user.py` | VERIFIED | 47 lines, argument parsing, guards, real `user.delete()`. |
| `gifter/tests/test_secrecy.py` (`StaffGifteeTests`, `staff_admin_probes`, `staff_probes`) | VERIFIED | `ADMIN_PATHS` pin of 34 unchanged. |
| `gifter/tests/test_lockdown.py` (`DeleteUserCommandTests`, `test_user_delete_is_refused_and_not_offered`) | VERIFIED | Old test that pinned admin deletion removed. |
| `DEPLOYMENT.md`, `01-REVIEW-DISPOSITION.md` | VERIFIED | See above. |
| Phase 3-01/3-02 artifacts (models Claim/Contribution, migration 0004, claims.py, claim_views.py, templates, tests) | VERIFIED (regression check) | Files exist; tests green; no app-code change since previous verification. |

### Key Links

| From | To | Status |
|------|----|--------|
| `GifterUserAdmin.has_delete_permission` -> admin `_delete_view` / `get_actions` | WIRED (403 on every delete URL; bulk action absent) |
| `GifterUserAdmin.lookup_allowed` -> changelist | WIRED (reverse-relation filters refused) |
| `staff_probes` -> `ADMIN_PATHS` and route guard | WIRED (any new admin path is snapshotted as a staff giftee) |
| DEPLOYMENT.md -> `delete_user` -> /privacy/ deletion route | WIRED |
| Deploy workflow test job -> build-and-push -> deploy-production | WIRED (unchanged) |

### Behavioral Spot-Checks and Probes

| Check | Command | Result | Status |
|-------|---------|--------|--------|
| Full test suite | `DEBUG=1 uv run python manage.py test` | Ran 264 tests, OK | PASS |
| Migrations current | `DEBUG=1 uv run python manage.py makemigrations --check --dry-run` | "No changes detected", exit 0 | PASS |
| Container smoke | `bash scripts/container-smoke.sh` | Checks (a)-(n) PASS, "SMOKE OK", "CONTAINER SMOKE OK" | PASS |
| Staff giftee extra admin probes (temporary test) | see above | 0 differences, 0 claim data | PASS |

Probe execution (Step 7c): the phase declares no `probe-*.sh`; container smoke stands in and passed.

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| CLAM-02 | 03-01 | SATISFIED | claim_wish, race test, "Someone just took it." |
| CLAM-03 | 03-01 | SATISFIED | Taken badge everywhere; co-member name rule |
| CLAM-04 | 03-01 | SATISFIED | chip_in with 200-char note |
| CLAM-05 | 03-01 | SATISFIED | release_claim hand-over |
| CLAM-06 | 03-01 | SATISFIED | mark_purchased |
| CLAM-07 | 03-01 | SATISFIED | my_claims_for |
| CLAM-08 | 03-01 | SATISFIED | changed marker, Withdrawn state, Got it |
| SECR-01 | 03-01, 03-02, 03-03 | SATISFIED | Holds on all pages, URLs, errors, ordering, timestamps, and now the admin channel for a staff giftee |
| SECR-02 | 03-02, 03-03 | SATISFIED | Sentinel crawl, byte-identical snapshots, uniform 404, now also a staff-giftee pass with a permanent sensitivity test |
| LIFE-01 | 03-02 | SATISFIED | wish_received |
| LIFE-02 | 03-02 | SATISFIED | wish_reopen |
| LIFE-03 | 03-02 | SATISFIED | collapsed `<details>` Received section |

All 12 requirement IDs are claimed by plan frontmatter and match REQUIREMENTS.md; no orphans.

### Anti-Patterns Found

None. No TBD/FIXME/XXX in files touched by 03-03; no stubs.

### Advisory notes (not gaps)

- `delete_user` removes rows from SQLite, but freed pages stay in the database file until a `VACUUM`. This is outside the phase goal and matches how the /privacy/ route and backups are described; consider mentioning it in Phase 4 backup work.
- Phase 4 should translate the two new msgids ("Claim %(pk)s", "Contribution %(pk)s").

### Human Verification Required

1. **Simultaneous claim on two phones.** Test: two people press "I'll get this" on the same wish at once. Expected: one wins, the other sees "Someone just took it." Why human: the threaded test passes; a real two-device race on the production stack and the phone layout need a live check. Not a gap.
2. **Giftee and staff walk-through on production after deploy.** As a non-staff giftee click through the pages while friends claim; as the staff author confirm the admin offers no delete and answers 403 on user delete URLs.

### Gaps Summary

No gaps. The one blocker from the previous verification (admin user-delete confirmation exposing claim rows to a staff giftee) is closed by denying admin user deletion, refusing reverse-relation list filters, making identity admins view only, removing wish names from Claim and Contribution string forms, and adding a staff-giftee snapshot pass with a permanent sensitivity test and cascade invariant. Status is `human_needed` only because live-device and production walk-throughs cannot be done from the codebase.

Nothing was deployed or pushed. Production still runs phase 2 (7dd6a6a).

---

_Verified: 2026-11-09_
_Verifier: Claude (gsd-verifier)_
