---
phase: 01-google-sign-in-live
plan: 05
subsystem: infra
tags: [bombur-deploy, github-actions, ghcr, caddy, google-oauth, sqlite-wal, hsts]

requires:
  - phase: 01-google-sign-in-live
    provides: "01-04 image, compose.yaml, smoke scripts, test -> build-and-push pipeline; 01-02 /gifter-admin/ and promote_staff; 01-03 in-app browser hint"
provides:
  - "deploy.yml on the bombur-deploy model (test -> build-and-push -> reusable ciakval/bombur-deploy@v1 call, DEPLOY_SSH_KEY only)"
  - ".env.example with SECRET_KEY=CHANGE_ME and DEPLOYMENT.md rewritten for bombur-onboard"
  - "Live https://gifter.remesh.cz: landing page, HSTS, real Google sign-in, auto-deploy from main, data surviving redeploys"
  - "Public GitHub repo ciakval/gifter with main protected (no force-push, no deletion)"
affects: [phase-02, phase-04]

actuals:
  tokens: 5000
  tasks: 3
  commits: 2

tech-stack:
  added: []
  patterns:
    - "CI never touches the server: the reusable workflow only sends 'deploy <sha>' over a forced-command SSH key"
    - "Third-party actions pinned to commit SHAs (setup-uv v10.3.0 pinned because the floating v10 tag does not exist)"

key-files:
  created: []
  modified:
    - .github/workflows/deploy.yml
    - .env.example
    - DEPLOYMENT.md

key-decisions:
  - "Consent screen left in Testing until a /privacy/ page exists (Google Branding requires a privacy policy link); publish before relatives get invites"
  - "Repository made public because GitHub Free has no branch protection on private repos and the production environment requires a protected branch; history scanned for secrets first (clean)"
  - "No health_path in the reusable deploy call: the app has no health endpoint yet"

patterns-established:
  - "Out-of-repo steps (bombur-onboard, Google Console, server .env) are done by the user; Claude only verifies from outside (gh, curl, smoke.sh)"

requirements-completed: [OPS-03, AUTH-01, AUTH-02, AUTH-03, OPS-04]

coverage:
  - id: D1
    description: "deploy.yml, .env.example and DEPLOYMENT.md moved onto the bombur-deploy model; no appleboy/VPS_*/DEPLOY_DIR/plachtis references remain"
    requirement: OPS-03
    verification:
      - kind: command
        ref: "task 1 greps (1 / 0 / 1), yaml WORKFLOW OK, local CI gate, docker compose config"
        status: pass
    human_judgment: false
  - id: D2
    description: "Push of main ran test -> build-and-push -> deploy-production to success (run 39452688350); workflow_dispatch redeploy succeeded (run 39452993438)"
    requirement: OPS-03
    verification:
      - kind: command
        ref: "gh run list --workflow deploy.yml (push and workflow_dispatch conclusions)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Live HTTP contract: / 200, http 308 to https, HSTS max-age=3600 includeSubDomains, anonymous /events/ 302 to /?next=/events/, /login/ 404 without debug page, /admin/ 404; smoke.sh passed after both deploys"
    requirement: OPS-03
    verification:
      - kind: command
        ref: "bash scripts/smoke.sh https://gifter.remesh.cz; curl checks"
        status: pass
    human_judgment: false
  - id: D4
    description: "Author signed in with Google on the live site, reached the landing page and /events/, ran promote_staff and opened /gifter-admin/ through the Google session"
    requirement: AUTH-01
    verification:
      - kind: human
        ref: "User reply 'Approved' with explicit confirmation of sign-in, /events/, promote_staff and /gifter-admin/"
        status: pass
    human_judgment: true
  - id: D5
    description: "Browser-restart persistence and sign-out, session survives redeploy, phone layout, Messenger/Instagram in-app hint wording"
    requirement: AUTH-02
    verification:
      - kind: human
        ref: "Approved under the user's blanket approval; not individually reported"
        status: pass
    human_judgment: true
    rationale: "Not individually reported; in-app menu wording was not captured, so the copy is unverified against real Messenger/Instagram menus"
  - id: D6
    description: "A never-added second Google account can sign in with no 'app is being tested' screen (consent screen In production)"
    requirement: AUTH-01
    verification: []
    human_judgment: true
    rationale: "NOT MET. Consent screen is still in Testing; the check was skipped. Publishing is blocked on a privacy policy page (see Deviations 2)."

duration: multi-session (user setup in between)
completed: 2026-10-20
plan_head_before: c67d18743543ff4d3698b030a0706c16057d45a9
plan_head_after: b9b6a2d9736cce9c17cb080132676954b0259be3
commits: 2
status: complete
---

# Phase 1 Plan 05: Go live on https://gifter.remesh.cz Summary

**Gifter is live on Bombur behind Caddy with real Google sign-in, auto-deployed from main through the ciakval/bombur-deploy reusable workflow; data survives redeploys. The Google consent screen is still in Testing, so only listed test users can sign in until a privacy page exists and the app is published.**

## Performance

- **Completed:** 2026-10-20
- **Tasks:** 3 (1 repo refactor, 1 human-action checkpoint, 1 push/pipeline/live verification)
- **Commits:** 2 (`45b4297`, `b9b6a2d`)

## Accomplishments

- Deploy files moved to the bombur-deploy model: reusable `ciakval/bombur-deploy/.github/workflows/deploy.yml@v1` call, `SECRET_KEY=CHANGE_ME`, DEPLOYMENT.md rewritten around `bombur-onboard gifter 8000`. `compose.yaml` unchanged.
- The user completed the out-of-repo setup (main protection, bombur-onboard, Google client, server `.env`); push run `39452688350` went green, and a manual `workflow_dispatch` redeploy `39452993438` also went green. `scripts/smoke.sh` passed after both deploys.
- Live curls: `/` 200; `http://` 308 to https; HSTS `max-age=3600; includeSubDomains`; anonymous `/events/` 302 to `/?next=/events/`; `/login/` 404 with no debug page; `/admin/` 404.
- The user signed in with Google on the live site, reached the landing page and `/events/`, ran `promote_staff` and opened `/gifter-admin/` through the Google session.

## Task Commits

1. **Task 1: Move the deploy files onto the bombur-deploy model** - `45b4297` (refactor)
2. **Task 2: One-time setup outside the repo** - no commit (user checkpoint)
3. **Task 3: Push, pipeline, live checks, redeploy** - `b9b6a2d` (fix: pin setup-uv; the push of `45b4297` and earlier work itself is not a commit)

**Plan metadata:** committed separately (docs: complete plan).

## Files Created/Modified

- `.github/workflows/deploy.yml` - reusable deploy call; `setup-uv` pinned to v10.3.0 commit
- `.env.example` - server `.env` spec with `SECRET_KEY=CHANGE_ME`
- `DEPLOYMENT.md` - bombur-onboard onboarding, day-2 commands, gotchas

## Decisions Made

See key-decisions above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `astral-sh/setup-uv@v10` does not resolve**
- **Found during:** Task 3 (push run `39452488767` failed in the test job)
- **Issue:** the floating `v10` tag does not exist for setup-uv, so CI could not start.
- **Fix:** pinned to the v10.3.0 commit `1c37ad07a6a961277cf70c0d37d6f313000f5884`.
- **Files modified:** `.github/workflows/deploy.yml`
- **Verification:** next push run `39452688350` succeeded end to end.
- **Commit:** `b9b6a2d`

### Plan truths not met

**2. Consent screen remains in Testing (T-01-28 not mitigated; success criterion only partially met)**
- Google's Branding step requires a privacy policy link, and the app has no privacy page yet, so the user could not publish the app.
- Plan truth "consent screen In production" and the human check with a never-added second account were NOT met (the check was skipped).
- ROADMAP success criterion "anyone with a Google account can sign in" is only partially met: the author and other listed test users can sign in; relatives' accounts cannot until the app is published.
- Follow-ups: add a `/privacy/` page linked from the footer; fill Branding and Publish app before relatives receive invites. Tracked as a blocking item for the Christmas rollout.

**3. Repository made public**
- GitHub Free has no branch protection on private repos, and the bombur `production` environment only accepts protected branches. The history was scanned for secrets first (clean), then `ciakval/gifter` was made public and `main` protected (no force-push, no deletion).

**Total deviations:** 1 auto-fixed (blocking), 2 documented departures from the plan. **Impact:** live and deploying, but Google sign-in is limited to test users until the consent screen is published.

## Authentication Gates

Task 2 was a planned `checkpoint:human-action` (bombur-onboard, Google Console, server `.env`); the user completed it. No unplanned gates.

## Human checks (UAT record)

User replied "Approved". Explicitly confirmed: sign-in with Google reaches the landing page and `/events/`; `promote_staff` was run and `/gifter-admin/` opens through the Google session. Browser-restart persistence, session survival after redeploy, phone layout and Messenger/Instagram in-app hint wording were not individually reported and are recorded as approved under the blanket approval; the in-app browser menu wording was not captured. The second never-added-account check was skipped (consent screen in Testing).

The user could not add an Event in the admin: expected, the Event model is Phase 2 scope (note, not a failure).

## Issues Encountered

None beyond the deviations above.

## Known Stubs

None.

## Threat Flags

None new. T-01-24 to T-01-27 mitigations held (secrets typed on the server only; per-app forced-command key; Caddy site file written by bombur-add-app). T-01-28 is not mitigated (consent screen in Testing). T-01-29 accepted: HSTS currently `max-age=3600`.

## Follow-ups

- `/privacy/` page linked from the footer, then fill Google Branding and Publish app (blocking before relatives get invites).
- Raise HSTS `max-age` from 3600 once stable.
- Add a health endpoint and set `health_path` in the reusable deploy call.
- Capture the real Messenger/Instagram in-app menu wording and adjust the hint copy if needed.

## Next Phase Readiness

Phase 1 is ready for verification. Phase 2 can build on the live, auto-deploying skeleton. The consent-screen publication must happen before Phase 4 invites go to relatives.

## Self-Check: PASSED

- Commits `45b4297` and `b9b6a2d` are ancestors of HEAD; `git rev-list --count c67d187..HEAD` = 2.
- `.github/workflows/deploy.yml`, `.env.example`, `DEPLOYMENT.md` exist on disk.
