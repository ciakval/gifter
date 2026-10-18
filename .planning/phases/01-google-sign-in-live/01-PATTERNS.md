# Phase 1: Google Sign-in Live - Pattern Map

**Mapped:** 2026-10-16
**Files analyzed:** 27 (new/modified/deleted)
**Analogs found:** 14 / 27 (the rest are greenfield; use the code in 01-RESEARCH.md "Code Examples", which was prototyped and run)

The gifter repo is nearly empty, so in-repo analogs exist only for the pieces being reshaped. Deploy files take their analogs from the bombur-infra skill templates (primary, canonical) and `~/GIT/plachtis` (tracked, deployed reference; verified with `git ls-files` run inside that repo). Do NOT copy plachtis wholesale: it predates the skill template (pip not uv, `docker compose down`, `docker system prune -f`, `DJANGO_*` env names, test+prod split, gettext in image). Where they differ, the skill template and 01-RESEARCH.md win.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `manage.py`, `web/{settings,urls,wsgi,asgi}.py`, `gifter/*` (flatten from `src/`, via `git mv`) | config | n/a | `src/` current layout | exact (move) |
| `web/settings.py` (env-driven rewrite) | config | request-response | `src/web/settings.py` (skeleton) + RESEARCH "web/settings.py" | role-match |
| `web/urls.py` | route | request-response | `src/web/urls.py` | exact (rewrite) |
| `gifter/urls.py` | route | request-response | `src/gifter/urls.py` | exact (rewrite) |
| `gifter/models.py` (User + repointed Wish) | model | CRUD | `src/gifter/models.py` | exact (modify) |
| `gifter/admin.py` (register User with UserAdmin) | config | CRUD | `src/gifter/admin.py` (stub) | stub |
| `gifter/views.py` (landing, home) | controller | request-response | `src/gifter/views.py` (CreateWishView; do not copy) | partial |
| `gifter/inapp.py` | utility | transform | none | no analog |
| `gifter/management/commands/promote_staff.py` | utility | batch | none | no analog |
| `gifter/templates/gifter/{base,landing,home}.html` | component | request-response | `src/gifter/templates/registration/login.html` (to be deleted) | weak |
| `gifter/templates/allauth/layouts/base.html`, `socialaccount/{authentication_error,login_cancelled}.html` | component | request-response | allauth stock templates (site-packages) | external |
| `gifter/static/vendor/bootstrap/*`, `gifter/static/gifter/landing.js` | asset | n/a | none | no analog |
| `gifter/tests/test_auth.py`, `test_inapp.py` | test | request-response | `src/gifter/tests.py` (empty stub) | stub |
| `gifter/migrations/0001_initial.py` (regenerated, never hand-edited) | migration | CRUD | `src/gifter/migrations/0001_initial.py` | regenerate |
| `pyproject.toml`, `uv.lock` | config | n/a | `~/GIT/plachtis/pyproject.toml`, `uv.lock` | role-match |
| `Dockerfile` | config | build | `~/GIT/plachtis/Dockerfile` | role-match |
| `.dockerignore` | config | build | none in plachtis tracked set; RESEARCH list | none |
| `compose.yaml` | config | deploy | `~/.claude/skills/bombur-infra/assets/compose.yaml` | exact |
| `.env.example` | config | deploy | `~/.claude/skills/bombur-infra/assets/env.example` | exact |
| `.github/workflows/deploy.yml` | config | CI/CD | `~/.claude/skills/bombur-infra/assets/deploy.yml` | exact |
| `DEPLOYMENT.md` | docs | n/a | `~/GIT/plachtis/DEPLOYMENT.md` | role-match |
| `.gitignore` (root) | config | n/a | `src/.gitignore`, `~/GIT/plachtis/.gitignore` | role-match |
| Deleted: `src/gifter/settings.py`, `requirements.txt`, `registration/login.html`, `create_wish.html`, `forms.py`, `CreateWishView`, `gifter/add` route, `login/` route | cleanup | n/a | n/a | n/a |

## Pattern Assignments

### `web/urls.py` (route, request-response)

**Analog:** `src/web/urls.py` (lines 17-26). Keep the `include` style, drop `auth_views` and the `login/` and `admin/` routes.

Current (to replace):
```python
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path("gifter/", include("gifter.urls")),
]
```
Target: RESEARCH "web/urls.py" verbatim. Order is load-bearing: the `login_not_required(RedirectView...)` routes for `accounts/login/` and `gifter-admin/login/` must precede `include("allauth.urls")` and `admin.site.urls`; `path("", include("gifter.urls"))` last.

### `gifter/urls.py` (route)

**Analog:** `src/gifter/urls.py` (whole file, 5 lines: `urlpatterns = [path("add", views.CreateWishView.as_view(), name="add_wish")]`). Replace with `landing` (`""`) and `home` (`"events/"`) from RESEARCH "gifter/views.py + urls.py". Keep `from django.urls import path` / `from . import views` import style.

### `gifter/models.py` (model, CRUD)

**Analog:** `src/gifter/models.py` (lines 1-13). Modify, not rewrite: keep Wish fields and `__str__`; replace line 2 `from django.contrib.auth.models import User` and the two FKs (lines 9, 11).
```python
# before
from django.contrib.auth.models import User
user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishes')
claimed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='claimed_wishes')
```
```python
# after (RESEARCH "gifter/models.py"): add User(AbstractUser) with display_name property,
# import settings, use settings.AUTH_USER_MODEL in both FKs, keep related_names
```
Then delete local `db.sqlite3` and run `makemigrations` to regenerate `0001_initial.py` (needs `data/` to exist; settings creates it).

### `web/settings.py` (config)

**Analog:** `src/web/settings.py`: keep the structure of `INSTALLED_APPS` (line 33), `MIDDLEWARE` (line 43), `TEMPLATES` (lines 55-65, with `request`, `auth`, `messages` context processors, already present and required by allauth). Replace hard-coded `SECRET_KEY` (line 23) and `DEBUG = True` with environ. Full target is RESEARCH "web/settings.py (core parts)". Reference for env style: plachtis uses plain env vars (`DJANGO_SECRET_KEY`); gifter uses django-environ with `SECRET_KEY`, `DEBUG`, `PUBLIC_HOSTS` (matching skill `env.example`). Gate the SSL block on `not DEBUG`. Note: the `SECRET_KEY` default must be NOTSET in production.

### `gifter/views.py` (controller)

**Analog:** none worth copying (`CreateWishView` is deleted). Use RESEARCH views block:
```python
@login_not_required
def landing(request):
    if request.user.is_authenticated:
        return redirect("home")
    ua = request.META.get("HTTP_USER_AGENT", "")
    in_app = is_in_app_browser(ua) and request.GET.get("force") != "1"
    return render(request, "gifter/landing.html", {"next": request.GET.get("next", ""), "in_app": in_app})
```
Imports needed: `from django.contrib.auth.decorators import login_not_required`, `redirect`, `render`.

### `gifter/templates/gifter/*.html`, allauth overrides (component)

No styled base exists. Put app templates under `gifter/templates/gifter/` (follows the existing `templates/gifter/create_wish.html` namespacing convention). Use RESEARCH "landing.html" form (POST to `{% provider_login_url 'google' %}`, `{% csrf_token %}`, hidden `next`) and logout form POST to `{% url 'account_logout' %}`. Wrap every string in `{% translate %}` (D-05). `base.html` must expose `head_title` and `content` blocks because `allauth/layouts/base.html` override extends it. Add `<meta name="viewport" content="width=device-width, initial-scale=1">`.

### `gifter/tests/` (test)

**Analog:** `src/gifter/tests.py` (`from django.test import TestCase` stub). Delete the stub module and create a `tests/` package (a module and package of the same name conflict). Use `django.test.TestCase`, run with `DEBUG=1` (SSL redirect otherwise 301s everything). Test matrix: RESEARCH "Tests worth writing".

### `Dockerfile`

**Analog:** `~/GIT/plachtis/Dockerfile` (tracked). Reuse these elements: `ARG VERSION/BUILD_ID` + `ENV VERSION=${VERSION} BUILD_ID=${BUILD_ID}`; `useradd -m -u 1000` + `chown` of the data dir; `collectstatic --noinput` before `USER`; `exec gunicorn` in CMD so signals forward.
```dockerfile
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/db_data && \
    chown -R appuser:appuser /app
RUN python manage.py collectstatic --noinput
USER appuser
CMD ... python manage.py migrate && exec gunicorn PlachtIS.wsgi:application --bind 0.0.0.0:8000 --workers 3 ...
```
Deviations for gifter (per RESEARCH "Dockerfile"): base `python:3.13-slim`; uv (`COPY --from=ghcr.io/astral-sh/uv:0.13.1`, `uv sync --frozen --no-dev --no-install-project`) instead of `pip install -r requirements.txt`; data dir is `/app/data` (not `db_data`); NO gettext/gcc/sqlite3/vim apt layer and NO `compilemessages` (Phase 4); `web.wsgi:application`, `--workers 2`; no `DJANGO_SETTINGS_MODULE` ENV (manage.py sets it); `collectstatic` needs dummy `SECRET_KEY`, `GOOGLE_CLIENT_ID/SECRET`. Keep `useradd -m` (gunicorn 26 control socket needs `$HOME`).

### `compose.yaml`

**Analog:** `~/.claude/skills/bombur-infra/assets/compose.yaml`: copy exactly, substituting `__APP__`=gifter (default repo `ciakval/gifter`). Key lines: `env_file: .env`, `OTEL_*` environment, `volumes: - ./data:/app/data`, `networks: [default, proxy]`, external `proxy` network, no `ports:`. plachtis's compose (inline `command:`, per-var `environment:` list, `networks: - proxy` only) is the older style; do not copy. CMD stays in the Dockerfile.

### `.env.example`

**Analog:** `~/.claude/skills/bombur-infra/assets/env.example`. Keep the "Managed by CI" block (`GITHUB_REPOSITORY`, `IMAGE_TAG`, `CONTAINER_NAME`, `DEPLOY_ENV`), uncomment/fill app block with `SECRET_KEY`, `DEBUG=False`, `PUBLIC_HOSTS=gifter.remesh.cz`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SECURE_HSTS_SECONDS=3600`; keep commented OTEL block. Comment: generate with `openssl rand -base64 48`.

### `.github/workflows/deploy.yml`

**Analog:** `~/.claude/skills/bombur-infra/assets/deploy.yml`: copy whole file; set `APP: gifter`, `DEPLOY_DIR: /home/<deploy-user>/DOCKER/gifter` (deploy user is an open question; check `id -u`), environment URL `https://gifter.remesh.cz`. Excerpts to keep:
```yaml
concurrency: { group: deploy-${{ github.ref }}, cancel-in-progress: false }
...
upsert() { if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi }
docker compose pull
docker compose up -d --remove-orphans
docker image prune -af --filter "until=72h"
```
Add the `test` job (RESEARCH "deploy.yml") and `needs: test` on `build-and-push`. Do NOT copy from plachtis `deploy.yml`: it has `docker compose down` and `docker system prune -f` (forbidden on the shared host), test/prod split and hand-repeated sed blocks. Secrets names are shared with plachtis: `VPS_HOST`, `VPS_SSH_PORT`, `VPS_USER`, `VPS_SSH_KEY`.

### `DEPLOYMENT.md`

**Analog:** `~/GIT/plachtis/DEPLOYMENT.md` (146 lines; headings: Local Development, One-time VPS Setup, GitHub Secrets Setup, Automatic Deployment, Caddy Configuration, Static Files, Production). Reuse the section skeleton and the Caddy note ("do not serve static in Caddy; WhiteNoise does"). Drop Translations and test-env sections; add: ordered user checklist (DNS, deploy key, `.env`, GH secrets, Caddy block `gifter.remesh.cz { reverse_proxy gifter-web:8000 }` on the `proxy` network, Google Console client + published consent screen + exact redirect URI `https://gifter.remesh.cz/accounts/google/login/callback/`), `promote_staff` command, uid 1000 vs `data/` ownership, and secret-rotation-logs-everyone-out note. Plachtis's Caddy snippet uses `localhost:8000`; gifter must use the container name.

### `.gitignore` (root)

**Analog:** `src/.gitignore` currently only `__pycache__/`; `~/GIT/plachtis/.gitignore` (starts with `__pycache__/`, `.env`, ...). Root file needs `data/`, `.env`, `staticfiles/`, `.venv/`, `*.sqlite3*`, `__pycache__/`.

### `pyproject.toml`

**Analog:** `~/GIT/plachtis/pyproject.toml` for layout only (not read in detail); content is given in RESEARCH "pyproject.toml" (5 runtime deps). Insert the single `checkpoint:human-verify` before the first `uv lock`.

## Shared Patterns

### Default-deny authentication
**Source:** Django `LoginRequiredMiddleware` (RESEARCH Pattern 1); settings `LOGIN_URL = "landing"`.
**Apply to:** every view. Public views opt out with `@login_not_required`: `landing`, and the `RedirectView` wrappers in `web/urls.py`. Missing the decorator on a redirect view causes a redirect loop to `/?next=/accounts/login/`.

### Env-driven settings, fail closed
**Source:** RESEARCH `web/settings.py`. **Apply to:** `settings.py`, `.env.example`, `compose.yaml` (`env_file`), CI `check --deploy` step. Production-only security block under `if not DEBUG`; tests/CI use `DEBUG=1`.

### i18n readiness
**Source:** D-05. **Apply to:** all templates (`{% load i18n %}` + `{% translate %}`), `gettext_lazy` in Python. No `.po` files, no gettext apt layer in Phase 1.

### Shared-host deploy hygiene
**Source:** skill `deploy.yml`. **Apply to:** `deploy.yml`, `DEPLOYMENT.md`: never `docker compose down` or `docker system prune`; image prune only; `./data` bind mount preserved; `.env` chmod 600 with `upsert` helper.

### Tracked-source gate
All analog paths above were checked: plachtis files are in `git ls-files` of that repo; gifter `src/*` files are tracked here. The skill assets under `~/.claude/skills/bombur-infra/assets/` are the infra template source (not a gitignored mirror of this repo). No mirror paths are emitted.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `gifter/inapp.py` | utility | transform | New; ~10-line UA regex per RESEARCH OPS-04 |
| `gifter/management/commands/promote_staff.py` | utility | batch | No management commands exist; RESEARCH has full code (`BaseCommand`, `email__iexact`, set `is_staff`/`is_superuser`) |
| `gifter/templates/**`, `static/**` | component/asset | request-response | No base template or static files exist |
| `.dockerignore` | config | build | Not tracked in plachtis; use RESEARCH list: `.git .github .env data/ .venv/ __pycache__/ *.sqlite3* staticfiles/ .planning .claude` |
| `gifter/tests/*` | test | request-response | Only an empty stub exists |

## Metadata

**Analog search scope:** `/home/ciakval/GIT/gifter` (all tracked non-.planning files, 22), `~/GIT/plachtis` deploy files, `~/.claude/skills/bombur-infra/assets/`.
**Files scanned:** ~35
**Pattern extraction date:** 2026-10-16
**Note:** 01-RESEARCH.md was read through line 565 of 678 (page cap); the remainder (open questions, assumptions) was not loaded by this mapper.
