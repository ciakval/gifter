# Requirements: Gifter

**Defined:** 2026-10-16
**Core Value:** Participants in an event can see what someone wishes for and coordinate who buys what — without the giftee ever finding out who claimed what.

## v1 Requirements

Requirements for the Christmas 2026 release. Each maps to roadmap phases.

### Foundation & Ops

- [ ] **OPS-01**: App runs on Django 6.1 with a minimal pinned dependency set (data-science requirements dump removed)
- [ ] **OPS-02**: Production settings come from environment variables (committed `SECRET_KEY` rotated out, `DEBUG` off, `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` for `gifter.remesh.cz`)
- [ ] **OPS-03**: App is reachable at `https://gifter.remesh.cz`, deployed to Bombur via GitHub Actions → GHCR → Docker Compose (per bombur-infra conventions), with SQLite persisted in the bind-mounted `./data`
- [ ] **OPS-04**: Users opening Gifter inside Messenger/Instagram (or similar) in-app browsers see an "open in your browser" hint instead of a Google sign-in error
- [ ] **OPS-05**: 2–3 relatives complete a dry-run (sign in, join, add wish, claim) by ~22 Nov 2026
- [ ] **OPS-06**: The SQLite database is backed up nightly to a location off the app directory, and a restore has been tested once before 1 Dec 2026

### Authentication

- [ ] **AUTH-01**: User can sign in with their Google account (the only login method; the old password `/login/` route is removed)
- [ ] **AUTH-02**: User stays signed in across browser sessions and can sign out
- [ ] **AUTH-03**: Every page except the landing and invite-confirm pages requires sign-in

### Events

- [ ] **EVNT-01**: User can create an event with a name and optional date/description
- [ ] **EVNT-02**: Event creator can copy an invite link for the event
- [ ] **EVNT-03**: A person opening the invite link signs in (if needed) and joins after an explicit confirm; merely opening/previewing the link never joins
- [ ] **EVNT-04**: Member can see the list of members of an event
- [ ] **EVNT-05**: User can see a list of the events they belong to

### Wishes

- [ ] **WISH-01**: User can add a wish to their personal wishlist with name, optional description, priority, and zero or more links
- [ ] **WISH-02**: User can edit and delete (withdraw) their own wishes, with identical controls whether or not anyone has claimed them
- [ ] **WISH-03**: User can choose which events each of their wishes is shared into
- [ ] **WISH-04**: User can share all their active wishes into an event in one action

### Browse & Claim

- [ ] **CLAM-01**: Member can browse other members' wishes in an event, grouped by person
- [ ] **CLAM-02**: Member can claim a wish; only one claimer at a time, and a simultaneous second claim is rejected with "someone just took it"
- [ ] **CLAM-03**: A claimed wish shows as taken in every event it is shared into; the claimer's/contributors' names are visible only to viewers who share at least one event with that person
- [ ] **CLAM-04**: Other members can chip in on a claimed wish, with an optional free-text note (no money handling)
- [ ] **CLAM-05**: Claimer can release their claim; if contributors exist, the earliest contributor becomes the claimer
- [ ] **CLAM-06**: Claimer can mark a claim as purchased (vs. reserved), visible to other non-giftee viewers
- [ ] **CLAM-07**: User has a "My claims" page listing everything they claimed or chipped in on, across events
- [ ] **CLAM-08**: Claimer sees when a claimed wish was edited after they claimed it, or withdrawn by its owner

### Secrecy

- [ ] **SECR-01**: A giftee can never see claims, contributors, purchase status or claim-derived hints on their own wishes — via pages, URLs, error messages, ordering or timestamps
- [ ] **SECR-02**: Automated tests prove SECR-01 (sentinel-name crawl of every route as the giftee; owner pages identical with and without a claim; non-member/owner probes get uniform 404)

### Lifecycle

- [ ] **LIFE-01**: Giftee can mark a wish as received; it leaves the active list everywhere and the giver stays hidden
- [ ] **LIFE-02**: Giftee can reopen a received wish
- [ ] **LIFE-03**: Giftee sees their received wishes in a collapsed "Received" section

### Language & Mobile

- [ ] **I18N-01**: All UI text is available in English and Czech (correct Czech plural forms), and the user can switch language
- [ ] **I18N-02**: All pages are comfortably usable on a phone screen (incl. in-app browsers that do work)

## v2 Requirements

Deferred to a future release. Tracked but not in current roadmap.

### Events

- **EVNT-06**: Event creator can regenerate/revoke the invite link
- **EVNT-07**: Member can leave an event (their claims stay on the wishes)
- **EVNT-08**: Event creator can remove a member

### Ops

- **OPS-07**: Error tracking (e.g. Sentry free tier / OTLP once a collector exists)

### Collaboration

- **COLL-01**: Hidden discussion on a wish among non-giftee members
- **COLL-02**: Members can add secret suggestions to someone's list

### Wishes

- **WISH-05**: Price estimate on a wish
- **WISH-06**: Image on a wish
- **WISH-07**: Quantity > 1 per wish

### Notifications

- **NOTF-01**: Email/push notifications (after a secrecy review; never notify the owner about claims)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Payment pooling / money amounts | Legal/complexity burden; chip-in is coordination only |
| Secret Santa draws | Different product |
| Revealing the giver to the giftee (opt-in or after receipt) | Breaks the core secrecy promise; receipt just closes the wish |
| Notifying the owner about claims/purchases | Secrecy leak |
| Organizer dashboard of all claims | Secrecy leak risk; not needed |
| Claim-aware owner UI (warnings, disabled buttons, "claimed" filters) | Itself a secrecy leak |
| Email/password login | Google login chosen for low friction |
| Persistent groups spanning events | "Event only" model chosen; personal wishlist gives continuity |
| Guest/anonymous claims without sign-in | Need identity for claims and secrecy |
| Native mobile app | Responsive web is enough |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| (filled by roadmapper) | | |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 0
- Unmapped: 33 ⚠️

---
*Requirements defined: 2026-10-16*
*Last updated: 2026-10-16 after initial definition*
