# Pitfalls Research

**Domain:** Group gift-wishlist web app (shared wishlists, secret claiming / chip-in, hidden from the giftee), Django 5.1 + SQLite, Google login, EN/CZ, public deployment, hard deadline (family Christmas, early-mid Dec 2026; today 2026-10-15)
**Researched:** 2026-10-15
**Confidence:** MEDIUM-HIGH. Django/allauth/SQLite/Google-OAuth facts verified against official docs. The secrecy-leak catalogue is domain reasoning (HIGH value, but derived from the PROJECT.md design plus common wishlist-app failure modes, not from a single post-mortem source). Czech plural header details are flagged as "verify locally".

**Phase naming note:** the roadmap does not exist yet. Phases below use working labels: **P-Foundation** (settings, user model, deploy skeleton), **P-Auth** (Google login), **P-Events** (events, membership, invites), **P-Wishes** (personal list, sharing into events), **P-Claims** (claim, chip-in, received), **P-Polish** (i18n pass, mobile, copy), **P-Launch** (hardening, backups, family dry-run). The roadmapper should map these onto real phase numbers.

**Facts about the existing code that shape these pitfalls** (read from the repo):
- `models.py` imports `django.contrib.auth.models.User` directly, and `Wish.claimed_by` is a plain FK on the Wish row. `is_active` conflates "visible", "deleted" and (later) "received".
- `views.py` `CreateWishView` has no login check, never sets `wish.user` (save will raise IntegrityError), and returns a bare `HttpResponse`.
- `web/settings.py`: `DEBUG = True`, hard-coded `django-insecure-...` SECRET_KEY committed to git, `ALLOWED_HOSTS = []`, `TIME_ZONE = "UTC"`, `LANGUAGE_CODE = "en-us"`, no `LocaleMiddleware`, no `STATIC_ROOT`, no `CSRF_TRUSTED_ORIGINS`, no `LOGIN_URL`. `src/gifter/settings.py` is an empty stray file.
- `src/.gitignore` contains only `__pycache__/`; `db.sqlite3` and any `.env` are not ignored. No repo-root `.gitignore`.
- `requirements.txt` is a 124-line data-science dump (torch, jupyter, pandas...). Only Django 5.1.4 is relevant.
- Templates are bare HTML: no base template, no `<meta name="viewport">`, no `{% trans %}`.
- Django 5.1 reached end of life (Dec 2025). Today a public deployment on `5.1.4` runs an unsupported release with known published CVEs. Django 5.2 LTS is the cheap, low-risk step up; every 5.1 feature recommended below (LoginRequiredMiddleware, SQLite `transaction_mode` / `init_command`) still exists there.

---

## Critical Pitfalls

### Pitfall 1: Claim data stored on, or reachable from, the object the giftee is allowed to read

**What goes wrong:**
`claimed_by` lives on `Wish`. The giftee's own list view, edit form, detail page, a shared card partial (`wish_card.html`), or a future JSON/HTMX endpoint loads the same `Wish` row and a single `{% if wish.claimed_by %}` or `fields = "__all__"` leaks the claim. Even when the template hides it today, the data is in the context, so the next refactor leaks it.

**Why it happens:**
The model puts the secret next to the public data, and one shared template/queryset serves both "my wish" and "someone else's wish". Secrecy is implemented as `if viewer != owner` in templates, which is a rule every future template must remember.

**How to avoid:**
Make secrecy structural, not conditional:
1. Put claims in their own tables (`Claim` with `OneToOne` to Wish; `Contribution` FK to Claim). Do not keep `claimed_by` on `Wish`. (Requirement "claim lives on the Wish, visible in every event" means one claim per Wish, not a column on it.)
2. Two code paths: an owner path (own-wishlist views, own-wish edit forms) that never joins/loads Claim, and a participant path (event views) that excludes the viewer's own wishes. Different templates for "my wishes" and "their wishes". Do not share a card partial between them.
3. A single selector, e.g. `wishes_visible_to(user, event)`, which is the only way event views get wishes. It excludes `wish.user == user`. Views never call `Wish.objects.filter(...)` directly for participant data.
4. Owner forms use an explicit `fields = [...]` list (never `__all__`/`exclude`); `user` is set server-side from `request.user`, never from POST.
5. Sentinel test: create a claim by a user named `ZZSECRETCLAIMER`, then request every URL (every named route, as the giftee, following links) and assert the sentinel never appears in any response body. Run it in CI from the first claim commit.

**Warning signs:**
`select_related("claimed_by")` in an owner-facing view; one template with both `owner` and `claim` branches; `{% include "wish_card.html" %}` used in both lists; `ModelForm` with `exclude`; the owner edit form POST accepting extra fields.

**Phase to address:** P-Wishes (data model decision, before claims exist) and P-Claims (sentinel test).

---

### Pitfall 2: IDOR on wish/claim/event URLs, and "oracle" responses that confirm a claim exists

**What goes wrong:**
`/wish/12/`, `/wish/12/claim/`, `/event/3/` are reachable by any logged-in user who guesses the integer. Worse, the giftee can POST to `/wish/12/claim/` on their own wish: a different response ("already claimed" vs "claimed") or a 403 vs 404 difference tells them whether someone claimed it, defeating the core promise without ever viewing a claim.

**Why it happens:**
`get_object_or_404(Wish, pk=pk)` is the default tutorial pattern. Authorization is added to the happy path only. Error branches are written for convenience and differ per state.

**How to avoid:**
- Every object lookup goes through a scoped queryset: wishes shared into an event the user is a member of AND not owned by the user (participant path), or owned by the user (owner path). Not found = 404, uniformly, never 403 and never state-dependent messages.
- Check ownership/membership BEFORE reading claim state in any claim/chip-in/unclaim endpoint. The giftee hitting a claim endpoint gets the same 404 as a non-member.
- Enable Django 5.1+ `LoginRequiredMiddleware` (default-deny for anonymous), and opt out only for the invite landing page, login, and static.
- Use opaque identifiers for anything shareable: `secrets.token_urlsafe` for invite tokens, UUIDs (or `django-hashids`-style slugs) for event URLs. Sequential IDs make enumeration trivial.
- Write negative authorization tests for every view: non-member, member-not-owner, owner, anonymous. Treat "owner POSTs to claim endpoint" as its own test.

**Warning signs:**
`get_object_or_404(Wish, pk=...)` with no scoping; views that return 403; error messages that mention "claimed"; no test where the user is the owner of the target wish.

**Phase to address:** P-Foundation (LoginRequiredMiddleware, scoped-queryset convention), enforced in P-Events, P-Wishes, P-Claims.

---

### Pitfall 3: Side-channel leaks - UI affordances, ordering, counts, timestamps

**What goes wrong:**
The giftee never sees "claimed by", but infers it: the Delete or Edit button is disabled/hidden/warns "cannot delete, claimed" for claimed wishes; the "Mark as received" button appears only when claimed; claimed wishes sort to the bottom/top; `auto_now` `updated_at` bumps on claim and the owner's list is ordered by it; "3 of 5 taken" progress summaries include the giftee's own wishes; a notification badge count changes; a wish vanishes from the owner's event view once claimed ("hide taken wishes" applied to everyone).

**Why it happens:**
Natural, helpful UX ("don't let them delete a claimed gift!") is the leak. Claim stored on the Wish row means `save()` touches the wish's timestamps.

**How to avoid:**
- Owner controls are identical for every own wish regardless of claim state: Edit, Delete, Mark received always shown and always allowed (see Pitfall 4 for the consequences).
- Owner-facing ordering uses only owner-controlled fields (priority, created_at, manual order). No `updated_at`, no claim-derived field. Claims in a separate table avoid touching `Wish.updated_at`.
- Aggregates ("N taken", progress bars) are computed only on the participant path and exclude the viewer's own wishes.
- Do not send HTTP caching validators (ETag/Last-Modified) derived from claim state on owner pages; do not add per-view/CDN HTML caching at all in v1.
- Review checklist item: "for each owner-visible element, does it change when a claim is made?" If yes, remove it.

**Warning signs:**
Any template conditional on claim state in an owner-reachable page; `order_by("-updated_at")` in an owner view; `auto_now=True` on Wish; a progress counter on event pages.

**Phase to address:** P-Wishes (owner UI, ordering), P-Claims (verify with sentinel + "toggle claim, diff owner HTML" test: render owner pages with and without a claim and assert byte-identical output).

---

### Pitfall 4: Owner edits or deletes a claimed wish and the claimer is silently wronged

**What goes wrong:**
Giftee changes "Blue wool sweater, M" to "Red scarf" or deletes the wish; the claimer (and chip-in contributors) have already bought it. With `on_delete=CASCADE` the claim silently disappears; with a hard "deleted" filter the claimer sees nothing. Alternatively the developer "fixes" this by blocking edit/delete for claimed wishes, which creates the leak in Pitfall 3.

**Why it happens:**
Two requirements collide: strict secrecy (owner cannot know it is claimed) and fairness to the claimer (should know the wish changed). Teams choose one and break the other.

**How to avoid:**
- Allow edit/delete always. Never say why or "claimed" to the owner.
- Soft-delete: `Wish.status` in {active, received, deleted/archived}. Never hard-delete a wish that has a claim; keep Claim rows.
- The claimer path shows "This wish was changed/removed by its owner" on the claimed wish, and "My claims" lists it. Optionally keep a `Wish.material_edited_at` (separate from `updated_at`, only participant-visible) and show "edited since you claimed" to claimer/contributors. This is participant-only data, so no leak.
- Stop using `is_active` as a combined flag; introduce an explicit status enum now (the received flow needs it).
- Decide and write down the rule for "wish unshared from event X": the claim stays (it is on the Wish) and the claimer must still see it in a claimer-owned page ("My claims") that does not depend on event membership.

**Warning signs:**
`CASCADE` from Wish to Claim; owner edit view containing any claim lookup; no "My claims" page; claimer cannot see a wish that was unshared.

**Phase to address:** P-Wishes (status enum, soft-delete), P-Claims ("My claims", edited/removed markers).

---

### Pitfall 5: The giftee is also a participant (and creator/admin) of the same event

**What goes wrong:**
In a family event everyone is both giftee and giver. The event page is one list "all participants' wishes" and includes the viewer's own; or event creator powers (view members, remove members, "see all") expose claims on the creator's own wishes; the shared "event summary" view or any export includes everyone's claims. In Czech family Christmas this is every user, so any single hole hits everyone.

**Why it happens:**
The mental model "giftee vs. giver" is per wish, but the code models roles per user/per event.

**How to avoid:**
- Roles are per wish: `viewer == wish.user` is the only thing that matters; there is no "admin sees everything" exception, including for the event creator and Django superusers in app views.
- Event page groups wishes by person; own section is the owner-path (no claim data); others' sections are the participant-path.
- When a member is removed or leaves, define claim behaviour explicitly: their claims on others' wishes are released with notice to nobody (or kept?), and their own wishes stop appearing. Write the rule; test it.
- Do not give the event creator extra data access; the only extra powers are invite-link management and removing members.

**Warning signs:**
`if request.user == event.creator` branches that widen what is displayed; event page query that does not exclude own wishes; any "export/print event" feature.

**Phase to address:** P-Events (roles), P-Claims (verification).

---

### Pitfall 6: Cross-event claim visibility discloses claimer identity to people outside the claimer's group

**What goes wrong:**
Claim lives on the Wish and shows in every event the Wish is shared into. Anna shares one wish into "Family Christmas" and "Office Secret Santa". Tom (family) claims it; the office colleagues see "taken by Tom" for a person they do not know. The reverse also happens: contributor lists reveal who chipped in across social circles. This is also a mild privacy issue (names) and can confuse ("who is Tom?").

**Why it happens:**
"No duplicate gifts across groups" is satisfied by showing the claim everywhere; the identity requirement ("and by whom") is applied globally.

**How to avoid:**
Decide explicitly and implement one rule. Recommended: in event E, show "Taken" always; show the claimer's/contributors' names only if the viewer shares at least one event with that user (or only members of E); otherwise show "Taken by someone outside this event". Put this in a single presenter function used by every participant view. Record the decision in PROJECT.md Key Decisions.

**Warning signs:**
Template renders `claim.user.get_full_name` with no membership check; no test with a wish shared into two events with disjoint member sets.

**Phase to address:** P-Wishes (sharing model) and P-Claims (presenter + two-event test). Needs a design decision in discuss-phase.

---

### Pitfall 7: Notifications, flash messages and emails that reveal or spoil

**What goes wrong:**
A "Wish claimed!" email/notification is sent to everyone in the event including the giftee; the "received" action emails "Thanks, X!"; Django `messages` frameworks carry text like "You claimed Anna's bike" into a page the giftee can see on a shared tablet; message text includes giver names; link previews or page titles include claim state; logs/Sentry capture claim details.

**Why it happens:**
Notification code is written with a generic "notify event members" helper. The giftee is a member.

**How to avoid:**
- v1: send no email at all (invites are links; email invitations are out of scope). Set `EMAIL_BACKEND` to console and disable allauth email verification, so a stray signup email cannot 500 in production (default SMTP backend points at localhost). If you later add notifications, they go only to the claimer/contributors of that specific claim, and a unit test asserts the giftee is never a recipient.
- Flash messages are shown to the actor only; they never name the giftee's claim state on an owner page.
- Do not put claim info in `<title>`, Open Graph tags, or URLs (e.g. `/wish/12/claimed/`).
- If error tracking is added later, scrub POST bodies and do not enable `send_default_pii`.

**Warning signs:**
A `notify_event_members()` helper; `send_mail` anywhere; `messages.success` in owner views mentioning other users.

**Phase to address:** P-Claims (design), P-Launch (logging/error-tracking review).

---

### Pitfall 8: "Mark as received" semantics - irreversible, leaks, or inconsistent across events

**What goes wrong:**
(a) The button appears only for claimed wishes (leak). (b) One mis-tap on a phone closes the wish forever (no undo; claimers' bookkeeping vanishes). (c) Closing in event A also closes it in B (correct, it is the same Wish) but nobody explains it. (d) The claim row is deleted on receipt so claimers lose their history, or the claimer sees nothing change. (e) The giftee cannot mark a self-bought or unclaimed wish received.

**How to avoid:**
Button always present on every active own wish; requires a confirm step on mobile; offer "Undo / show closed wishes" for the owner (status flips back; claim data untouched). Keep Claim rows after receipt; show claimers "Delivered" or simply move to a "Done" tab. Never display the giver to the giftee (already decided). This is the most cuttable feature if the schedule slips; build it last and keep the status enum ready.

**Warning signs:**
Receive view filters `claim__isnull=False`; no undo; claim row deleted in `received()`.

**Phase to address:** P-Claims (last item; cut candidate).

---

### Pitfall 9: Race conditions on claim and chip-in (and SQLite makes the obvious fix a no-op)

**What goes wrong:**
Two relatives claim the same wish within seconds on Christmas shopping day. Code does `if wish.claimed_by is None: wish.claimed_by = request.user; wish.save()` - both succeed, last writer wins, the first claimer buys a duplicate gift believing they own it. The textbook fix `select_for_update()` is silently ignored on SQLite (Django docs: no effect, no error), so it passes tests and still races. Double-click / retry double-submits chip-in. Under SQLite default deferred transactions, read-then-write inside a transaction can fail with "database is locked".

**Why it happens:**
Check-then-write in Python; lock primitives that do not exist on the dev/prod DB; tests wrapped in `TestCase` transactions hide locking issues.

**How to avoid:**
- Let the database arbitrate: `Claim.wish = OneToOneField(Wish)` (unique), create inside `transaction.atomic()`, catch `IntegrityError` and show "Someone just claimed this - see who". Or conditional `UPDATE ... WHERE claimed_by IS NULL` and check rows-affected. Same for `Contribution` (unique on `(claim, user)`) so double-submit is idempotent.
- Unclaim and chip-in re-check state inside the transaction. Define what happens to contributors when the claimer releases (transfer to a contributor or block release while contributors exist) - otherwise orphaned contributions.
- SQLite settings (Django 5.1+): `OPTIONS = {"transaction_mode": "IMMEDIATE", "timeout": 20, "init_command": "PRAGMA journal_mode=WAL;"}` so writes serialize and readers do not block. Run gunicorn with 2-3 workers max.
- Test with `TransactionTestCase` + two threads/processes hitting the claim function; assert exactly one winner. A plain `TestCase` cannot prove this.
- The UI must handle the loser gracefully (stale page showed "Claim" button).

**Warning signs:**
`claimed_by` read, branch, then `save()`; `select_for_update` as the only guard; no unique constraint on the claim; tests only use `TestCase`.

**Phase to address:** P-Claims (design with constraint from the first migration); the unique constraint must exist in the initial Claim migration.

---

### Pitfall 10: Invite links that auto-join on GET, never expire, or get consumed by chat-app link previews

**What goes wrong:**
- WhatsApp/Messenger/Telegram unfurl bots fetch the link with GET. If the invite view joins on GET, the bot "joins" (or consumes a single-use token), or the app 500s because the bot is anonymous.
- The link pasted in a big family group chat also includes people who should not be in the event (ex-partner, a friend of a friend). A joined stranger sees every wish and every claim, and the link never expires.
- Guessable/short tokens; token equals event PK.
- Token leaked via Referer when a participant clicks an outbound shop link from a page whose URL contains the token.
- After login via Google the user lands on the home page, not in the event (invite token lost), so non-technical relatives think the link is broken.

**How to avoid:**
- GET on the invite URL renders a landing page ("Join Family Christmas 2026?" + login/Join button). Joining is a POST. Landing page has no side effects, so bots are harmless; keep it free of wish data (OG tags show at most the event name).
- Token: `secrets.token_urlsafe(16+)`, stored separately from event PK, revocable and regeneratable by the creator, optional expiry, creator can see member list and remove members. A member cap is a cheap guard.
- Carry the invite through authentication by putting it into the `next` parameter (and also session as backup); after callback, redirect to the event with the user already joined/confirmed.
- Django's default `Referrer-Policy: same-origin` (SecurityMiddleware, `SECURE_REFERRER_POLICY`) already prevents the Referer leak; keep it, and add `rel="noopener noreferrer"` on external wish links.
- Rate-limit the join POST lightly (even a per-IP cache counter).
- Already-member, creator-clicks-own-link, and revoked-token cases each show a sane message.

**Warning signs:**
Join logic in a `get()`; token short or sequential; no "regenerate link" or "remove member" UI; testing only with the author's already-logged-in browser.

**Phase to address:** P-Events (all of it); P-Auth interaction (invite survives login).

---

### Pitfall 11: Google sign-in fails for real relatives - in-app browsers, consent-screen "Testing" mode, redirect URI mismatch

**What goes wrong:**
It works for the author in desktop Chrome and breaks for the family:
1. Invite links are sent via chat apps. Links opened inside embedded webviews (Facebook Messenger / Instagram in-app browsers; behaviour varies by app and OS) hit Google's `disallowed_useragent` block on "Sign in with Google" (Google's embedded-webview policy, enforced since 2021). The relative sees an error page and gives up.
2. The OAuth consent screen is left in "Testing": only the 100 explicitly listed test users can sign in, everyone else gets an access error; authorizations also expire after 7 days.
3. `redirect_uri_mismatch`: the authorized redirect URI must match exactly, including scheme, host, port and trailing slash: `https://<domain>/accounts/google/login/callback/`. `http://localhost:8000` and `http://127.0.0.1:8000` are different entries. In production behind a TLS-terminating proxy, Django builds an `http://` redirect URI unless `SECURE_PROXY_SSL_HEADER` is configured, so it works locally and fails only live.
4. A raw IP or non-public domain cannot be used as an authorized redirect/origin for production; a real domain with HTTPS is required.

**How to avoid:**
- Request only `openid email profile` (default allauth scopes); with basic scopes the app can be moved to "In production" status without Google verification. Do this early (week 2-3), then test sign-in with a Google account that is NOT listed as a test user and not owned by the author.
- Register all redirect URIs up front: local (`http://127.0.0.1:8000/...` and `localhost`), staging if any, production. Configure Google credentials in settings from env vars (`SOCIALACCOUNT_PROVIDERS["google"]["APP"]`), not both settings and the admin SocialApp (allauth then raises `MultipleObjectsReturned`).
- Set `SECURE_PROXY_SSL_HEADER` and trust only a proxy that overwrites `X-Forwarded-Proto`.
- Detect in-app browser user agents (FBAN, FBAV, Instagram, Messenger) on the login page and show a plain-language "Open this page in Chrome/Safari" instruction with a copy-link button. Test the invite link end to end from WhatsApp and Messenger on a real iPhone and a real Android phone. (MEDIUM confidence on per-app behaviour: depends on app versions; verify empirically.)
- Keep the login button a POST form: allauth's `SOCIALACCOUNT_LOGIN_ON_GET` defaults to False, and a plain `<a href="/accounts/google/login/">` shows an intermediate confirmation page.

**Warning signs:**
Only the author's account has ever signed in; consent screen status says "Testing"; first live login attempt is on deploy day; redirect URIs list only localhost.

**Phase to address:** P-Auth (config, prod redirect URI, consent screen publish) and P-Launch (real-device test). Needs deeper phase research for in-app browser handling.

---

### Pitfall 12: Account model and linking traps with allauth

**What goes wrong:**
- The author already has a password `User` (superuser) from `createsuperuser` with the same email as their Google account. First Google login either shows the signup form with an "email already in use" conflict or creates a second user; wishes end up under the wrong account. By default (`SOCIALACCOUNT_EMAIL_AUTHENTICATION = False`) allauth will not auto-merge.
- The old `/login/` username/password `LoginView` remains live next to Google login - a second, weaker door (email/password signup is out of scope).
- Users hard-coded to `django.contrib.auth.models.User`; adding `language`/display-name later means a painful `AUTH_USER_MODEL` swap after real data exists.
- `LOGIN_URL`/`LOGIN_REDIRECT_URL` unset: `@login_required` redirects to `/accounts/login/` which is allauth's page or 404 depending on URL order.
- Two relatives with the same first name ("Jan"): claims read "taken by Jan".
- Some relatives (older, children, privacy-conscious) have no Google account at all.

**How to avoid:**
- Decide the user model NOW (before any production migration): `AUTH_USER_MODEL` custom user subclassing `AbstractUser` (add `preferred_language`), and use `settings.AUTH_USER_MODEL` in FKs. There is no real data yet, so you can regenerate `0001_initial` cleanly (only until the first deploy; after that never edit applied migrations).
- Keep `SOCIALACCOUNT_EMAIL_AUTHENTICATION` at its default False (allauth docs: only enable for fully trusted providers; Google is, but you have no local accounts to link, so linking logic is unneeded). Make the author's superuser by logging in with Google once, then `createsuperuser`-style promote (`user.is_staff = user.is_superuser = True`) in a shell.
- Remove or redirect the old `/login/` route; the admin keeps Django's own password login (protected, strong password).
- Show a display name that disambiguates ("Jan R.") using `given_name` + initial from the Google profile; allow editing a nickname in a settings page.
- Accept Google-only as a decision but run the family dry-run (Pitfall 28) to count relatives who cannot sign in; if more than 1-2, a v1.1 fallback (allauth login-by-code via email) is the escape hatch. Log this as a known risk.

**Warning signs:**
Two rows for the author in `auth_user`; `/login/` still reachable; FKs referencing `User` directly; `makemigrations` adds `AUTH_USER_MODEL` swap after prod data exists.

**Phase to address:** P-Foundation (user model), P-Auth (everything else).

---

### Pitfall 13: Going to production with development settings and an unsupported Django, found out on deploy day

**What goes wrong:**
`DEBUG=True` on a public host shows source, settings and SQL on error pages; the committed `django-insecure-...` key is public if the repo is (it is in git history forever); `ALLOWED_HOSTS=[]` with `DEBUG=False` returns 400 for every request; login/POST forms return 403 "CSRF verification failed" behind the proxy because `CSRF_TRUSTED_ORIGINS` lacks the scheme (must be `https://your.domain`, Django 4.0+); `SECURE_SSL_REDIRECT=True` without `SECURE_PROXY_SSL_HEADER` loops forever; the admin is unstyled (static files not served when DEBUG is off); and Django 5.1.4 is itself past end of life.

**How to avoid:**
- One `settings.py` driven by env vars (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`), with fail-closed defaults (DEBUG False unless explicitly set). Generate a NEW production SECRET_KEY; never reuse the committed one.
- Production block: `SECURE_PROXY_SSL_HEADER`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS` starting small (e.g. 3600, no preload, no includeSubDomains; raise after a week of working HTTPS), plus `python manage.py check --deploy` clean as a release gate.
- Upgrade to Django 5.2 LTS during P-Foundation (bump, run migrations/tests); do it while the app has 1 model.
- Deploy a skeleton to the real host and real domain in week 1-2, not week 7 (see Pitfall 27).
- Configure `LOGGING` to stdout/file so 500s are visible with DEBUG off.

**Warning signs:**
`check --deploy` never run; staging does not exist; first HTTPS visit is the week-7 deploy.

**Phase to address:** P-Foundation (settings, skeleton deploy), P-Launch (checklist gate).

---

### Pitfall 14: Static files and the removed `STATICFILES_STORAGE` setting

**What goes wrong:**
With `DEBUG=False`, Django does not serve static files; the admin and CSS vanish. Copy-pasted WhiteNoise tutorials set `STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"`, but that setting was removed in Django 5.1, so it is silently ignored and manifest hashing never happens. With the manifest storage correctly configured, forgetting `collectstatic` on deploy causes 500s (`Missing staticfiles manifest entry`).

**How to avoid:**
Set `STATIC_ROOT`, add WhiteNoise middleware right after `SecurityMiddleware`, configure via the `STORAGES` dict (`STORAGES["staticfiles"]["BACKEND"] = "whitenoise.storage.CompressedManifestStaticFilesStorage"`), run `collectstatic --noinput` in the deploy script, and have a post-deploy smoke test that fetches `/` and one CSS file.

**Warning signs:**
`STATICFILES_STORAGE` in settings; no `STATIC_ROOT`; admin unstyled on staging.

**Phase to address:** P-Foundation (deploy skeleton).

---

### Pitfall 15: SQLite in production on a host that wipes the filesystem, with no tested backup

**What goes wrong:**
On most PaaS (Heroku, Render free tier, Railway/Fly without a volume, Cloud Run) the container filesystem is ephemeral: every deploy or restart wipes `db.sqlite3`; all wishes and claims vanish a week before Christmas. On VPS: `cp db.sqlite3` while the app writes can produce a corrupt backup; backups stored on the same disk die with it; the restore was never tried. Running SQLite on a network filesystem or with many gunicorn workers triggers locking errors. `db.sqlite3` is not gitignored, so `git add .` can commit user data and sessions, and `git pull` deploys can overwrite the live DB.

**How to avoid:**
- Pick the host and DB together, now. Opinionated: a small VPS or a PaaS with a persistent volume + SQLite (WAL + IMMEDIATE, 2-3 workers) is adequate for tens of users; on an ephemeral-FS PaaS use managed Postgres from day one (and `select_for_update` then works too). Develop against the same engine as production, otherwise the concurrency tests prove nothing.
- Put the DB path in an env var pointing outside the code directory; add `db.sqlite3`, `*.sqlite3-wal`, `*.sqlite3-shm`, `.env`, `staticfiles/` to a root `.gitignore`.
- Backups: nightly `sqlite3 db.sqlite3 ".backup /path/backup-$(date +%F).db"` (or `VACUUM INTO`), copy off the host, keep 14 days, and do one actual restore test before December. Take an extra backup immediately before each deploy that includes a migration.
- Schema freeze: once real family data exists (~mid Nov), every migration must be data-preserving; no hand-editing applied migrations.

**Warning signs:**
Host docs say "ephemeral filesystem"; DB file inside the repo/app directory; no backup cron; backup never restored.

**Phase to address:** P-Foundation (host + DB decision), P-Launch (backup + restore drill).

---

### Pitfall 16: Deploying the data-science `requirements.txt`

**What goes wrong:**
`pip install -r requirements.txt` pulls torch, jupyter, pandas and ~120 other packages: multi-GB image, build timeouts or memory limits on small hosts, a large vulnerability surface, and transitive version conflicts with Django/allauth.

**How to avoid:**
Replace it now with a minimal pinned file: Django 5.2.x, `django-allauth[socialaccount]`, gunicorn, whitenoise, `python-dotenv` or `django-environ`, `psycopg[binary]` if Postgres. Use a clean virtualenv to verify `manage.py check` and the test suite from the new file. Optionally add `pip-audit` once.

**Warning signs:**
`torch` anywhere in the deploy install log; image > 500 MB.

**Phase to address:** P-Foundation (first task).

---

### Pitfall 17: i18n retrofitted late - or done "from the start" in ways that still break Czech

**What goes wrong:**
- Strings in models/forms/choices evaluated at import time with `gettext` (not `gettext_lazy`) are frozen to the default language.
- English-style pluralization (`"{n} contributor(s)"` or `n == 1 ? ... : ...`). Czech has 3 forms for integers (1; 2-4; 5+), and newer gettext catalogs define 4 (adding fractions). Django ticket #30439 shows mixed 3-form/4-form `Plural-Forms` headers across catalogs causing lookups to fall back to English for some counts (ticket #30535: counts of 5+ fell back to English). Verify the header in your generated `locale/cs/LC_MESSAGES/django.po` matches the header in Django's own shipped `cs` catalog.
- Building sentences from fragments and names ("Wishes for " + name; "taken by " + name; "claimed" in past tense). Czech declines names and verbs are gendered ("Dárky pro Honzu", "Rezervoval/a"). Concatenation yields wrong grammar and no translator can fix it.
- Missing `LocaleMiddleware` (must come after `SessionMiddleware` and before `CommonMiddleware`) or `LANGUAGES`; language switch via GET link (the `set_language` view needs POST); no per-user preferred language stored.
- `makemessages`/`compilemessages` need GNU gettext binaries (`msgfmt`) on dev machine and in deploy; `.mo` files not compiled/committed means production is English-only while dev is Czech.
- `TIME_ZONE = "UTC"`: event dates and "Dec 24" boundaries are off by 1-2 hours; Czech date formats need `LANGUAGE_CODE`-aware formatting (do not hand-format dates).
- Czech strings run 20-40% longer; mobile buttons wrap or overflow.

**How to avoid:**
- Wrap every user-visible string from the first template (`{% trans %}`, `{% blocktrans %}` with named placeholders, `gettext_lazy` in models/forms/choices). Add a CI check that `makemessages -l cs` leaves no untranslated entries for new strings (or at least a smoke test rendering every page under `translation.override("cs")`).
- Use `{% blocktrans count n=... %}...{% plural %}...{% endblocktrans %}` for every count; check Plural-Forms.
- Write whole-sentence strings with the name as a standalone placeholder, and prefer constructions that avoid declension: "Wishes — Honza" / "Taken: Jan R." / noun/status forms instead of gendered verbs.
- Set `TIME_ZONE = "Europe/Prague"`, `LANGUAGE_CODE = "cs"` default or keep `en` default with `LocaleMiddleware` honoring `Accept-Language`; store `preferred_language` on the user for any out-of-request rendering (emails if ever added).
- Install gettext in the deploy pipeline, run `compilemessages`, and decide whether `.mo` is committed or built.
- Get a Czech speaker to read the whole UI in the final week (the author is presumably it).

**Warning signs:**
`gettext` (not lazy) at module scope; `"(s)"` in strings; `.po` Plural-Forms header differing from Django's cs catalog; production in English when the browser is Czech.

**Phase to address:** P-Foundation (middleware, settings, base template with `{% trans %}`), every feature phase (strings), P-Polish (plural/grammar audit, length test).

---

### Pitfall 18: Mobile layout and interaction mistakes that matter more than desktop polish

**What goes wrong:**
No viewport meta tag (current templates have none) so phones render a zoomed-out desktop page; `form.as_p` unstyled inputs; Claim and Chip-in buttons adjacent with small tap targets, so mis-taps claim a gift (consequential on a phone while scrolling); one flat list of all wishes from all people, so users forget whose wish they are looking at; clipboard "copy invite link" fails because it needs HTTPS and a user gesture; relatives open links inside chat-app browsers that lose cookies/sessions.

**How to avoid:**
- Base template with viewport meta from the start; mobile-first CSS using one lightweight framework or hand-rolled CSS; do not introduce a JS build pipeline or SPA in an 8-week window.
- Group wishes under the person's name (collapsible sections); show the person at the top of every wish detail page.
- Claiming needs a confirm (or a visible 10-second undo) and primary/secondary button separation; minimum 44px tap targets.
- Invite sharing: "Copy link" plus Web Share API (`navigator.share`) falling back to copy; test on HTTPS.
- Use `type="url"`, appropriate `autocomplete`/`inputmode`, and visible labels; make the wish form short (name required, rest optional).
- Test on a real iPhone Safari and Android Chrome and inside WhatsApp's in-app browser before launch.

**Warning signs:**
Never opened on a phone; Chrome devtools device mode is the only test; buttons adjacent.

**Phase to address:** P-Foundation (base template), P-Polish (device test), P-Claims (button design).

---

## Moderate Pitfalls

### Pitfall 19: Chip-in is much harder than it looks, and the model must support it from the start

**What goes wrong:** Single `claimed_by` FK cannot represent contributors; retrofitting a `Contribution` table after claims exist requires data migration. Semantics are undefined: Can contributors withdraw? What if the claimer releases? Can the giftee's group coordinate with no comments (out of scope)? Does chip-in imply money amounts (do NOT build payments or splits)?
**Prevention:** Create `Claim` and `Contribution` tables together in the first claims migration, even if the chip-in UI ships last. Define: release by claimer is blocked or transfers to the earliest contributor; contributors can withdraw; chip-in is a plain "I'm in" list with no amounts. Cut line: if the schedule slips, ship claim without chip-in UI; the table stays ready.
**Phase:** P-Claims.

### Pitfall 20: Wish-to-event sharing model hidden complexity

**What goes wrong:** "User chooses which Wishes appear in which Events" needs a through table `WishShare(wish, event)`. Pitfalls: new members see old wishes only if shared; unsharing a claimed wish leaves a dangling claim; a user who joins later has nothing shared and sees an empty page (friction for non-technical users); wedding guests with no wishes see an empty event with no explanation.
**Prevention:** Through table with unique `(wish, event)`; "share all my active wishes into this event" default checkbox on join; empty-state copy ("Anna hasn't shared any wishes yet"); decide the unshare-while-claimed rule (Pitfall 4/6).
**Phase:** P-Wishes.

### Pitfall 21: User-supplied wish links as XSS/abuse vectors

**What goes wrong:** Storing links in a `TextField` and rendering `href="{{ link }}"` allows `javascript:` URLs; link-preview/title-fetching features create SSRF risk.
**Prevention:** Use `URLField` (Django's validator allows only http/https/ftp/ftps), render with `rel="noopener noreferrer nofollow"`, store multiple links in a child `WishLink` table (not comma-separated text). Do NOT fetch link metadata server-side in v1 (images/price are out of scope anyway).
**Phase:** P-Wishes.

### Pitfall 22: Admin exposure and the author-as-giftee problem

**What goes wrong:** `/admin/` is public at the default path; `Wish` admin `list_display` or inline shows claims; the author (a family participant) sees claims while debugging, spoiling their own surprises; a second superuser (relative) can see everything.
**Prevention:** Do not register `Claim`/`Contribution` in admin (or register read-only, superuser-only); change the admin URL path; strong password; at most one superuser. Be honest in PROJECT.md: the developer/DB admin can technically see claims; to protect the author's own surprises, test with seeded fake users and avoid querying claims on own wishes. Disable debug toolbars in production.
**Phase:** P-Foundation (admin path), P-Claims.

### Pitfall 23: Django-specific forms/views defaults that bite early

**What goes wrong:** Existing add view lacks login and `wish.user`; `HttpResponse("created")` response; no redirect after POST (refresh double-submits); `ModelForm.save()` without `commit=False` for owner assignment; CSRF on claim endpoints implemented as GET links (`<a href="/claim/3">`), so a prefetching browser, link scanner or chat preview claims a wish.
**Prevention:** All state changes are POST with CSRF; Post/Redirect/Get; `LoginRequiredMiddleware`; fix the add view in the first phase and cover with a test. Claim, release, chip-in, receive are POST-only endpoints.
**Phase:** P-Foundation, P-Wishes.

### Pitfall 24: Caching layers and shared devices serving the wrong person's page

**What goes wrong:** Adding per-view caching, a CDN or Cloudflare "cache everything" in front of HTML pages serves one user's claim-bearing page to another; browser back button or shared family tablet shows the previous user's page after logout.
**Prevention:** No page caching in v1; if a CDN is used, cache only `/static/`; set `Cache-Control: private, no-store` on authenticated HTML (a small middleware or `never_cache`); logout via POST; keep sessions at the default 2 weeks or shorter on shared devices.
**Phase:** P-Foundation (middleware), P-Launch (check).

### Pitfall 25: allauth configuration details

**What goes wrong:** `SITE_ID`/`django.contrib.sites` default `example.com` domain generates wrong absolute URLs if used; allauth URLs not mounted at `/accounts/`; allauth default templates are English-unstyled; allauth shows its own "signup" form on social signup when username/email conflicts; email-verification flow tries to send mail; login via old username form still enabled.
**Prevention:** Configure social-only flow explicitly: `SOCIALACCOUNT_AUTO_SIGNUP = True`, `ACCOUNT_EMAIL_VERIFICATION = "none"` (Google already verifies), no email sending, override the login template to a single "Continue with Google" POST form, set `LOGIN_URL`, `LOGIN_REDIRECT_URL`, and if you keep `django.contrib.sites` update the Site domain in a data migration. Pin allauth and read its release notes (the settings API changed repeatedly across versions; check the doc for the installed version).
**Phase:** P-Auth.

### Pitfall 26: Settings and secrets management

**What goes wrong:** `.env` committed; Google client secret committed (public repo); two copies of settings (stray empty `src/gifter/settings.py`) confuse tooling; local settings diverge from production so prod-only bugs appear.
**Prevention:** Root `.gitignore` before the first deploy; secrets only in env; delete the stray file; `.env.example` committed; one settings module with env switches; rotate any secret that ever touched git.
**Phase:** P-Foundation.

---

## Schedule and Scope Pitfalls (hard deadline)

### Pitfall 27: Deploy last, secrecy tests last, polish last

**What goes wrong:** The OAuth redirect URI, HTTPS, static files, host persistence and consent-screen publish are all discovered in week 7. The calendar also has a hidden earlier deadline: wishes must be entered before relatives start buying (early December; Czech gifts are often bought in the Mikulas-to-Dec-23 window), so the product must be "feature complete and in the family's hands" around mid-late November, not early December.
**Prevention:** Deploy a walking skeleton (login with Google + one page) to the real domain within the first 2 weeks and redeploy every phase. Write the secrecy sentinel test with the first claim feature. Suggested milestones: feature-complete ~Nov 15; family dry-run with 2-3 relatives ~Nov 15-22; feature freeze Dec 1; backups verified before Dec 1. Cut order if behind: received flow, then chip-in UI, then priority, then Czech polish beyond strings (never cut secrecy tests or backups).
**Phase:** P-Foundation (skeleton deploy), P-Launch.

### Pitfall 28: No family dry-run

**What goes wrong:** Real relatives hit things the author never did: no Google account, in-app browser failures, forgot which account, same-name confusion, uncertain what "chip in" means, grandma finds the invite link in WhatsApp but can't sign in.
**Prevention:** Run an actual 2-3 person trial in the real event two to three weeks before the target; watch one person do the whole flow on their own phone; write a one-page "how to join" in Czech (screenshots) for the family group chat. Log failure counts.
**Phase:** P-Launch.

### Pitfall 29: Scope creep into explicitly out-of-scope items

**What goes wrong:** Comments on wishes, price estimates, images, persistent groups, email invitations are all out of scope in PROJECT.md but are exactly the features gift apps tempt developers to add (chip-in naturally invites "let me comment" and "split the cost").
**Prevention:** Treat the PROJECT.md out-of-scope list as a gate in plan review; log new ideas in a backlog; no payments/amounts in chip-in.
**Phase:** all.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep `claimed_by` FK on `Wish` | No new model, quick | Secrecy depends on every template; chip-in needs a rewrite and data migration; `updated_at` side channel | Never |
| Keep `django.contrib.auth.models.User` with no custom model | One less step | `AUTH_USER_MODEL` swap after prod data is painful | Only if you are sure you need no extra user fields; since a language preference is likely, do the custom model now |
| Hard-coded settings / `DEBUG=True` default | Works locally | One forgotten flag exposes the app | Never in committed code; env-driven with safe defaults |
| SQLite in prod with no volume/backup | Zero ops | Data loss | Never without persistent disk + tested backup |
| `is_active` doubles as received/deleted/hidden | No migration | Cannot distinguish states; undo impossible | Never; add `status` enum now |
| Skipping tests for authorization | Faster features | Silent secrecy regressions | Never for the core promise; skip elsewhere |
| English strings first, wrap later | Faster first view | Thousands of edits, missed strings | Never (project decision: i18n from start) |
| One shared wish card template | Less duplication | Leak vector (Pitfall 1) | Never across owner/participant paths |
| No unique constraints, "check in Python" | Simple code | Race duplicates | Never for Claim/Contribution/WishShare |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Google OAuth | Consent screen left in Testing (100 test users, 7-day expiry); redirect URI missing trailing slash or HTTPS variant | Publish to production with basic scopes early; register exact `https://<domain>/accounts/google/login/callback/` plus localhost variants |
| Google OAuth in chat apps | Assume it works in every link-opening context | Detect embedded webviews, instruct "open in browser"; test on real devices |
| django-allauth | Credentials in both settings and admin SocialApp; GET login link; leaving email verification on with no email backend | Settings-based `APP` from env; POST button; verification off; console email backend |
| Reverse proxy / TLS | No `SECURE_PROXY_SSL_HEADER`; `CSRF_TRUSTED_ORIGINS` missing scheme | Set header only if proxy overwrites it; `https://domain` in CSRF_TRUSTED_ORIGINS |
| WhiteNoise | Using removed `STATICFILES_STORAGE`; skipping `collectstatic` | `STORAGES` dict; `collectstatic` in deploy script |
| Chat link previews (WhatsApp/Messenger) | Side-effecting GET on invite URL | GET landing page, POST to join |
| SQLite | `select_for_update` assumed to lock | Unique constraints + `IntegrityError`; `transaction_mode: IMMEDIATE`; WAL |
| gettext | No `msgfmt` on server; `.mo` missing | Install gettext, run `compilemessages` in deploy |

## Performance Traps

Expected scale is tens of users, a handful of events; performance is not a risk. Only these matter:

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| N+1 queries on event page (wish -> user -> claim -> contributors) | Slow event page on phone | `select_related`/`prefetch_related` in the participant selector only | ~20 people x 15 wishes |
| SQLite write lock under burst claims (Christmas shopping weekend) | "database is locked" 500s | WAL + `IMMEDIATE` + timeout 20; 2-3 workers | Dozens of simultaneous writers (unlikely) |
| Prefetching claim data in owner path "for efficiency" | Leak via shared queryset helper | Separate owner queryset (Pitfall 1) | Always |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Owner can reach claim endpoints or see differing errors | Claim existence leaks (HIGH) | Scoped querysets, uniform 404, ownership check before state check |
| Claim/receive/unclaim via GET | Chat previews/prefetch trigger state changes (HIGH) | POST + CSRF only |
| Invite token = guessable/permanent/public | Strangers see all wishes and claims (HIGH) | `token_urlsafe`, revoke/regenerate, member removal |
| Event URLs with sequential IDs | Enumeration of events (MEDIUM) | UUID/opaque slugs; membership check regardless |
| Per-user HTML cached by CDN/middleware | Cross-user page serving (HIGH) | No HTML caching; `private, no-store` |
| Public `/admin/`, claims registered in admin | Spoilers, brute force (MEDIUM) | Rename path, strong password, no claim admin |
| `javascript:` links in wish links | XSS (MEDIUM) | `URLField`, http(s) only |
| Committed secret key / OAuth client secret | Session forgery, account takeover (HIGH) | Env vars, new prod key, rotate leaked secrets |
| `DEBUG=True` live | Source/settings disclosure (HIGH) | Env-driven, `check --deploy` gate |
| Unsupported Django (5.1 EOL) | Known CVEs (MEDIUM-HIGH) | Upgrade to 5.2 LTS now |
| Old password `/login/` kept alongside Google | Weak back door (MEDIUM) | Remove route |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Claim without confirm/undo on phone | Accidental claims block others from buying | Confirm step or visible undo |
| Flat wish list across people | Buying for the wrong person | Group by person |
| Empty event pages (no wishes shared yet) | Relatives think app is broken | Empty-state copy; "share all my wishes" default on join |
| Jargon ("claim", "chip in") | Non-technical relatives confused | Plain Czech wording tested on a relative ("Beru to" / "Přidám se") |
| Login failure shown as raw Google error | Relative gives up | In-app-browser detection with clear instruction |
| No way to see what I already claimed | Duplicate buying, lost track | "My claims" page independent of events |
| Giftee sees disabled/blocked controls on claimed wishes | Secrecy leak | Uniform controls |
| Stale page after another user claims | Confusing error | Friendly "just taken" message with refreshed state |
| Chip-in with no way to coordinate (no comments) | Contributors can't agree who pays what | Show claimer's name; coordination happens in the family chat; consider this in help text |

## "Looks Done But Isn't" Checklist

- [ ] **Giftee secrecy:** Often missing the owner-POSTs-to-claim-endpoint case; verify sentinel test + toggle-claim-diff test on every owner-reachable page.
- [ ] **Claim race:** Often missing a DB unique constraint; verify with a two-thread `TransactionTestCase`.
- [ ] **Invite link:** Often missing revoke/regenerate and POST-to-join; verify with `curl` GET that membership is unchanged.
- [ ] **Google login:** Often only tested with the author's account; verify with a non-test-user Google account on a phone, from a WhatsApp link, on the production domain.
- [ ] **Event in two groups:** Often missing the disjoint-members test; verify claimer name rule.
- [ ] **Owner edit/delete of claimed wish:** Often silently destroys claim; verify claimer sees "changed/removed", Claim rows survive.
- [ ] **Received flow:** Often button only on claimed; verify identical owner UI with/without claim, and undo works.
- [ ] **i18n:** Often missing plural/forms and compiled `.mo`; verify page renders in cs on production, counts 1/2/4/5/11/21 correct.
- [ ] **Mobile:** Often missing viewport, tap targets; verify on real devices.
- [ ] **Static/HTTPS:** Often missing `collectstatic`/proxy header; verify admin is styled and no mixed content on the live domain.
- [ ] **Backups:** Often missing restore test; verify a restored copy boots and shows data.
- [ ] **Settings:** `python manage.py check --deploy` is clean; DEBUG false; new SECRET_KEY.
- [ ] **Django version:** On 5.2 LTS (or newer supported), not 5.1.4.
- [ ] **Old login route:** `/login/` removed/redirected.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Claim leaked to giftee | HIGH (trust, surprise ruined, unrecoverable) | Fix, disclose to affected users; prevention is the only real strategy, so invest in tests |
| Duplicate claims from race | LOW | Add unique constraint + migration deduplicating (keep earliest), notify the later claimer |
| DB wiped on ephemeral host | HIGH | Restore from latest backup; if none, users re-enter wishes; sets back the whole family event |
| Wrong/missing `AUTH_USER_MODEL` after data exists | HIGH | New DB with data export/import script; avoid by deciding now |
| Redirect URI mismatch at launch | LOW | Add exact URI in Google console (propagation is minutes) |
| Consent screen stuck in Testing | LOW | Publish; recheck with non-test account |
| Invite link leaked to outsiders | LOW-MEDIUM | Regenerate link, remove members; requires the UI to exist |
| i18n retrofit | MEDIUM-HIGH | Mechanical wrapping + `makemessages`; larger the codebase, the worse; do it from phase 1 |
| Static files missing in prod | LOW | `collectstatic`, correct `STORAGES` |
| Migrations destroy live data | HIGH | Restore backup; always backup before migrating once data is real |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 Claim data reachable by giftee | P-Wishes (model), P-Claims | Sentinel crawl test as giftee; owner-HTML-identical test |
| 2 IDOR / oracle responses | P-Foundation convention; P-Events/Wishes/Claims | Negative authz tests per view; uniform 404 |
| 3 Side-channel leaks | P-Wishes, P-Claims | Owner page byte-diff with/without claim |
| 4 Edit/delete of claimed wish | P-Wishes, P-Claims | Claimer sees change/removal; Claim survives delete |
| 5 Giftee also participant/creator | P-Events, P-Claims | Event page excludes own wishes; creator has no extra claim visibility |
| 6 Cross-event claimer disclosure | P-Wishes/P-Claims (decision in discuss) | Two-event, disjoint-members test |
| 7 Notifications/emails/messages | P-Claims, P-Launch | No email backend in v1; recipient assertion if added |
| 8 Received flow | P-Claims | Button always shown; undo; claims retained |
| 9 Claim races / SQLite | P-Claims | Unique constraint; two-thread TransactionTestCase |
| 10 Invite link abuse/previews | P-Events | GET has no side effects; revoke works |
| 11 Google OAuth in the real world | P-Auth, P-Launch | Non-test account on phone via WhatsApp/Messenger on prod domain |
| 12 Account/model/linking | P-Foundation, P-Auth | Single author account; `/login/` gone; custom user model in 0001 |
| 13 Dev settings in prod; EOL Django | P-Foundation, P-Launch | `check --deploy` clean; Django 5.2 LTS |
| 14 Static files / removed setting | P-Foundation | Live admin styled; smoke test |
| 15 SQLite/ephemeral FS/backups | P-Foundation, P-Launch | Persistent volume or Postgres; restore drill |
| 16 Data-science requirements | P-Foundation | Fresh venv install < 1 min, no torch |
| 17 i18n and Czech plurals/grammar | P-Foundation, all phases, P-Polish | cs render smoke test; counts 1/2/4/5/11 |
| 18 Mobile | P-Foundation, P-Polish | Real-device pass |
| 19 Chip-in complexity | P-Claims | Contribution table in same migration as Claim |
| 20 Wish-to-event sharing model | P-Wishes | Empty states; unshare rule tested |
| 21 Link XSS | P-Wishes | `javascript:` rejected |
| 22 Admin exposure | P-Foundation, P-Claims | Admin path changed; claims not in admin |
| 23 Django view defaults | P-Foundation | All mutating endpoints POST-only; add view fixed |
| 24 Caching / shared devices | P-Foundation, P-Launch | `no-store` header on auth pages |
| 25 allauth config | P-Auth | Social-only flow, no emails sent |
| 26 Secrets management | P-Foundation | `.gitignore`; env-only secrets |
| 27 Deploy-last schedule risk | P-Foundation (walking skeleton), P-Launch | Production deploy within first 2 weeks |
| 28 No family dry-run | P-Launch | 2-3 real relatives complete the flow |
| 29 Scope creep | all | Out-of-scope gate in plan review |

## Research Flags for Phases

- **P-Auth:** Needs deeper research (in-app browser behaviour per app/OS, allauth settings for the exact installed version, consent-screen publishing steps).
- **P-Claims:** Needs a design discussion (claim release with contributors, cross-event name visibility, claim-visible-after-unshare) before planning.
- **P-Foundation (deploy):** Needs a host decision first; research depends on the chosen host (volume vs. Postgres, proxy headers).
- **P-Wishes, P-Events, P-Polish:** Standard Django patterns; unlikely to need research beyond the pitfalls above.

## Sources

- Django 5.1 release notes (LoginRequiredMiddleware, SQLite `transaction_mode` and `init_command`, removal of `STATICFILES_STORAGE`): https://docs.djangoproject.com/en/5.1/releases/5.1/ (HIGH)
- Django `select_for_update` docs (no-op on SQLite, requires atomic on supporting DBs, TestCase caveat): https://docs.djangoproject.com/en/5.1/ref/models/querysets/#select-for-update (HIGH)
- django-allauth Google provider docs (redirect URI format, consent screen, SocialApp vs settings): https://docs.allauth.org/en/latest/socialaccount/providers/google.html (HIGH)
- django-allauth socialaccount settings (`LOGIN_ON_GET`, `EMAIL_AUTHENTICATION`, `AUTO_SIGNUP`, `ONLY`): https://docs.allauth.org/en/latest/socialaccount/configuration.html (HIGH)
- Google: embedded webview OAuth block (`disallowed_useragent`): https://developers.googleblog.com/en/upcoming-security-changes-to-googles-oauth-20-authorization-endpoint-in-embedded-webviews/ (HIGH for policy; MEDIUM for which chat apps are affected today)
- Google OAuth consent screen Testing status limits (100 test users, 7-day expiry): https://support.google.com/cloud/answer/10311615 (MEDIUM; summarized via search)
- Django tickets on Czech plural forms (#30439, #30535): https://code.djangoproject.com/ticket/30439, https://code.djangoproject.com/ticket/30535 (MEDIUM; exact header for current Django cs catalog to be verified locally)
- Project files read: `.planning/PROJECT.md`, `src/gifter/models.py`, `views.py`, `src/web/settings.py`, `urls.py`, templates, `requirements.txt`, `.gitignore` (HIGH)
- Domain reasoning on secrecy leaks, invite-link abuse, and schedule risk: author analysis based on the PROJECT.md design (MEDIUM; no single external post-mortem source)

---
*Pitfalls research for: group gift-wishlist web app (Django 5.1, secret claiming)*
*Researched: 2026-10-15*
