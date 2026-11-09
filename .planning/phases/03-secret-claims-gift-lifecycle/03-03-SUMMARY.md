---
phase: 03-secret-claims-gift-lifecycle
plan: 03
subsystem: admin-secrecy
tags: [django, admin, secrecy, gap-closure, delete_user, test-suite]

requires:
  - phase: 03-secret-claims-gift-lifecycle
    provides: test_secrecy.py (Fixture, snapshot, probes, ADMIN_PATHS), Claim and Contribution models
provides:
  - GifterUserAdmin (delete denied, reverse-relation list filters refused)
  - SocialAccount and EmailAddress admins view only
  - Claim and Contribution string forms without the wish name
  - StaffGifteeTests (staff snapshot pass over every route plus admin probes, permanent sensitivity test, deletion cascade invariant)
  - manage.py delete_user (dry run by default, output independent of claims, last-staff guard)
  - DEPLOYMENT.md "Delete someone's account (data request)"
affects: [04 launch hardening (two new msgids, backups vs deletion copies)]

status: complete
actuals:
  tokens: 7500
  tasks: 3
  commits: 6
plan_head_before: 97adb9ae58f8095bce5cb147fb19871cc030c547
plan_head_after: 1a056f0cf4ad84dd889a19ce15f2b52cd080d3f0
commits: 6

tech-stack:
  added: []
  patterns:
    - "Staff probe list = probes(fx) + staff_admin_probes(fx), deduplicated by (method, path); related-object filter probes are generated from User._meta.related_objects"
    - "Sensitivity test patches the admin fixes out with mock.patch.object and requires snapshot_findings to report exactly the selected probes"
    - "NestedObjects invariant over every registered ModelAdmin and row: delete must be denied wherever Claim or Contribution is reached"

key-files:
  created:
    - gifter/management/commands/delete_user.py
  modified:
    - gifter/admin.py
    - gifter/models.py
    - gifter/tests/test_secrecy.py
    - gifter/tests/test_lockdown.py
    - DEPLOYMENT.md
    - .planning/phases/01-google-sign-in-live/01-REVIEW-DISPOSITION.md

key-decisions:
  - "User deletion is denied in the admin; people are deleted with manage.py delete_user, whose output never depends on claims"
  - "03-03 reverses 01-07's WR-04 admin-deletion must-have for SECR-01; recorded in 01-REVIEW-DISPOSITION.md (WR-04 itself stays fixed)"
  - "Admin 403s are Django's uniform 403 for any id, a nonexistent one included, so they are no existence oracle and not an exception to D-15 (see note below)"
  - "Pre-deletion copy is taken with sqlite3 .backup (online-consistent, single file); the alternative is a stopped-container copy of all three files"

requirements-completed: [SECR-01, SECR-02]
duration: ~35 min
completed: 2026-11-09
---

# Phase 3 Plan 03: Close the admin channel for a staff giftee Summary

**A staff giftee can no longer learn anything about claims from the Django admin: user deletion and bulk delete are denied, claim-based list filters answer 400, and a staff-giftee pass of the secrecy suite (with a permanent sensitivity test) proves it on every run.**

## What was built

- `GifterUserAdmin`: `has_delete_permission` is False (uniform 403 on every user delete URL, `delete_selected` gone from the list), and `lookup_allowed` refuses lookups whose first segment is a reverse relation of User (`claims__isnull`, `contributions=2`, ...), so those answer 400 while `is_staff__exact`, `groups__id__exact` and search keep working.
- SocialAccount and EmailAddress admins are view only (403 on add, change and delete; no bulk delete).
- `Claim.__str__` is "Claim <pk>" and `Contribution.__str__` is "Contribution <pk>" (gettext with placeholders, no migration; two new msgids for Phase 4).
- `StaffGifteeTests`: the staff giftee gets byte-identical responses with and without claims over 129+ probes (every route plus admin user, identity, group pages, bulk-delete POSTs on four lists, a filter probe per reverse relation, content-type shortcut for claim and contribution ids 1 to 8). `last_login` is removed at the source by disconnecting `update_last_login`, not masked.
- `manage.py delete_user USERNAME [--yes]`: dry run by default, prints username, display name and email only, discards `delete()`'s per-model counts, refuses the last active staff account with "Nobody was deleted.".
- DEPLOYMENT.md: Day-2 "Delete someone's account (data request)" with the pre-deletion copy removed after verification, the "removed or rotated" statement for older copies and backups, the shell-deletion warning, and updated admin and copy bullets.

## TDD record (RED evidence)

- Task 1 RED (commit 44fd54b), at HEAD the delete pages answered 200 and the bulk delete was offered. First failing assertion: `self.assertEqual(response.status_code, 403)` -> `AssertionError: 200 != 403` (for gita, carl, kim, sam, oscar), and `302 != 403` for the nonexistent id 999999 (the stock admin redirects a missing object to the index). The delete page lists "Claim: Lego set" style rows at HEAD, which is why the page was 200.
- Task 2 RED (commit 1c5c305), failing labels: snapshot test failed on `staff filter claims isnull GET`, `staff filter claims pk GET`, `staff filter contributions isnull GET`, `staff filter contributions pk GET` (four, one more than the plan's three: `?contributions=2` also narrows the list); `test_staff_pass_catches_a_reopened_admin_leak` failed on its lookup selection (`staff filter claims isnull GET`, `staff filter contributions isnull GET` reported before the patch); `test_claim_and_contribution_str_never_name_the_wish` failed for all 7 claims and 3 contributions. The delete half and the cascade invariant passed (Task 1 had denied delete).
- Task 3 RED (commit 591d7d6): all `DeleteUserCommandTests` errored with "Unknown command: 'delete_user'".

## D-15 note

Admin denials are Django's 403 with one body for every id, a nonexistent id included, so they offer no existence oracle. They are not an exception to D-15, which governs the claim, chip-in, release, purchased and got-it URLs and stays a uniform 404. The "uniform 404s, never 403" pattern in CONTEXT.md covers the app's own views, not the Django admin.

## Supersession of 01-07 WR-04

03-03 reverses 01-07's WR-04 admin-deletion must-have ("users, social accounts and email addresses viewable and deletable in the admin; deleting a user with a Google account still works") for SECR-01. Recorded in `01-REVIEW-DISPOSITION.md` (WR-04 Source cell, `updated` bumped). WR-04 stays `fixed`: SocialApp and SocialToken are still out of the admin. The old lockdown test that pinned admin deletion was replaced by `test_user_delete_is_refused_and_not_offered`.

## Deviations from Plan

**1. [Rule 1 - Bug in plan/test design] Sensitivity test patches all three admins' delete permission**
- **Found during:** Task 2 GREEN
- **Issue:** With `GifterUserAdmin.has_delete_permission` alone patched to True, Gita's and Sam's delete pages and the bulk POST did not differ with claims. Both fixture users (and, in the bulk POST, one of the selected users) have Google identity rows, and the identity admins now deny delete, so Django renders a plain "Cannot delete user" page naming only "social account" and "email address". That is a second protective layer the plan did not account for (the planner's probe predated Task 1). The plan's required "exactly those three labels" could not hold with a single patch.
- **Fix:** The delete half of the sensitivity test patches `has_delete_permission` to True on `GifterUserAdmin`, `ReadOnlySocialAccountAdmin` and `ReadOnlyEmailAddressAdmin` together (via `contextlib.ExitStack`), which is the real "admin deletion reopened" scenario, and then reports exactly Gita's page, Sam's page and the bulk POST. The explanatory comment is in the test.
- **Files modified:** gifter/tests/test_secrecy.py
- **Commit:** a7ca26a

**2. [Rule 2 - Missing coverage] Added `test_reverse_relation_filters_are_refused_and_builtin_filters_work`**
- Pins the behavior bullet that every reverse-relation filter answers 400 and the built-in filters and search answer 200 (the plan listed the behavior but only implied the test).
- **Commit:** a7ca26a

**3. [Minor] DEPLOYMENT.md snapshot method (plan_checker_must_fix)**
- Step 3 uses `sqlite3 <db> ".backup <copy>"` (online-consistent), with the stopped-container three-file copy as the alternative; the step 4 restore path covers both (for `.backup`: copy over `db.sqlite3` and delete the stale `-wal` and `-shm`). Step 5 removes the copy.

**4. [Minor] Extra assertion in delete_user tests**
- `test_output_prints_no_number_that_depends_on_the_data` additionally checks that the `--yes` output contains no digits (apart from the email), guarding the "no counts" prohibition.

## Verification

- `DEBUG=1 uv run python manage.py test`: 264 tests, OK (251 before).
- `makemigrations --check --dry-run`: No changes detected.
- `check --deploy --fail-level WARNING` with production-style env: no issues.
- `git diff --quiet 38eadd8 -- gifter/templates/gifter/privacy.html gifter/migrations pyproject.toml uv.lock`: exits 0.
- ruff is not installed in the environment, so lint/format was not run.

## Known Stubs

None.

## Threat Flags

None. delete_user is an operator CLI already covered by T-03-22, T-03-23, T-03-27.

## Issues Encountered

None beyond the deviation above.

## Self-Check: PASSED

- FOUND: gifter/management/commands/delete_user.py
- FOUND commits: 44fd54b, eb4a3b3, 1c5c305, a7ca26a, 591d7d6, 1a056f0
