---
phase: 05-secret-discussions
plan: 02
subsystem: discussions
tags: [django, secrecy, i18n, privacy-policy, read-receipts]
status: complete

requires:
  - phase: 05-secret-discussions
    provides: Thread, Comment, ThreadVisit models and the gifter/discussions.py chokepoint (05-01)
provides:
  - Read receipt (ThreadVisit upsert) when a gated viewer opens a thread
  - summaries_for(viewer, event) with per-card count and "new since your last visit" marker
  - comment_delete (author only, uniform 404), no edit path
  - Discussions section in the privacy policy (EN and CS), bumped PRIVACY_POLICY_UPDATED
  - Czech strings for markers, plural counts, delete flash and the policy
affects: [05-03]

actuals:
  tokens: 30000
  tasks: 3
  commits: 3
plan_head_before: acce08dd9191d280b31daec3e138c2e7c76abded
plan_head_after: fda30ac88115d5d26c22ad8944052edbb1ddcb3b

key-files:
  created: []
  modified:
    - gifter/discussions.py
    - gifter/discussion_views.py
    - gifter/views.py
    - gifter/urls.py
    - gifter/templates/gifter/discussion.html
    - gifter/templates/gifter/includes/member_wish.html
    - gifter/templates/gifter/event_detail.html
    - gifter/templates/gifter/privacy.html
    - gifter/tests/test_discussions.py
    - gifter/tests/test_secrecy.py
    - gifter/tests/test_privacy.py
    - gifter/tests/test_i18n.py
    - locale/cs/LC_MESSAGES/django.po
    - locale/cs/LC_MESSAGES/django.mo

key-decisions:
  - "The read receipt is written inside _read, after the view gate and after the giftee refusal, only for the viewer's own ThreadVisit row; reading an empty thread writes nothing"
  - "summaries_for excludes threads about the viewer in the query itself and never selects the comment body; at most 3 queries"
  - "Comments are hard-deleted; a thread left empty shows no count and no marker (P-07)"
  - "A viewer re-rendering the thread after an invalid POST also records their own receipt (the page is the thread), which is the viewer's own row only"

requirements-completed: [DISC-03]
---

# Phase 5 Plan 02: Markers, Delete and Privacy Policy Summary

Event-page cards show a comment count and a "New since your last visit" badge computed per viewer (never for threads about the viewer), opening a thread clears it, authors can delete their own comments, and the privacy policy describes discussions in English and Czech.

## Accomplishments

- `_read` records a `ThreadVisit` upsert after the gate and marks `CommentView.is_new` for comments by others written after the previous visit (all of them on a first visit). It is the one write on a GET in the app (P-05), documented in the module docstring and pinned by tests: 404 gate failures, empty threads and plain POSTs create no visit.
- `summaries_for` builds `Summaries(wishes, members)` of frozen `ThreadSummary(count, new)`; exactly 1 query with no threads, at most 3 otherwise; the thread about the viewer is excluded before anything is loaded.
- `event_detail` attaches a summary to every other-member card and wish; templates show "Discussion (N comments)" / "Discussion about this person (N comments)" with `blocktranslate count`, plus the badge. A per-comment "New" badge appears on the thread page.
- `comment_delete` (POST only, `comments/<pk>/delete/`): author deletes, flash "Comment deleted.", same-site `next` else the events list; missing, foreign and giftee attempts return the identical bare 404. No edit route, no `updated_at` field. Two probes added to the secrecy route guard.
- Privacy page: new "Discussions" section (three paragraphs) in English and Czech; `PRIVACY_POLICY_UPDATED` is 2026-11-14 and the committed date gate exits 0.
- Czech catalogue: markers, two plural entries with three forms each, delete flash, section heading and the three policy paragraphs. Catalogue diff kept to the new entries (makemessages noise reverted by hand).

## Verification

- Full suite `DEBUG=1 uv run python manage.py test -v 1`: 388 tests, OK.
- `makemigrations --check --dry-run`: No changes detected (no model change in this plan).
- `bash scripts/check-translations.sh`: TRANSLATIONS OK.
- Privacy date gate after the Task 3 commit: exit 0.

## Task Commits

1. Task 1 (tracer: read receipt, summaries, markers, counts): a1eec13
2. Task 2 (comment_delete, no edit, route probes): 7623516
3. Task 3 (privacy policy, Czech plural tests, catalogue): fda30ac

## Deviations from Plan

None - plan executed as written. Two minor choices: the "Delete" msgid gained a `discussion.html` location in the catalogue (unavoidable, accurate); and the test for an invalid POST asserts only that the other viewer's (carol's) receipt is untouched, because the invalid POST re-renders the thread for its own author, who legitimately records their own receipt.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model (T-05-05 to T-05-09 mitigated and tested).

## Notes for the family check

A Czech-speaking relative should read the new copy: "Nové od tvé poslední návštěvy", "Nové", "Diskuse (N komentář/komentáře/komentářů)", "Diskuse o této osobě (N ...)", "Komentář byl smazán." and the three new privacy paragraphs under "Diskuse". Do not deploy after this plan alone; 05-03 (exhaustive secrecy suite and delete_user) is still part of the phase promise.

## Self-Check: PASSED

Commits a1eec13, 7623516, fda30ac verified in history; full suite and catalogue gate green.
