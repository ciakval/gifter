# Phase 1: Google Sign-in Live - Research

**Researched:** 2026-10-16
**Domain:** Django 6.1 + django-allauth (Google only) + Docker/Caddy/GHCR deploy on Bombur, SQLite
**Confidence:** HIGH for the allauth/Django behaviour and the Docker image (both prototyped and run this session); MEDIUM for in-app browser behaviour and the Google Console click-path (policy confirmed, per-app behaviour and UI labels are not)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Minimal landing page: app name/logo, one sentence explaining what Gifter is, and a prominent "Sign in with Google" button. No multi-step explainer, no marketing content.
- **D-02:** Signed-in users land on a placeholder home ("Hi <name>, you're signed in" + sign-out). This page lives at the URL/view that Phase 2 will turn into "My events", so it is not throwaway routing. Signed-in users hitting `/` should get this home (or be redirected to it) rather than the sign-in pitch.
- **D-03:** The landing button starts the Google OAuth flow directly — a `<form method="post">` to allauth's Google provider login URL (keeps `SOCIALACCOUNT_LOGIN_ON_GET = False`). No intermediate allauth login page in the normal path.
- **D-04:** `LOGIN_URL` points at the landing page; protected pages (AUTH-03) redirect there with `next` preserved, and the landing button carries `next` through the OAuth round trip so the user returns to the original page. allauth's own `/accounts/login/` may still exist as a fallback but should be styled consistently or redirect to the landing page — planner's choice.
- **D-05:** Phase 1 ships English text only. All strings are wrapped for translation (`{% translate %}`, `gettext_lazy`), `LocaleMiddleware` and `LANGUAGES = [en, cs]` are configured now, but the Czech catalogue and the language switcher are Phase 4.

### Claude's Discretion
The user chose not to discuss the following. Follow the research recommendations in `.planning/research/` and `.claude/CLAUDE.md`:
- **In-app browser hint (OPS-04):** detection scope (at least Messenger/FB, Instagram; others such as TikTok/LinkedIn if cheap), banner vs blocking interstitial, copy-link button and/or Android intent deep link. It must replace the Google button (or precede it) so users never hit Google's `disallowed_useragent` error.
- **Accounts & admin:** custom user model (`AbstractUser` subclass) before the first prod migration; display name sourced from Google profile; session length long enough that relatives effectively stay signed in (AUTH-02); admin moved off `/admin/` with only the author as staff.
- **Dev & deploy setup:** repo layout (`pyproject.toml` + `uv`, keep or flatten `src/`), how local dev signs in (separate Google OAuth dev client with `127.0.0.1` redirect is the default), whether a staging environment is worth it, CI gates (tests + `manage.py check --deploy` + `makemigrations --check` block deploy). Follow bombur-infra conventions and the `~/GIT/plachtis` reference app.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. (Phase boundary: no events, invites, wishlists, claims — Phases 2–3; no Czech catalogue / language switcher / backups — Phase 4.)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OPS-01 | Django 6.1, minimal pinned dependency set | Five runtime deps, `pyproject.toml` + `uv.lock` (Standard Stack); prototype resolved and ran on Django 6.1.2 |
| OPS-02 | Prod settings from env (new `SECRET_KEY`, `DEBUG` off, `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`) | Settings skeleton using django-environ, fail-closed secret; `check --deploy --fail-level WARNING` passes (verified) |
| OPS-03 | Reachable at https://gifter.remesh.cz via GH Actions → GHCR → Compose, SQLite in `./data` | Dockerfile built and run as uid 1000 with bind mount; compose/deploy.yml/Caddy/DEPLOYMENT.md from bombur-infra; WAL verified |
| OPS-04 | In-app browser hint instead of Google error | Server-side UA detection in landing view, hint replaces the button, "continue anyway" escape hatch, copy-link |
| AUTH-01 | Google is the only login; old `/login/` removed | `SOCIALACCOUNT_ONLY = True` removes signup/password routes (verified: 404); old route + template deleted; admin login redirected to Google |
| AUTH-02 | Stays signed in across browser sessions; sign out | Django persistent session cookie, `SESSION_COOKIE_AGE` 90 d (verified Max-Age 7776000); POST logout |
| AUTH-03 | Everything except landing requires sign-in, returns after login | `LoginRequiredMiddleware` + `login_not_required` + `LOGIN_URL="landing"`; `next` round-trip verified end to end with mocked Google |
</phase_requirements>

## Summary

The whole auth path was prototyped in a scratch project (`/tmp`, not the repo) on Django 6.1.2 + django-allauth 65.19.7 and exercised with the Django test client, including a mocked Google callback: landing page (200), anonymous `/home/` (302 to `/?next=/home/`), `POST /accounts/google/login/` with `next` (302 to `accounts.google.com`, `next` stored in session state), callback (user created from Google `given_name`/`family_name`, redirect to `next`), 90-day persistent cookie, POST logout, and logged-in `/` redirecting to home. `django.contrib.sites` is **not needed**: allauth only requires it when it must build absolute URLs without a request, and the sign-in flow always has one. The Docker image was also built and run (python:3.13-slim, uid 1000, bind-mounted data dir, gunicorn 26.2.0, WhiteNoise static serving, 301 without `X-Forwarded-Proto` and 200 with it).

Three things differ from what the project docs imply and the planner must act on them: (1) **`SESSION_REMEMBER` does nothing for social login** — persistence comes entirely from Django's session cookie age, so set `SESSION_COOKIE_AGE`; (2) **`check --deploy` returns exit 0 with warnings** unless `--fail-level WARNING` is passed, and then W005 (HSTS include-subdomains) and W021 (HSTS preload) must be resolved or silenced, otherwise "passes in CI" is vacuous or red; (3) **the Django admin keeps its own password login** unless explicitly redirected, which would violate "Google is the only way to sign in". Also: the SQLite `data/` directory must exist before any DB command (`makemigrations` fails with "unable to open database file"), and CI/test runs must use dev-mode settings or the SSL redirect turns every test-client request into a 301.

**Primary recommendation:** Flatten `src/` to the repo root, add `gifter.User(AbstractUser)`, wire allauth with `SOCIALACCOUNT_ONLY=True` and settings-based Google `APPS`, protect everything with `LoginRequiredMiddleware` (`LOGIN_URL="landing"`), serve a single `/` landing view that does server-side in-app-browser detection, and ship the bombur-infra Dockerfile/compose/deploy.yml with a `test` job gating the build. The user-owned steps (DNS, server `.env`, deploy key, GH secrets, Caddy block, Google Console) should be written as one ordered checklist in `DEPLOYMENT.md` and a `checkpoint:human-action` task, because Google sign-in cannot be proven live until all of them are done.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| TLS termination, HTTP→HTTPS, domain | Reverse proxy (Caddy on Bombur) | — | Caddy owns certificates; app only trusts `X-Forwarded-Proto` |
| Google OAuth round trip (state, PKCE, token exchange) | API / Backend (allauth) | Browser (redirects) | Server-side code flow; no client-side token handling |
| "Must be signed in" gate (AUTH-03) | API / Backend (`LoginRequiredMiddleware`) | — | Default-deny at middleware, public views opt out |
| Return-to-page after login | API / Backend (`next` in allauth session state) | Browser (hidden form field) | Landing form carries `next`; allauth validates and stores it |
| In-app browser detection (OPS-04) | Frontend Server (SSR in landing view, UA regex) | Browser (copy-link JS only) | Works with no JS; decision made before the Google button is rendered |
| Session persistence / sign out | API / Backend (DB sessions, cookie age) | Browser (cookie) | Persistent cookie, POST logout |
| Static assets (vendored Bootstrap) | Frontend Server (WhiteNoise in gunicorn) | — | Caddy only proxies (bombur-infra convention) |
| Persistence | Database / Storage (SQLite WAL in `./data`) | — | Bind-mounted host dir survives redeploys |
| Build/deploy | CI (GitHub Actions) | Bombur (Compose) | Image tagged by SHA, `up -d` on server |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | `>=6.1,<6.2` (6.1.2 resolved) | Framework | Locked by PROJECT.md; `LoginRequiredMiddleware`, `login_not_required` built in [VERIFIED: pip resolution + read `django/contrib/auth/middleware.py` `class LoginRequiredMiddleware`] |
| django-allauth | `>=65.19,<66` (65.19.7 resolved) | Google login | Runs on 6.1; sites framework optional [VERIFIED: read `allauth/app_settings.py:23` `return apps.is_installed("django.contrib.sites")`] |
| django-environ | `>=0.14,<0.15` (0.14.0) | Env parsing | Per STACK.md; worked in prototype |
| gunicorn | `>=26,<27` (26.2.0) | WSGI | Ran in container, 2 sync workers |
| whitenoise | `>=6.12,<7` (6.12.0) | Static files | Served `/static/admin/css/base.css` from the container with no login |

No psycopg, no crispy-forms, no django-htmx, no pytest in Phase 1 (nothing uses them yet; add when the phase that needs them lands). Tests use Django's built-in runner (zero deps). Dev group empty at first (add `ruff` if the planner wants lint in CI).

### Vendored front end (committed into `gifter/static/vendor/`)
| Asset | Version | Files (verified present in the npm tarball) |
|-------|---------|------|
| Bootstrap | 5.3.8 | `dist/css/bootstrap.min.css`, `dist/js/bootstrap.bundle.min.js` [VERIFIED: `npm pack bootstrap@5.3.8` + `tar tzf`] |
| htmx | 2.0.11 | **Not needed in Phase 1** — vendor it in Phase 2 with the first interactive view |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| django-environ | plain `os.environ` | Removes a dependency; STACK.md already chose environ, keep it |
| Flat repo root | keep `src/` | `src/` needs `WORKDIR /app/src` and path edits in every template from bombur-infra; flattening is a one-time `git mv` |
| allauth `/accounts/login/` page styled | redirect it to `/` | Redirect is less code and one source of truth (recommended below) |

**Installation / lock:**
```bash
uv init --bare   # or hand-write pyproject.toml (see Code Examples)
uv lock          # produces uv.lock (commit it)
uv sync          # local dev; Docker uses `uv sync --frozen --no-dev`
```
**Version verification:** resolved this session in a clean venv: Django 6.1.2, django-allauth 65.19.7, django-environ 0.14.0, gunicorn 26.2.0, whitenoise 6.12.0 [VERIFIED: `uv pip list`]. uv itself: 0.13.1 on PyPI [VERIFIED: pypi.org JSON]; local box has 0.12.19; pin the Docker image `ghcr.io/astral-sh/uv:0.13.1` (built successfully).

## Package Legitimacy Audit

| Package | Registry | Age (first upload) | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| Django | PyPI | 2010 (445 releases) | seam: unavailable | github.com/django/django | SUS (seam: `too-new`, `unknown-downloads`) | Approved on evidence below; consolidated checkpoint |
| django-allauth | PyPI | 2011 (140 releases) | seam: unavailable | codeberg.org/allauth/django-allauth | SUS (`too-new`, `unknown-downloads`) | Same |
| gunicorn | PyPI | 2010 (100 releases) | seam: unavailable | gunicorn.org | SUS (`unknown-downloads`) | Same |
| whitenoise | PyPI | 2013 (60 releases) | seam: unavailable | none listed on PyPI | SUS (`unknown-downloads`, `no-repository`) | Same |
| django-environ | PyPI | 2013 (25 releases) | seam: unavailable | django-environ.readthedocs.org | SUS (`unknown-downloads`) | Same |
| bootstrap (vendored, not installed) | npm | 2011+ | 5.9M/wk | github.com/twbs/bootstrap | OK | Approved |

`gsd-tools query package-legitimacy check --ecosystem pypi …` returned SUS for all five. The reasons are artefacts: `too-new` is the date of the *latest release* (days/weeks old), and the seam has no PyPI download statistics. I cross-checked first-upload dates and release counts directly on the PyPI JSON API (table above): all are 12–16-year-old, multi-release projects, and Django/allauth are documented at djangoproject.com / docs.allauth.org. **Planner: add one `checkpoint:human-verify` immediately before the first `uv lock`/`uv sync` that shows the user these five names and versions** (one checkpoint, not one per package). Packages removed (SLOP): none.

## Architecture Patterns

### System Architecture Diagram

```
Phone (Chrome/Safari/Messenger/Instagram)
   │ https://gifter.remesh.cz/…
   ▼
Caddy container (443, auto-TLS)  ──sets X-Forwarded-For/Proto/Host (ignores client-supplied)──┐
   │ reverse_proxy gifter-web:8000 over external docker network "proxy"                        │
   ▼                                                                                           │
gifter-web container (uid 1000): gunicorn ── 2 sync workers ── Django                          │
   │                                                                                           │
   ├─ SecurityMiddleware (SSL redirect unless XFP=https) ◄─────────────────────────────────────┘
   ├─ WhiteNoise  ── /static/* served here, before any login check
   ├─ Session → Locale → Common → CSRF → Authentication
   ├─ LoginRequiredMiddleware
   │     anonymous + view not @login_not_required ──► 302 /?next=<path>  (LOGIN_URL="landing")
   ├─ AccountMiddleware (allauth)
   ▼
 urls:  /                    landing  (@login_not_required)
                              ├ authenticated → 302 home
                              ├ in-app browser UA → hint card (+ "continue anyway", copy link)
                              └ else → <form POST /accounts/google/login/> + hidden next
        /events/ (name=home) placeholder "Hi <name>" + POST sign-out        (login required)
        /accounts/login/     → login_not_required redirect to landing (query kept)
        /accounts/…          allauth (Google login, callback, logout, error pages)
        /<admin-slug>/       Django admin; its /login/ redirected to landing; staff only
   │
   ▼  POST /accounts/google/login/ ─► 302 accounts.google.com (state+PKCE in session)
      Google ─► GET /accounts/google/login/callback/?code&state ─► token exchange (server→Google)
      ─► user get_or_create (gifter.User) ─► session cookie (90 d) ─► 302 next | home
   │
   ▼
SQLite /app/data/db.sqlite3 (WAL)  ◄── bind mount ── host ~/DOCKER/gifter/data
```

### Recommended Project Structure (flattened)
```
.                              # repo root = Docker build context
├── manage.py
├── pyproject.toml / uv.lock
├── Dockerfile / .dockerignore / compose.yaml / .env.example / DEPLOYMENT.md
├── .github/workflows/deploy.yml
├── web/                       # settings.py (env-driven), urls.py, wsgi.py
├── gifter/
│   ├── models.py              # User(AbstractUser) (+ Wish repointed, see Pitfall 9)
│   ├── views.py               # landing, home
│   ├── inapp.py               # is_in_app_browser(user_agent)
│   ├── urls.py
│   ├── management/commands/promote_staff.py
│   ├── templates/gifter/{base,landing,home}.html
│   ├── templates/allauth/layouts/base.html     # extends gifter/base.html (restyles allauth pages)
│   ├── templates/socialaccount/{authentication_error,login_cancelled}.html
│   ├── static/gifter/…  static/vendor/bootstrap/…
│   ├── migrations/0001_initial.py              # regenerated
│   └── tests/ (test_auth.py, test_inapp.py)
└── data/                      # gitignored, created by settings
```
Delete: `src/gifter/settings.py` (empty), `requirements.txt`, `registration/login.html`, `create_wish.html`, `forms.py`, `CreateWishView` and the `gifter/add` route (Phase 2 rebuilds wishes). Add a root `.gitignore` (`data/`, `.env`, `staticfiles/`, `.venv/`, `*.sqlite3*`, `__pycache__/`).

### Pattern 1: Default-deny auth with explicit public views
**What:** `LoginRequiredMiddleware` after `AuthenticationMiddleware`; every view is private unless decorated `login_not_required`. allauth's own views are already decorated, so `/accounts/google/login/` and the callback work for anonymous users [VERIFIED: `allauth/account/views.py:98-100` `@method_decorator(login_not_required)`; behaviour confirmed by test run]. Unresolvable URLs still 404 (not redirect). WhiteNoise serves static before the check.
**Example:** see Code Examples (settings, urls, views).

### Pattern 2: Landing page doubles as LOGIN_URL
`LOGIN_URL = "landing"` makes the middleware redirect to `/?next=/some/page/`; the landing view puts `request.GET["next"]` in a hidden field of the Google form. allauth validates `next` (safe-URL check) and stores it in the OAuth state [VERIFIED: test run showed session `{'process': 'login', …, 'next': '/home/'}` and callback `Location: /home/`]. Because the Phase 2 invite flow also redirects anonymous users here with `next=/join/<token>/`, the in-app-browser hint on the landing page automatically covers invite links.

### Pattern 3: Google-only admin
Mount allauth, and place a `login_not_required` `RedirectView` for `<admin>/login/` **before** `admin.site.urls` (and for `accounts/login/` before `include("allauth.urls")`). Staff then reach admin via their Google session. Verified: staff user 200, non-staff gets bounced to landing then home with no loop. Drop `ModelBackend` from `AUTHENTICATION_BACKENDS` (allauth docs: "Do not add ModelBackend solely for username login in Django admin"); verified permissions and admin still work with only the allauth backend. To make the author staff, no password exists, so use a management command run after the author's first Google sign-in (see Code Examples).

### Anti-Patterns to Avoid
- **`SOCIALACCOUNT_LOGIN_ON_GET = True`:** login CSRF via link; D-03 already forbids it. Default is `False` [VERIFIED: `allauth/socialaccount/app_settings.py:143` `return self._setting("LOGIN_ON_GET", False)`].
- **`SocialApp` DB row *and* settings `APPS`:** `MultipleObjectsReturned`. Use settings only; do not register `socialaccount` admin entries.
- **`ACCOUNT_SESSION_REMEMBER` for persistence:** only read by the password login form [VERIFIED: `allauth/account/forms.py:231`, inside `_login_with_password`]; ignored for Google login.
- **Adding `django.contrib.sites`/`SITE_ID`:** unnecessary here and brings the `example.com` pitfall.
- **Putting prod-only SSL settings unconditionally:** breaks local `http://127.0.0.1:8000` and the test client.
- **`docker compose down` / `docker system prune` in deploy** (bombur-infra pitfalls): shared host.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth state/nonce/PKCE/token exchange/account linking | custom `requests` code | allauth Google provider | `OAUTH_PKCE_ENABLED` and state handled; prototype shows state+next stored |
| "Everything requires login" | per-view decorators / custom middleware | `LoginRequiredMiddleware` + `login_not_required` | Built in since Django 5.1; forgetting a view fails closed |
| Safe `next` handling | own redirect parsing | allauth/Django `redirect_to_login` + safe-URL check | Open-redirect prevention |
| Static serving/compression | Caddy file_server config | WhiteNoise `CompressedManifestStaticFilesStorage` | bombur-infra convention: Caddy only proxies |
| Env parsing | ad-hoc `os.environ` casting | django-environ (`env.list`, `env.bool`, `NOTSET` default) | Fail-closed `SECRET_KEY` |
| Secret generation | Django `get_random_secret_key()` | `openssl rand -base64 48` / `secrets.token_urlsafe(64)` | Django's alphabet contains `$`, which Compose may interpolate in `.env` [ASSUMED] |
| Webview detection list | a library | a ~10-line regex in `gifter/inapp.py` | Only need "is this likely an embedded webview"; false positives are cured by "continue anyway" |

## Runtime State Inventory

Phase 1 swaps the user model and flattens the repo, but nothing has ever been deployed, so there is no live state to migrate. Answered explicitly:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None in production (no deploy exists). No `db.sqlite3` is tracked in git (`git ls-files` shows none). Any local dev DB built with `auth.User` is invalid after the swap | Delete local `db.sqlite3`; regenerate `0001_initial.py` (code edit, not data migration) |
| Live service config | None — Google OAuth client, DNS, Caddy block, GH secrets do not exist yet | Create (user checklist) |
| OS-registered state | None | None |
| Secrets/env vars | The committed `SECRET_KEY` (`src/web/settings.py:23`: `SECRET_KEY = "django-insecure-4&zdy#x%n99(uuelq4b6+kl_fhpivjvao$!2uago2rnil#^-wa"`) is in git history permanently | Never use it; new key lives only in server `.env`; keep out of CI logs |
| Build artifacts | None installed from this repo (`requirements.txt` is a data-science dump to delete) | Delete; `uv.lock` replaces it |

## Common Pitfalls

### Pitfall 1: `check --deploy` "passes" but means nothing, or fails on advisory warnings
**What goes wrong:** the command exits 0 on warnings. With `--fail-level WARNING`, a correct production config still reports W005 and W021 [VERIFIED: ran it: `security.W005 … SECURE_HSTS_INCLUDE_SUBDOMAINS`, `security.W021 … SECURE_HSTS_PRELOAD`].
**How to avoid:** set `SECURE_HSTS_INCLUDE_SUBDOMAINS = True` (the header is scoped to `gifter.remesh.cz`, it does not touch other `remesh.cz` apps) and `SILENCED_SYSTEM_CHECKS = ["security.W021"]` with a comment (no preload). Verified result: `System check identified no issues (1 silenced).` exit 0. Run it in CI with `DEBUG=0`, a random 64-char `SECRET_KEY`, `PUBLIC_HOSTS=gifter.remesh.cz`.
**Warning signs:** CI green but `--deploy` never given `--fail-level`.

### Pitfall 2: Tests hit 301 because prod security settings are on
**What goes wrong:** `SECURE_SSL_REDIRECT=True` makes every plain-HTTP test-client request a 301 [VERIFIED: ran the app with `DEBUG=0`, no XFP header → `301 https://gifter.remesh.cz/`].
**How to avoid:** gate the whole security block on `not DEBUG`; CI runs `manage.py test` with `DEBUG=1`, and only the `check --deploy` step with `DEBUG=0`.

### Pitfall 3: `data/` missing → "unable to open database file"
**What goes wrong:** `makemigrations`/`migrate` fail on a fresh clone and in CI [VERIFIED: reproduced].
**How to avoid:** `DATA_DIR.mkdir(parents=True, exist_ok=True)` in settings.

### Pitfall 4: Bind-mounted `./data` not writable by uid 1000
**What goes wrong:** container runs as uid 1000; the host dir is created by the deploy user's `mkdir -p data` in the workflow. If the deploy user's uid is not 1000, SQLite cannot create `db.sqlite3` / `-wal` / `-shm` (the *directory* must be writable, not just the file) [bombur-infra SKILL.md "Known pitfalls"].
**How to avoid:** on Bombur run `id -u <deploy-user>` and, if not 1000, either `chown`/set `user:` in compose. Locally the prototype ran fine as uid 1000 with a bind mount. This was an open question because I did not SSH to the server. Now resolved: the user checks `id -u` at plan 01-05 Task 1, and DEPLOYMENT.md (plan 01-04) carries the `chown` fallback (see Open Questions (RESOLVED), Q1).

### Pitfall 5: `redirect_uri_mismatch` / `http` redirect URI in production
**What goes wrong:** without `SECURE_PROXY_SSL_HEADER`, the callback URL is built with `http://`. With it, verified: `redirect_uri=https%3A%2F%2Fgifter.remesh.cz%2Faccounts%2Fgoogle%2Flogin%2Fcallback%2F`. Caddy sets `X-Forwarded-Proto` itself and ignores client-supplied values unless `trusted_proxies` is configured [CITED: caddyserver.com/docs/caddyfile/directives/reverse_proxy], so trusting the header is safe as long as the container is reachable only through Caddy (no `ports:`).
**How to avoid:** register exactly `https://gifter.remesh.cz/accounts/google/login/callback/` (trailing slash) in the Google client.

### Pitfall 6: allauth rate limits keyed on the proxy IP
**What goes wrong:** allauth ignores `X-Forwarded-For` by default [VERIFIED: `allauth/app_settings.py:59-66` `return self._setting("TRUSTED_PROXY_COUNT", 0)`]. Set `ALLAUTH_TRUSTED_PROXY_COUNT = 1` (one proxy, Caddy). Note allauth raises `ImproperlyConfigured` if an `X-Forwarded-For` header has *fewer* entries than the count [VERIFIED: `allauth/core/internal/httpkit.py:204-206`]; requests with no XFF at all are fine (curl from inside the container).

### Pitfall 7: Google error for relatives in chat-app browsers
Google blocks OAuth in embedded webviews (`disallowed_useragent`) [CITED: developers.googleblog.com/en/upcoming-security-changes-to-googles-oauth-20-authorization-endpoint-in-embedded-webviews/ — "All embedded webviews will be blocked starting on September 30, 2021"; the post tells apps to hand third-party links to the OS/Custom Tabs/SFSafariViewController]. Reports exist for Messenger (iOS), Instagram and TikTok [CITED: Auth0 community threads, via search]. See the dedicated OPS-04 section. Also: a direct visit to `GET /accounts/google/login/` (allauth confirm page) in an in-app browser bypasses the landing hint; it is unlinked, so accept it, or wrap the hint check in a tiny middleware if the planner wants belt and braces.

### Pitfall 8: Consent screen left in "Testing"
Google (support.google.com/cloud/answer/15549945): in Testing only listed test users (max 100) can sign in and authorizations lapse after seven days; In production any Google Account holder can authorize. For **basic scopes only (`openid`, `email`, `profile`)** the page states "your users do not need to be in the trusted user list, they will not see a warning message" and the 7-day expiry does not apply [CITED: support.google.com/cloud/answer/15549945]. Request exactly those scopes (set `SCOPE` explicitly; allauth's default is `profile` + `email` [CITED: docs.allauth.org Google page]) and publish. SC-2's "never added as a test user" case can only be proven live, by a second Google account.

### Pitfall 9: Wish model after the user swap
`Wish` imports `django.contrib.auth.models.User` (`src/gifter/models.py:2` `from django.contrib.auth.models import User`; lines 9 and 11 use it in two `ForeignKey`s). With `AUTH_USER_MODEL` swapped this breaks at import/migration. Either repoint to `settings.AUTH_USER_MODEL` (CONTEXT says "at least be repointed") or drop the model until Phase 2 reshapes it. Recommend repoint (honours CONTEXT; migration `0001` then contains `User` and `Wish`; Phase 2 migrates it with zero prod data). Do **not** hand-edit the generated migration.

### Pitfall 10: Session invalidation and cookie lifetime surprises
Django's default is a 2-week persistent cookie [ASSUMED from Django defaults; prototype with `SESSION_COOKIE_AGE=7776000` showed `Max-Age 7776000`]. Rotating `SECRET_KEY` later logs everyone out (session auth hash). Fine for Phase 1; note it in DEPLOYMENT.md. Add `clearsessions` to ops notes only if wanted (tens of users).

### Pitfall 11: Compose `.env` and CI upserts
The deploy workflow `sed`-upserts `IMAGE_TAG` etc. into `.env`; secrets live in the same file. Generate secrets with `openssl rand -base64 48`, avoid `$` and spaces, keep `chmod 600` (workflow does `touch .env && chmod 600 .env`).

### Pitfall 12: gettext not required yet
bombur-infra/plachtis Dockerfile installs `gettext` and runs `compilemessages`; Phase 1 has no `.po` files (Czech is Phase 4). Do not add the apt layer or the build step now; add both in Phase 4. Strings must still be wrapped (D-05).

## OPS-04: In-app browser hint (recommended design)

- **Detect server-side** in the landing view from `request.META["HTTP_USER_AGENT"]`; no JS needed for the decision. Regex (case-insensitive) covering Facebook/Messenger (`FBAN|FBAV|FB_IAB|FBIOS|FB4A|Messenger`), `Instagram`, TikTok (`BytedanceWebview|musical_ly|TikTok`), `LinkedInApp`, `Snapchat`, and Android WebView (`; wv\)`). These tokens come from open-source detector lists seen in search results and the Android `wv` convention [ASSUMED — not verified on real devices; confirm with a real iPhone and Android phone in Messenger/Instagram].
- **Behaviour:** when matched, render a Bootstrap card *instead of* the Google button: plain-language "Google doesn't allow sign-in inside this app's browser. Open this page in Chrome or Safari", a **Copy link** button (copies `request.build_absolute_uri()` *including* `next`), and numbered steps: open the ⋯/menu → "Open in browser" / "Open in Safari" (labels [ASSUMED]; menu wording varies by app and OS). Add a small secondary link **"Continue anyway"** (`?force=1`, preserving `next`) that shows the normal button, because detection is heuristic and a false positive must not lock someone out.
- **Do not use an Android `intent://` deep link in Phase 1.** A Meta developer-community report says Instagram's browser does not launch `intent://` URLs [CITED: developers.secure.facebook.com/community/threads/470205278761649 — user report, not official]; there is no iOS equivalent. Copy-link + steps is the reliable path. Real-device verification belongs in the human UAT at end of phase (config `human_verify_mode: end-of-phase`) and again in Phase 4.
- **Copy-link JS:** `navigator.clipboard.writeText` needs HTTPS and a user gesture (satisfied); fall back to a read-only `<input>` that is selected on tap. Keep it in a static `landing.js` (no CSP configured in Phase 1).
- **Not CSP:** Django 6's built-in `ContentSecurityPolicyMiddleware` is available (STACK.md) but enabling it in Phase 1 adds breakage risk for no requirement; defer.

## Dev & deploy decisions (resolving the "discretion" items)

| Item | Recommendation | Reason |
|------|----------------|--------|
| Layout | Flatten `src/*` to repo root via `git mv` | bombur-infra/plachtis Dockerfile pattern assumes root `manage.py`; one less `WORKDIR` quirk |
| App count | One app, `gifter`, owns `User` (`AUTH_USER_MODEL = "gifter.User"`) | ARCHITECTURE.md: single domain app. Its "keep `auth.User`" line is superseded by PROJECT.md/STACK.md/CONTEXT |
| Env var names | `SECRET_KEY`, `DEBUG`, `PUBLIC_HOSTS` (host list → derive both `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS=https://<host>`), `DATA_DIR`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SECURE_HSTS_SECONDS` | `PUBLIC_HOSTS` matches the bombur-infra `.env.example`; deriving the origins removes the "scheme missing" CSRF 403 pitfall |
| Local dev sign-in | Separate Google OAuth client, redirect `http://127.0.0.1:8000/accounts/google/login/callback/`, creds in gitignored `.env` loaded by `environ.Env.read_env()` | CONTEXT default |
| Staging | None for Phase 1 | Walking skeleton goes straight to prod; `-test` env doubles the Caddy/DNS/Google redirect work. Add later only if needed |
| Tests | Django built-in runner | Zero deps; add pytest-django when Phase 3's secrecy suite needs it |
| CI gates | `test` job (check, `check --deploy --fail-level WARNING`, `makemigrations --check --dry-run`, `manage.py test`) → `build-and-push` `needs: test` → deploy | Matches bombur-infra's "add a test job" note |
| Gunicorn | 2 sync workers | SQLite writer concurrency; STACK/PITFALLS say 2–3 max |
| Observability | Keep the `OTEL_*` lines in compose/`.env.example` but add no instrumentation | bombur-infra says apps must run fine without an endpoint; OTLP/error tracking is OPS-07 (v2) |
| Healthcheck | None | Direct container requests get SSL-redirected; Caddy/`docker compose ps` suffice |
| Session length | `SESSION_COOKIE_AGE = 60*60*24*90` | Covers Christmas season; verified |
| Admin path | non-default slug (e.g. `gifter-admin/`) | CONTEXT; keep it out of the landing page |

## Code Examples

All of this ran in the scratch prototype unless noted.

### pyproject.toml
```toml
[project]
name = "gifter"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "Django>=6.1,<6.2",
    "django-allauth[socialaccount]>=65.19,<66",
    "django-environ>=0.14,<0.15",
    "gunicorn>=26,<27",
    "whitenoise>=6.12,<7",
]
```
Local dev uses the system Python 3.14.8 (valid for Django 6.1); the image uses 3.13.

### web/settings.py (core parts)
```python
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")   # local dev only; prod passes real env via compose

DEBUG = env("DEBUG")
# Fail closed: no default in production -> ImproperlyConfigured if missing (verified)
SECRET_KEY = env("SECRET_KEY", default="dev-insecure-key" if DEBUG else environ.Env.NOTSET)
PUBLIC_HOSTS = env.list("PUBLIC_HOSTS", default=["localhost", "127.0.0.1"])
ALLOWED_HOSTS = PUBLIC_HOSTS
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in PUBLIC_HOSTS if h not in ("localhost", "127.0.0.1")]

INSTALLED_APPS = [
    "gifter",
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "allauth", "allauth.account", "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]   # no django.contrib.sites, no SITE_ID

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]
# TEMPLATES: DIRS=[BASE_DIR/"templates"] optional; APP_DIRS=True; context processors incl. request, auth, messages

DATA_DIR = Path(env("DATA_DIR", default=str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": DATA_DIR / "db.sqlite3",
    "OPTIONS": {
        "transaction_mode": "IMMEDIATE",
        "timeout": 20,
        "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
    },
}}   # verified: PRAGMA journal_mode -> 'wal', synchronous -> 1

AUTH_USER_MODEL = "gifter.User"
AUTHENTICATION_BACKENDS = ["allauth.account.auth_backends.AuthenticationBackend"]

LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("cs", "Čeština")]
TIME_ZONE = "Europe/Prague"; USE_I18N = True; USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "static/"; STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- auth ---
LOGIN_URL = "landing"
LOGIN_REDIRECT_URL = "home"
ACCOUNT_LOGOUT_REDIRECT_URL = "landing"
ACCOUNT_EMAIL_VERIFICATION = "none"          # required by SOCIALACCOUNT_ONLY (allauth system check)
SOCIALACCOUNT_ONLY = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"    # required by SOCIALACCOUNT_ONLY
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_PROVIDERS = {"google": {       # keep everything in ONE dict
    "APPS": [{"client_id": env("GOOGLE_CLIENT_ID"), "secret": env("GOOGLE_CLIENT_SECRET"), "key": ""}],
    "SCOPE": ["openid", "profile", "email"],  # basic scopes only -> no Google verification needed
    "OAUTH_PKCE_ENABLED": True,
    "AUTH_PARAMS": {"prompt": "select_account"},   # optional: lets relatives pick the right Google account
}}
SESSION_COOKIE_AGE = 60 * 60 * 24 * 90
ALLAUTH_TRUSTED_PROXY_COUNT = 1

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=3600)   # raise after a week of working HTTPS
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SILENCED_SYSTEM_CHECKS = ["security.W021"]   # HSTS preload deliberately not enabled
```
Note: `GOOGLE_CLIENT_ID/SECRET` should have `default=""` guarded so `check`/CI works without real credentials (prototype used `default="x"`; CI should set dummy values rather than weakening production, which must fail loudly if unset). SQLite `OPTIONS` keys `transaction_mode`, `timeout`, `init_command` are accepted by Django 6.1.2 [VERIFIED: migrations and test client ran with them].

### web/urls.py
```python
from django.contrib import admin
from django.contrib.auth.decorators import login_not_required
from django.urls import include, path
from django.views.generic import RedirectView

to_landing = login_not_required(RedirectView.as_view(pattern_name="landing", query_string=True))

urlpatterns = [
    path("accounts/login/", to_landing),          # before the include; reverse("account_login") still resolves to allauth's
    path("accounts/", include("allauth.urls")),
    path("gifter-admin/login/", to_landing),      # before admin.site.urls: Google is the only login
    path("gifter-admin/", admin.site.urls),
    path("", include("gifter.urls")),
]
```
The `login_not_required` wrapper on the redirects is mandatory: without it the middleware redirects the redirect view to `/?next=/accounts/login/…` [VERIFIED: observed in first test run]. Old `login/` route and `auth_views` import are removed.

### gifter/models.py
```python
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    @property
    def display_name(self) -> str:
        return self.first_name or self.username


class Wish(models.Model):            # reshaped in Phase 2; repointed only
    ...
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishes")
    claimed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="claimed_wishes")
```
allauth populated `first_name`/`last_name` from Google `given_name`/`family_name` and auto-generated `username` (`anna`) with this model [VERIFIED: mocked callback]. Register `User` with `UserAdmin` in `admin.py`.

### gifter/views.py + urls.py
```python
@login_not_required
def landing(request):
    if request.user.is_authenticated:
        return redirect("home")
    ua = request.META.get("HTTP_USER_AGENT", "")
    in_app = is_in_app_browser(ua) and request.GET.get("force") != "1"
    return render(request, "gifter/landing.html", {"next": request.GET.get("next", ""), "in_app": in_app})

def home(request):                   # login required by default
    return render(request, "gifter/home.html")

urlpatterns = [path("", views.landing, name="landing"), path("events/", views.home, name="home")]
```
Always `reverse("home")`/`{% url 'home' %}`; Phase 2 swaps the view behind the same name. The path is a suggestion consistent with ARCHITECTURE.md's `/events/` space.

### landing.html (form, essential parts)
```django
{% load i18n socialaccount %}
{% if in_app %} … hint card, copy link, steps, "continue anyway" … {% else %}
<form method="post" action="{% provider_login_url 'google' %}">
  {% csrf_token %}
  <input type="hidden" name="next" value="{{ next }}">
  <button type="submit" class="btn btn-primary btn-lg">{% translate "Sign in with Google" %}</button>
</form>
{% endif %}
```
`{% provider_login_url 'google' %}` rendered `/accounts/google/login/` [VERIFIED]. Sign-out in `home.html`: `<form method="post" action="{% url 'account_logout' %}">{% csrf_token %}<button>…</button></form>`; POST logout cleared the session and redirected to `/` [VERIFIED].

### allauth page styling
Override `templates/allauth/layouts/base.html` with `{% extends "gifter/base.html" %}` (the stock layout renders a "Menu:" list of Sign Up / Change Password links [VERIFIED: read `allauth/templates/allauth/layouts/base.html`]); your base must expose `head_title` and `content` blocks. Override `socialaccount/authentication_error.html` and `socialaccount/login_cancelled.html` (user pressing Cancel on Google lands on `/accounts/3rdparty/login/cancelled/`; denied/failed callback returns a 401 error page [VERIFIED: test client]) with a friendly message and a "Try again" link to `{% url 'landing' %}`.

### promote_staff management command
```python
class Command(BaseCommand):
    def add_arguments(self, p): p.add_argument("email")
    def handle(self, *a, **o):
        u = get_user_model().objects.get(email__iexact=o["email"])   # exists after first Google sign-in
        u.is_staff = u.is_superuser = True; u.save(update_fields=["is_staff", "is_superuser"])
```
Run: `docker exec -ti gifter-web python manage.py promote_staff you@gmail.com`. No `createsuperuser` (it would create a password account).

### Dockerfile (built and run this session)
```dockerfile
FROM python:3.13-slim
ARG VERSION=dev
ARG BUILD_ID=unknown
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never PATH="/app/.venv/bin:$PATH" VERSION=${VERSION} BUILD_ID=${BUILD_ID}
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN SECRET_KEY=build-only-not-a-secret GOOGLE_CLIENT_ID=x GOOGLE_CLIENT_SECRET=x python manage.py collectstatic --noinput
RUN useradd -m -u 1000 app && mkdir -p /app/data && chown app:app /app/data
USER app
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn web.wsgi:application --bind 0.0.0.0:8000 --workers 2 --access-logfile - --error-logfile -"]
```
Observed: image builds; as uid 1000 `migrate` creates `db.sqlite3` in the bind mount; gunicorn 26.2.0 listens on 8000 (keep `useradd -m`: gunicorn 26 creates a control socket under `$HOME/.gunicorn`); `/` → 301 without XFP, 200 with `X-Forwarded-Proto: https`; static file 200 anonymously. `.dockerignore`: `.git .github .env data/ .venv/ __pycache__/ *.sqlite3* staticfiles/ .planning .claude`. The `data/` dir must be in `.dockerignore` or a developer DB is baked into the image.

### compose.yaml (from the bombur-infra asset, `__APP__`=gifter, port 8000)
```yaml
services:
  web:
    image: ghcr.io/${GITHUB_REPOSITORY:-ciakval/gifter}:${IMAGE_TAG:-latest}
    container_name: ${CONTAINER_NAME:-gifter-web}
    restart: unless-stopped
    env_file: .env
    environment:
      OTEL_SERVICE_NAME: ${OTEL_SERVICE_NAME:-gifter}
      OTEL_RESOURCE_ATTRIBUTES: deployment.environment=${DEPLOY_ENV:-production}
    volumes:
      - ./data:/app/data
    networks: [default, proxy]
networks:
  proxy:
    external: true
```
No `ports:`. `.env.example` keys: managed-by-CI block (`GITHUB_REPOSITORY`, `IMAGE_TAG`, `CONTAINER_NAME`, `DEPLOY_ENV`), app block (`SECRET_KEY`, `DEBUG=False`, `PUBLIC_HOSTS=gifter.remesh.cz`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SECURE_HSTS_SECONDS=3600`), commented OTEL block. `DATA_DIR` need not be set (default `/app/data` is `BASE_DIR/data` with `WORKDIR /app`).

### .github/workflows/deploy.yml
Start from `~/.claude/skills/bombur-infra/assets/deploy.yml` (`APP: gifter`, `DEPLOY_DIR: /home/<deploy-user>/DOCKER/gifter`; deploy user defaults to `plachtis` and is confirmed at plan 01-05's checkpoint, see Open Questions (RESOLVED), Q1) and add:
```yaml
  test:
    runs-on: ubuntu-latest
    env: { PUBLIC_HOSTS: gifter.remesh.cz, GOOGLE_CLIENT_ID: ci, GOOGLE_CLIENT_SECRET: ci }
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v10
      - run: uv sync --frozen
      - run: uv run python manage.py makemigrations --check --dry-run
        env: { DEBUG: "1" }
      - run: uv run python manage.py test
        env: { DEBUG: "1" }
      - name: check --deploy
        run: |
          export SECRET_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(64))')" DEBUG=0
          uv run python manage.py check --deploy --fail-level WARNING
```
and `needs: test` on `build-and-push`. Action versions: latest releases seen via `gh api`: checkout v7.0.1 (template uses v6, still fine), setup-uv v10.3.0, build-push-action v7.4.0, ssh-action v1.2.5, scp-action v1.0.0 [VERIFIED: gh api releases/latest]. Keep the template's `docker image prune -af --filter "until=72h"` (never `system prune`) and `up -d` without `down`.

### Tests worth writing (Django `TestCase`, `DEBUG=1`)
Anonymous `/events/` → 302 `/?next=/events/`; anonymous `/` → 200 with form posting to `/accounts/google/login/`; signed-in `/` → 302 home; `/login/`, `/accounts/signup/`, `/accounts/password/reset/`, `/admin/` → 404; `/accounts/login/?next=/events/` → 302 to `/?next=/events/`; admin login redirects to landing; POST logout ends the session; UA matrix for `is_in_app_browser` (Messenger iOS, FB Android, Instagram, TikTok vs Chrome/Safari) and `?force=1`; mocked callback creates `gifter.User` with `first_name` and redirects to `next` (pattern: patch `OAuth2Client.get_access_token` and `GoogleOAuth2Adapter.complete_login` returning `provider.sociallogin_from_response(request, info)`); `get_user_model()._meta.label == "gifter.User"`; session cookie Max-Age 7776000.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `login_required` on every view / custom middleware | `LoginRequiredMiddleware` + `login_not_required` | Django 5.1 | AUTH-03 is one setting |
| `django.contrib.sites` mandatory for allauth | optional | allauth 0.5x+ | No `SITE_ID`/Site-row migration pitfall |
| allauth `ACCOUNT_EMAIL_REQUIRED` etc. | `SOCIALACCOUNT_ONLY` removes password/signup routes | allauth 65.x | Verified 404 on `/accounts/signup/`, `/accounts/password/reset/`; POST to `/accounts/login/` forbidden [VERIFIED: `account/views.py:106`] |
| allauth trusts `X-Forwarded-For` | distrusts by default; `ALLAUTH_TRUSTED_PROXY_COUNT` | 65.14.2 (per STACK.md) | Must set to 1 behind Caddy |
| `STATICFILES_STORAGE` | `STORAGES["staticfiles"]` | Django 4.2/5.1 | Use the dict form |

**Deprecated/outdated:** Django 5.1.4 (current pin; unsupported); the `requirements.txt` env dump; hard-coded `SECRET_KEY`/`DEBUG`; `LoginView` at `/login/`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker (local) | build/verify image | ✓ | 29.9.1 (daemon reachable) | CI builds anyway |
| uv | lock/sync | ✓ | 0.12.19 local (Docker pins 0.13.1) | — |
| Python | dev | ✓ | 3.14.8 (valid for Django 6.1); image uses 3.13 | — |
| gh CLI | setting GH secrets | ✓ | 2.97.0 | web UI |
| sqlite3 CLI | inspecting DB | ✓ | present | — |
| gettext/msgfmt | `compilemessages` | ✓ local | — | Not needed until Phase 4 |
| Node/npm | only to fetch Bootstrap | ✓ | v22.22.2 | download from getbootstrap.com |
| Bombur access (SSH, Caddy, DNS) | deploy | ✗ not probed | — | **User-only steps** (not touched this session) |
| Google Cloud Console access | OAuth client + publish | ✗ user-only | — | none; blocks SC-2 |
| GitHub remote | CI | ✓ `git@github.com:ciakval/gifter.git` | — | — |

**Missing dependencies with no fallback:** Google Console and Bombur steps (user).

## User-only checklist (put in DEPLOYMENT.md and a `checkpoint:human-action` plan task)

Order matters: Let's Encrypt needs DNS first; Google redirect URI needs the domain; the first push needs secrets.
1. DNS: CNAME `gifter.remesh.cz` → `bombur.remesh.cz`.
2. Server: confirm the deploy user (default `plachtis`, confirmed at plan 01-05's checkpoint; see Open Questions (RESOLVED), Q1); `mkdir -p ~/DOCKER/gifter/data && cd ~/DOCKER/gifter`; create `.env` from `.env.example` (`openssl rand -base64 48` for `SECRET_KEY`), `chmod 600 .env`. `id -u` of the user must be 1000 or `data/` must be chowned.
3. Deploy key: `ssh-keygen -t ed25519 -f gifter-deploy -N ''`; append `.pub` to the deploy user's `authorized_keys`.
4. GitHub secrets: `VPS_HOST=bombur.remesh.cz`, `VPS_SSH_PORT=10022`, `VPS_USER`, `VPS_SSH_KEY` (via `gh secret set`).
5. Caddy (as `ciakval`, confirm before editing — shared): add `gifter.remesh.cz { reverse_proxy gifter-web:8000 }` to `/home/ciakval/DOCKER/web/Caddyfile`, `docker exec caddy caddy validate …` then `caddy reload`; if the edit is not visible in the container, restart the caddy compose project (single-file bind mount inode issue).
6. Google Cloud Console: project → OAuth consent screen (the console now brands this "Google Auth Platform"; menu labels [ASSUMED]) → External → app name, support email → scopes only `openid`, `email`, `profile` → **Publish app / "In production"**. Create OAuth client "Web application" with authorized redirect URIs `https://gifter.remesh.cz/accounts/google/login/callback/` and (second client for dev) `http://127.0.0.1:8000/accounts/google/login/callback/`; JavaScript origins are not needed for the server-side flow. Put the client id/secret into the server `.env`.
7. Push to `main`; watch the Actions run; `curl -I https://gifter.remesh.cz`; sign in with the author's Google account, then `promote_staff`; sign in with a *second* Google account that was never added anywhere (SC-2) and from the Messenger/Instagram in-app browser on a real phone (SC-4).

## Security Domain

`security_enforcement` is enabled (ASVS level 1, block on high).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | allauth Google code flow with state + PKCE; no passwords; admin password login removed |
| V3 Session Management | yes | DB sessions, `SESSION_COOKIE_SECURE`, HttpOnly (Django default), 90-day age, POST logout, `Cache-Control` for authenticated HTML deferred (no caching layer in v1) |
| V4 Access Control | yes | `LoginRequiredMiddleware` default-deny; admin gated by `is_staff`; only author promoted |
| V5 Input Validation | yes | allauth/Django safe `next` handling; template autoescape for `next` value; no user text stored in Phase 1 |
| V6 Cryptography | yes | never hand-roll; fresh `SECRET_KEY` from `openssl rand`; TLS at Caddy |
| V13/V14 Config | yes | `check --deploy --fail-level WARNING` gate, `DEBUG=0`, secrets only in server `.env`, container non-root, no published ports |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Login CSRF via GET link | Tampering | `SOCIALACCOUNT_LOGIN_ON_GET=False`; POST form with CSRF token |
| Open redirect via `next` | Tampering | allauth/Django safe-URL validation; do not construct redirects from `next` yourself |
| Forged `X-Forwarded-*` | Spoofing | Only Caddy reaches the container (no `ports:`); Caddy overwrites incoming values [CITED: caddy docs] |
| Compromised committed `SECRET_KEY` | Elevation | New key only in server `.env`; old key never used |
| Secrets in git/CI logs/image | Info disclosure | `.env` and `data/` in `.gitignore` and `.dockerignore`; build-time `SECRET_KEY` is a dummy; Google secret only in server `.env` |
| Account takeover via admin password | Spoofing | No password accounts; admin login redirected to Google |
| Rate-limit bypass / misattribution | DoS | `ALLAUTH_TRUSTED_PROXY_COUNT=1` |
| Chat-app link previews hitting state-changing URLs | Tampering | Nothing state-changing on GET in Phase 1 (login and logout are POST) |
| SQLite DB exfiltration via image | Info disclosure | `data/` excluded from build context |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Bombur deploy user (e.g. `plachtis`) has uid 1000, so the bind-mounted `data/` is writable by the container user | Pitfall 4 | SQLite "unable to open database file" at first deploy; fix is a one-line `chown`/`user:` |
| A2 | In-app browser UA tokens (`FBAN`, `FBAV`, `FB_IAB`, `Messenger`, `Instagram`, TikTok/LinkedIn/Snapchat markers, `; wv)`) match the real apps today | OPS-04 | Hint not shown (relatives see Google 403) or shown too eagerly (mitigated by "continue anyway") |
| A3 | Messenger/Instagram menus offer "Open in browser"/"Open in Safari" wording | OPS-04 | Hint instructions slightly off; adjust copy after real-device test |
| A4 | Google Console menu names ("Google Auth Platform", "Publish app") | User checklist | User clicks around; behaviour documented by Google (Testing vs In production) is cited |
| A5 | Compose may interpolate `$` in `.env`, hence avoid Django's secret alphabet | Don't Hand-Roll | None if `openssl rand -base64` is used regardless |
| A6 | Django's default session age is 2 weeks | Pitfall 10 | Irrelevant since we set 90 days explicitly |
| A7 | Bombur's Caddy has default `reverse_proxy` header behaviour (no global `trusted_proxies`) | Pitfall 5 | Wrong scheme/IP; check Caddyfile global block |
| A8 | The five PyPI packages are legitimate (seam says SUS for artefact reasons; evidence gathered manually) | Package Legitimacy | Supply-chain risk; mitigated by one human-verify checkpoint |

## Open Questions (RESOLVED)

1. **Which Bombur deploy user hosts gifter (reuse `plachtis`, which already hosts plachtis, plachtis-test, gustik, or create `gifter`)?**
   - Known: reuse works (separate directories); new user is "tidier, not isolated" per bombur-infra.
   - Unclear: user preference and its uid.
   - Recommendation: reuse `plachtis` unless uid != 1000; planner must make `DEPLOY_DIR`/`VPS_USER` a clearly marked placeholder resolved by the human checkpoint.
   - **RESOLVED:** defaults to `plachtis` (`DEPLOY_DIR: /home/plachtis/DOCKER/gifter` in plan 01-04's deploy.yml and DEPLOYMENT.md). The user confirms it or names another user at plan 01-05 Task 1 (checkpoint:human-action), and 01-05 Task 2 rewrites `DEPLOY_DIR` if it differs. A uid other than 1000 is handled by the documented one-time `chown`.
2. **Is the GitHub repo public or private?** Affects only whether GHCR pulls by hand need `docker login`; the workflow's `GITHUB_TOKEN` login covers CI deploys either way.
   - **RESOLVED:** private (`gh repo view ciakval/gifter` reported PRIVATE on 2026-10-16). CI deploys log in to GHCR with `GITHUB_TOKEN`; manual pulls on Bombur need `docker login ghcr.io` with a `read:packages` PAT, as documented in DEPLOYMENT.md (plan 01-04).
3. **Is the Google Cloud project/consent screen already in use for another app (name, branding)?** Publishing is per project; a fresh project for Gifter avoids side effects.
   - **RESOLVED:** use a fresh Google Cloud project named "Gifter" (plan 01-05 Task 1 step 6, also in DEPLOYMENT.md from plan 01-04).
4. **Path for the placeholder home (`/events/` suggested) and admin slug** — planner's call; keep the URL name `home`.
   - **RESOLVED:** home is at `/events/` with URL name `home` (plan 01-01); the admin is at `/gifter-admin/`, and its login redirects to Google sign-in (plan 01-02).
5. **Does a UI contract exist?** ROADMAP marks `UI hint: yes`; run `/gsd-ui-phase` first if a UI-SPEC is wanted, otherwise the planner uses the Bootstrap defaults and the landing/home/hint specs above.
   - **RESOLVED:** no UI-SPEC, and the UI gate did not block planning. The plans use vendored Bootstrap 5.3.8 defaults with the landing/home copy in plan 01-01, the allauth page copy in 01-02 and the in-app hint copy in 01-03.

## Project Constraints (from CLAUDE.md)

- Stack: Django 6.1.x, allauth 65.19.x, WhiteNoise, gunicorn, django-environ, uv + `pyproject.toml`/`uv.lock`, Bootstrap 5.3.8 vendored (no CDN), htmx vendored from Phase 2; no DRF/SPA, no Celery/Redis, no `django-csp`/`django-template-partials`, no `social-auth-app-django`, no rosetta/modeltranslation, no `i18n_patterns`.
- Google creds via settings `APPS` from env, **not** a `SocialApp` row; `SOCIALACCOUNT_ONLY = True`; never `SOCIALACCOUNT_LOGIN_ON_GET`; sign-in is a POST form.
- Custom user model before the first production `migrate`; admin off the default path, author-only staff.
- `LocaleMiddleware` after `SessionMiddleware`, before `CommonMiddleware`; wrap all strings; `LANGUAGES = [en, cs]`, `TIME_ZONE = "Europe/Prague"`; `USE_TZ = True`.
- Production settings list: `DEBUG=False`, `SECRET_KEY` from env (rotate), `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` with `https://`, `SECURE_SSL_REDIRECT`, `SECURE_PROXY_SSL_HEADER`, secure cookies, HSTS starting small, `collectstatic` at image build, `check --deploy` in CI.
- **Superseded by CONTEXT/ROADMAP:** CLAUDE.md's Fly.io/Neon/Postgres/psycopg hosting advice. Phase 1 is Bombur + SQLite (WAL) per bombur-infra; no psycopg.
- Viewport meta tag in base template; test on a real phone.
- GSD workflow enforcement: file edits go through GSD commands (executor concern).

## Sources

### Primary (HIGH confidence)
- Prototype runs this session (scratch dir `/tmp/gr`): Django 6.1.2 + allauth 65.19.7 test-client transcript (landing, redirects, OAuth redirect, mocked callback, logout, admin, `check --deploy`), and `docker build` + `docker run` of the proposed Dockerfile.
- Installed source read: `allauth/app_settings.py`, `allauth/utils.py`, `allauth/core/internal/httpkit.py`, `allauth/account/{urls,views,forms}.py`, `allauth/socialaccount/{app_settings,adapter}.py`, `allauth/socialaccount/providers/google/*`, `allauth/templates/allauth/layouts/base.html`, `django/contrib/auth/middleware.py`.
- `~/.claude/skills/bombur-infra` (SKILL.md, assets/deploy.yml, compose.yaml, env.example, references/dockerfiles.md) and `~/GIT/plachtis` (Dockerfile, compose.yaml, .env.example, DEPLOYMENT.md, deploy.yml).
- PyPI JSON API (first-upload dates, versions), npm (`bootstrap@5.3.8` tarball contents), `gh api` releases for action versions.

### Secondary (MEDIUM confidence)
- https://support.google.com/cloud/answer/15549945 (Testing vs In production, basic scopes exception)
- https://developers.googleblog.com/en/upcoming-security-changes-to-googles-oauth-20-authorization-endpoint-in-embedded-webviews/ (embedded webview block, `disallowed_useragent`)
- https://docs.allauth.org/en/latest/socialaccount/providers/google.html and /installation/quickstart.html (settings, ModelBackend warning, no sites requirement mentioned)
- https://caddyserver.com/docs/caddyfile/directives/reverse_proxy (X-Forwarded-* handling)

### Tertiary (LOW confidence)
- Auth0 community threads on `disallowed_useragent` from Messenger/Instagram/TikTok (via web search summary)
- https://developers.secure.facebook.com/community/threads/470205278761649 (Instagram browser and `intent://`, user report)
- Open-source in-app UA marker lists (inapp-spy / PHP detector, via search summary)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — resolved and run; legitimacy seam SUS is an artefact, one checkpoint
- Architecture / auth wiring: HIGH — end-to-end tested with mocked Google
- Deploy (Docker/compose/CI): MEDIUM-HIGH — image built and run locally; Bombur-side facts (uid, Caddy globals, deploy user) not probed
- In-app browser behaviour: MEDIUM-LOW — policy is documented, per-app UAs/menus need real-device verification
- Pitfalls: HIGH for those reproduced (1, 2, 3, 5, 6), MEDIUM for the rest

**Research date:** 2026-10-16
**Valid until:** 2026-11-15 (allauth releases frequently; re-check `uv lock` resolution and the allauth release notes if planning slips)
