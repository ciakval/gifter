# Stack Research

**Domain:** Group gift-wishlist web app (server-rendered Django, Google login, EN+CZ, mobile-first, small family/friends audience)
**Researched:** 2026-10-15
**Confidence:** HIGH on Django/allauth/i18n/static/DB driver (verified against PyPI + official docs today); MEDIUM on hosting (prices and free-tier terms drift; verify at signup)

## Headline Recommendations

1. **Upgrade Django 5.1.4 -> 6.1.x now (not 5.2 LTS).** Django 5.1 is out of security support. The project has one model and one view, so the upgrade costs nothing today and gets harder later. See "Django version" below for the one-line fallback to 5.2 LTS.
2. **django-allauth 65.19.x, Google only, settings-based credentials, `SOCIALACCOUNT_ONLY = True`.** Do not hand-roll OAuth.
3. **Server-rendered Django templates + htmx 2.x + Bootstrap 5.3, all vendored as static files.** No Node, no bundler, no SPA.
4. **Django built-in i18n (gettext, `LocaleMiddleware`).** No extra i18n libraries.
5. **PostgreSQL in production (psycopg 3), configured via `DATABASE_URL`.** Keep SQLite only for local dev if wanted, but Postgres locally is better for parity.
6. **Hosting: Fly.io (always-cheap, autostop) + Neon free Postgres, about $3-5/month.** Alternative: one Hetzner VPS with Docker Compose + Caddy + Postgres. The "Hosting" section has the decision table.
7. **Replace the 124-line `requirements.txt` with roughly 10 direct dependencies** (list below). Drop `pillow` and `requests` as direct deps (images are out of scope; `requests` comes in transitively via allauth).

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Python | 3.13 (3.12-3.14 all valid) | Runtime | Django 6.x requires >= 3.12. Local dev box already has 3.14.8; pin the **Docker/host image to 3.13** (most wheels/mature) and make dev match. | HIGH |
| Django | **6.1.2** (`Django>=6.1,<6.2`) | Web framework | Latest series, released 2026-08-05; mainstream support to ~Apr 2027, extended to Dec 2027. Built-in **template partials** (`{% partialdef %}` / `{% partial %}`, since 6.0) are exactly what htmx fragment responses need, so no `django-template-partials` dependency. Built-in **CSP middleware** (6.0) gives a secure-headers story without `django-csp`. allauth officially supports 6.1 since 65.19.0. | HIGH |
| django-allauth | **65.19.7** (`django-allauth[socialaccount]>=65.19,<66`) | Google OAuth/OIDC login, account linking, session handling | The de-facto standard for social login in Django; actively released (7 releases Aug-Oct 2026), security-responsive, ships a Czech locale, Django 4.2-6.1 supported. Handles state/PKCE, nonce, token exchange, email handling, `next` redirect. | HIGH |
| PostgreSQL | 16 or 17 (managed, e.g. Neon) | Production DB | Django 6.1 needs PG 15+. Fly/Render/etc. have ephemeral or awkward disks; Postgres decouples data from the app host. Row-level constraints (unique claim per wish, partial unique indexes, `CheckConstraint`) are first-class and matter for the claim/chip-in invariants. | HIGH |
| psycopg | **3.3.6** (`psycopg[binary]>=3.3,<4`) | Postgres driver | Django's recommended modern driver (psycopg 3). `[binary]` avoids needing libpq-dev at build time. | HIGH |
| gunicorn | **26.2.0** | WSGI server | Boring, correct choice for sync Django at this scale. 2 workers is plenty. No need for ASGI (htmx polling/SSE not required). | HIGH |
| WhiteNoise | **6.12.0** | Serve static files from the app process | Removes the need for nginx/S3/CDN for CSS/JS. Use `CompressedManifestStaticFilesStorage` via the `STORAGES` setting. | HIGH |
| htmx | **2.0.11** (stable; vendored `htmx.min.js`) | Partial page updates (claim, chip-in, share-to-event toggles) without a JS app | Stay on **2.x**: it is the `latest` npm tag. htmx 4.0.0 is only the `next`/beta tag, and django-htmx itself says "default htmx version remains 2, since htmx 4 is in beta." | HIGH |
| Bootstrap | **5.3.8** (vendored CSS + `bootstrap.bundle.min.js`) | Responsive, mobile-first UI components | Navbar collapse, cards, badges, progress bars, modals, offcanvas, form styling, all JS-optional or tiny. Non-technical relatives on phones need predictable, familiar UI patterns. Vendoring avoids CDN + CSP + privacy headaches. | HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| django-htmx | **1.29.0** | `request.htmx` detection, `{% htmx_script %}` tag, CSRF header glue | Use from the first htmx view. Supports Django 5.2/6.0/6.1. Tiny, optional but saves boilerplate (`if request.htmx: render partial else: render page`). |
| django-crispy-forms + crispy-bootstrap5 | **2.7** + **2026.9** | Render Django forms with Bootstrap 5 markup | Use for Wish/Event forms. Alternative with less magic: `django-widget-tweaks` 1.5.1. Pick one; do not use both. |
| django-environ | **0.14.0** | Read `SECRET_KEY`, `DEBUG`, `DATABASE_URL`, `ALLOWED_HOSTS`, Google creds from env | One dependency covers env casting plus `env.db()`. Replaces the hard-coded `SECRET_KEY` and `DEBUG=True` currently in `src/web/settings.py`. (`dj-database-url` 3.1.2 + `os.environ` is the minimal alternative.) |
| pytest + pytest-django | pytest **9.1.1**, pytest-django **4.14.0** | Tests, especially the **giftee-secrecy tests** | Core promise is privacy; test every view/URL as giftee vs participant vs non-member. Django's built-in runner is acceptable if you want zero extra deps. |
| model-bakery | 1.24.2 | Test data factories | Optional; only if fixtures get painful. |
| sentry-sdk | 2.72.0 | Error reporting | Optional and free tier is enough; add in the deploy phase if you want to learn about 500s from relatives before they tell you. |

Transitive (do not pin directly): `requests`, `PyJWT`, `cryptography`, `oauthlib` via `django-allauth[socialaccount]`; `asgiref`, `sqlparse` via Django.

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv 0.13.1 | Dependency management and venv | Create `pyproject.toml` with the ~10 direct deps, generate `uv.lock`, and use `uv export --no-dev -o requirements.txt` if the host wants a requirements file. Fully replaces the env dump. |
| ruff 0.17.1 | Lint + format | Single tool, near-zero config. |
| GNU gettext (system package) | `makemessages` / `compilemessages` | **Required for i18n**: `apt install gettext` locally and in the Dockerfile (needed at build time to run `compilemessages`). |
| django-debug-toolbar 8.0.0 | Query inspection (dev only) | Useful for catching N+1 on the "wishes x claims x contributors" event page. Dev dependency group only. |
| `manage.py check --deploy` | Production settings audit | Run in CI/deploy script; it flags missing HSTS, secure cookies, etc. |

## Detailed Rationale and Configuration Notes

### Django version (5.1 -> ?)

Verified on djangoproject.com/download (2026-10-15): 5.1 is not even listed as supported; **5.2 LTS** supported to April 2028 (latest 5.2.18); **6.0** mainstream ended Aug 2026 (latest 6.0.9); **6.1** latest 6.1.2, supported to Dec 2027; **6.2 LTS** due April 2027.

- **Recommend 6.1.x.** Reasons: template partials and CSP are built in; project code is tiny so there is no migration risk; a 6.1 -> 6.2 LTS hop in spring 2027 is a normal minor-style upgrade.
- **Fallback: 5.2 LTS** (`Django>=5.2,<5.3`) if you prefer "set it and forget it until 2028." Cost: you add `django-template-partials` (25.3) for htmx fragments and `django-csp` (4.0) if you want CSP; everything else in this document is unchanged. Both choices are defensible. 6.1 is the recommendation because the app is also a learning/hobby project with a 2026-12 deadline and no long-lived maintenance burden, so the support window is irrelevant, but built-in partials are not.
- Upgrade steps: bump pin, run `manage.py check`, run tests, `makemigrations --check`. Django 6.0 changed `DEFAULT_AUTO_FIELD` default to `BigAutoField` (the project already sets it, so no impact). 6.1 raises SQLite minimum to 3.37 and drops PG 14.

### Authentication: django-allauth with Google

Recommended settings shape (names verified against allauth docs, 65.x):

```python
INSTALLED_APPS += [
    # django.contrib.sites: not needed when credentials come from settings (APPS) instead of SocialApp rows (verify on install)
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]
MIDDLEWARE += ["allauth.account.middleware.AccountMiddleware"]   # after AuthenticationMiddleware
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",             # keeps /admin login working
    "allauth.account.auth_backends.AuthenticationBackend",
]
SOCIALACCOUNT_ONLY = True               # no local passwords/signup at all (PROJECT.md: email/password is out of scope)
ACCOUNT_EMAIL_VERIFICATION = "none"     # Google already verified the email; no SMTP needed
SOCIALACCOUNT_LOGIN_ON_GET = False      # default; keep it. Login button must be a POST form (CSRF-safe)
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "..."              # event list / my wishlist
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": [{"client_id": env("GOOGLE_CLIENT_ID"), "secret": env("GOOGLE_CLIENT_SECRET"), "key": ""}],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "OAUTH_PKCE_ENABLED": True,
    }
}
```

Key points:

- **Credentials in settings (`APPS`) via env, not a `SocialApp` DB row.** Allauth warns that configuring the same provider both ways raises `MultipleObjectsReturned`. Settings-based keeps the secret out of the DB and makes deploys reproducible. (HIGH)
- **Redirect URI to register in Google Cloud Console:** `https://<domain>/accounts/google/login/callback/` plus `http://127.0.0.1:8000/accounts/google/login/callback/` for dev. Create an OAuth client of type "Web application".
- **Google consent screen:** use User type "External" and **publish it ("In production")** even though it is a hobby app. In "Testing" status only listed test users (hard cap 100) can sign in unless the app uses only basic scopes, and users see a "testing" warning. Basic scopes (`openid`, `email`, `profile`) do not trigger OAuth verification. Expect an "unverified app" cosmetic caveat (no logo/name branding) until brand verification, which is optional. Relatives will not be added as test users one by one, so do not rely on Testing mode. (MEDIUM: Google's wording on exactly what Testing allows with basic scopes is subtle; verify in Cloud Console on setup.)
- **Behind a proxy (Fly, Render, Caddy):** allauth >= 65.14.2 **distrusts `X-Forwarded-For` by default** (rate limiting was spoofable). Set `ALLAUTH_TRUSTED_PROXY_COUNT = 1` (or the platform's client-IP header) or all users appear to share the proxy's IP and rate limits misfire. Also set `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` so the OAuth callback URL is built with `https`. A mismatched scheme is the classic `redirect_uri_mismatch` failure in production. (HIGH)
- **Invite-link flow:** invite URL requires login; unauthenticated visitors are redirected to `account_login?next=/join/<token>/`. Allauth round-trips `next` through the OAuth dance. As a belt-and-braces measure, also stash the token in `request.session["pending_invite"]`. Use `secrets.token_urlsafe(16+)` (or UUID4) as the token, with no library needed.
- **Custom user model now.** Django strongly recommends it at project start and the project is at that point (one migration, no production data). Create `AbstractUser` subclass before the first production `migrate`; switch `Wish.user` to `settings.AUTH_USER_MODEL`. Retrofitting later is painful. (HIGH)
- **Do not use `django-axes`, `django-ratelimit`, or password validators for auth** - there are no passwords; allauth has its own rate limits for the OAuth endpoints. The remaining `AUTH_PASSWORD_VALIDATORS` block can be left as default or removed.
- **Alternatives rejected:** `social-auth-app-django` (more manual wiring, weaker account-management story); `authlib` / raw `google-auth` (you'd write callback, session, linking, and edge-case handling yourself); Google One Tap (nice, but needs extra JS/CSP config; add later only if friction is observed); `django-allauth-ui` (1.8.1, restyles allauth; unnecessary when login is a single button).

### Frontend: server-rendered + htmx + Bootstrap

- **Why server-rendered:** the secrecy requirement is easiest to guarantee when the server decides, per request, exactly what HTML is produced. There is no client-side API surface exposing claim data to a giftee. No DRF, no JSON API, no React/Vue. (`djangorestframework` 3.18.3 exists but is explicitly **not** needed.)
- **Why htmx (not just plain templates):** claim / unclaim / chip-in / "share this wish to event X" toggles feel broken on phones if each is a full-page reload with scroll reset. htmx covers that with `hx-post` + partial responses. Use Django 6.1 `{% partialdef %}` to define the row/card fragment once and render it both in full pages and in htmx responses. Keep every interaction functional **without** JS where cheap (normal POST + redirect) so htmx is progressive enhancement.
- **Why Bootstrap 5.3 (not Tailwind / Pico / DaisyUI):**
  - Tailwind 4.3 would need either Node or `django-tailwind-cli` 4.8.1 (standalone binary) plus a build step in Docker and a custom component vocabulary. Too much setup for an 8-week window.
  - Pico CSS 2.1.1 is lovely and classless but lacks the navbar/offcanvas/progress/badge components a claims UI uses.
  - Bootstrap works from vendored files, has a stable class vocabulary, handles the mobile viewport, and pairs with crispy-forms.
- **Vendor, don't CDN:** download `bootstrap.min.css`, `bootstrap.bundle.min.js`, `htmx.min.js` into `src/gifter/static/vendor/` and let WhiteNoise serve them. Works with a strict CSP, offline dev, and no third-party requests from a privacy-minded gift app.
- **Don't add Alpine.js** unless a concrete need appears (Bootstrap's JS covers modals/collapse; htmx covers the rest).
- Add `<meta name="viewport" content="width=device-width, initial-scale=1">` in the base template, and test on a real phone early because the audience is mostly phones opening a link from a chat app.
- **htmx + CSRF:** set `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'` on `<body>` (or use django-htmx's script tag) so every htmx POST is CSRF-protected.

### Internationalization (EN + CZ)

- **Use Django's built-in i18n only**: `gettext`/`gettext_lazy`, `{% trans %}`/`{% blocktranslate %}`, `locale/{en,cs}/LC_MESSAGES/django.po`, `LocaleMiddleware`.
- Settings: `LANGUAGE_CODE = "en"`, `LANGUAGES = [("en", "English"), ("cs", "Čeština")]`, `LOCALE_PATHS = [BASE_DIR / "locale"]`, `TIME_ZONE = "Europe/Prague"`, `USE_I18N = True`, `USE_TZ = True`. `LocaleMiddleware` goes after `SessionMiddleware`, before `CommonMiddleware`.
- **Language selection:** Accept-Language auto-detect, then a visible switcher posting to Django's built-in `set_language` view (stores a cookie). Do **not** use `i18n_patterns` URL prefixes: invite links should be one stable URL regardless of language, and prefixes add routing complexity for no user value here. (MEDIUM: preference call, either works.)
- **Czech plurals:** Czech has three plural forms (1 / 2-4 / 5+). Always use `ngettext` / `{% blocktranslate count %}` for counts like "3 contributors"; never concatenate strings. Django ships a Czech catalog and so does allauth, so built-in messages are translated already.
- **Write all UI strings wrapped from day one**, including model `verbose_name`s, form labels, and messages. Retrofitting is the cost the PROJECT.md decision log called out. Add a CI/precommit check that `makemessages -l cs` leaves no untranslated new strings.
- **Do not add** `django-rosetta` (0.10.3, web .po editor) or `django-modeltranslation` (0.20.6). User-generated wish text is not translated, and one translator (the author) edits `.po` files directly. Skip DB-level translation entirely.
- Gotcha: `gettext` binaries must exist in the build image or `compilemessages` fails, and the compiled `.mo` files must be built in deploy (commit `.po`, generate `.mo` in the Docker build, or commit both; pick one and stay consistent).

### Database

- **Production: Postgres.** Dev: either local Postgres (docker `postgres:17`) or SQLite; if SQLite stays for dev, run the test suite against Postgres at least in CI/pre-deploy because constraint semantics and case-sensitivity differ.
- **Why not SQLite in production?** It *can* work for tens of users (WAL mode, single writer, one machine). It requires a persistent volume (not available on Render free; billed on Fly), a single instance (no rolling deploys), and a backup story (Litestream or volume snapshots). For ~$0 more, managed Postgres gives backups/branches and decouples app and data. Not worth saving the complexity of adding a volume.
- Model-level safeguards to lean on (Postgres supports them natively): `UniqueConstraint(fields=["wish"], condition=Q(...))` for the single claimer, `UniqueConstraint(fields=["claim", "user"])` for contributors, `CheckConstraint` to forbid giftee == claimer. Django 6.1's `DB_CASCADE` exists but does not fire signals; prefer plain `CASCADE` unless there is a reason.
- Connection settings: `DATABASES = {"default": env.db("DATABASE_URL")}`; add `CONN_MAX_AGE = 60` and `CONN_HEALTH_CHECKS = True`. Neon's serverless endpoint scales to zero after ~5 minutes, so the first request after idle pays a cold start; health checks avoid stale-connection errors.

### Hosting (public, low cost, small audience)

Facts verified 2026-10-15 from vendor docs (Fly pricing, Render free docs, PythonAnywhere pricing, Neon pricing):

| Option | Cost | Fit | Verdict |
|--------|------|-----|---------|
| **Fly.io app + Neon free Postgres** | Fly shared-cpu-1x 512MB = $3.69/mo if always-on (`min_machines_running=1`); 256MB = $2.19/mo; with `auto_stop_machines` stopped machines cost only rootfs storage. Shared IPv4/IPv6 and certs free. Neon free: 1 GB, 100 CU-hours, scales to zero, no expiry, no card. No Fly free tier; card required after a ~2h / 7-day trial. | Dockerized, HTTPS + custom domain included, `fly launch` detects Django, region `fra` (Frankfurt) close to Czech users, `release_command` for `migrate`. | **Recommended primary.** About $3-5/month total. |
| Hetzner CX23 VPS + Docker Compose (Django + Postgres + Caddy) | about $6.49/mo ex-VAT | Cheapest RAM per dollar; full control; Caddy gives automatic HTTPS. You own OS patching, backups (`pg_dump` cron), and monitoring. | **Alternative** if you enjoy ops or want to host more apps. Do not choose it for this deadline unless you already have a Compose template. |
| Render (free web + free Postgres) | $0 for web, but sleeps after 15 min, **about 1 min cold start**; free Postgres **expires after 30 days** (deleted 14 days later) | A relative tapping an invite link and staring at a loading page for a minute will assume it is broken. Free Postgres is unusable. | Avoid. Paid Render (web $7 + PG $6) is more than Fly + Neon. |
| PythonAnywhere free | $0 | One `*.pythonanywhere.com` site, **no custom domain on free**, outbound internet limited to a whitelist (risk for the Google OAuth token exchange), no always-on/MySQL/Postgres on free, 100 CPU-s/day. Paid Developer $10/mo. | Avoid for an OAuth app; paid is pricier than Fly. |
| Railway Hobby | $5/mo + usage; one-time $5 trial | Fine, usage billing is less predictable. | Acceptable alternative; no advantage over Fly. |
| Heroku | $5-7/mo, sustaining-engineering mode since Feb 2026 | Works but no advantage. | Avoid. |
| Fly Managed Postgres | $38/mo Basic | Overkill. | Avoid; use Neon. |

- **Domain:** buy a cheap domain (about $10/year) instead of using `*.fly.dev`: Google consent screen looks more trustworthy and invite links look legitimate in family chats. Put the domain in `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` (with `https://` scheme), and the Google redirect URIs.
- **Required production settings (PROJECT.md constraint):** `DEBUG=False`; `SECRET_KEY` from env (rotate the one committed in git today, since it is in the repo history); `ALLOWED_HOSTS`; `CSRF_TRUSTED_ORIGINS`; `SECURE_SSL_REDIRECT=True`; `SECURE_PROXY_SSL_HEADER`; `SESSION_COOKIE_SECURE`; `CSRF_COOKIE_SECURE`; `SECURE_HSTS_SECONDS` (start small, e.g. 3600, raise later); `STORAGES["staticfiles"] = "whitenoise.storage.CompressedManifestStaticFilesStorage"`; run `collectstatic` at image build.
- **Admin:** keep `/admin/` (needed to inspect data) but move to a non-default path, and let only the author's account be `is_staff`.
- **Backups:** Neon free retains limited history; add a weekly `pg_dump` (GitHub Actions or local cron) before Christmas. Data is small and the group is trusting, but lost claims would be embarrassing.
- **Email:** none required (invite links, social login only). If error emails or later notifications are wanted, use `django-anymail` 15.2 with a transactional provider; Django 6.1 introduces `MAILERS`, so skip configuring legacy `EMAIL_*` settings for now. Note Render blocks SMTP ports on free tier, one more reason to avoid it.

## Installation

Target direct-dependency list (replaces the 124-line env dump; `pillow` and `requests` dropped as direct deps):

```bash
# Runtime (pyproject.toml [project.dependencies])
uv add "Django>=6.1,<6.2" \
       "django-allauth[socialaccount]>=65.19,<66" \
       "psycopg[binary]>=3.3,<4" \
       "gunicorn>=26,<27" \
       "whitenoise>=6.12,<7" \
       "django-environ>=0.14" \
       "django-htmx>=1.29" \
       "django-crispy-forms>=2.7" "crispy-bootstrap5>=2026.9"

# Dev group
uv add --dev "pytest>=9" "pytest-django>=4.14" "ruff" "django-debug-toolbar>=8"

# Vendored front-end (one-time download into src/gifter/static/vendor/, committed)
#   bootstrap@5.3.8  -> dist/css/bootstrap.min.css, dist/js/bootstrap.bundle.min.js
#   htmx.org@2.0.11  -> dist/htmx.min.js
# System packages (local + Dockerfile)
sudo apt install gettext
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Django 6.1 | Django 5.2 LTS | You want support until April 2028 with no upgrade until then; add `django-template-partials` for htmx fragments. |
| django-allauth | social-auth-app-django | Never for this project; allauth has the better maintained Google + account-linking path. |
| htmx 2.0.x | htmx 4 (beta) | After 4.x is stable and django-htmx defaults to it; not before Christmas 2026. |
| Bootstrap 5.3 | Tailwind 4 via `django-tailwind-cli` | If a designer-ish workflow and custom look matter more than speed; accept a build step. |
| Bootstrap 5.3 | Pico CSS 2.1 | If the UI is only forms and lists and you want ~10 KB of classless CSS. |
| crispy-forms + crispy-bootstrap5 | django-widget-tweaks | If you prefer hand-written form markup with classes injected in templates. |
| Fly.io + Neon | Hetzner VPS + Compose + Caddy | You want everything (app, DB, backups) on one box you control and do not mind ops. |
| Postgres | SQLite + Litestream on Fly volume | Single-machine, cost-minimal, willing to manage replication; adds a volume and removes zero-downtime deploys. |
| django-environ | dj-database-url + `os.environ` | You want the smallest dependency footprint. |
| pytest-django | `manage.py test` | You want zero test dependencies; the existing `tests.py` already uses the stock runner. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Django 5.1.x (current pin 5.1.4) | Past end of support; no security patches. | Django 6.1.x (or 5.2 LTS) |
| Hand-rolled Google OAuth / `requests`-based token exchange | Easy to get state, nonce, redirect-URI, and account-linking wrong. | django-allauth |
| Email/password signup, `django.contrib.auth` `LoginView` page, password reset flows | Out of scope per PROJECT.md; extra attack surface; delete the existing `/login/` `LoginView` route when allauth lands. | allauth `SOCIALACCOUNT_ONLY = True` |
| `SOCIALACCOUNT_LOGIN_ON_GET = True` | Enables login CSRF via a plain link. Docs "strongly recommend" POST. | A `<form method="post">` button |
| Google OAuth consent screen left in "Testing" | 100 test-user cap, test-warning UI, test-user-only access for non-basic scopes. | Publish as External with basic scopes |
| DRF / GraphQL / SPA frameworks (React, Vue) | Doubles the surface where claim data could leak to a giftee; heavy for 8 weeks. | Server-rendered templates + htmx |
| htmx 4 beta, CDN-loaded scripts | Beta churn, extra third-party requests, CSP friction. | Vendored htmx 2.0.11 |
| `django-template-partials` (on Django >= 6.0) | Built into Django 6.0+. | `{% partialdef %}` / `{% partial %}` |
| `django-csp` (on Django >= 6.0) | Django 6.0+ ships `ContentSecurityPolicyMiddleware`. | `SECURE_CSP` setting |
| Celery / Redis / background workers | No async work needed (no emails, no notifications in v1). | Nothing; revisit with Django 6 `@task` later |
| Pillow, torch, pandas, jupyter, numpy, etc. (everything in current `requirements.txt` beyond Django) | Images are out of scope; data-science packages bloat the image from MBs to GBs and slow every deploy. | Trimmed dependency list above |
| Render free tier, PythonAnywhere free | Cold starts/expiring DB / whitelisted outbound / no custom domain. | Fly.io + Neon |
| Committed `SECRET_KEY` / `DEBUG=True` in `settings.py` | The key in git history is already compromised. | env vars; generate a new key for prod |
| `django-rosetta`, `django-modeltranslation`, `i18n_patterns` | Unneeded complexity for two languages and user-generated content. | Built-in gettext + cookie-based language switch |

## Stack Patterns by Variant

**If you want maximum safety margin before Christmas (hard deadline):**
- Deploy a "hello world with Google login" to Fly + Neon in the **first** phase, with a real domain, a published Google consent screen, and a working invite-redirect round trip.
- Because OAuth redirect URIs, proxy headers, and Google consent publishing are the most environment-dependent pieces, and failures there cannot be found locally.

**If Neon cold starts annoy users (about a second after 5 min idle):**
- Use Neon's paid tier toggle to disable scale-to-zero, or move Postgres onto the Fly app (unmanaged, a volume plus your own backups).
- Because a 1-2 second delay on first load is acceptable for a family app, but is easy to fix if it is not.

**If you outgrow one gunicorn process or want zero downtime deploys:**
- Add a second Fly machine; do not use SQLite in that case.
- Because multiple writers + SQLite on separate volumes would split-brain.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Django 6.1.2 | Python 3.12, 3.13, 3.14 | Python 3.10/3.11 dropped as of Django 6.0. |
| Django 6.1 | PostgreSQL 15+, SQLite 3.37+ | PG 14 dropped; SQLite minimum raised. |
| django-allauth 65.19.7 | Django 4.2-6.1, Python 3.10+ | 6.1 officially supported since 65.19.0. Requires `asgiref>=3.8.1`. |
| django-htmx 1.29.0 | Django 5.2 / 6.0 / 6.1, htmx 2 (default) and 4 (beta, opt-in) | 1.28.0 dropped Django < 5.2. |
| psycopg 3.3.x | Django 4.2+ | Django's recommended driver; `psycopg2` not needed. |
| crispy-bootstrap5 2026.9 | django-crispy-forms 2.x, Bootstrap 5 | Set `CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"` and `CRISPY_TEMPLATE_PACK = "bootstrap5"`. Confirm Django 6.1 in changelog at install (MEDIUM). |
| WhiteNoise 6.12.0 | Django 4.2+ / Python 3.10+ | Use `STORAGES` dict (not the removed `STATICFILES_STORAGE`). |

## Confidence Notes

| Claim | Confidence | Basis |
|-------|------------|-------|
| Package versions listed | HIGH | PyPI JSON API and npm registry queried 2026-10-15 |
| Django support windows, 6.0/6.1 features | HIGH | djangoproject.com download page and 6.0/6.1 release notes |
| allauth settings and Google setup, release notes | HIGH | docs.allauth.org (stable docs plus 65.x release notes) |
| Google consent-screen publishing behaviour | MEDIUM | Google docs via web search summary; confirm in Cloud Console |
| Hosting prices and free-tier terms | MEDIUM | Vendor docs fetched today (Fly, Render, PythonAnywhere, Neon); prices and plans change, re-check at signup |
| Bootstrap vs Pico vs Tailwind, Fly+Neon vs VPS | MEDIUM | Opinionated judgment against the 8-week deadline and non-technical audience, not a measured benchmark |
| crispy-bootstrap5 2026.9 on Django 6.1 | MEDIUM | Version confirmed on PyPI; Django 6.1 compatibility not explicitly verified |

## Sources

- PyPI JSON API (2026-10-15): Django 6.1.2, django-allauth 65.19.7, psycopg 3.3.6, gunicorn 26.2.0, whitenoise 6.12.0, django-htmx 1.29.0, django-crispy-forms 2.7, crispy-bootstrap5 2026.9, django-environ 0.14.0, pytest-django 4.14.0, sentry-sdk 2.72.0 (HIGH)
- npm registry: htmx.org latest 2.0.11 (`next` = 4.0.0), bootstrap 5.3.8, @picocss/pico 2.1.1, tailwindcss 4.3.3 (HIGH)
- https://www.djangoproject.com/download/ (supported versions table) (HIGH)
- https://docs.djangoproject.com/en/6.1/releases/6.1/ and /6.0/ (template partials, CSP, DB requirements) (HIGH)
- https://docs.allauth.org/en/latest/socialaccount/providers/google.html, /socialaccount/configuration.html, /socialaccount/provider_configuration.html, /account/configuration.html, /release-notes/recent.html (HIGH)
- https://django-htmx.readthedocs.io/en/latest/changelog.html (htmx 2 default, 4 beta) (HIGH)
- https://developers.google.com/identity/protocols/oauth2/production-readiness/overview (consent screen publishing status) (MEDIUM)
- https://docs.fly.io/about/pricing (no free tier, shared-cpu prices, autostop billing) (MEDIUM-HIGH)
- https://render.com/docs/free (spin-down, free Postgres 30-day expiry) (HIGH)
- https://www.pythonanywhere.com/pricing/ (free tier limits) (HIGH)
- https://neon.com/pricing (free plan limits) (MEDIUM-HIGH)
- https://fly.io/learn/django-hosting/ (comparative prices checked 2026-09-28; vendor-authored, so used for price points only) (LOW-MEDIUM)
- https://bex.co/blog/2026/09/24/qovery-heroku-alternative-price-table-recomputed (third-party cost estimates; cross-check only) (LOW)
