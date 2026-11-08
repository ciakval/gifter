---
phase: 01-google-sign-in-live
verified: 2026-11-08T18:40:00Z
status: human_needed
score: 4/5 must-haves verified
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
  - .planning/phases/01-google-sign-in-live/01-06-PLAN.md
  - .planning/phases/01-google-sign-in-live/01-06-SUMMARY.md
  - .planning/phases/01-google-sign-in-live/01-07-PLAN.md
  - .planning/phases/01-google-sign-in-live/01-07-SUMMARY.md
  - .planning/phases/01-google-sign-in-live/01-08-PLAN.md
  - .planning/phases/01-google-sign-in-live/01-08-SUMMARY.md
  - DEPLOYMENT.md
  - Dockerfile
  - compose.yaml
  - gifter/adapters.py
  - gifter/admin.py
  - gifter/inapp.py
  - gifter/management/commands/promote_staff.py
  - gifter/models.py
  - gifter/static/gifter/landing.js
  - gifter/templates/gifter/base.html
  - gifter/templates/gifter/home.html
  - gifter/templates/gifter/landing.html
  - gifter/templates/gifter/privacy.html
  - gifter/tests/test_allauth_pages.py
  - gifter/tests/test_auth.py
  - gifter/tests/test_inapp.py
  - gifter/tests/test_lockdown.py
  - gifter/tests/test_privacy.py
  - gifter/urls.py
  - gifter/views.py
  - pyproject.toml
  - scripts/container-smoke.sh
  - scripts/smoke.sh
  - uv.lock
  - web/settings.py
  - web/urls.py
covered_digest: "v4:sha256:61bef4083cc9f14016240ad9f53d62af60e4e6994f4040138ff8a4e2d0784426"
behavior_unverified: 1
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 5/6
  gaps_closed:
    - "Missing /privacy/ page and footer link (code side of the SC-2 gap): now live, 200 anonymously, linked from the landing footer"
  gaps_remaining: []
  regressions: []
behavior_unverified_items:
  - truth: "A user whose Google account was never added as a test user can sign in (ROADMAP SC-2, AUTH-01)"
    test: "From a Google account that was never a test user, open https://gifter.remesh.cz, press the Google button, finish the Google flow"
    expected: "No 'Access blocked' or 'app is being tested' screen from Google; lands on /events/ greeted by name"
    why_human: "The user reports the consent screen is now Published (In production), but Google Cloud Console state is not observable from the repo or from outside, and the user declined to run the sign-in. Nothing in the codebase can prove Google's side."
human_verification:
  - test: "Never-test-user sign-in (SC-2, AUTH-01), then confirm that account is bounced from /gifter-admin/ to /events/"
    expected: "Signs in with no Google testing or blocked screen, greeted by name on /events/; /gifter-admin/ does not admit it"
    why_human: "Depends on the Google Cloud Console publishing state and a real never-added Google account. This is the only evidence that closes the previous blocking gap. User declined to run it on 2026-11-08."
  - test: "While signed in on desktop, reload /events/ (both deploys have already happened); then fully close and reopen the browser and open /events/; then Sign out and sign in again"
    expected: "Session survives the redeploys and the browser restart with no new Google prompt; Sign out returns to the landing page and /events/ then redirects to sign-in"
    why_human: "Real browser restart and cross-deploy session survival. Only cookie Max-Age 7776000 and POST-only logout are test-proven. Declined."
  - test: "Open the landing page and /events/ on a phone, including the footer Privacy policy link"
    expected: "Readable and tappable at phone width"
    why_human: "Visual check. Declined."
  - test: "Open https://gifter.remesh.cz inside the real Messenger and Instagram in-app browsers"
    expected: "The 'Open Gifter in your browser' hint shows instead of the Google button; the menu wording in the copy ('Tap the ... menu', 'Open in browser', 'Open in Safari/Chrome') matches the real apps; Copy link works; Continue anyway shows the Google button"
    why_human: "Server-side detection is proven live with a spoofed FBAN/FBIOS user agent, but the real apps' wording and clipboard behaviour were never captured on a device. Declined."
---

# Phase 1: Google Sign-in Live Verification Report

**Phase Goal:** Anyone with a Google account can sign in to Gifter at https://gifter.remesh.cz. The site runs on a cleaned-up Django 6.1 codebase that redeploys automatically from `main`.
**Verified:** 2026-11-08
**Status:** human_needed
**Re-verification:** Yes, after gap closure plans 01-06, 01-07 and 01-08

Note on mode: ROADMAP marks the phase `mode: mvp`, but the goal is not in user-story format (acknowledged in the plans), so standard goal-backward verification was applied.

## Result in one paragraph

Everything that can be checked from the repository and from outside the Google Cloud Console passes. The previous blocking gap (no privacy page, so the consent screen could not be published) is closed on the code side: `/privacy/` is live, public, and linked from the footer. The user reports the consent screen is now Published, but that is a user statement about state this verification cannot observe, and the user declined the never-added-Google-account sign-in that would prove it. SC-2's "including a user never added as a test user" clause is therefore recorded as present-but-unproven (human item), not as passed and not as a code gap. No code gap remains.

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | https://gifter.remesh.cz shows the landing page over HTTPS; every push to `main` redeploys without losing `./data` | VERIFIED (session survival across deploy is a human item) | Live `GET /` 200 via Caddy, HSTS `max-age=3600; includeSubDomains`. `gh run list`: push run 42508044579 and workflow_dispatch run 42508233756 on main both `success`. `compose.yaml` bind-mounts `./data`; DB lives in `DATA_DIR/db.sqlite3` (WAL). Live site serves `/privacy/` added in 01-06, so the deployed image contains the newest code. Deployed SHA 1a47ff0 equals origin/main; HEAD is 20be54e, docs only (`git diff 1a47ff0 HEAD` touches only .planning). |
| 2 | A user can sign in with Google, **including a never-added test user**; Google is the only way in; `/login/` gone; stays signed in across browser restart; can sign out | **Code side VERIFIED; never-added-user clause PRESENT_BEHAVIOR_UNVERIFIED** | Google-only: live `/login/` 404, `/admin/` 404, `/accounts/signup/` 404, `/accounts/password/reset/` 404, `/accounts/google/login/token/` 404, `/accounts/3rdparty/` 404, `/accounts/inactive/` 404, `/accounts/login/` 302 to `/`. Live OAuth start redirects to accounts.google.com with `redirect_uri=https://gifter.remesh.cz/accounts/google/login/callback/` (smoke g). Author signed in live earlier (user-confirmed in 01-05). 90-day cookie and POST-only logout test-proven. Consent screen: user reports "published"; not observable by this verification; real never-added sign-in not run (user declined). See human_verification 1. |
| 3 | A signed-out visitor opening any non-landing page is sent to sign in, then returned to that page | VERIFIED | Live `/events/` 302 to `/?next=/events/` (smoke c). `LoginRequiredMiddleware`, `LOGIN_URL="landing"`; round-trip and open-redirect tests pass in the 72-test suite. |
| 4 | Messenger/Instagram in-app browser shows an "open in your browser" hint instead of a Google error | VERIFIED (server side); real-device wording is a human item | Spoofed-UA live check passed in the earlier verification; `gifter/inapp.py` and 14 `test_inapp.py` tests pass. Real app menu wording never captured. |
| 5 | Django 6.1, small pinned deps, `DEBUG` off, secrets from server `.env`, `check --deploy` passes in CI | VERIFIED | `pyproject.toml`: exactly 5 runtime deps (Django>=6.1,<6.2, allauth, environ, gunicorn, whitenoise); `uv lock --locked` clean (19 packages). Settings fail closed without `SECRET_KEY` and Google credentials when DEBUG is off. `check --deploy --fail-level WARNING` with DEBUG=0 only flags W009 for the throwaway short key I supplied for the probe; CI test job runs the same gate and passed twice. Live `/login/` plain 404 confirms DEBUG off. |

**Score:** 4/5 truths verified, 1 present but behavior-unverified (SC-2's never-added-user clause; the rest of SC-2 is verified, the unproven part is Google-side state).

### Gap-closure plan truths (01-06, 01-07, 01-08)

| Item | Status | Evidence |
|------|--------|----------|
| `/privacy/` public, no personal data, only Phase 1 data described | VERIFIED | Live: 200 anonymous, no redirect. Page text lists stored Google data, cookies, EU server, deletion by email; says it will be updated before wishlists/events; no claims/chip-in/member mentions. 15 tests in `test_privacy.py` pass. |
| Footer link to `/privacy/` on every page | VERIFIED | Live landing HTML contains `<a href="/privacy/">Privacy policy</a>`; smoke (i) passes. |
| Contact comes only from `GIFTER_CONTACT_EMAIL`, no address in tracked files | VERIFIED | `git grep "@gmail"` outside `.planning` finds nothing; live page shows the configured contact. |
| No Google tokens stored | VERIFIED | `SOCIALACCOUNT_STORE_TOKENS = False` in settings; pinned by mocked sign-in test. |
| `deploy.yml`: `latest` only on main, SHA-pinned actions, `contents: read` | VERIFIED | `type=raw,value=latest,enable=${{ github.ref == 'refs/heads/main' }}`; all `docker/*`, `actions/*`, `astral-sh/*` uses are 40-hex SHAs with version comments; `permissions: contents: read` at workflow and job level. `secrets: inherit` and `@v1` on the bombur-deploy call remain (WR-02 recorded as partial/deferred). |
| Accounts allowlist: only the 7 listed routes resolve, URL-table test | VERIFIED | `web/urls.py` allowlist with docstring; 27 tests in `test_lockdown.py`; live 404s listed above. |
| Adapters prevent NoReverseMatch 500s and block connect | VERIFIED | `gifter/adapters.py` `respond_user_inactive`, `pre_social_login` (refuses `AuthProcess.CONNECT`), `get_connect_redirect_url`; wired via `ACCOUNT_ADAPTER` / `SOCIALACCOUNT_ADAPTER` in settings. |
| Admin: no SocialApp/SocialToken, social accounts and emails read-only, Wish not registered | VERIFIED | `gifter/admin.py` unregisters SocialApp/SocialToken, read-only SocialAccount/EmailAddress admins (add/change denied, `actions = []`); no Wish registration. |
| `promote_staff` trusts only Google-verified email with uid output | VERIFIED | Command requires verified `EmailAddress` row AND Google `SocialAccount.extra_data` email match with `email_verified`; refuses on none or ambiguous; prints uid. |
| Smoke covers (h)-(k) live | VERIFIED | Re-run by me against production: PASS (a) through (k), `SMOKE OK`. |
| Review dispositions recorded | VERIFIED | `01-REVIEW-DISPOSITION.md`: 15 findings, 0 open; WR-01/03/04/05 fixed, WR-02 partial-deferred with reason, others deferred with target phase. |
| Plan 01-08 never-test-user sign-in, admin bounce, session survival, phone, in-app wording reported | NOT RUN (user declined) | Recorded as human verification items, never as pass. |

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `gifter/templates/gifter/privacy.html`, `gifter/views.py` privacy view, `gifter/urls.py` route | VERIFIED | Exists, substantive, wired, live 200 |
| `gifter/templates/gifter/base.html` footer | VERIFIED | Link present on live landing |
| `gifter/adapters.py`, `gifter/admin.py`, `promote_staff.py`, `web/urls.py` | VERIFIED | Substantive and wired (settings + URL conf) |
| `.github/workflows/deploy.yml`, `scripts/smoke.sh` | VERIFIED | Hardened; two green runs; smoke passes live |
| `web/settings.py`, `pyproject.toml`, `uv.lock`, `Dockerfile`, `compose.yaml`, `.env.example`, `DEPLOYMENT.md` | VERIFIED | No regressions from the first verification |

### Key Link Verification

| From | To | Status | Details |
|------|----|--------|---------|
| landing form | `/accounts/google/login/` | WIRED | POST with CSRF and `next`; live OAuth start redirects to Google |
| Google client | `https://gifter.remesh.cz/accounts/google/login/callback/` | WIRED | Live `redirect_uri` matches exactly |
| landing footer | `/privacy/` | WIRED | Live HTML and smoke (i) |
| `LoginRequiredMiddleware` | landing with `next` | WIRED | Live `/events/` 302 |
| settings | `gifter.adapters.*` | WIRED | `ACCOUNT_ADAPTER`, `SOCIALACCOUNT_ADAPTER` |
| `deploy.yml` | Bombur via `bombur-deploy@v1` | WIRED | Runs 42508044579 and 42508233756 succeeded |

### Data-Flow Trace (Level 4)

Landing and privacy pages render static copy plus settings constants (contact email, policy date); no dynamic user data. Live privacy page shows the configured contact, confirming the setting reaches the template.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Test suite | `DEBUG=1 uv run python manage.py test` | Ran 72 tests, OK | PASS |
| Live contract | `bash scripts/smoke.sh https://gifter.remesh.cz` | PASS (a)-(k), SMOKE OK | PASS |
| Live route table | curl of `/ /privacy/ /events/ /login/ /admin/ /accounts/{login,signup,google/login/token,3rdparty,inactive,password/reset}/` | 200, 200, 302-to-next, 404, 404, 302, 404, 404, 404, 404, 404 | PASS |
| Lock reproducible | `uv lock --locked` | Resolved 19 packages | PASS |
| Deploy audit | `check --deploy --fail-level WARNING` (DEBUG=0, placeholder env) | Only W009 for my deliberately short probe key | PASS |

### Probe Execution

No `probe-*.sh` scripts declared by the phase. Skipped.

### Requirements Coverage

| Requirement | Source Plans | Status | Evidence |
|-------------|--------------|--------|----------|
| OPS-01 Django 6.1, minimal pinned deps | 01-01, 01-04 | SATISFIED | uv.lock Django 6.1.x, 5 runtime deps |
| OPS-02 env-driven prod settings, rotated key, DEBUG off, hosts/CSRF origins | 01-01, 01-04, 01-06 | SATISFIED | Fail-closed settings; contact via env; no committed secret |
| OPS-03 reachable at gifter.remesh.cz via Actions, GHCR, Compose, SQLite in ./data | 01-04, 01-05, 01-06, 01-08 | SATISFIED | Live; two green runs this round; hardened workflow. Data survival across a redeploy with a live session is a human item. |
| OPS-04 in-app browser hint | 01-03, 01-05 | SATISFIED (server side) | Real-device wording is a human item |
| AUTH-01 sign in with Google (only method, `/login/` removed) | 01-01, 01-02, 01-05, 01-06, 01-07 | SATISFIED (code); never-added-account proof is a human item | Google-only enforced by URL allowlist and live 404s; consent screen reported published |
| AUTH-02 stays signed in, can sign out | 01-01, 01-05 | SATISFIED (code); real-browser restart is a human item | 90-day cookie, POST logout tests |
| AUTH-03 every page except landing requires sign-in | 01-01, 01-05 | SATISFIED | Live and test-proven. `/privacy/` is a deliberate public page, consistent with the landing exception and Google's Branding requirement. |

All 7 phase IDs (OPS-01..04, AUTH-01..03) appear in plan frontmatter and in REQUIREMENTS.md as Phase 1 / Complete. No orphaned requirements: REQUIREMENTS.md maps only these IDs to Phase 1 (OPS-05/06 are Phase 4).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (phase files) | - | TBD/FIXME/XXX grep over `gifter web scripts Dockerfile compose.yaml .github DEPLOYMENT.md` | none found | No debt-marker blocker |
| `.github/workflows/deploy.yml` | 118 | `bombur-deploy@v1` mutable ref with `secrets: inherit` | Warning (known, WR-02 partial) | Supply-chain hygiene; recorded in disposition with follow-up in bombur-deploy |
| `gifter/models.py` | - | `Wish.claimed_by` on giftee-readable row (WR-06) | Warning | Deferred to Phase 2 per disposition; not a Phase 1 must-have |

### Human Verification Required

These are verification items the user declined on 2026-11-08 ("I want the app to start being usable asap"). They are open, not passed, and not code gaps.

1. **Never-test-user Google sign-in and admin bounce** (SC-2, AUTH-01). Test: sign in from a Google account never added as a test user. Expected: no Google "testing" or "Access blocked" screen; greeted by name on `/events/`; `/gifter-admin/` does not admit it. Why human: Google Cloud Console state is not observable here; the user's "published" report is unconfirmed. This is the one item that proves the phase goal's "anyone with a Google account" clause.
2. **Session persistence** (AUTH-02, SC-1). Test: reload `/events/` on a desktop session that predates the deploys; fully restart the browser; sign out; sign in again. Expected: session survives deploys and restart; sign-out returns to landing.
3. **Phone layout** of landing, `/events/`, footer link. Expected: readable and tappable.
4. **Real Messenger and Instagram in-app hint** (SC-4, OPS-04). Expected: hint shows, menu wording in the copy matches the real apps, Copy link works, Continue anyway shows the Google button.

### Gaps Summary

No code gaps. The previous blocking gap's code cause (missing privacy page and footer link) is fixed and live; the Google-console half is user-operated and user-reported as done. Practical risk to flag: if the consent screen is not actually published, any relative who is not a listed test user will hit Google's testing wall; the first real relative sign-in (or check 1 above) will reveal it immediately and fixing it needs no code change. Also keep the privacy page in step with features: update it and bump `PRIVACY_POLICY_UPDATED` before Phase 2 ships wishlists, events and members.

---

_Verified: 2026-11-08_
_Verifier: Claude (gsd-verifier)_
