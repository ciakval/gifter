---
phase: 05-secret-discussions
verified: 2026-11-14T11:26:11Z
status: human_needed
score: 11/11 must-haves verified
covered_files:
  - ".planning/phases/05-secret-discussions/05-01-PLAN.md"
  - ".planning/phases/05-secret-discussions/05-01-SUMMARY.md"
  - ".planning/phases/05-secret-discussions/05-02-PLAN.md"
  - ".planning/phases/05-secret-discussions/05-02-SUMMARY.md"
  - ".planning/phases/05-secret-discussions/05-03-PLAN.md"
  - ".planning/phases/05-secret-discussions/05-03-SUMMARY.md"
  - "DEPLOYMENT.md"
  - "gifter/discussion_views.py"
  - "gifter/discussions.py"
  - "gifter/forms.py"
  - "gifter/management/commands/delete_user.py"
  - "gifter/migrations/0005_discussions.py"
  - "gifter/models.py"
  - "gifter/templates/gifter/discussion.html"
  - "gifter/templates/gifter/event_detail.html"
  - "gifter/templates/gifter/includes/member_wish.html"
  - "gifter/templates/gifter/privacy.html"
  - "gifter/tests/helpers.py"
  - "gifter/tests/test_discussions.py"
  - "gifter/tests/test_i18n.py"
  - "gifter/tests/test_lockdown.py"
  - "gifter/tests/test_phone.py"
  - "gifter/tests/test_privacy.py"
  - "gifter/tests/test_secrecy.py"
  - "gifter/urls.py"
  - "gifter/views.py"
  - "locale/cs/LC_MESSAGES/django.mo"
  - "locale/cs/LC_MESSAGES/django.po"
covered_digest: "v4:sha256:bf9e457d71e58f1afcfb60634cf6477a3290e244e7e03c1449603d83b77bec11"
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Czech copy review of the new Phase 5 strings: thread page labels, 'Diskuse' / 'Diskuse o této osobě' headings, 'Nové od tvé poslední návštěvy' / 'Nové' markers, plural counts (1 komentář / 2 komentáře / 5 komentářů), 'Komentář byl smazán.', and the three Discussions paragraphs in the Czech privacy policy"
    expected: "A Czech-speaking relative reads each string and finds it natural and correctly toned; plural forms read correctly for 1, 2-4 and 5+"
    why_human: "Translation naturalness and tone cannot be checked by grep; the catalogue only proves the msgids are translated and the plural forms are complete"
  - test: "End-of-phase UAT on production after the deploy, with two family members (B, C) and the giftee A, each on their own phone (from 05-03-PLAN.md human-check). (1) B opens one of A's wish cards on the event page, taps Discuss and posts 'test ahoj'. (2) C opens the event page: that wish card shows 'New since your last visit' and 'Discussion (1 comment)'; C taps it, reads the comment, goes back: the marker is gone. (3) A opens the event page and My wishlist: nothing anywhere mentions a discussion; A types B's thread address into the browser: Gifter shows its normal Not Found page. (4) B posts in 'Discussion about this person' on A's card; A's pages still show nothing. (5) B deletes their own comment; C cannot delete it. (6) Switch to Czech: labels read naturally, '1 komentář / 2 komentáře / 5 komentářů'. (7) Open /privacy/ and read the Discussions section in both languages. Report each step as passed or failed."
    expected: "All seven steps pass on real phones against gifter.remesh.cz"
    why_human: "Real phones, production deployment, and a real giftee's view cannot be exercised from the codebase; nothing is deployed yet, so this is a post-deploy step, not a gap"
---

# Phase 5: Secret Discussions Verification Report

**Phase Goal:** Givers in an event can talk about a giftee's wishes, and about the giftee in general, without the giftee ever knowing the conversations exist.
**Verified:** 2026-11-14T11:26:11Z
**Status:** human_needed
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths

Roadmap success criteria (SC1-SC5) are the contract. Plan-level truths from 05-01, 05-02 and 05-03 are merged in and deduplicated.

| #  | Truth | Status | Evidence |
| -- | ----- | ------ | -------- |
| 1  | SC1: Every member except the wish owner can read and post on a wish; the thread is per (wish, event) | ✓ VERIFIED | `discussions.py` `_find_thread` / `_post` key on `(event, wish)`; `models.py` `Thread` has `unique_wish_thread_per_event`. `discussion_views.wish_discussion` gates via `claim_views._participant_wish_or_404` (membership, `events=event`, ACTIVE, owner is member, `.exclude(owner=user)`). Tests: `DiscussionTracerTests`, `OneThreadPerEventTests.test_the_same_wish_has_separate_threads_in_two_events`, `GateMatrixTests.test_wish_route_gates` all pass. |
| 2  | SC2: Every member except the giftee can read and post in a discussion about that giftee, including when the giftee has no wishes | ✓ VERIFIED | `discussion_views.member_discussion` looks the person up among event members with `.exclude(pk=request.user.pk)`, so the giftee gets the same 404 as a missing id. No wish requirement. Tests: `MemberThreadTests` (incl. `test_a_person_with_no_wishes_still_has_a_thread`) and `GateMatrixTests.test_member_route_gates` pass. |
| 3  | SC3: "New since your last visit" marker on wish cards and giftee sections; opening clears it; a viewer's own comments never mark anything new | ✓ VERIFIED | `discussions._read` upserts the viewer's own `ThreadVisit` after the gate and sets `CommentView.is_new` only for others' comments newer than `last_seen_at`. `summaries_for` mirrors this for the event page (`ThreadSummary.new`). Behavioral tests exercise the transition: `MarkerTests.test_opening_clears_the_marker_and_new_comments_bring_it_back`, `MarkerTests.test_own_comments_never_mark_anything_new_for_the_author`, `ThreadVisitRuleTests.test_first_open_creates_one_row_and_second_updates_it` all pass. |
| 4  | SC3 (cont.): No notifications and no emails of any kind | ✓ VERIFIED | Grep of `discussions.py`, `discussion_views.py`, `views.py` and the discussion templates finds no mail, EmailMessage or notification code. The privacy copy states the same. |
| 5  | SC4: An author can delete their own comment; nobody can edit a comment | ✓ VERIFIED | `discussions.delete_comment` filters `author=user`; `discussion_views.comment_delete` is `@require_POST` and raises the same bare 404 for missing, foreign and giftee cases. `models.Comment` has no `updated_at`. `urls.py` has no edit route. Tests: `CommentDeleteTests` (incl. `test_nothing_can_edit_a_comment`, `test_everyone_else_gets_the_missing_comment_404_and_nothing_is_deleted`) pass. |
| 6  | SC5: The giftee cannot learn a thread or comment exists, through any page, count, marker, URL, POST response or admin view, including giftee-as-giver and staff giftee | ✓ VERIFIED | Gate-before-read in every public function; `summaries_for` excludes `giftee=viewer` in the query; `Thread`/`Comment`/`ThreadVisit` use `related_name="+"`; admin does not register them (`test_discussion_models_are_not_registered_in_the_admin`); user admin has `has_delete_permission` False, so the cascade confirmation page the giftee could otherwise reach is closed. `DiscussionUniformNotFoundTests` (30+ requests, identical 404 bodies, rows unchanged), `GifteeAsGiverTests`, `StaffGifteeTests`, `SentinelCrawlTests`, `ByteIdenticalTests` and the Czech subclasses all pass. Ran 221 targeted tests: OK. |
| 7  | Event page shows a discussion link on other members' wish cards and one per other member; never on the viewer's own wishes or a card about the viewer | ✓ VERIFIED | `event_detail.html` includes `member_wish.html` only inside `member_cards`, which exclude `request.user`. `owner_wish.html` contains no discussion markup. Tests: `EventPageLinkTests.test_links_for_others_never_for_oneself`, `test_the_owner_sees_nothing_about_her_own_wish_or_herself`. |
| 8  | Event-page summaries never include a thread about the viewer (D-05) | ✓ VERIFIED | `discussions.summaries_for` line `.exclude(giftee=viewer)` runs before any comment is loaded. Test: `SummariesForTests.test_a_thread_about_the_viewer_is_absent`, `test_query_budget_and_no_body_column`. |
| 9  | Owner pages never query discussion tables; the 404 gate answers before any discussion read | ✓ VERIFIED | `DiscussionOwnerQueryTests.test_owner_pages_and_refused_discussion_requests_never_query_discussion_tables` captures queries for owner pages and refused discussion requests. `wish_discussion` calls the gate before `read()` (the 05-03 SUMMARY reports that reordering this call is caught by that test; I did not re-run the mutant). |
| 10 | The migration only creates tables and their constraints; nothing existing is altered | ✓ VERIFIED | `migrations/0005_discussions.py` contains three `CreateModel` and three `AddConstraint` operations on `thread` and `threadvisit` only. `makemigrations --check --dry-run` reports "No changes detected". Test: `DiscussionTracerTests.test_the_migration_only_creates_tables_and_their_constraints`. |
| 11 | delete_user removes a person's comments, discussions about them and their read receipts, with output that never depends on discussions (D-07); privacy policy (EN and CS) describes discussions and PRIVACY_POLICY_UPDATED is bumped (D-06) | ✓ VERIFIED | `delete_user.py` relies on the CASCADE chain (`Thread.giftee`, `Thread.wish`, `Comment.author`, `ThreadVisit.user`); tests `test_yes_deletes_comments_discussions_and_read_receipts`, `test_dry_run_keeps_every_comment` in `test_lockdown.py` pass. `privacy.html` has the Discussions section (three paragraphs); `views.PRIVACY_POLICY_UPDATED = 2026-11-14`; `test_privacy.py` and `test_i18n.py` pass. Czech wording quality is a human item (see below). |

**Score:** 11/11 truths verified (0 behavior-unverified, 0 failed)

### Behavior-dependent truths

Truths 3, 5, 6 and 9 are state transitions or ordering invariants. Each one has a named passing test that exercises the transition (see the Evidence column), so none is downgraded to PRESENT_BEHAVIOR_UNVERIFIED.

### Deferred Items

None. No later milestone phase addresses any of these items.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `gifter/models.py` | Thread, Comment, ThreadVisit with hidden relations | ✓ VERIFIED | All three present, all FKs `related_name="+"`, conditional unique constraints in `Meta`. |
| `gifter/migrations/0005_discussions.py` | Additive migration | ✓ VERIFIED | Only new tables and constraints. |
| `gifter/discussions.py` | Sole reader/writer; refuses giftee; summaries | ✓ VERIFIED | 163 lines. Every public function gated; `CommentView`, `ThreadSummary`, `Summaries`, `summaries_for`, `delete_comment`, `read_*` and `post_*`. |
| `gifter/discussion_views.py` | wish_discussion, member_discussion, comment_delete | ✓ VERIFIED | Wired in `urls.py` (`wish_discussion`, `member_discussion`, `comment_delete`). |
| `gifter/views.py` `event_detail` | Attaches summaries to cards | ✓ VERIFIED | Calls `summaries_for(request.user, event)`; attaches `discussion` to each item and member card. |
| `gifter/templates/gifter/discussion.html` | One thread page for both kinds | ✓ VERIFIED | Renders comments with escaped body, delete form only for `is_mine`, POST form. |
| `gifter/templates/gifter/includes/member_wish.html` | Discuss link and marker | ✓ VERIFIED | Included only from the participant event page. |
| `gifter/templates/gifter/event_detail.html` | Per-member discussion footer | ✓ VERIFIED | Footer link per other member with count and marker. |
| `gifter/templates/gifter/privacy.html` | Discussions section | ✓ VERIFIED | Three paragraphs, translated (EN and CS). |
| `gifter/management/commands/delete_user.py` | Removes discussion data via cascade; silent about it | ✓ VERIFIED | Help text and comment updated; output unchanged. |
| `gifter/tests/test_secrecy.py`, `helpers.py` | Discussion data in fixture; detectors and mutant | ✓ VERIFIED | `add_discussions` called from `add_claims`; `DISCUSSION_MARKERS` folded into `claim_state_markers`; `test_detectors_catch_injected_comment_leak` present. |
| `locale/cs/LC_MESSAGES/django.po` / `.mo` | Czech strings with three plural forms | ✓ VERIFIED | `nplurals=3`; `Discussion (%(counter)s comment)` and `Discussion about this person (...)` each have three msgstr forms. `scripts/check-translations.sh` prints TRANSLATIONS OK. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `discussion_views.py` | `claim_views._participant_wish_or_404` | Import and call before any read or write | ✓ WIRED | Wish threads share the claim gate and its bare 404. |
| `discussion_views.py` | `discussions.py` | Every read and write through the chokepoint | ✓ WIRED | No model query for discussion data in the views. |
| `member_wish.html` | `wish_discussion` URL | `{% url 'wish_discussion' ... %}` | ✓ WIRED | Link on other members' cards only. |
| `event_detail.html` | `member_discussion` URL | `{% url 'member_discussion' ... %}` | ✓ WIRED | One footer per other member. |
| `views.event_detail` | `discussions.summaries_for` | Call with `request.user` and `event` | ✓ WIRED | Summaries attached to every card. |
| `discussion.html` | `comment_delete` URL | POST form on `is_mine` comments with same-site `next` | ✓ WIRED | `_back` in `claim_views` rejects external `next`. |
| `test_secrecy.add_claims` | `test_secrecy.add_discussions` | Direct call | ✓ WIRED | Every detector carries discussion data. |
| `delete_user` | `Thread`, `Comment`, `ThreadVisit` | CASCADE via `user.delete()` | ✓ WIRED | Tested in `test_lockdown.py`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `discussion.html` | `comments` | `discussions._read` → `Comment.objects.filter(thread=...)` | Yes | ✓ FLOWING |
| `event_detail.html` member footer | `card.discussion` | `summaries_for` → `Thread`/`Comment`/`ThreadVisit` queries | Yes | ✓ FLOWING |
| `member_wish.html` count and marker | `discussion` | `summaries.wishes` from `summaries_for` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Discussion, secrecy, lockdown, privacy, i18n and phone suites | `DEBUG=1 uv run python manage.py test gifter.tests.test_discussions gifter.tests.test_secrecy gifter.tests.test_lockdown gifter.tests.test_privacy gifter.tests.test_i18n gifter.tests.test_phone` | Ran 221 tests, OK | ✓ PASS |
| Migration is in sync with models | `DEBUG=1 uv run python manage.py makemigrations --check --dry-run` | No changes detected | ✓ PASS |
| Czech catalogue gate | `bash scripts/check-translations.sh` | TRANSLATIONS OK | ✓ PASS |

The orchestrator's full-suite run (415 tests OK) was not repeated here. The targeted run above covers every module this phase changed.

### Probe Execution

Not applicable. Phase 5 is a feature phase and declares no `scripts/*/tests/probe-*.sh` probes.

### Requirements Coverage

Requirement IDs taken from PLAN frontmatter (05-01: DISC-01, DISC-02; 05-02: DISC-03; 05-03: DISC-04) and cross-checked against `.planning/REQUIREMENTS.md`. REQUIREMENTS.md maps DISC-01 to DISC-04 to Phase 5 and nothing else. No orphaned IDs and no unclaimed IDs.

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| DISC-01 | 05-01 | Every event member except the wish's owner can read and post comments on a wish, in a thread for that wish within that event | ✓ SATISFIED | Truths 1 and 9; `Thread` unique per (event, wish); `DiscussionTracerTests`, `OneThreadPerEventTests`, `GateMatrixTests` pass. |
| DISC-02 | 05-01 | Every event member except the giftee can read and post in a discussion about that giftee within the event | ✓ SATISFIED | Truth 2; `MemberThreadTests`, `GateMatrixTests.test_member_route_gates` pass. |
| DISC-03 | 05-02 | "New since your last visit" marker, no notifications; authors delete own comments, nobody edits | ✓ SATISFIED | Truths 3, 4, 5; `MarkerTests`, `ThreadVisitRuleTests`, `CommentDeleteTests` pass. |
| DISC-04 | 05-03 | Automated tests prove the giftee cannot learn a thread or comment exists (pages, counts, markers, URLs, POST responses, admin; giftee-as-giver; staff giftee) | ✓ SATISFIED | Truth 6; `test_secrecy.py` discussion classes pass in English and Czech, including `DiscussionUniformNotFoundTests`, `GifteeAsGiverTests`, `StaffGifteeTests`, and the injected comment-leak mutant. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `gifter/discussion_views.py` | `_thread_page` redirect | POST response anchors on the global `Comment.pk` (`redirect(f"{thread_url}#comment-{pk}")`), and the author's delete URL embeds it | ℹ️ Info | Weak side channel: a giftee who posts can infer that other comments were created elsewhere in the database between her posts, from gaps in global pks. It does not reveal that a comment about her exists, and no test covers it. Optional hardening: use a per-thread ordinal in the anchor. Not a gap under DISC-04 as written. |
| `gifter/discussions.py` | `_post` | `get_or_create` race on unique constraints | ℹ️ Info | Django's `get_or_create` retries on `IntegrityError`, so a concurrent first comment does not 500. Noted only. |

No debt markers (TBD, FIXME, XXX, TODO, HACK, PLACEHOLDER) in any phase file. No stub returns in `discussions.py` or `discussion_views.py`.

### Human Verification Required

1. **Czech copy review.** See the frontmatter item. Automated checks prove that the msgids are translated and the plural forms are complete, but not that the wording is natural. The nine new Czech strings and the Discussions privacy paragraphs need a Czech-speaking relative to read them.
2. **End-of-phase production UAT (05-03 human-check).** See the frontmatter item. It needs the deploy first. Nothing has been deployed yet, which is expected, so this is not a gap.

### Warnings

- **MVP framing not applied (WARNING, human decision requested).** ROADMAP.md marks Phase 5 `mode: mvp`, but the goal "Givers in an event can talk about..." is not in User Story format. `query user-story.validate` returns `valid: false`. The verifier spec says to refuse verification in this case and ask for `/gsd-mvp-phase`. This report does not refuse, for two reasons: the orchestrator asked for a report, and phases 2 and 3 (also `mode: mvp`, with non-User-Story goals) were verified with the standard goal-backward method and no "User Flow Coverage" section. Decision needed: either accept standard verification for this project's MVP-mode phases, or reformat the goal with `/gsd-mvp-phase` before a future verification. The goal-backward result above does not depend on the answer.

### Gaps Summary

No blocking gaps. All 11 truths are VERIFIED, all four requirement IDs are satisfied, and every artifact is present, substantive and wired. Status is `human_needed` because of the two human items and because the MVP framing decision is open.

---

_Verified: 2026-11-14T11:26:11Z_
_Verifier: Claude (gsd-verifier)_
