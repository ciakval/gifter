# Phase 3: Secret Claims & Gift Lifecycle - Context

**Gathered:** 2026-11-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Members can claim another member's wish (single claimer), chip in on a claimed wish with an optional note, mark a claim purchased, and release it (hand-over to the earliest contributor). A "My claims" page lists everything the user claimed or chipped in on, across events, including edited / withdrawn / received states. Giftees can mark their own wishes received (and reopen them). A giftee never learns, from any page, URL, error, ordering or timestamp, whether their wishes are claimed. Automated secrecy tests enforce this and gate deploys.

Not in this phase: Czech catalogue, language switcher and mobile polish (Phase 4); notifications, hidden discussion, secret suggestions (v2); money handling (out of scope).

User priority (2026-11-08): "I want the app to start being usable asap." Phase 2 is live in production. Prefer the smallest correct implementation and few plans, but never trade away secrecy.

</domain>

<decisions>
## Implementation Decisions

### Claiming on the event page
- **D-01:** Buttons on another member's wish card. Free wish: "I'll get this" (claim). Taken by someone else: "Chip in", with an optional free-text note. Your own claim: "Mark purchased" and "Release". If you already chip in: "Stop chipping in". The owner's own cards never show any of these (see D-13).
- **D-02:** Every non-giftee viewer sees a "Taken" badge (or "Purchased" once marked), in every event the wish is shared into. The claimer's and contributors' names and chip-in notes are shown only to viewers who share at least one event with that person (PROJECT.md decision, CLAM-03). Otherwise it is just "Taken" / "Purchased", or "someone" in place of the name.
- **D-03:** Concurrent claims: a unique constraint (one active claim per wish) plus catching `IntegrityError`. The second claimer gets the flash message "Someone just took it" and the refreshed card. Covered by a two-thread race test (`select_for_update` is a no-op on SQLite).
- **D-04:** Interaction: plain POST plus a redirect back to the event page anchor `#wish-<id>`. No htmx in this phase. Every state change is POST-only with CSRF.

### Release, un-share, withdraw, edits
- **D-05:** The claim belongs to the wish, not to an event. If the owner un-shares a claimed wish from an event, the claim stays. The wish leaves that event's page but remains in the claimer's and contributors' "My claims". The owner sees no difference.
- **D-06:** Release with contributors: the earliest contributor (by chip-in time) becomes the claimer, their contribution row is removed, and the other contributors stay. Release with no contributors makes the wish free again.
- **D-07:** Owner withdraws (soft-deletes) a claimed wish: "My claims" shows "Withdrawn by the owner" with a "Remove from my claims" button, which releases/leaves. The wish never reappears on event pages.
- **D-08:** CLAM-08: when the owner edits a wish after it was claimed (wish `updated_at` later than the claimer's acknowledged time), the claimer sees a "Changed since you claimed" badge on My claims and on the card, until they click "Got it". This applies to the claimer. Contributors may get the same marker at Claude's discretion.

### Received flow
- **D-09:** The giftee marks a wish received with a "Received" button on their own wishlist. It moves to a collapsed "Received" section (`<details>`) with a "Reopen" button (LIFE-01..03).
- **D-10:** A received wish leaves every event page. Claimers and contributors see "Received" for it in My claims.
- **D-11:** Build the received flow in this phase. It is small, and still the first cut candidate if the schedule slips.
- **D-12:** Claims on a received wish stay as history and are never shown to the giftee.

### Secrecy
- **D-13:** Owner and giftee pages (wishlist, own wishes on event page, wish edit, received section, every error/404) are byte-identical with and without claims or contributions (CSRF token and any per-request nonce masked). There is no claim-aware owner UI: no warnings, no disabled buttons, no claim-dependent ordering or timestamps (REQUIREMENTS out-of-scope list).
- **D-14:** Sentinel-name crawl test: claims and chip-ins (with notes) are made by a user whose name contains a sentinel string. Every URL pattern is visited as the giftee, and the test asserts the sentinel never appears (SECR-02). **Amended by the user on 2026-11-08:** "The giftee should not be aware of who is getting him what (if anything) in order to maintain surprise. That does not preclude having these literal words on a page." So the protected property is information, not vocabulary. The giftee must not be able to tell whether, or by whom, any of their own wishes is claimed, chipped in on or purchased. Generic UI copy may use the words claim, taken, purchased and chip anywhere (the "My claims" nav link, the privacy policy, the giftee's own claims on other people's wishes). The guarantees are: the sentinel never appears on any giftee page; giftee pages are byte-identical with and without claims on their wishes (D-13); claim-state badges and labels never render on or next to the giftee's own wishes; uniform 404s (D-15). There is no blanket word ban and no word-check exemption list.
- **D-15:** Uniform 404: claim / chip-in / release / purchased / got-it URLs on your own wish, on a wish not shared into any of your events, on a nonexistent id, or with a nonexistent event return the same 404 response.
- **D-16:** The secrecy tests run in the normal Django test suite. The deploy workflow's test job already blocks deploys when tests fail, so no separate CI job is needed.
- **D-17:** Update `/privacy/` and bump `PRIVACY_POLICY_UPDATED` (claims, chip-in notes and who can see them), with the same automated date gate as Phase 2.

### Claude's Discretion
- Model shape (e.g. `Claim` with `wish` OneToOne/unique active + `claimer` + `status` reserved/purchased + `acknowledged_at`; `Contribution` with `claim` FK + `user` + `note` + `created_at`, unique (claim, user)). The claim and contribution tables land in one migration.
- Wish status gains `received` alongside active/withdrawn.
- URL shapes, template partial structure, "My claims" layout and nav placement (add "My claims" to the top bar).
- Whether a claimer can also chip in (no), and whether the owner's own claim attempt 404s (yes, D-15).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 2 models: `Event`, `Membership`, `Wish` (owner, name, description, priority, links, status active/withdrawn, `updated_at`, M2M share into events), `User.display_name` (never email-derived).
- `_member_event_or_404` helper (uniform 404 for non-members and missing events).
- Separate owner and participant templates for wishes (Phase 2 decision), plus member cards on the event page.
- `normalize_links`, `WishForm`, wishlist, wish_create/edit/delete, share-all views. Existing test modules under `gifter/tests/` (157 tests).

### Established Patterns
- `LoginRequiredMiddleware`. POST-only state changes with `@require_POST` and CSRF. Uniform 404s, never 403.
- All strings wrapped for translation, with `ngettext` for counts. Never shadow `_` (the 02-01 deviation).
- Wish and Event are not registered in the admin. Claim and contribution models must stay out of the admin too (01-07 lockdown note).
- The privacy-page date gate pattern from 02-01/02-02 acceptance criteria.

### Integration Points
- `gifter/models.py` (new Claim and Contribution models, Wish status `received`), migration 0004.
- `gifter/views.py` and `gifter/urls.py` (claim actions, My claims, received/reopen).
- Event page participant cards (badges, buttons, names visibility), wishlist owner template (Received button and section), `base.html` nav ("My claims").
- `scripts/smoke.sh`: optionally a signed-out redirect check for `/claims/`.

</code_context>

<specifics>
## Specific Ideas

- Name visibility (D-02) is computed per viewer: show a person's name only if the viewer and that person share at least one event membership.
- "Someone just took it" is the exact user-facing copy for the race (CLAM-02).

</specifics>

<deferred>
## Deferred Ideas

None. Discussion stayed within phase scope.

</deferred>
