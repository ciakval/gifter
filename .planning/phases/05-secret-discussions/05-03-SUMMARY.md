---
phase: 05-secret-discussions
plan: 03
subsystem: discussions
tags: [django, secrecy, tests, i18n, delete-user]
status: complete

requires:
  - phase: 05-secret-discussions
    provides: Thread, Comment, ThreadVisit, discussions chokepoint, markers, delete (05-01, 05-02)
provides:
  - Discussion data in the secrecy suite fixture and add_claims, so every detector covers it
  - Discussion markers (English, Czech, stems) checked in the giftee's own-wish regions
  - Comment-leak mutant that the snapshot, sentinel and region detectors must catch on every run
  - Uniform-404 matrix, giftee-as-giver, gate-before-read, chokepoint and staff/admin checks (English and Czech)
  - delete_user coverage and docs for comments, discussions and read receipts
affects: []

actuals:
  tokens: 32000
  tasks: 3
  commits: 3
plan_head_before: 8d312e58032de0ad757e6c456e39f02618b403a7
plan_head_after: c6b1048b0d1bce9880539c7b041d0eccf05220ef

key-files:
  created: []
  modified:
    - gifter/tests/helpers.py
    - gifter/tests/test_secrecy.py
    - gifter/tests/test_lockdown.py
    - gifter/management/commands/delete_user.py
    - DEPLOYMENT.md

key-decisions:
  - "Discussions about Gita are created by add_claims (via add_discussions); only the co-member threads she may legitimately see (on Carl's wish and about Carl) live in Fixture.__init__, so they exist on both sides of every comparison"
  - "claim_state_markers() now also returns discussion markers, so existing region checks cover discussions without a second code path; czech_claim_state_markers() and CLAIM_STATE_MSGIDS are untouched"
  - "Staff filter probes for thread, comment and threadvisit are explicit, because their hidden relations are not listed in User._meta.related_objects"

requirements-completed: [DISC-04]
---

# Phase 5 Plan 03: Secrecy Proof and delete_user Summary

The secrecy suite now carries discussion data: with threads and comments about Gita and her wishes present (sentinel in comment bodies and a sentinel-named author), every page she or a staff Gita can open is byte-identical, sentinel-free and marker-free in English and Czech. No production code needed changing.

## Accomplishments

- **Fixture and detectors:** `add_discussions(fx)` creates threads on all of Gita's wishes (both events, received and withdrawn included), member threads about her in both events, an unrelated thread in a foreign event, comments by Carl, Kim and the sentinel user Sam, and read receipts. `add_claims` calls it, so the sentinel crawl, byte-identical snapshots, region check and staff pass cover it. Base-state co-member threads (on Carl's wish and about Carl) are in `Fixture.__init__`.
- **Markers:** `DISCUSSION_MARKERS`, `DISCUSSION_MSGIDS`, `DISCUSSION_STEMS_CS`, `czech_discussion_markers()` in helpers; `claim_state_markers` returns them too.
- **Self-sensitivity:** `leaked_comments` context processor, `LEAKED_COMMENT_FRAGMENT`, generalized `mutant_templates`, and `test_detectors_catch_injected_comment_leak` (all three detectors report both pages under the mutant and nothing afterwards; Czech subclass reruns it).
- **Giftee in every role:** `DiscussionUniformNotFoundTests` (every discussion URL, GET and POST, for Gita and an outsider gets the same 404; Thread, Comment and ThreadVisit rows including `last_seen_at` unchanged afterwards), `GifteeAsGiverTests` (she can read and post on others' threads, her own stay a bare 404, no flash after a refused POST, wishlist identical after she posts, no thread URL or marker on her event page), `DiscussionOwnerQueryTests` (owner pages and the eight refused discussion probes never touch the three discussion tables), `DiscussionChokepointTests` (chokepoint refusals write nothing, `summaries_for` holds only her legitimate view, `str()` of rows leaks nothing, models unregistered in the admin).
- **Staff giftee:** the cascade invariant now includes Thread, Comment and ThreadVisit; three extra user-list filter probes and content-type shortcut probes for the three models are compared byte for byte.
- **delete_user (D-07):** help text and comment say comments, discussions and read receipts are removed; output unchanged. New tests: `test_yes_deletes_comments_discussions_and_read_receipts`, `test_dry_run_keeps_every_comment`; the existing output-identity tests now run with discussion data.
- **DEPLOYMENT.md:** data-request paragraph, admin, `/privacy/` and secrecy-test bullets updated; new bullet for the read receipt as the only write on a GET.

## Sensitivity checks (done by hand, reverted)

| Mutation | Failing tests |
|----------|---------------|
| (a) remove `.exclude(giftee=viewer)` in `summaries_for` | `DiscussionChokepointTests.test_summaries_hold_only_her_legitimate_view` (and its Czech twin) |
| (b) drop `.exclude(pk=request.user.pk)` in `member_discussion` | `DiscussionUniformNotFoundTests` (all four self-thread requests) plus `ByteIdenticalTests` and `StaffGifteeTests` on the `member_discussion ... self` probes, English and Czech |
| (c) read `Thread` before the gate in `wish_discussion` | `DiscussionOwnerQueryTests` on the four `wish_discussion ... own` probes |

All three production files were restored with `git checkout`; the final diff touches no production code except the `delete_user` help text and comment.

## Verification

- Full suite `DEBUG=1 uv run python manage.py test -v 1`: 415 tests, OK.
- `makemigrations --check --dry-run`: No changes detected.
- `bash scripts/check-translations.sh`: TRANSLATIONS OK.
- `scripts/container-smoke.sh` not run (needs Docker); the CI test and build jobs are the gate.
- The human UAT in the plan (two family members and the giftee on production phones) is left for after the deploy.

## Task Commits

1. Task 1 (tracer: discussion data, markers, comment-leak mutant): 1cb283b
2. Task 2 (uniform-404 matrix, giftee-as-giver, query, chokepoint, staff and Czech): 220f3b3
3. Task 3 (delete_user, lockdown tests, DEPLOYMENT.md): c6b1048

## Deviations from Plan

None - plan executed as written. The extended suite found no real leak, so no production fix was made (P-09 not triggered). Minor choices: `DiscussionDataTests` has two tests that do not run in Czech (they assert data, not rendering); the plan's `makemessages` was not needed (no new strings).

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model (T-05-10 to T-05-14 mitigated and tested).

## Notes

Phase 5 is ready for verification and deploy; run the human UAT from the plan's Task 3 after the deploy.

## Self-Check: PASSED

Commits 1cb283b, 220f3b3 and c6b1048 are present in history; full suite, migration check and catalogue gate green.
