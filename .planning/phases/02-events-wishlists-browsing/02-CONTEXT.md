# Phase 2: Events, Wishlists & Browsing - Context

**Gathered:** 2026-11-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Signed-in users can create an event, invite family with a link (explicit Join confirm), keep a personal wishlist (name, description, priority, links; edit; soft delete), choose which of their wishes are shared into which events (per wish, or "share all" into one event), and browse the other members' shared wishes grouped by person. Non-members get a 404 on event URLs.

Not in this phase: claims, chip-ins, purchased status, "My claims", received flow (Phase 3); Czech catalogue and language switcher (Phase 4); invite revoke/regenerate, leaving events, removing members (v2).

User priority (2026-11-08): "I want the app to start being usable asap". Prefer the smallest correct implementation, few plans, no optional polish.

</domain>

<decisions>
## Implementation Decisions

### Events & invites
- D-01: Any member of an event can see and copy its invite link (not only the creator). Relatives forward it in family chats anyway.
- D-02: One permanent random invite token per event (`secrets.token_urlsafe`, 16+ bytes). No expiry. Revoke/regenerate is v2 (EVNT-06).
- D-03: The invite URL opens a confirm page showing event name, date, creator's display name, member count and a prominent "Join" button (POST). Opening or previewing the link never joins (EVNT-03). Already-members see "You're already in" with a link to the event. Signed-out visitors go through the existing landing/Google flow with `next` preserved (D-04 from Phase 1), with a session fallback for the pending invite.
- D-04: Event fields: name (required), optional date (DateField), optional description. The events list is sorted by date (undated last), then name.

### Wishes
- D-05: Priority has 3 levels: High / Normal / Low, default Normal.
- D-06: Links are a textarea with one URL per line. Each line is validated as http(s), stored normalized, and displayed as a clickable domain name. Works without JS.
- D-07: Delete is a soft delete: `status` = active / withdrawn (received comes in Phase 3). Withdrawn wishes disappear everywhere, and the owner gets the normal "deleted" confirmation. Owner controls are identical whether or not a wish is claimed (WISH-02).
- D-08: Remove `Wish.claimed_by` now (review finding WR-06). There are no claim fields on `Wish`; claims become their own model in Phase 3. Fix the old add-wish path (owner never set, no login check), or replace it entirely.

### Sharing wishes into events
- D-09: Choose events with checkboxes of the user's events on the add/edit wish form.
- D-10: A new wish pre-ticks all of the user's current events.
- D-11: "Share all my wishes here" (WISH-04) is a button on the event page. It is also offered right after joining an event. It shares all active wishes into that event (idempotent).
- D-12: On the event page, the viewer's own shared wishes appear in a "Your wishes shared here" section in plain owner view (never any claim info), with a link to My wishlist.

### Pages & browsing
- D-13: The home page after sign-in (`/events/`, the existing `home` view) becomes "My events" with a "Create event" action, replacing the Phase 1 placeholder.
- D-14: Top navigation bar: Events · My wishlist · Sign out, collapsing on phones (Bootstrap navbar).
- D-15: Event page: the members list first (collapsible), then one card per other member with their shared active wishes, high priority first, then newest.
- D-16: Update `/privacy/` and bump `PRIVACY_POLICY_UPDATED` in this phase to describe events, wishes and who can see them (the 01-06 rule in DEPLOYMENT.md / STATE).

### Claude's Discretion
- URL shapes, model names, and whether to use htmx at all in this phase (plain POST + redirect is acceptable and preferred for speed).
- Form rendering approach (hand-written Bootstrap markup or a small helper; no new heavy dependency).
- Exact copy-to-clipboard UX for the invite link (a read-only input plus a Copy button with a small vendored-free JS snippet, under the existing CSP).
- Test layout. It must include membership 404 tests for event pages and invite-join (no join on GET).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `gifter.User(AbstractUser)` with `display_name` (first name from Google, falling back to username).
- `gifter/templates/gifter/base.html` (Bootstrap 5 vendored under `gifter/static/vendor/bootstrap`, footer with the Privacy policy link), `home.html` (placeholder to turn into My events), `landing.html` (Google sign-in form carrying `next`), `privacy.html`.
- `gifter/views.py`: `landing` (`login_not_required`, keeps `next`), `privacy`, `home`. `_landing_path` helper builds landing URLs with params.
- `gifter/inapp.py` for in-app browser detection (landing hint).

### Established Patterns
- `LoginRequiredMiddleware` is on: every view needs sign-in unless decorated `login_not_required`. `LOGIN_URL = "landing"`.
- All UI strings are wrapped (`{% translate %}`, `gettext_lazy`, `ngettext` for counts). Keep wrapping every new string (Phase 4 adds Czech).
- Tests use Django's test runner (`DEBUG=1 uv run python manage.py test`), and live in `gifter/tests/test_*.py`. 72 tests currently pass.
- `accounts/` routes are an explicit allowlist (`web/urls.py`, `gifter/tests/test_lockdown.py`). Invite routes must live outside `accounts/`.
- The admin must not register wish/claim models (01-07 lockdown; Wish stays unregistered).
- Static storage depends on DEBUG (WhiteNoise manifest in prod). Vendored assets only, with no CDN.

### Integration Points
- `gifter/urls.py` (landing, `events/` → home, privacy): add the event, invite, wishlist and wish routes here.
- `gifter/models.py`: reshape `Wish`, and add `Event`, `Membership` and the wish↔event share link. New migration 0002, with no production data in `Wish` yet.
- `scripts/smoke.sh`: consider one live check that `/events/<id>/` for a random id is not 200 when signed out (stays a redirect).

</code_context>

<specifics>
## Specific Ideas

- The invite round trip for a signed-out relative on a phone must land back on the confirm page after Google sign-in (ROADMAP note: keep `next`, plus a session fallback).
- Non-members opening an event URL get a uniform 404, the same as for a nonexistent event.

</specifics>

<deferred>
## Deferred Ideas

None. Discussion stayed within phase scope.

</deferred>
