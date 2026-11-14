---
phase: 05-secret-discussions
plan: 01
subsystem: discussions
tags: [django, secrecy, i18n, threads]
status: complete

requires:
  - phase: 03-claims
    provides: SecrecyViolation, _participant_wish_or_404 gate, hidden-relation device
provides:
  - Thread, Comment, ThreadVisit tables (additive migration 0005)
  - gifter/discussions.py chokepoint (wish and member threads)
  - wish_discussion and member_discussion pages, event page links
  - Czech strings for the nine new msgids
affects: [05-02, 05-03]

actuals:
  tokens: 30000
  tasks: 3
  commits: 3
plan_head_before: 3a9ae4157380a1666577258aaf22863de769f746
plan_head_after: a32a4bd2f22c6bd5c9361b260df144eed39602e3

key-files:
  created:
    - gifter/discussions.py
    - gifter/discussion_views.py
    - gifter/migrations/0005_discussions.py
    - gifter/templates/gifter/discussion.html
    - gifter/tests/test_discussions.py
  modified:
    - gifter/models.py
    - gifter/forms.py
    - gifter/urls.py
    - gifter/templates/gifter/event_detail.html
    - gifter/templates/gifter/includes/member_wish.html
    - gifter/tests/test_secrecy.py
    - gifter/tests/test_phone.py
    - locale/cs/LC_MESSAGES/django.po
    - locale/cs/LC_MESSAGES/django.mo

key-decisions:
  - "All three new models use related_name '+' so Wish, Event and User have no accessor to threads or comments"
  - "One shared private view helper renders both thread kinds so they cannot drift"
  - "Wish threads reuse _participant_wish_or_404; member threads exclude the viewer in the user lookup so own id, non-member id and missing id share one bare 404"

requirements-completed: [DISC-01, DISC-02]
---

# Phase 5 Plan 01: Secret Discussions Summary

Per-event private threads about a wish (DISC-01) and about a person (DISC-02), on dedicated pages reached from the event page; the wish owner and the person get the same bare 404 as a stranger, on GET and POST, with nothing written.

## Accomplishments

- Models `Thread` (event, nullable wish, giftee; unique per (event, wish) and per (event, giftee) when wish is null), `Comment` (no updated_at, no edit path), `ThreadVisit` (unused until 05-02). Migration 0005 only creates tables and their constraints.
- `gifter/discussions.py` is the only reader/writer; every public function raises `SecrecyViolation` (imported from `gifter.claims`) when the viewer is the giftee. Templates get `CommentView` dataclasses. Reading never creates a Thread; posting uses `get_or_create`.
- `wish_discussion` and `member_discussion` views; "Discuss" button on other members' wish cards and a card footer "Discussion about this person" per other member. Own wishes and the viewer never get a link.
- Comment form: plain text, 1 to 1000 chars, stripped, CRLF normalised, rendered escaped with line breaks.
- Secrecy route guard probes for both routes (own, self and co-member, GET and POST); `discussion.html` added to the phone stacking-group check.
- Nine Czech strings translated; `scripts/check-translations.sh` prints TRANSLATIONS OK.

## Verification

- Full suite: `DEBUG=1 uv run python manage.py test -v 1`: 363 tests, OK (secrecy suite in English and Czech included).
- `makemigrations --check --dry-run`: no changes.
- `bash scripts/check-translations.sh`: TRANSLATIONS OK.

## Task Commits

1. Task 1 (tracer: models, migration, chokepoint, view, template, link): 9bb6705
2. Task 2 (member thread tests, gate matrix, route probes): 2241fe1
3. Task 3 (validation/Czech tests, phone group, catalogue): a32a4bd

## Deviations from Plan

**1. [Rule 3 - Blocking] Migration contains AddConstraint operations**
- **Issue:** The plan expected only three `CreateModel` operations; Django 6.1 emits the three conditional unique constraints as separate `AddConstraint` operations on the new tables.
- **Fix:** Kept the generated migration (still purely additive, touches only the new tables). The additive-migration test accepts `CreateModel` and `AddConstraint` on `thread`/`threadvisit` and asserts exactly three `CreateModel`.
- **Files modified:** gifter/tests/test_discussions.py

**2. [Ordering] Member thread view, URL and event-page footer landed in the Task 1 commit**
- They were written together with the shared view helper. Task 2 added their tests and probes. Between commits 9bb6705 and 2241fe1 the secrecy route guard had no probe for the new routes (green again from 2241fe1).

**3. [Housekeeping] makemessages noise reverted**
- makemessages added two `gifter/tests/test_secrecy.py` location lines and rewrapped one existing Czech paragraph; both were reverted by hand so the catalogue diff contains only the nine new entries plus the POT-Creation-Date header.

Commits were made on `main` (protected-branch guard reports true) as the dispatch stated (branching_strategy=none, sequential executor).

## Known Stubs

None. `ThreadVisit` is created but intentionally unused until 05-02.

## Threat Flags

None beyond the plan's threat model (T-05-01 to T-05-04 all mitigated and tested).

## Notes for the family check

A Czech-speaking relative should read the nine new Czech strings (Diskutovat, Diskuse, "Diskuse o této osobě", "Diskuse: %(name)s", "%(name)s tuhle diskusi nikdy neuvidí.", "Zpět na událost", "Zatím tu nejsou žádné komentáře. Začni diskusi.", "Tvůj komentář", "Přidat komentář"). Do not push or deploy after this plan alone: 05-02 (privacy policy) and 05-03 (exhaustive secrecy suite) are part of the promise.

## Self-Check: PASSED

Files and commits 9bb6705, 2241fe1, a32a4bd verified present; full suite green.
