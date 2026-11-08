---
phase: 02-events-wishlists-browsing
verified: 2026-11-08T21:00:00Z
status: human_needed
score: 5/5 must-haves verified
covered_files:
  - ".planning/phases/02-events-wishlists-browsing/02-01-PLAN.md"
  - ".planning/phases/02-events-wishlists-browsing/02-01-SUMMARY.md"
  - ".planning/phases/02-events-wishlists-browsing/02-02-PLAN.md"
  - ".planning/phases/02-events-wishlists-browsing/02-02-SUMMARY.md"
  - "gifter/forms.py"
  - "gifter/migrations/0002_event_membership.py"
  - "gifter/migrations/0003_wish_owner_status_sharing.py"
  - "gifter/models.py"
  - "gifter/templates/gifter/event_detail.html"
  - "gifter/templates/gifter/includes/member_wish.html"
  - "gifter/templates/gifter/includes/owner_wish.html"
  - "gifter/templates/gifter/invite.html"
  - "gifter/templates/gifter/privacy.html"
  - "gifter/tests/test_events.py"
  - "gifter/tests/test_privacy.py"
  - "gifter/tests/test_wishes.py"
  - "gifter/urls.py"
  - "gifter/views.py"
  - "scripts/smoke.sh"
covered_digest: "v4:sha256:9ce506c0e50ed376aff974f4bd8b78a26018a13892f89f5a4beaca2d885cf4c0"
behavior_unverified: 1
overrides_applied: 0
behavior_unverified_items:
  - truth: "[WISH-02 · concurrency] The edit save writes only name, description, priority, links and updated_at (update_fields), never status, so a delete racing an edit can never bring a withdrawn wish back (verification: backstop)"
    test: "Open a wish's edit page in two tabs, delete the wish in one, then submit the edit in the other"
    expected: "The edit is refused (404) and the wish stays deleted; it never reappears on My wishlist or in any event"
    why_human: "Code uses save(update_fields=[...]) without status, and test_edit_never_writes_status passes, but that test deletes BEFORE the edit POST (it exercises the 404 path), not the window between the form's wish lookup and the save. Presence of update_fields is not behavioral proof of a true race."
human_verification:
  - test: "Signed-out relative on a real phone opens an invite link (e.g. from a family chat), signs in with Google, and lands back on the confirm page"
    expected: "After Google sign-in the browser shows 'You are invited to <event>' with a Join button; nothing joined until Join is pressed. If next is lost, the first visit to /events/ forwards once to the confirm page."
    why_human: "Needs live Google OAuth on https://gifter.remesh.cz and a real phone. Local tests prove the mocked sign-in round trip and the session fallback only. Phase 2 is not yet pushed or deployed (production still at 1a47ff0)."
  - test: "Paste an invite link into Messenger/WhatsApp and let the chat app render a link preview, without anyone tapping it"
    expected: "Preview shows no event name, and no membership is created for anybody"
    why_human: "Real chat-app preview bots cannot be run locally. Tests prove anonymous GET (including bot user-agents) redirects to sign-in with no event details and joins nobody."
  - test: "Deploy Phase 2 and run scripts/smoke.sh against the live site"
    expected: "New smoke checks (/events/1/ and /invite/<token>/ signed out redirect to landing) pass live; migrations 0002 and 0003 apply cleanly on the production SQLite"
    why_human: "Phase 2 exists only on local main; deployment is a separate step. Container smoke (local) already proved migrations apply on a fresh DB."
---

# Phase 2: Events, Wishlists & Browsing Verification Report

**Phase Goal:** Signed-in users can create an event, invite family with a link, keep a personal wishlist, choose which wishes to share into which events, and browse what the other members wish for.
**Verified:** 2026-11-08
**Status:** human_needed (code side passes; live phone/Google round trip still to be confirmed after deploy)
**Re-verification:** No, initial verification

## Commands run by the verifier

| Command | Result |
|---|---|
| `DEBUG=1 uv run python manage.py test` | Ran 157 tests, OK |
| `DEBUG=1 uv run python manage.py makemigrations --check --dry-run` | No changes detected; system check clean |
| `bash scripts/container-smoke.sh` | SMOKE OK and CONTAINER SMOKE OK (migrations applied in the production image; /events/1/ and /invite/<token>/ signed out redirect to landing with next preserved) |
| Single named tests: `test_edit_never_writes_status`, `test_event_and_membership_are_atomic`, `InviteRoundTripTests` | OK (6 tests) |

## Goal Achievement

### Observable Truths (ROADMAP success criteria, the contract)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A user can create an event (name, optional date/description), copy its invite link, and see it in their list of events | VERIFIED | `event_create` creates Event + Membership in one `transaction.atomic()` (views.py); `home` lists `request.user.events` ordered date asc nulls-last, name, pk; event_detail.html shows read-only invite URL + Copy button for every member (token = `secrets.token_urlsafe(16)`, unique). Tests: EventCreateTests, MyEventsTests, `test_every_member_sees_the_invite_link`, atomicity test. |
| 2 | Signed-out relative opens invite link, signs in with Google, lands on confirm page, joins only on pressing Join; preview/opening joins nobody | VERIFIED (code side; live round trip listed under human verification) | `invite` view: anonymous -> stores token in session, `redirect_to_login` (same redirect for every token, no event data); authenticated GET renders confirm page without creating a membership; only POST does `get_or_create`. Tests: `test_anonymous_get_redirects_and_joins_nobody`, `test_link_preview_bots_join_nobody_and_see_nothing`, `test_anonymous_post_does_not_join`, `test_signed_in_get_shows_confirm_page_without_joining`, `test_post_joins_once_and_is_idempotent`, `InviteRoundTripTests` (mocked Google round trip lands on confirm page; session fallback forwards once from /events/). |
| 3 | A user can add a wish with name, optional description, priority and any number of links, and later edit or delete it | VERIFIED | Wish model reshaped (owner, name, description, priority High/Normal/Low default Normal, links, status, events M2M); `wish_create/edit/delete` views with `normalize_links` (rejects javascript:/data:/mailto:, trims, dedupes, caps length); links rendered with `rel="noopener noreferrer nofollow"`, `target=_blank`; delete is soft (`status=withdrawn`) and idempotent. Tests: WishCrudTests, NormalizeLinksTests. |
| 4 | A user can choose which events each wish is shared into, or share all active wishes into an event in one action | VERIFIED | `WishForm.events` is a checkbox field limited to `owner.events` (forged id rejected), new wish pre-ticks all; `event_share_all` is `@require_POST`, `event.wishes.add(*active_wishes)` (idempotent, local to that event), 404 for non-member. Tests: TracerTests, ShareAllTests, `test_forged_event_id_is_rejected`. |
| 5 | A member sees who is in the event and browses other members' shared wishes grouped by person; a non-member opening the event URL gets 404 | VERIFIED | `event_detail` uses `_member_event_or_404` (single path for non-member and missing id), members in join order, one card per other member built from active wishes shared into this event (`owner__memberships__event=event`), sorted priority then newest; own wishes in a separate owner-view section. Tests: `test_non_member_and_missing_id_get_identical_404`, `test_non_member_gets_404_with_no_wish_names`, ordering and adjacency tests. |

**Score:** 5/5 roadmap truths verified. Plan-level truths (including the edge-case truths tagged EVNT/WISH · empty/encoding/idempotency/ordering/adjacency) all map to named passing tests; one backstop truth is present-but-behavior-unverified (see below).

### Plan must_haves: behavior-dependent / backstop truth

| Truth | Status | Evidence |
|---|---|---|
| [WISH-02 · concurrency] Edit never writes status, so a racing delete cannot resurrect a wish | PRESENT_BEHAVIOR_UNVERIFIED | `wish.save(update_fields=["name","description","priority","links","updated_at"])` in `wish_edit` and `wish_delete` writes `status` only with `update_fields`. The test covers the delete-then-edit-POST ordering (404), not the true in-flight window. Routed to human item; not a gap (code is correct by inspection). |

### Prohibitions (must_haves.prohibitions, all `verification: test`)

| Prohibition | Status | Wired enforcement |
|---|---|---|
| GET /invite/<token>/ never joins anyone (anonymous, bots, signed-in) | VERIFIED | Only `request.method == "POST"` branch creates Membership; tests above pass |
| Signed-out visitor/bot sees no event name, description, creator or member names | VERIFIED | Anonymous branch redirects before any Event lookup; `test_link_preview_bots_join_nobody_and_see_nothing`, `test_anonymous_unknown_token_looks_identical` |
| Non-member and nonexistent event get the same 404 | VERIFIED | `_member_event_or_404`; `test_non_member_and_missing_id_get_identical_404` |
| No email or email-derived identifier on member lists/event/invite pages | VERIFIED | `User.display_name` = first name, else last name, else "Unnamed member" (no username fallback); `test_member_email_never_shown`, `test_nameless_member_shown_as_unnamed_never_username` |
| Wish row and owner pages carry/render no claim state | VERIFIED | No claim fields on Wish (migration 0003 drops `claimed_by`); owner_wish.html separate from member_wish.html; `test_wish_has_no_claim_fields`, `test_owner_pages_render_no_claim_data` |
| A wish never appears in an event it was not shared into | VERIFIED | Event page queries `events=event`; `test_unshared_wish_is_invisible_to_other_members`, `test_wish_shared_elsewhere_is_not_in_this_event` |
| Deleted wish appears nowhere | VERIFIED | All queries filter `status=ACTIVE`; edit/delete GET 404 for withdrawn; `test_deleted_wish_vanishes_everywhere` |
| Privacy policy does not imply erasure on delete and does not describe claims/chip-ins | VERIFIED | privacy.html says "Gifter keeps a copy in its database"; `test_policy_does_not_mention_claims_or_chip_ins_yet`. `PRIVACY_POLICY_UPDATED` = 2026-11-08, same date as the last privacy.html commit. |

No unflagged or unwired prohibitions.

### Required Artifacts

| Artifact | Status | Details |
|---|---|---|
| gifter/models.py (Event, Membership, Wish reshaped, display_name) | VERIFIED | Substantive; unique_event_membership constraint; not registered in admin (checked gifter/admin.py) |
| gifter/migrations/0002, 0003 | VERIFIED | `makemigrations --check` clean; applied in container smoke image |
| gifter/forms.py (EventForm, WishForm, normalize_links, EventChoiceField) | VERIFIED | Wired from views |
| gifter/views.py | VERIFIED | All routes wired in urls.py |
| Templates (event_detail, invite, wishlist, wish_form, wish_confirm_delete, owner/member wish includes, privacy) | VERIFIED | All POST forms carry `{% csrf_token %}` |
| gifter/tests/test_events.py, test_wishes.py, test_privacy.py | VERIFIED | 157 tests total pass |

### Key Link Verification

| From | To | Status | Details |
|---|---|---|---|
| urls.py | views (event, invite, wishes, share-all) | WIRED | 11 routes present; `invite/` is outside the `accounts/` allowlist |
| WishForm.events | request.user.events | WIRED | `owner.events` queryset, forged ids invalid |
| event_detail member cards | Wish.events through table | WIRED | filtered by `events=event`, active, owner is a member |
| landing/invite -> Google -> next | invite confirm | WIRED (mocked) | `InviteRoundTripTests`; live check pending |
| base.html navbar | events, wishlist, logout | WIRED | `test_navbar`, `test_navbar_has_my_wishlist_link` |

### Data-Flow Trace (Level 4)

| Artifact | Variable | Source | Real data | Status |
|---|---|---|---|---|
| home.html | events | `request.user.events` DB query | Yes | FLOWING |
| event_detail.html | memberships, member_cards, own_wishes | Membership/Wish DB queries | Yes | FLOWING |
| wishlist.html | wishes | `request.user.wishes` DB query | Yes | FLOWING |
| invite.html | member_count, creator_name | Membership count / Event.created_by | Yes | FLOWING |

### Behavioral Spot-Checks / Probes

Full test suite (157), migration check, and the container smoke script were run once each (see top table). No `scripts/*/tests/probe-*.sh` probes are declared by the phase. Live (signed-out) smoke additions in `scripts/smoke.sh` could not run against production because it is not deployed.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| EVNT-01 | 02-01 | Create an event with name, optional date/description | SATISFIED | event_create, EventCreateTests |
| EVNT-02 | 02-01 | Copy an invite link | SATISFIED | event_detail invite card, token >= 22 chars |
| EVNT-03 | 02-01 | Invite link signs in then joins after explicit confirm; preview never joins | SATISFIED (live round trip pending, human item) | invite view, tests above |
| EVNT-04 | 02-01 | See the members list | SATISFIED | event_detail members `<details>` in join order |
| EVNT-05 | 02-01 | See events the user belongs to | SATISFIED | home view and MyEventsTests |
| WISH-01 | 02-02 | Add wish with name, description, priority, links | SATISFIED | WishForm, wish_create |
| WISH-02 | 02-02 | Edit and delete own wishes, identical controls | SATISFIED | wish_edit/wish_delete; owner_wish.html has the same controls for every wish |
| WISH-03 | 02-02 | Choose which events each wish is shared into | SATISFIED | WishForm.events checkboxes |
| WISH-04 | 02-02 | Share all active wishes into an event | SATISFIED | event_share_all |
| CLAM-01 | 02-02 | Browse other members' wishes in an event, grouped by person | SATISFIED | event_detail member_cards |

All 10 IDs claimed by the plans exist in REQUIREMENTS.md and are marked complete there. REQUIREMENTS.md maps no additional Phase 2 IDs (no orphans); CLAM-02..08 belong to Phase 3.

### Anti-Patterns Found

None blocking. No TBD/FIXME/XXX/TODO/HACK markers in `gifter/` (non-vendor). No stub returns in views; empty-state strings are real empty states, not placeholders.

### Human Verification Required

1. **Live invite round trip on a real phone.** Test: signed-out relative opens an invite link from a chat app on a phone, signs in with Google, and returns to the confirm page. Expected: "You are invited to <event>" with Join; joins only after pressing Join. Why human: needs live Google OAuth and a phone, and Phase 2 is not deployed yet.
2. **Chat-app link preview.** Test: paste an invite link into a family chat and let the preview render. Expected: no event details shown, nobody joined. Why human: real preview bots cannot be run locally (tests prove anonymous GET reveals nothing and joins nobody).
3. **Deploy and live smoke.** Test: push, let CI deploy, run `scripts/smoke.sh` against gifter.remesh.cz. Expected: all checks pass and migrations 0002/0003 apply on production. Why human: deploy is a separate step; container smoke already proved migrations on a fresh DB.
4. **(Low priority) Edit/delete race.** See `behavior_unverified_items`. The code is correct by inspection; this only upgrades it from inspected to exercised.

### Gaps Summary

No gaps. Every roadmap success criterion, every must-have prohibition and all 10 requirement IDs are satisfied in the local codebase, with 157 passing tests, a clean migration check and a passing production-image smoke run. The status is `human_needed` only because the live phone/Google round trip, chat-app preview behavior and the deploy cannot be proven locally, plus one backstop-tagged race truth that is present but not exercised by a test.

---

_Verified: 2026-11-08_
_Verifier: Claude (gsd-verifier)_
