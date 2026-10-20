---
phase: 01-google-sign-in-live
verified: 2026-10-20T16:20:00Z
status: gaps_found
score: 5/6 must-haves verified
covered_files:
  - .env.example
  - .github/workflows/deploy.yml
  - .planning/phases/01-google-sign-in-live/01-01-PLAN.md
  - .planning/phases/01-google-sign-in-live/01-01-SUMMARY.md
  - .planning/phases/01-google-sign-in-live/01-02-PLAN.md
  - .planning/phases/01-google-sign-in-live/01-02-SUMMARY.md
  - .planning/phases/01-google-sign-in-live/01-03-PLAN.md
  - .planning/phases/01-google-sign-in-live/01-03-SUMMARY.md
  - .planning/phases/01-google-sign-in-live/01-04-PLAN.md
  - .planning/phases/01-google-sign-in-live/01-04-SUMMARY.md
  - .planning/phases/01-google-sign-in-live/01-05-PLAN.md
  - .planning/phases/01-google-sign-in-live/01-05-SUMMARY.md
  - DEPLOYMENT.md
  - Dockerfile
  - compose.yaml
  - gifter/admin.py
  - gifter/inapp.py
  - gifter/management/commands/promote_staff.py
  - gifter/models.py
  - gifter/static/gifter/landing.js
  - gifter/templates/allauth/layouts/base.html
  - gifter/templates/gifter/base.html
  - gifter/templates/gifter/home.html
  - gifter/templates/gifter/landing.html
  - gifter/tests/test_allauth_pages.py
  - gifter/tests/test_auth.py
  - gifter/tests/test_inapp.py
  - gifter/tests/test_lockdown.py
  - gifter/views.py
  - pyproject.toml
  - scripts/container-smoke.sh
  - scripts/smoke.sh
  - uv.lock
  - web/settings.py
  - web/urls.py
covered_digest: "v3:sha256:77b283f8e40428de1e3f59358d4b2349beec2d41f6f9d83b7db7fc068f9e5056"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "A user can sign in with Google, including a user whose account was never added as a test user (ROADMAP SC-2; phase goal: anyone with a Google account can sign in)"
    status: failed
    reason: "The Google OAuth consent screen is still in Testing status. Only listed test users can sign in; any other relative's Google account is refused by Google. Publishing is blocked because Google's Branding step requires a privacy policy URL and the app has no privacy page. 01-05 SUMMARY records this as 'NOT MET' (deviation 2, coverage D6)."
    artifacts:
      - path: "gifter/urls.py"
        issue: "No /privacy/ route or template exists, so the Google Branding step cannot be completed"
      - path: "gifter/templates/gifter/base.html"
        issue: "No footer link to a privacy page"
    missing:
      - "Add a public /privacy/ page (login_not_required) linked from the landing page and footer"
      - "Fill the Google Auth Platform Branding step and Publish app to In production (basic scopes only, no verification needed); user-only action in Google Cloud Console"
      - "Re-test with a Google account that was never added as a test user (no 'app is being tested' screen)"
deferred: []
human_verification:
  - test: "Sign in on a phone, fully close and reopen the browser, open https://gifter.remesh.cz/events/"
    expected: "Still signed in with no new Google prompt (90-day persistent cookie); Sign out button returns to landing and /events/ then redirects to sign-in"
    why_human: "Real browser restart behaviour. Only the cookie Max-Age (7776000) is test-proven. The user's blanket 'approved' did not report it individually."
  - test: "While signed in, trigger a redeploy (workflow_dispatch) and reload /events/"
    expected: "Session survives (sessions live in ./data/db.sqlite3 on the bind mount)"
    why_human: "Cannot SSH or trigger workflows from verification. Not individually reported by the user."
  - test: "Open https://gifter.remesh.cz inside the real Messenger and Instagram in-app browsers (link shared in a chat/DM) on a phone"
    expected: "The 'Open Gifter in your browser' hint shows instead of the Google button; menu wording (the ... menu, Open in browser) matches the real app; Copy link works; Continue anyway shows the Google button"
    why_human: "Server-side detection is proven live with a spoofed FBAN/FBIOS user agent. Real in-app menu wording and the Copy link clipboard behaviour were never captured on a device."
  - test: "Check the phone layout of the landing page and /events/"
    expected: "Readable and tappable at phone width"
    why_human: "Visual check. Only reported under the blanket approval."
---

# Phase 1: Google Sign-in Live Verification Report

**Phase Goal:** Anyone with a Google account can sign in to Gifter at https://gifter.remesh.cz. The site runs on a cleaned-up Django 6.1 codebase that redeploys automatically from `main`.
**Verified:** 2026-10-20
**Status:** gaps_found
**Re-verification:** No (initial verification)

Note on mode: ROADMAP marks the phase `mode: mvp`, but the goal is not in user-story format (`user-story.validate` returns `valid: false`; the plans acknowledge this). Standard goal-backward verification was applied instead of the User Flow Coverage structure.

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | https://gifter.remesh.cz shows the Gifter landing page over HTTPS; every push to `main` redeploys (Actions to GHCR to Bombur) without losing `./data` | VERIFIED (persistence partly human) | Live `curl -sI`: HTTP/2 200, `via: Caddy`, `strict-transport-security: max-age=3600; includeSubDomains`. `http://` returns 308 to https. `gh run list`: push run 39452688350 and workflow_dispatch run 39452993438 both succeeded (test, build-and-push, deploy-production). Deployed SHA `b9b6a2d` equals `origin/main`; the two local-ahead commits are docs only. `compose.yaml` bind-mounts `./data:/app/data`; `settings.py` puts the DB at `DATA_DIR/db.sqlite3`. Survival of a live session across redeploy is a human item. |
| 2 | A user can sign in with Google, **including a never-added test user**; Google is the only way in; `/login/` gone; stays signed in after browser restart; can sign out | **FAILED** (BLOCKER) | Google-only: PASS. Live `/login/` 404, `/admin/` 404, `/accounts/signup/` 404. `/accounts/login/` 302 to `/`. Live `POST /accounts/google/login/` redirects to accounts.google.com with `redirect_uri=https://gifter.remesh.cz/accounts/google/login/callback/` (smoke check g, real client id). Author signed in live (user-confirmed). Cookie Max-Age 7776000 is test-proven (`test_session_cookie_90_days`); sign-out is POST-only (`test_post_logout`, `test_get_logout_does_not_sign_out`). **But** the consent screen is in Testing, so a never-added Google account cannot sign in. Plan 01-05's own truth and check for this were not met (SUMMARY deviation 2, coverage D6). No later phase covers privacy page or publishing (grep of ROADMAP/REQUIREMENTS finds no match), so this cannot be deferred. |
| 3 | A signed-out visitor opening any non-landing page is sent to sign in, then returned to that page | VERIFIED | `LoginRequiredMiddleware` + `LOGIN_URL="landing"`. Live: `/events/` returns 302 to `/?next=/events/`. Landing form carries hidden `next`. `test_google_round_trip_returns_to_next`, `test_offsite_next_rejected`, `test_protected_redirects_with_next`, `test_unresolvable_path_404` pass. |
| 4 | Opening the site in the Messenger or Instagram in-app browser shows an "open in your browser" hint instead of a Google error | VERIFIED (server side); real-device wording is a human item | Live curl with UA `Mozilla/5.0 (iPhone) [FBAN/FBIOS;FBAV/400]` returns the hint ("Open Gifter in your browser", Copy link, Continue anyway) and no Google form. `gifter/inapp.py` regex plus 12 `test_inapp.py` tests pass. Menu wording not checked on a real device. |
| 5 | Django 6.1 from a small pinned dependency set, `DEBUG` off, secrets from server `.env` incl. fresh `SECRET_KEY`, `check --deploy` passes in CI | VERIFIED | `uv.lock` pins Django 6.1.2; `pyproject.toml` has exactly 5 runtime deps; `requirements.txt` and `src/` are gone. `uv lock --locked` is clean. Local `check --deploy --fail-level WARNING` with DEBUG=0 exits 0. With no `SECRET_KEY`, `manage.py check` raises ImproperlyConfigured (fail-closed). CI runs the same gate (`deploy.yml` test job) and passed. Live `/login/` returns a plain 404, so DEBUG is off. `git grep django-insecure` outside `.planning` finds nothing. |

### Plan-level truths and prohibitions (spot confirmation)

| Item | Status | Evidence |
|------|--------|----------|
| User model is `gifter.User`, first name from Google | VERIFIED | `AUTH_USER_MODEL="gifter.User"`; round-trip test passes |
| SQLite WAL | VERIFIED | `init_command` sets `PRAGMA journal_mode=WAL` in `settings.py` |
| Basic scopes only, PKCE, login-on-GET off | VERIFIED | `SCOPE=["openid","profile","email"]`, `SOCIALACCOUNT_LOGIN_ON_GET=False`. Live `GET /accounts/google/login/` returns 200 (confirm page), not a redirect to Google. |
| No third-party assets | VERIFIED | `test_no_third_party_assets`; live HTML loads only `/static/...` |
| Landing shows no user data to anonymous | VERIFIED | Live landing HTML contains only static copy; `test_landing_hides_user_data` |
| Admin is Google-only and moved | VERIFIED | Live `/gifter-admin/` redirects to login, which goes to landing; `promote_staff` confirmed by user live |
| Deploy via restricted bombur-deploy key, no host ports | VERIFIED | `deploy.yml` calls `ciakval/bombur-deploy/...@v1`; `compose.yaml` has no `ports:` and uses the external `proxy` network |
| Full test suite | VERIFIED | `DEBUG=1 uv run python manage.py test`: Ran 41 tests, OK |
| Live smoke script | VERIFIED | `scripts/smoke.sh https://gifter.remesh.cz`: checks a through g PASS, SMOKE OK |

**Score:** 5/6 (5 ROADMAP success criteria plus the plan-level behaviors, counted as 6 groups; SC-2 fails on its "never-added user" clause)

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `pyproject.toml`, `uv.lock` | VERIFIED | 5 deps, Django 6.1.2, lock reproducible |
| `web/settings.py` | VERIFIED | Env-driven, fail-closed, production security block, WAL |
| `web/urls.py` | VERIFIED | Login redirects placed before includes; admin at `gifter-admin/` |
| `gifter/models.py`, migration 0001 | VERIFIED (WR-06 noted) | Custom user in place before first deploy |
| `gifter/inapp.py`, `landing.html`, `landing.js` | VERIFIED | Wired in `views.landing`; live-confirmed |
| `gifter/management/commands/promote_staff.py` | VERIFIED | Used live by the author |
| `Dockerfile`, `compose.yaml`, `.env.example`, `deploy.yml`, `DEPLOYMENT.md`, `scripts/*smoke.sh` | VERIFIED | Pipeline ran green twice; image runs as uid 1000 |
| `/privacy/` page | **MISSING** | Required to publish the consent screen (see gap) |

### Key Link Verification

| From | To | Status | Details |
|------|----|--------|---------|
| landing form | `/accounts/google/login/` | WIRED | POST with CSRF and `next` (live HTML) |
| Google client | `https://gifter.remesh.cz/accounts/google/login/callback/` | WIRED | Live redirect_uri matches exactly |
| `LoginRequiredMiddleware` | landing with `next` | WIRED | Live `/events/` 302 |
| `deploy.yml` | Bombur via `bombur-deploy@v1` | WIRED | Two successful runs |
| Caddy | `gifter-web:8000` | WIRED | Live responses carry `via: 1.1 Caddy` |

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| OPS-01 Django 6.1, minimal pinned deps | 01-01, 01-04 | SATISFIED | uv.lock Django 6.1.2, 5 deps, no requirements.txt |
| OPS-02 env-driven prod settings, rotated key, DEBUG off, hosts/CSRF origins | 01-01, 01-04 | SATISFIED | Fail-closed settings; `PUBLIC_HOSTS`; no committed key; check --deploy passes |
| OPS-03 reachable at https://gifter.remesh.cz via Actions, GHCR, Compose, SQLite in ./data | 01-04, 01-05 | SATISFIED | Live site; green runs; bind mount. Cross-redeploy survival of data: see human item. |
| OPS-04 in-app browser hint | 01-03, 01-05 | SATISFIED (server side) | Live spoofed-UA check; real-device wording human item |
| AUTH-01 sign in with Google (only login method; `/login/` removed) | 01-01, 01-02, 01-05 | PARTIAL | Works for listed test users; not for arbitrary Google accounts while in Testing. The requirement text itself does not say "any account", but the phase goal and SC-2 do. REQUIREMENTS.md already marks it Complete; consider reopening it or keeping the gap on the phase. |
| AUTH-02 stays signed in across sessions; can sign out | 01-01, 01-05 | SATISFIED (code); real-browser restart is a human item | Cookie Max-Age 7776000; POST logout tested |
| AUTH-03 every page except landing requires sign-in | 01-01, 01-05 | SATISFIED | Live and test-proven |

All 7 phase IDs (OPS-01..04, AUTH-01..03) appear in plan frontmatter and in REQUIREMENTS.md. No orphaned requirements: REQUIREMENTS.md maps only these IDs to Phase 1.

### Review Warnings vs Must-Haves

The review (0 critical, 7 warnings) was checked against the must-haves.

- WR-03 (undermines "Google is the only door" in spirit, but not a must-have failure): live `/accounts/google/login/token/` answers 401 (routed, CSRF-exempt One Tap endpoint). `/accounts/3rdparty/` is reachable when signed in. Neither provides a non-Google way to sign in, because a Google-signed ID token for this client is still required. Not a gap against SC-2 (the SC only requires that no password or other login method exists), but hardening is recommended before relatives are invited.
- WR-01/WR-02 (CI hygiene), WR-04 (SocialApp in admin), WR-05 (`promote_staff` trusts unverified email), WR-06 (`Wish.claimed_by` conflicts with secrecy design, Phase 3 concern), WR-07 (`<html lang>` always en; Phase 4 concern): none contradict a Phase 1 must-have. All are open in `01-REVIEW-DISPOSITION.md`. WR-06 should be resolved at the start of Phase 2/3 rather than left.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| (phase files) | TBD/FIXME/XXX debt markers | none found in the phase's implementation files scanned | No debt-marker blocker |
| `gifter/models.py` | `Wish.claimed_by` on the giftee-readable row (WR-06) | Warning | Phase 2/3 secrecy design conflict, not Phase 1 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Test suite | `DEBUG=1 uv run python manage.py test` | 41 tests OK | PASS |
| Deploy audit | `check --deploy --fail-level WARNING` (DEBUG=0) | exit 0 | PASS |
| Fail-closed secret | `manage.py check` without SECRET_KEY | ImproperlyConfigured | PASS |
| Lock reproducible | `uv lock --locked` | Resolved 19 packages | PASS |
| Live contract | `scripts/smoke.sh https://gifter.remesh.cz` | SMOKE OK (a-g) | PASS |
| In-app hint live | `curl -A "...FBAN/FBIOS..."` | Hint shown | PASS |

### Human Verification Required

See the `human_verification` frontmatter: browser-restart persistence and sign-out, session survival across a redeploy, real Messenger/Instagram menu wording and Copy link, phone layout. These were covered only by the user's blanket "approved".

### Gaps Summary

One blocking gap. The phase goal says anyone with a Google account can sign in, and ROADMAP SC-2 explicitly includes a user never added as a test user. The Google consent screen is still in Testing, so that is false today. The root cause is a missing privacy policy page that Google's Branding step requires before the app can be published. Closing it needs a small code change (a `/privacy/` page linked from the footer, then deployed), then a user-only action in Google Cloud Console (fill Branding, Publish app to In production), then a re-test with a never-added Google account. Everything else in the phase (Django 6.1 cleanup, env-driven settings, auto-deploy, lockdown, in-app hint, default-deny auth) is present, wired and exercised live. Suggested next step: `/gsd-plan-phase 1 --gaps`.

---

_Verified: 2026-10-20_
_Verifier: Claude (gsd-verifier)_
