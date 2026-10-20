---
phase: 01-google-sign-in-live
reviewed: 2026-10-20T00:00:00Z
depth: standard
files_reviewed: 28
files_reviewed_list:
  - .dockerignore
  - .env.example
  - .gitignore
  - .github/workflows/deploy.yml
  - DEPLOYMENT.md
  - Dockerfile
  - compose.yaml
  - pyproject.toml
  - web/settings.py
  - web/urls.py
  - gifter/admin.py
  - gifter/inapp.py
  - gifter/models.py
  - gifter/urls.py
  - gifter/views.py
  - gifter/migrations/0001_initial.py
  - gifter/management/commands/promote_staff.py
  - gifter/static/gifter/landing.js
  - gifter/templates/allauth/layouts/base.html
  - gifter/templates/gifter/base.html
  - gifter/templates/gifter/home.html
  - gifter/templates/gifter/landing.html
  - gifter/templates/socialaccount/authentication_error.html
  - gifter/templates/socialaccount/login_cancelled.html
  - gifter/tests/test_allauth_pages.py
  - gifter/tests/test_auth.py
  - gifter/tests/test_inapp.py
  - gifter/tests/test_lockdown.py
  - scripts/container-smoke.sh
  - scripts/smoke.sh
findings:
  critical: 0
  warning: 7
  info: 8
  total: 15
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-10-20
**Depth:** standard
**Files Reviewed:** 28 (plus the in-scope test files; the list above is exact)
**Status:** issues_found

## Summary

The auth core is sound. Sign-in is a CSRF-protected POST, PKCE is on, the `next` redirect is validated by allauth, and secrets fail closed. The production security block, proxy settings and non-root image are correct. The 41 tests pass (`DEBUG=1 manage.py test`). I confirmed each of these by running them:

- Password routes redirect or 404.
- Admin login redirects to the landing page without a loop.
- `/accounts/google/login/` over GET only renders a confirmation page.
- Disconnecting the last social account is refused.

There are no blockers. The seven warnings fall into three groups:

1. **Pipeline hygiene:** `latest` can be overwritten from any branch, and action refs are mutable while `secrets: inherit` is passed on.
2. **Lockdown gaps:** several allauth routes and admin models remain reachable although the design says "Google is the only door". Examples are the CSRF-exempt `google/login/token/` route and the SocialApp admin that DEPLOYMENT.md warns against.
3. **Forward-looking defects:** a `lang` attribute stuck on `en`, and `Wish.claimed_by`, which contradicts the giftee-secrecy design.

## Warnings

### WR-01: `latest` image tag is overwritten by a workflow_dispatch run on any branch

**File:** `.github/workflows/deploy.yml:86` (trigger at line 7)
**Issue:** `type=raw,value=latest,enable=${{ github.ref_type == 'branch' }}` is true for every branch, not just `main`. `workflow_dispatch` can run on any branch, and the test and build jobs have no branch guard. A manual run from a feature branch pushes an unreviewed image as `ghcr.io/ciakval/gifter:latest`. `compose.yaml` defaults to `IMAGE_TAG:-latest`, and the rollback and manual `docker compose up -d` paths in DEPLOYMENT.md reuse the server `.env`. If `IMAGE_TAG` is ever empty or reset, the server pulls whatever `latest` points to. The deploy job is correctly limited to `refs/heads/main`; the tag is not.
**Fix:**
```yaml
type=raw,value=latest,enable=${{ github.ref == 'refs/heads/main' }}
```

### WR-02: Supply chain: mutable action refs, and a mutable reusable-workflow ref that receives `secrets: inherit`

**File:** `.github/workflows/deploy.yml:25,72,74,81,90,112,117`
**Issue:** Only `setup-uv` is pinned to a commit SHA. `checkout@v6`, `setup-buildx@v3`, `login-action@v4`, `metadata-action@v6` and `build-push-action@v7` are mutable tags. I confirmed they currently exist. The `build-and-push` job holds `packages: write` and the GITHUB_TOKEN, so a compromised tag could push a malicious image that `bombur-deploy` then ships to production. The deploy job calls `ciakval/bombur-deploy/...@v1` (a movable tag) with `secrets: inherit`, which hands it every repository secret instead of the single one it needs. The `test` job also has no `permissions:` block, so it uses the repository default token scope. The repo is public, which raises the stakes.
**Fix:** Pin every `uses:` to a full commit SHA with a `# vN` comment. Add a top-level `permissions: contents: read`, which the jobs that need more already override. Replace `secrets: inherit` with an explicit mapping, for example `secrets: { DEPLOY_SSH_KEY: ${{ secrets.DEPLOY_SSH_KEY }} }`. Check the secret name against what the `bombur-deploy` workflow declares. Pin `@v1` of `bombur-deploy` to its SHA as well (currently `2839093b05e2008a6c52967d4cc0d731aa49fdf6`). Optionally enable Dependabot for `github-actions`.

### WR-03: "Google is the only door" is not enforced: the CSRF-exempt token login and the connections UI are still routed

**File:** `web/urls.py:23` (`include("allauth.urls")`); tests in `gifter/tests/test_lockdown.py`
**Issue:** Including `allauth.urls` wholesale exposes, besides the intended OAuth flow:
- `/accounts/google/login/token/`: a `csrf_exempt`, login-not-required POST endpoint. It does Google One Tap login through a double-submit cookie that the client controls. This bypasses the "sign-in must be a CSRF-protected POST" decision (D-03, `settings.py:134`). It needs a Google-signed ID token with the app's audience, so it is not trivially exploitable. It is still unneeded attack surface, and the deployment docs say no JavaScript origins are configured.
- `/accounts/3rdparty/` (and the `/accounts/social/...` aliases): the stock connections page, reachable by any signed-in user (I got a 200). It adds UI nobody designed.
- `/accounts/inactive/`.

The lockdown tests only assert 404 for signup, password reset, `/admin/` and `/login/`. They do not cover any of these routes, so a future allauth upgrade could add routes unnoticed.
**Fix:** Replace `include("allauth.urls")` with an explicit list. Keep these routes:
- `account_login` (the redirect)
- `account_logout`
- `socialaccount_login_cancelled` and `socialaccount_login_error`
- the Google `login` and `callback` routes. Include `allauth.socialaccount.providers.google.urls` and remove `google/login/token/`, or filter the resolved patterns.

Add a test asserting that `/accounts/google/login/token/` and `/accounts/3rdparty/` return 404. Also add a test asserting that GET `/accounts/google/login/` does not redirect to Google (login-on-GET must stay off).

### WR-04: SocialApp (and other allauth models) are exposed in the admin, although the docs say adding one breaks sign-in

**File:** `gifter/admin.py:7-12` and `DEPLOYMENT.md:165`
**Issue:** The comment and DEPLOYMENT.md rely on discipline: "Never add a Social application row". But `allauth.socialaccount` registers `SocialApp`, `SocialToken`, `SocialAccount` and `EmailAddress` in the admin (confirmed in the URL table: `gifter-admin/socialaccount/socialapp/add/` exists). One slip by a superuser makes allauth raise `MultipleObjectsReturned`, which locks everyone out until a shell fix. `SocialToken` and `EmailAddress` add/edit forms also let an admin forge identities.
**Fix:** In `gifter/admin.py` (admin autodiscovery runs after all apps are loaded, so allauth's registrations exist by then):
```python
from allauth.socialaccount.models import SocialApp, SocialToken
admin.site.unregister(SocialApp)
admin.site.unregister(SocialToken)
```
Make `SocialAccount` and `EmailAddress` read-only if they are kept.

### WR-05: `promote_staff` trusts `User.email`, which allauth populates even when Google says it is unverified

**File:** `gifter/management/commands/promote_staff.py:18`
**Issue:** The command grants `is_staff` and `is_superuser` to the user matched by `email__iexact` on `User.email`. allauth's Google provider copies `email` into the user whatever `email_verified` is; verification is tracked only on `EmailAddress.verified`. `ACCOUNT_EMAIL_VERIFICATION="none"` and no email-uniqueness at the DB level add to this. A Google account carrying someone else's unverified email can therefore exist, and the operator could promote the wrong account. The `MultipleObjectsReturned` branch shows the author expected duplicates. The command prints no stable identifier (Google `uid`) to double-check.
**Fix:** Select through the verified address and the Google account:
```python
from allauth.account.models import EmailAddress
ea = EmailAddress.objects.select_related("user").filter(email__iexact=email, verified=True, user__socialaccount__provider="google")
```
Fail if the result is not exactly one. Print the user's Google `uid` on success.

### WR-06: `Wish.claimed_by` stores claim state on the giftee-readable Wish row

**File:** `gifter/models.py:21`; `gifter/migrations/0001_initial.py:54`
**Issue:** The core promise is that the giftee never sees claims. This model keeps the claimer as a nullable FK on `Wish` itself, with no uniqueness or `CheckConstraint` (claimer != owner). Any default `Wish` serialisation, admin page, template or `.values()` call exposes it to the owner. Contributors and chip-ins cannot be modelled this way. The planned design in CLAUDE.md is a separate Claim table with constraints. The migration is now `0001_initial`, so removing the field later costs a migration, although the database holds no data yet. Also `description = TextField()` has no `blank=True`.
**Fix:** Before any wish UI ships, drop `claimed_by` and add a separate `Claim` model: `Claim(wish, claimer)` with a `UniqueConstraint` on `wish` and a check constraint. Regenerate migration 0001 while no data exists.

### WR-07: `<html lang>` is always `en`: the i18n context processor is missing

**File:** `web/settings.py:90-95`; `gifter/templates/gifter/base.html:2`
**Issue:** The template uses `{{ LANGUAGE_CODE|default:'en' }}`, but `django.template.context_processors.i18n` is not in `context_processors`. `LANGUAGE_CODE` is therefore never in the context, and the `default` filter hides the bug. When the Czech catalogue and `LocaleMiddleware` language switching arrive (Phase 4), pages will still be labelled `lang="en"`. Screen readers will mispronounce them, and browsers will offer to "translate" Czech pages.
**Fix:** Add `"django.template.context_processors.i18n"` to the list, or use `{% get_current_language as LANGUAGE_CODE %}` in the template (after `{% load i18n %}`).

## Info

### IN-01: No Content-Security-Policy, and inline styles would conflict with one later

**File:** `web/settings.py` (absent); `gifter/templates/gifter/landing.html:9`
**Issue:** The stack decision cites Django 6's built-in CSP middleware, but none is configured. Everything is vendored and first-party, so a strict policy would be easy now. `style="max-width: 32rem;"` would break under `style-src 'self'`.
**Fix:** Move the inline style to a class, then enable `SECURE_CSP` with `default-src 'self'` (report-only first).

### IN-02: Landing response varies by User-Agent but sends no `Vary` header

**File:** `gifter/views.py:25-33`
**Issue:** The page renders either the in-app hint or the sign-in form depending on `User-Agent`. A shared cache in front of the app (Caddy has none today) could serve the wrong variant. Low risk now.
**Fix:** Decorate `landing` with `@vary_on_headers("User-Agent")`.

### IN-03: `.dockerignore` patterns are root-anchored, and base images are not digest-pinned

**File:** `.dockerignore:6`; `Dockerfile:1,15`
**Issue:** `__pycache__/` only matches the repo root, so nested `gifter/__pycache__` (built on the host with Python 3.14 here) is copied into the image. `.env` has the same root-only scope. `python:3.13-slim` and the `uv:0.13.1` stage are tag-pinned but not digest-pinned. The Dockerfile comment claims the build is reproducible.
**Fix:** Use `**/__pycache__`, `**/*.pyc` and `**/.env*`. Optionally pin the base images by `@sha256:` digest.

### IN-04: Shell script robustness

**File:** `scripts/smoke.sh:34,89`; `scripts/container-smoke.sh:24`
**Issue:**
- `"${PROXY_HEADERS[@]}"` is an empty array under `set -u`. This aborts with "unbound variable" on bash < 4.4 (for example macOS `/bin/bash` 3.2) when no HOST is given.
- `container-smoke.sh` cleanup swallows `rm -rf` failures for uid-1000-owned files, although its comment promises removal "through a throwaway container". Temp directories leak.
- The fixed default port 18000 collides when run twice.

**Fix:** Use `${PROXY_HEADERS[@]+"${PROXY_HEADERS[@]}"}`. Add `docker run --rm -v "$DATA_DIR:/d" "$IMAGE" sh -c 'rm -rf /d/*'` (with `--entrypoint sh`) to cleanup.

### IN-05: Sessions are never purged; long-lived sessions apply to superusers too

**File:** `web/settings.py:152`; `Dockerfile:36`
**Issue:** The database-backed sessions table grows with every sign-in, and nothing runs `clearsessions`. The 90-day cookie also applies to the staff and superuser accounts created by `promote_staff`, which makes a stolen laptop or cookie a long-lived admin session.
**Fix:** Run `manage.py clearsessions` at container start (before gunicorn) or on a schedule. Consider a shorter age for `is_staff`.

### IN-06: `models.py` leftovers

**File:** `gifter/models.py:14-24`
**Issue:** Boilerplate comment `# Create your models here.`, single-quoted strings and a long one-line field, unlike the rest of the code base. See WR-06 for the design issue.
**Fix:** Remove the comment and reformat; fold into the WR-06 rework.

### IN-07: `LANGUAGES` wraps an autonym in `gettext_lazy`

**File:** `web/settings.py:159`
**Issue:** A language's own name should not be translated; a Czech catalogue entry for "Čeština" would show in the switcher in the current UI language. Other entries are not wrapped, so this is also inconsistent.
**Fix:** `LANGUAGES = [("en", "English"), ("cs", "Čeština")]` and drop the unused import.

### IN-08: Authenticated visitor loses `next` on the landing page; proxy headers are trusted from the whole shared network

**File:** `gifter/views.py:19-20`; `compose.yaml:15-17`
**Issue:**
- `landing` redirects any signed-in user to `home` and ignores `?next=`. This is harmless today, but it will break deep links such as an invite link opened by an already-logged-in user once more routes exist.
- The container joins the shared external `proxy` network. Any other container on it can reach port 8000 and spoof `X-Forwarded-Proto` and `X-Forwarded-For`. The first defeats the SSL redirect, and the second defeats the allauth rate limit key with `ALLAUTH_TRUSTED_PROXY_COUNT=1`. Neighbours are the owner's own apps, so risk is low.

**Fix:** Redirect to the safe `next` target when present, using `url_has_allowed_host_and_scheme`. Document the network-trust assumption in DEPLOYMENT.md, or give Caddy a dedicated per-app network.

---

_Reviewed: 2026-10-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
