# Project Research Summary

**Project:** Gifter — group gift-wishlist web app (personal wishlists shared into events, secret single-claimer claims + chip-in contributors, hidden from the giftee). Server-rendered Django, Google login, EN + CZ, mobile-first, family/friends audience.
**Domain:** Group gift-wishlist / secret gift coordination
**Researched:** 2026-10-15
**Confidence:** MEDIUM-HIGH overall

## Executive Summary

Gifter is a small, opinionated Django monolith whose entire value rests on one promise: **a giftee never learns who claimed or chipped in on their wishes**. The ecosystem convention (Giftster, Elfster, Amazon lists) is uniform: claim visible to everyone except the owner, claim is undoable, owner is never notified. Gifter's differentiator is chip-in (group gifts) plus a claim that lives on the Wish, so it holds across every event the wish is shared into.

Recommended approach: one Django app with internal layering (selectors for reads, services for writes), django-allauth with Google only, server-rendered templates + htmx + Bootstrap 5.3 (vendored), Django's built-in gettext for EN/CZ, PostgreSQL in production. Secrecy is enforced structurally: claims in separate tables, separate owner and participant templates, a single selector chokepoint for claim reads. Atomicity via unique constraints + `IntegrityError` (not `select_for_update`, which is a no-op on SQLite). Received/withdrawn are status transitions, not row deletes.

Main risks: (1) secrecy leak via a shared template, queryset, URL or side channel (`updated_at`, ordering, owner-visible error text); (2) Google sign-in failing for relatives (consent screen in "Testing", in-app browsers, redirect URI / proxy-scheme mismatch); (3) the deadline — family usable ~15 Nov, feature freeze ~1 Dec. Mitigation: walking-skeleton deploy with real Google login on a real domain in weeks 1–2; secrecy sentinel and owner-diff tests written with the first claim feature; 2–3 person family dry-run in November.

## Open Decisions (researchers disagreed; recommendations given)

1. **Django version.** STACK: 6.1.x (built-in template partials + CSP; 6.1.2 current; supported to ~Dec 2027). PITFALLS: 5.2 LTS (supported to Apr 2028). ARCHITECTURE: unpinned.
   **Recommendation: 6.1.x.** Both agree 5.1.4 (EOL) must go; the codebase is tiny so the bump is cheap now. Fallback 5.2 LTS + `django-template-partials` + `django-csp`. Either way `check --deploy` and tests must pass after the bump.

2. **Production DB / host.** STACK: PostgreSQL on Fly.io + Neon free (~$3–5/mo); alt Hetzner VPS + Compose + Caddy + Postgres (~$6.50/mo). PITFALLS: either managed Postgres or SQLite on a persistent volume with WAL + IMMEDIATE + tested backup; ephemeral-filesystem PaaS requires Postgres.
   **Recommendation: Postgres on Fly + Neon.** Managed backups, data decoupled from the app. Trade-off: Neon scale-to-zero → 1–2 s cold start after ~5 min idle. Avoid Render free (sleeps; free Postgres expires after 30 days) and PythonAnywhere free (no custom domain; restricted outbound).

3. **User model.** STACK + PITFALLS: custom `AbstractUser` subclass before first production migration. ARCHITECTURE: keep `auth.User`, reference via `settings.AUTH_USER_MODEL`.
   **Recommendation: custom user model now (Phase 0).** Cheap now; high cost to retrofit once real data exists.

4. **Cross-event claimer-name visibility.** ARCHITECTURE / PROJECT.md: claim is global, so a viewer in event B sees "taken by Alice" even if Alice isn't in B. PITFALLS: "Taken" shown everywhere, but claimer/contributor *names* only to viewers who share an event with that person.
   **Recommendation: PITFALLS' name rule with a global claim.** Keeps no-duplicates, limits exposure. Decide in Phase 5 discuss-phase; record in PROJECT.md.

5. **Edit / delete / un-share of claimed wishes.** All sources agree: owner may always edit, soft-delete (WITHDRAWN) and mark received with identical owner-side UI regardless of claim state. Claimer sees "changed since you claimed" / "withdrawn by owner" and keeps the claim record. LOW confidence (author recommendation, no industry source) — confirm with the author.

## Key Findings

### Recommended Stack

Django 6.1.x on Python 3.13 (3.12–3.14 valid). ~10 direct dependencies replacing the 124-line data-science `requirements.txt`; drop `pillow` and `requests` as direct deps.

**Core technologies:**
- **django-allauth[socialaccount] 65.19.x** — Google OAuth. `SOCIALACCOUNT_ONLY = True`, settings-based `APPS` credentials from env, `SOCIALACCOUNT_LOGIN_ON_GET = False`, `ACCOUNT_EMAIL_VERIFICATION = "none"`, PKCE on.
- **PostgreSQL 16/17 (Neon) + psycopg 3.3.x** — `DATABASE_URL` via django-environ; `CONN_MAX_AGE = 60`, `CONN_HEALTH_CHECKS = True`.
- **gunicorn 26.x** — 2 sync workers.
- **WhiteNoise 6.12** — `CompressedManifestStaticFilesStorage` via `STORAGES` (`STATICFILES_STORAGE` was removed).
- **htmx 2.0.11** (stay on 2.x; 4.x is beta) + **Bootstrap 5.3.8**, vendored under `static/vendor/`. No CDN / Node / bundler.
- **Django built-in i18n** — gettext, `LocaleMiddleware`, `set_language` cookie switcher. No `i18n_patterns` (keeps invite URLs stable), no rosetta, no modeltranslation.

**Supporting:** django-htmx 1.29, crispy-forms 2.7 + crispy-bootstrap5 (or widget-tweaks — not both), django-environ 0.14, pytest 9 + pytest-django 4.14, ruff, debug-toolbar (dev only), sentry-sdk optional.

**Avoid:** DRF, SPA, Celery/Redis, Tailwind build chain, Alpine (unless needed), django-axes/ratelimit, email backends (no email in v1), `SOCIALACCOUNT_LOGIN_ON_GET = True`.

### Expected Features

**Must have (table stakes):**
- Google sign-in (old `/login/` removed)
- Create event (name, optional display-only date)
- Invite link (`secrets.token_urlsafe`; login-then-join preserving `next`; idempotent; regenerate/revoke)
- Member list + leave event (claims stay on the wish)
- Personal wishlist CRUD (name, optional description, 0..n `WishLink` http(s) URLs, 3-level priority)
- Choose wishes per event, with "share all" shortcut; participation optional with empty-state copy
- Browse others' wishes grouped by person
- Atomic single-claimer claim, visible to all except giftee, releasable
- "My claims" across events
- Chip-in (contribution row, no money amounts, optional note)
- Strict giftee secrecy enforced in queries and tests
- Giftee marks received (reopen allowed; collapsed "received" section)
- EN + CZ from the first template (Czech three-form plurals)
- Responsive layout tested in WhatsApp/Messenger in-app browsers; public HTTPS hosting

**Should have (differentiators, if cheap):** reserved vs purchased status on the claim (one enum); free-text contribution note; "changed since you claimed" marker.

**Defer (v1.1+):** secret suggestions on someone's list; hidden discussion among non-giftees; quantities > 1; URL scraping; email/push notifications (secrecy review first; never notify owner about claims); browser extension; parent-managed child lists.

**Anti-features:** payment pooling / money amounts; Secret Santa; guest/anonymous claims; opt-in reveal to giftee; owner notification on purchase; organizer dashboard of claims; claim-aware owner UI (warnings, disabled buttons, claimed filters); social features; native app.

### Architecture Approach

One app `gifter` with `selectors.py` (all read visibility), `services.py` (all transitions in `transaction.atomic`), and `views/owner.py`, `views/events.py`, `views/participant.py`. Owner modules and `templates/gifter/owner/` must never import or render claim code (grep-based test enforces it).

**Data model:**
- `Event` — name, description, date, `created_by` (PROTECT), `invite_token` (unique), `invite_enabled`. `EventMembership` — unique (event, user), role.
- `Wish` — owner, name, description (blank ok), priority, `status` (ACTIVE / RECEIVED / WITHDRAWN), `received_at`, `created_at`, `updated_at` (touched only by owner edits, never by claim ops). Drop `claimed_by` and `is_active`.
- `WishLink` (wish FK, url, label). `EventWish` (event, wish; unique together).
- `Claim` — OneToOne → Wish with `related_name="+"`, claimer, created_at. "Taken" = Claim row exists.
- `Contribution` — claim FK, user; unique (claim, user).

**Secrecy layers:** (1) no claim columns on Wish, separate templates; (2) querysets exclude viewer's own wishes; (3) chokepoint `claim_views_for(viewer, wishes)` raises if the viewer owns any and returns plain dataclasses to templates; (4) uniform 404, never 403, via visibility-scoped lookups; (5) `LoginRequiredMiddleware` default-deny; (6) canary tests in CI.

**Invite flow:** GET `/join/<token>/` shows a confirm page only (side-effect-free for link previewers); POST joins idempotently; unauthenticated users go through allauth with `next=/join/<token>/`, token also kept in session as fallback.

**Claim flow:** POST → `Claim.objects.create` in `transaction.atomic`, catch `IntegrityError` → "someone just took it". Release with hand-over: promote earliest contributor to claimer if any, else delete the claim.

**Existing code fixes:** `CreateWishView` never sets owner and has no login check; `WishForm` must use explicit fields (drop `is_active`); make description optional; env-driven settings (SECRET_KEY and DEBUG committed); add `LocaleMiddleware` and base template; move `/gifter/add` → `/wishes/add/`; delete empty stray `src/gifter/settings.py`; add root `.gitignore` for `db.sqlite3`, `.env`, `staticfiles/`.

### Critical Pitfalls

1. **Claim data reachable by giftee** via shared card partial, `__all__` form, `select_related("claimed_by")`, or JSON/HTMX endpoint — separate paths/templates, explicit fields, sentinel crawl test as giftee, owner-HTML byte-diff test with/without a claim.
2. **Side channels and oracles** — `updated_at` bumps, claim-based ordering, "claimed" in error text, different response for delete-if-claimed, 403 vs 404 probes — identical owner controls, owner-only ordering fields, uniform 404.
3. **Claim/chip-in races** — `select_for_update` is a silent no-op on SQLite — unique constraints in the first claims migration, `IntegrityError` handling, idempotent contribution, two-thread `TransactionTestCase`.
4. **Invite link side effects / leakage** — join on GET, guessable tokens, no revoke, invite lost across login — GET confirm + POST join, `token_urlsafe`, regenerate/disable, `next` + session fallback.
5. **Google sign-in fails for real relatives** — consent screen in Testing (100 test users, 7-day expiry), `redirect_uri_mismatch`, in-app browser `disallowed_useragent`, missing `SECURE_PROXY_SSL_HEADER`, `CSRF_TRUSTED_ORIGINS` without scheme — publish with basic scopes early, exact https redirect URIs, proxy header, in-app-browser detection with "open in Chrome/Safari" hint, test with a non-test Google account from a WhatsApp link on a phone.

Also: deploying the data-science requirements file; DEBUG / committed secret in production; Django 5.1.4 past EOL; `STATICFILES_STORAGE`; `gettext` at import time or string concatenation in Czech; no backup/restore drill.

## Implications for Roadmap

Suggested phase structure (ARCHITECTURE build order, cross-checked with PITFALLS and FEATURES):

### Phase 0: Foundation
**Rationale:** naming and schema are cheapest to change now.
**Delivers:** Django upgrade, trimmed deps (uv / pyproject), custom user model, `Wish.user` → `owner`, `status` field in initial migration, env-driven settings, root `.gitignore`, base template with viewport + `{% trans %}`, `LocaleMiddleware`, views package, root URLs, test scaffolding, `check --deploy` in CI.
**Avoids:** committed secrets, EOL Django, retrofit of user model / i18n, inconsistent 404 handling.

### Phase 1: Google auth + walking-skeleton deploy
**Rationale:** environment-dependent work with the longest lead time.
**Delivers:** allauth Google (settings credentials, POST button), `LoginRequiredMiddleware`, old `/login/` removed, deploy to Fly + Neon on a real domain with HTTPS + WhiteNoise, consent screen published, author promoted to superuser after first login.
**Research flag:** allauth settings for installed version, `django.contrib.sites` need, `next` across social login, consent-screen steps, current Fly/Neon pricing.

### Phase 2: Owner wishlist (parallel with Phase 3)
**Delivers:** Wish CRUD, priority, WishLink formset, Active / Received lists, POST-only state changes, PRG. Standard patterns.

### Phase 3: Events + invite link (parallel with Phase 2)
**Delivers:** Event, EventMembership, create, event page, member list, invite token with confirm-on-GET + POST join, session fallback, rotate/disable, leave.
**Research flag (moderate):** invite + OAuth round trip for logged-out users, tested on a clean device.

### Phase 4: Sharing + participant browse
**Delivers:** EventWish (unique), share selector, "share all" default, participant event/member pages grouped by person excluding viewer's own wishes, "Your wishes" owner block, empty states. Start canary harness and route-inventory test here.

### Phase 5: Claims, chip-in, secrecy suite (critical path)
**Delivers:** Claim + Contribution in the same migration, `claim_views_for` chokepoint, claim / release-with-hand-over / contribute / uncontribute services, participant UI with confirm/undo, My claims page, optional reserved status + note, name-visibility rule, two-event disjoint-members test, sentinel crawl test, owner-diff test, two-thread race test.
**Research flag:** needs a design discussion (Open Decisions 4 and 5) before planning.

### Phase 6: Lifecycle
**Delivers:** mark_received (+ reopen), withdraw (soft, identical owner response), My gifts page, hide non-active wishes from others. Cut candidate. Standard patterns.

### Phase 7: Czech translation, mobile polish, hardening
**Delivers:** Czech `.po` (check Plural-Forms against Django's `cs` catalog), `compilemessages` in build, real-device pass (iPhone Safari, Android Chrome, WhatsApp/Messenger in-app browsers), Neon backups + weekly `pg_dump` with restore drill, `check --deploy` gate, plain-Czech "how to join" one-pager, family dry-run with 2–3 relatives.
**Schedule:** feature-complete ~15 Nov, dry-run 15–22 Nov, feature freeze 1 Dec, backups verified before 1 Dec.

### Phase Ordering Rationale

Foundation first (naming cheapest now); auth + deploy at weeks 2–3 (environment-dependent, longest lead); owner and events parallelizable; sharing before claims so the owner/participant split exists first; claims is the critical path together with its tests; polish last, but i18n markup is in from Phase 0.

**Cut order if behind:** received flow → chip-in UI (table stays) → priority → Czech polish beyond strings. Never cut secrecy tests or backups.

### Research Flags

- **Needs research/decision:** Phase 1 (allauth settings, consent screen, Fly/Neon pricing), Phase 3 (invite through OAuth), Phase 5 (claim release, name visibility, un-share — discuss-phase), Phase 7 (in-app browser behaviour, Czech plural header, Czech copy reviewed by a relative).
- **Standard patterns (skip research):** Phases 0, 2, 4, 6.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified on PyPI / npm / djangoproject.com 2026-10-15. Hosting prices MEDIUM (recheck at signup). crispy-bootstrap5 on Django 6.1 not explicitly verified. |
| Features | MEDIUM | Claim/secrecy conventions HIGH (Giftster, Elfster, Amazon). Chip-in MEDIUM. Edit/delete/release-with-contributors LOW (author recommendation). |
| Architecture | HIGH (model, secrecy) / MEDIUM (allauth specifics) | Standard Django patterns; allauth details to verify in Phase 1. |
| Pitfalls | MEDIUM-HIGH | Official-doc facts verified; secrecy catalogue is domain reasoning. Czech plural header needs local check. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- Confirm the five open decisions above (Django version, DB/host, custom user model, name visibility, edit/delete rules).
- Verify allauth settings for the installed version and whether `django.contrib.sites` is required.
- Verify Google consent-screen "In production" flow with basic scopes in Cloud Console.
- Verify in-app browser sign-in (Messenger, WhatsApp, Instagram) on real iPhone and Android.
- Verify Czech plural header against Django's own `cs` catalog; have a Czech speaker review copy.
- The SECRET_KEY committed in git history must be treated as compromised; dev data can be discarded with the custom-user `0001_initial` regeneration before first deploy.
- The family dry-run is the only reliable check for sign-in and comprehension failures.

## Sources

### Primary (HIGH confidence)
- PyPI JSON API and npm registry (2026-10-15): Django 6.1.2, django-allauth 65.19.7, psycopg 3.3.6, gunicorn 26.2.0, whitenoise 6.12.0, django-htmx 1.29.0, htmx 2.0.11, Bootstrap 5.3.8
- djangoproject.com download page; 6.1, 6.0, 5.1 release notes; `select_for_update` docs
- docs.allauth.org (Google provider, socialaccount/account configuration, release notes); django-htmx changelog

### Secondary (MEDIUM confidence)
- Google OAuth consent screen and embedded-webview policy pages
- Fly.io, Neon, Render, PythonAnywhere pricing pages
- Giftster, Elfster, Wishpicks, Amazon help pages (claim visibility conventions)
- code.djangoproject.com tickets #30439, #30535 (Czech plural headers)

### Tertiary (LOW confidence)
- Competitor marketing, a 2020 Czech article (Tomikup.cz), Wishfox / WishApp listings, third-party cost table — context only

---
*Research completed: 2026-10-15*
*Ready for roadmap: yes (after Open Decisions 1–4 are confirmed)*
