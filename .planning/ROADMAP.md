# Roadmap: Gifter

## Overview

Gifter goes from a half-working Django skeleton to a family-ready Christmas 2026 app in four vertical slices. Each slice is deployed to https://gifter.remesh.cz. Phase 1 puts a modernized Django 6.1 app with Google sign-in live on Bombur, so the riskiest environment work (OAuth, hosting, in-app browsers) is proven first. Phase 2 lets the family create events, join via invite links, keep personal wishlists and browse each other's wishes. Phase 3 delivers the core promise: secret claims, chip-in and the received flow, with automated tests proving the giftee can never see who claimed what. Phase 4 gets it ready for relatives: full Czech, a pass on real phones, nightly backups and a family dry-run before the 1 Dec freeze.

**Schedule anchors (user deadlines, not estimates):** today 2026-10-16 · features complete ~15 Nov · family dry-run 15–22 Nov · feature freeze 1 Dec · family use over Christmas 2026.

**If behind schedule, cut in this order:** received flow → chip-in UI → priority → Czech polish beyond the strings themselves. Never cut the secrecy tests or the backups.

## Standing Rules (every phase)

- Every phase ends deployed to https://gifter.remesh.cz from `main` as a usable vertical slice, not a technical layer.
- Every user-facing string is marked for translation from the first template on. Translatable text is never built by string concatenation, because Czech word order and plurals differ. The final phase completes the Czech catalogue.
- Templates are mobile-first from the first page. The final phase verifies them on real phones.
- Owner-facing views and templates never load or render claim data; participant views are separate. Lookups are scoped to what the viewer may see and return 404 (never 403) otherwise.
- State changes happen only via POST.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Google Sign-in Live** - Django 6.1 app with Google login, auto-deployed to gifter.remesh.cz
- [ ] **Phase 2: Events, Wishlists & Browsing** - Create events, join by invite link, keep a wishlist, share wishes, browse others' wishes
- [ ] **Phase 3: Secret Claims & Gift Lifecycle** - Claim, chip in, mark purchased and received, all invisible to the giftee and proven by tests
- [ ] **Phase 4: Family Launch** - Full Czech, a real-phone pass, nightly backups and a relatives' dry-run before the 1 Dec freeze

## Phase Details

### Phase 1: Google Sign-in Live

**Goal:** Anyone with a Google account can sign in to Gifter at https://gifter.remesh.cz. The site runs on a cleaned-up Django 6.1 codebase that redeploys automatically from `main`.
**Mode:** mvp
**Depends on:** Nothing (first phase)
**Requirements:** OPS-01, OPS-02, OPS-03, OPS-04, AUTH-01, AUTH-02, AUTH-03
**Success Criteria** (what must be TRUE):
  1. Visiting https://gifter.remesh.cz shows a Gifter landing page over HTTPS. Every push to `main` redeploys the site automatically (GitHub Actions → GHCR → Bombur) without losing data stored in `./data`.
  2. A user can sign in with Google, including a user whose account was never added as a test user. Google is the only way to sign in and the old `/login/` page is gone. The user stays signed in after closing and reopening the browser, and can sign out.
  3. A signed-out visitor who opens any page other than the landing page is sent to sign in, then returned to that page afterwards.
  4. Opening the site inside the Messenger or Instagram in-app browser shows an "open in your browser" hint instead of a Google sign-in error.
  5. Production runs Django 6.1 from a small pinned dependency set, with `DEBUG` off. All secrets, including a fresh `SECRET_KEY`, are read from the server's `.env`, and `manage.py check --deploy` passes in CI.

**Plans:** 1/5 plans executed

Plans:
**Wave 1**
- [x] 01-01-PLAN.md — Walking skeleton tracer: flattened Django 6.1 app, gifter.User, env-driven settings, Google sign-in round trip with next (local, mocked Google)

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 01-02-PLAN.md — Google is the only door (signup/password/admin login closed, Google-only admin, promote_staff) and allauth's dead ends restyled to lead back to sign-in
- [ ] 01-03-PLAN.md — In-app browser hint: Messenger/Instagram/TikTok/LinkedIn/Snapchat/WebView visitors get open-in-browser steps, Copy link and Continue anyway instead of the Google button
- [ ] 01-04-PLAN.md — Production image with container smoke test, compose/.env spec, test-gated GitHub Actions → GHCR → Bombur pipeline, DEPLOYMENT.md

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 01-05-PLAN.md — Go live: user's one-time setup, first deploy, live smoke + persistence proof, real-device/real-account checks

**UI hint**: yes
**Notes:** Before the first production deploy, switch to a custom user model and regenerate the initial migrations. Treat the committed `SECRET_KEY` as compromised. Publish the Google OAuth consent screen ("In production", basic scopes), register the exact https redirect URI, and set the proxy SSL header behind Caddy. Enable SQLite WAL mode. Follow the bombur-infra conventions (Dockerfile, `compose.yaml`, `deploy.yml`, `.env.example`, `DEPLOYMENT.md`); the steps outside the repo (DNS, server `.env`, deploy key, GitHub secrets, Caddy block) need the user. Research: check the allauth settings for the installed version, including whether `django.contrib.sites` is required.

### Phase 2: Events, Wishlists & Browsing

**Goal:** Signed-in users can create an event, invite family with a link, keep a personal wishlist, choose which wishes to share into which events, and browse what the other members wish for.
**Mode:** mvp
**Depends on:** Phase 1
**Requirements:** EVNT-01, EVNT-02, EVNT-03, EVNT-04, EVNT-05, WISH-01, WISH-02, WISH-03, WISH-04, CLAM-01
**Success Criteria** (what must be TRUE):
  1. A user can create an event with a name and an optional date and description, and copy its invite link. They see the event in their list of all the events they belong to.
  2. A signed-out relative who opens the invite link signs in with Google and lands back on a confirm page. They join only after pressing Join. A chat-app link preview, or opening the link without confirming, joins nobody.
  3. A user can add a wish with a name, optional description, priority and any number of links, and can later edit or delete it.
  4. A user can choose which of their events each wish is shared into, or share all their active wishes into an event in one action.
  5. A member can see who is in the event and browse the other members' shared wishes, grouped by person. A non-member who opens the event's URL gets a 404.

**Plans**: TBD
**UI hint**: yes
**Notes:** Research: the invite → Google sign-in → back-to-confirm round trip for signed-out users (keep `next`, with a session fallback), tested on a clean phone. Fix the existing add-wish view: it never sets the owner and has no login check. Reshape `Wish` around an owner and a status field, with no claim fields on the wish itself. Build the owner wishlist and the participant browse pages as separate views and templates from the start.

### Phase 3: Secret Claims & Gift Lifecycle

**Goal:** Members can coordinate who buys what (claim, chip in, mark purchased) and giftees can close wishes once received. A giftee never learns who claimed or contributed, and automated tests enforce this.
**Mode:** mvp
**Depends on:** Phase 2
**Requirements:** CLAM-02, CLAM-03, CLAM-04, CLAM-05, CLAM-06, CLAM-07, CLAM-08, SECR-01, SECR-02, LIFE-01, LIFE-02, LIFE-03
**Success Criteria** (what must be TRUE):
  1. A member can claim a wish, and every other non-giftee viewer sees it as taken in every event it is shared into. The names of the claimer and contributors appear only to viewers who share an event with that person. If two members claim at the same moment, the second sees "someone just took it".
  2. Other members can chip in on a claimed wish with an optional note. The claimer can mark it purchased, or release it, in which case the earliest contributor takes over. A "My claims" page lists everything the user claimed or chipped in on, across all events.
  3. A claimer sees when the owner edited the wish after it was claimed, and when the owner withdrew it.
  4. From no page, URL, error message, ordering or timestamp can the giftee tell whether their wishes are claimed. Their pages are identical with and without claims. A sentinel-name crawl as the giftee, an owner-page diff and uniform-404 probe tests run in CI and block deploys when they fail.
  5. A giftee can mark a wish as received. It then leaves the active list everywhere and moves into a collapsed "Received" section without revealing the giver. The giftee can also reopen it.

**Plans**: TBD
**UI hint**: yes
**Notes:** Run discuss-phase before planning, to settle what happens when an owner un-shares a claimed wish from an event and the details of the release hand-over. The claim and contribution tables, with their unique constraints, land in one migration. Concurrent claims are handled with unique constraints plus `IntegrityError` (`select_for_update` is a no-op on SQLite), covered by a two-thread race test. The cross-event name-visibility rule is already decided (see PROJECT.md). The received flow is the first cut candidate if the schedule slips.

### Phase 4: Family Launch

**Goal:** Czech- and English-speaking relatives can use Gifter comfortably on their phones, the data is safely backed up, and a real family dry-run has passed before the 1 Dec freeze.
**Mode:** mvp
**Depends on:** Phase 3
**Requirements:** I18N-01, I18N-02, OPS-05, OPS-06
**Success Criteria** (what must be TRUE):
  1. A user can switch between English and Czech at any time. Every page reads naturally in Czech, with correct plural forms (e.g. 1 dárek / 2 dárky / 5 dárků).
  2. Every page is comfortable to use on an iPhone (Safari) and an Android phone (Chrome), and in the in-app browsers where Google sign-in works.
  3. By ~22 Nov, 2–3 relatives have each used their own phone to sign in, join an event, add a wish and claim someone else's wish. The problems they hit are fixed before the 1 Dec freeze.
  4. The production database is backed up nightly to a location outside the app directory, and a restore from that backup has succeeded at least once before 1 Dec.

**Plans**: TBD
**UI hint**: yes
**Notes:** Check the Czech Plural-Forms header against Django's own `cs` catalogue, and have a Czech-speaking relative review the copy. Prepare a short plain-Czech "how to join" message for relatives. Finish the Czech catalogue and the phone pass before the dry-run window opens (~15 Nov). Backups can be set up any time after the first deploy, but the restore drill must be done before 1 Dec.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Google Sign-in Live | 1/5 | In Progress | - |
| 2. Events, Wishlists & Browsing | 0/TBD | Not started | - |
| 3. Secret Claims & Gift Lifecycle | 0/TBD | Not started | - |
| 4. Family Launch | 0/TBD | Not started | - |
