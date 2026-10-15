# Gifter

## What This Is

Gifter is a web app for groups of people who want to give each other gifts but don't know what the other person wishes for. Each person keeps a personal list of Wishes and shares them into Events (family Christmas, a friend's wedding, …); the other participants can see the Wishes, claim them ("I'm getting X, don't buy the same"), or chip in on someone else's claim — all hidden from the giftee. When the gift arrives, the giftee marks the Wish as received.

## Core Value

Participants in an event can see what someone wishes for and coordinate who buys what — without the giftee ever finding out who claimed what.

## Requirements

### Validated

<!-- Inferred from existing code (commit a2bfe88). -->

- ✓ Django 5.1 project skeleton (`src/web` project, `src/gifter` app, SQLite) — existing
- ✓ `Wish` model with name, description, owner, `is_active`, `claimed_by` — existing
- ✓ "Add Wish" form page at `/gifter/add` — existing (note: view does not set `wish.user`, so save likely fails on the non-null owner FK — must be fixed)
- ✓ Login page via Django `LoginView` at `/login/` — existing

### Active

- [ ] Users sign in with Google
- [ ] User can create an Event (e.g. "Christmas 2026", "Anna & Tom's wedding")
- [ ] Event creator can share an invite link; anyone opening it signs in and joins the event
- [ ] User keeps one personal wishlist; each Wish has name, description, link(s), priority
- [ ] User chooses which of their Wishes appear in which Events
- [ ] Everyone in an event may add/share wishes (nobody is required to — e.g. wedding guests won't)
- [ ] Participants can browse other participants' Wishes within an event
- [ ] Participant can claim a Wish (single claimer); others see it as taken and by whom
- [ ] Other participants can chip in on a claimed Wish as co-contributors (group gift)
- [ ] A claim lives on the Wish itself — it shows as "taken" in every event the Wish is shared into (no duplicate gifts across groups)
- [ ] Giftee never sees claims or contributors on their own Wishes (strict secrecy)
- [ ] Giftee can mark a Wish as received; it closes and leaves the active list, still without revealing the giver
- [ ] UI available in English and Czech (i18n from the start)
- [ ] Usable on mobile phones (responsive)
- [ ] Deployed on public hosting

### Out of Scope

- Discussion/comments on Wishes among other participants (hidden from giftee) — wanted later, not for Christmas 2026 v1
- Price estimates and images on Wishes — not selected for v1
- Persistent groups spanning multiple events — chosen model is "event only"; personal wishlist provides cross-event continuity instead
- Email-based invitations — invite link chosen instead
- Revealing the giver after receipt — receipt just closes the Wish
- Email/password signup — Google login chosen

## Context

- Brownfield but very early: a default Django project plus one app with a `Wish` model and an add-wish page. The existing `Wish.claimed_by` single FK will need to evolve to support chip-in contributors and per-event sharing.
- `requirements.txt` is a dump of a data-science environment (torch, jupyter, pandas, …) — far more than the app needs; should be trimmed to what Gifter actually uses before deploying.
- Target users: families (Christmas), friends (weddings, birthdays). Many are non-technical relatives — low friction (Google login, invite link, phone-friendly) matters.
- Users are Czech and English speakers.

## Constraints

- **Tech stack**: Django (existing project, Django 5.1) — keep building on it
- **Timeline**: Must be usable by the author's family for Christmas 2026 (≈ early-mid December 2026; today is 2026-10-15) — roughly 8 weeks of build time
- **Security/privacy**: Giftee must never be able to see claims on their own Wishes, via UI or URL guessing — this is the core promise
- **Hosting**: Public internet deployment — needs production settings (secrets, HTTPS, allowed hosts, static files)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Events only, no persistent groups | Simpler model; each occasion is its own space | — Pending |
| Personal wishlist shared into events | Wishes carry over between occasions without re-entry | — Pending |
| Claim belongs to the Wish, visible across all events | Prevents duplicate gifts from different groups | — Pending |
| Single claimer + chip-in contributors | Supports group gifts while keeping one responsible person | — Pending |
| Google login | Least friction for relatives | — Pending |
| Invite link for joining | Easy to share via chat apps | — Pending |
| EN + CZ i18n from start | Users span both languages; retrofitting i18n is costly | — Pending |
| Receipt closes wish without revealing giver | Keeps secrecy simple | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-15 after initialization*
