# Walking Skeleton — Gifter

**Phase:** 1
**Generated:** 2026-10-16

## Capability Proven End-to-End

> A relative opens https://gifter.remesh.cz on a phone, signs in with Google, and lands on a home page that greets them by first name; their account row lives in SQLite under the bind-mounted `./data` on Bombur and survives every redeploy from `main`.

Plans: 01-01 (tracer: local round trip with mocked Google), 01-02 (Google-only lockdown, friendly allauth pages), 01-03 (in-app browser hint), 01-04 (production image + CI/CD + deploy pipeline), 01-05 (go live).

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | Django 6.1 (`Django>=6.1,<6.2`), server-rendered templates, no DRF/SPA | PROJECT.md; the server decides per request exactly what HTML a viewer gets, which is the simplest way to keep the giftee-secrecy promise later. Built-in `LoginRequiredMiddleware`, template partials (Phase 2+) and CSP middleware are available |
| Runtime | Python 3.13 in the image (local dev 3.14 is fine), `uv` + `pyproject.toml` + committed `uv.lock`, five runtime deps | OPS-01; reproducible installs (`uv sync --frozen` in Docker, `--locked` in CI) |
| Data layer | SQLite at `/app/data/db.sqlite3` (WAL, `synchronous=NORMAL`, `transaction_mode=IMMEDIATE`, 20 s timeout), bind-mounted `./data` | PROJECT.md Key Decision (Bombur + SQLite); backup = copy the deploy dir (Phase 4). Concurrency invariants later use unique constraints + `IntegrityError` (no `select_for_update` on SQLite) |
| Identity | Custom user `gifter.User(AbstractUser)` = `AUTH_USER_MODEL`, shape confirmed in 01-01 Task 2; `display_name` = Google given name | Promote decision (assumption-delta): every user FK targets `settings.AUTH_USER_MODEL`; regenerated `0001_initial` before the first production migrate (one-way door) |
| Auth | django-allauth 65.19 Google provider only: `SOCIALACCOUNT_ONLY`, credentials in settings `APPS` (never a `SocialApp` row), PKCE, scopes `openid email profile`, POST-only sign-in (`SOCIALACCOUNT_LOGIN_ON_GET=False`), POST-only sign-out | AUTH-01; D-03; no passwords anywhere (admin login redirected to Google, only allauth's backend) |
| Access control | Default deny: `LoginRequiredMiddleware`; public views opt out with `@login_not_required`; `LOGIN_URL = "landing"` with `next` carried through the OAuth state | AUTH-03; D-04. Phase 2's invite confirm page and every later view inherit "private unless decorated" |
| Sessions | DB sessions, persistent cookie, `SESSION_COOKIE_AGE` 90 days; secure cookies + HSTS in production | AUTH-02 (allauth's "remember me" does nothing for social login) |
| Config | django-environ; `SECRET_KEY`, `GOOGLE_CLIENT_ID/SECRET` fail closed when `DEBUG` is off; `PUBLIC_HOSTS` derives `ALLOWED_HOSTS` and `https://` `CSRF_TRUSTED_ORIGINS`; production security block only when not `DEBUG`; tests run with `DEBUG=1` | OPS-02; `check --deploy --fail-level WARNING` gates CI |
| Frontend | Vendored Bootstrap 5.3.8 under `gifter/static/vendor/` (no CDN, no third-party requests), mobile-first templates, no inline JS; htmx 2.0.x vendored when Phase 2's first interactive view lands | Standing rule (mobile-first from the first page); privacy; future CSP |
| i18n | All strings wrapped (`{% translate %}`, `gettext_lazy`), `LocaleMiddleware`, `LANGUAGES = en, cs`, English only until Phase 4 | D-05; no `i18n_patterns` (invite links keep one URL) |
| Static files | WhiteNoise `CompressedManifestStaticFilesStorage` in production, plain `StaticFilesStorage` under `DEBUG`; `collectstatic` at image build | Caddy only proxies (bombur-infra) |
| Deployment target | Bombur VPS: GitHub Actions (`test` → `build-and-push` → `deploy-production`) → GHCR `ghcr.io/ciakval/gifter:<sha>` → Docker Compose in `~/DOCKER/gifter` → Caddy `gifter.remesh.cz` → `gifter-web:8000` over the external `proxy` network; image runs as uid 1000, gunicorn 2 sync workers, `migrate` at container start | OPS-03; bombur-infra skill conventions; no staging environment in Phase 1 |
| Directory layout | Flat repo root: `manage.py`, `web/` (project: settings, urls, wsgi), `gifter/` (the single domain app: models, views, `inapp.py`, `templates/gifter/`, `templates/allauth/`, `templates/socialaccount/`, `static/`, `management/commands/`, `tests/` package), `scripts/` (host-side smoke tests) | Matches the bombur-infra Dockerfile pattern; one app until a real seam appears |
| URL contracts | `landing` = `/`, `home` = `/events/` (Phase 2 turns it into "My events"), allauth under `/accounts/`, admin under `/gifter-admin/` (staff via Google only) | D-02; reverse by name everywhere |

## Stack Touched in Phase 1

- [x] Project scaffold (framework, build, lint, test runner) — 01-01: flattened Django 6.1 project, `uv`, Django test runner (`DEBUG=1 uv run python manage.py test`)
- [x] Routing — at least one real route — 01-01: `/` (landing), `/events/` (home), `/accounts/…`; 01-02: `/gifter-admin/`
- [x] Database — at least one real read AND one real write — 01-01: Google sign-in writes a `gifter.User` row and a session row; home reads `request.user` (WAL SQLite); 01-04/01-05 prove the rows survive container replacement and redeploys
- [x] UI — at least one interactive element wired to the API — 01-01: Sign in with Google POST form and Sign out POST form; 01-03: Copy link button in the in-app hint
- [x] Deployment — running on the real environment — 01-04 builds the production image and pipeline; 01-05 deploys to https://gifter.remesh.cz

## Out of Scope (Deferred to Later Slices)

- Events, invite links and the invite → sign-in → confirm round trip (Phase 2)
- Wishlists, sharing wishes into events, browsing other members' wishes (Phase 2); the existing `Wish` model is only repointed to `gifter.User`, its views/forms are removed
- Claims, chip-in, purchased/received lifecycle and the giftee-secrecy test suite (Phase 3)
- Czech catalogue, language switcher, gettext in the image (Phase 4)
- Nightly backups and the restore drill (Phase 4)
- htmx, crispy-forms, Content-Security-Policy middleware, error tracking / OTLP instrumentation (OPS-07, v2)
- A staging environment, Postgres, email of any kind, password or email login, other identity providers

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- Phase 2: A signed-in user creates an event, invites family by link, keeps a wishlist, shares wishes into events, and browses other members' wishes (owner and participant views separate from the start)
- Phase 3: Members claim, chip in and mark purchased, giftees mark received — invisible to the giftee and proven by CI secrecy tests that block deploys
- Phase 4: Full Czech, a real-phone pass, nightly backups with a tested restore, and a relatives' dry-run before the 1 Dec freeze
