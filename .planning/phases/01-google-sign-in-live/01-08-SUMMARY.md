---
phase: 01-google-sign-in-live
plan: 08
subsystem: ops
tags: [deploy, privacy-page, consent-screen, google-oauth, smoke, gap-closure]
status: complete

requires:
  - phase: 01-google-sign-in-live
    provides: "01-06 privacy page, footer link, pipeline hardening, smoke (h)/(i); 01-07 Google-only URL allowlist, admin lockdown, promote_staff, smoke (j)/(k)"
provides:
  - "01-06 and 01-07 live on https://gifter.remesh.cz after two deploys (push + workflow_dispatch), smoke.sh SMOKE OK after each"
  - "Live /privacy/ (200 anonymous, linked from landing footer, mailto contact variant A)"
  - "Live lockdown: One Tap token POST, connections page and inactive page all 404"
  - "Google consent screen reported PUBLISHED (In production) by the user"
affects: [phase-02, phase-04, end-of-phase-uat]

actuals:
  tokens: 2000
  tasks: 3
  commits: 0

plan_head_before: 1a47ff0a199832b709104faba2c90c22a1a55767
plan_head_after: 1a47ff0a199832b709104faba2c90c22a1a55767
commits: 0

key-files:
  created: []
  modified:
    - .planning/phases/01-google-sign-in-live/01-08-SUMMARY.md
    - .planning/STATE.md
    - .planning/ROADMAP.md

key-decisions:
  - "01-08: consent screen reported published (In production) by the user; Branding fields and the never-test-user sign-in were NOT individually confirmed"
  - "01-08: human checks 1-6 declined by the user ('I want the app to start being usable asap'); recorded as later, never as pass"

requirements-completed: []

duration: multi-session
completed: 2026-11-08
---

# Phase 1 Plan 08: Deploy the privacy page and lockdown, publish the consent screen Summary

Plans 01-06 and 01-07 are live behind two green deploys and the consent screen is reported published by the user, but the proof that a never-added Google account can sign in (check 1) and all other live human checks were declined and stay open for the end-of-phase UAT.

## Outcome in one paragraph

Code side fully done and proven from outside: push deploy and a workflow_dispatch redeploy of the same HEAD both succeeded, `scripts/smoke.sh` printed `SMOKE OK` with PASS (a)-(k) after each and once more at the close of this plan. The user reported "published" for the Google Auth Platform consent screen. They declined to run checks 1-6 (verbatim: "published. I don't care about checking the rest. I want the app to start being usable asap."). Per the plan, check 1 passing is what closes the SC-2 gap, so that gap is reported as **reported-fixed but unverified**, not as closed.

## Task results

| Task | Name | Result |
|------|------|--------|
| 1 | User reviewed privacy text, set contact, authorized deploy | Done. User: "wording is good ... deploy. contact set." No wording corrections. |
| 2 | Push main, watch both deploys, prove privacy page and lockdown live | Done, no file changes, no commits. |
| 3 | User fills Branding, publishes, reports checks | Resumed with "published" and a decline of all checks. See table below. |

## Deploy evidence

| Item | Value |
|------|-------|
| Pushed range | b9b6a2d..1a47ff0 on main (17 commits, no force) |
| Deploy 1 (push) | run 42508044579, success, headSha 1a47ff0 |
| Deploy 2 (workflow_dispatch) | run 42508233756, success, headSha 1a47ff0 |
| smoke.sh after deploy 1 | SMOKE OK, PASS (a)-(k) |
| smoke.sh after deploy 2 | SMOKE OK, PASS (a)-(k) |
| smoke.sh at plan close (this segment) | SMOKE OK, PASS (a)-(k), client_id ends in .apps.googleusercontent.com, redirect_uri https://gifter.remesh.cz/accounts/google/login/callback/ |
| Live /privacy/ | 200, no redirect; landing footer links to it |
| GIFTER_CONTACT_EMAIL | Set by the user ("contact set"); variant A (mailto link) is live; the address was not printed anywhere by Claude |
| POST /accounts/google/login/token/ | 404 |
| GET /accounts/3rdparty/ | 404 |
| GET /accounts/inactive/ | 404 |

## Human checks 1-6

| # | Check | Result |
|---|-------|--------|
| 1 | Never-test-user Google account signs in, lands on /events/ greeted by name, no "Access blocked" | later (user declined to run it, wants to move on) |
| 2 | That account is bounced from /gifter-admin/ | later (user declined to run it, wants to move on) |
| 3 | Desktop session survived both deploys | later (user declined to run it, wants to move on) |
| 4 | Browser restart keeps session, sign out, sign in again | later (user declined to run it, wants to move on) |
| 5 | Phone layout: landing, /events/, footer Privacy policy link | later (user declined to run it, wants to move on) |
| 6 | Messenger and Instagram in-app hint, with the apps' exact menu wording | later (user declined to run it, wants to move on) |

None of these is recorded as pass. They remain open for the end-of-phase UAT (`/gsd-verify-work`).

## Google Cloud Console (user-operated, user-reported)

- Publishing status: user reported "published". Not independently observable by Claude (Claude must not operate the console).
- Branding fields (home page, privacy link, remesh.cz, no logo) and Data access scopes (openid, email, profile only) were not individually confirmed in the reply. Google refuses to publish without home page and privacy link, so the publish report implies Branding was filled, but this is an inference.
- Evidence that would settle it: check 1 (a real sign-in from a never-added account).

## REQUIREMENTS.md and STATE.md changes

- REQUIREMENTS.md: **unchanged on purpose.** AUTH-01, AUTH-02, OPS-03 and OPS-04 were already Complete from earlier plans. The plan's "never-added" re-verification note is only to be added when check 1 passes, and it did not run. The `requirements-completed` list is empty for this plan because no new requirement was closed.
- STATE.md: the "[blocking for Christmas rollout] /privacy/ + Publish" pending todo and the Phase 1 consent-screen blocker are resolved as user-reported (privacy page live, consent screen published) and replaced by explicit deferred human-verification items. The decision "01-08: consent screen reported published (In production), live checks deferred" is recorded.

## Deferred human verification (visible, not passed)

1. Sign in with a Google account that was never a test user (SC-2, AUTH-01) and confirm no "Access blocked"/"being tested" screen. This is the only thing that proves the publish worked and closes the 01-VERIFICATION blocking gap.
2. That account bounced from /gifter-admin/ to /events/.
3. Desktop session survives the two deploys; survives full browser restart; sign-out and sign-in again (AUTH-02, SC-1).
4. Phone layout check of landing, /events/, footer Privacy policy link.
5. Real Messenger and Instagram in-app hint check, capturing each app's exact menu wording for "open in browser" (SC-4, OPS-04). The landing copy ("Tap the ⋯ menu in the corner of the screen." / "Choose Open in browser (it may say Open in Safari or Open in Chrome).") is therefore still unconfirmed against real apps.

## Follow-ups

- Raise HSTS max-age above 3600 once the site is stable (smoke (b) currently shows max-age=3600).
- Add a health endpoint and set `health_path` in the reusable deploy call.
- In-app hint copy wording unconfirmed (deferred check 5).
- bombur-deploy: declare `DEPLOY_SSH_KEY` as a `workflow_call` secret, then replace `secrets: inherit` with an explicit mapping (carried from 01-06).
- Update /privacy/ and bump PRIVACY_POLICY_UPDATED before Phase 2 (wishlists/events/members), Phase 3 (claims/chip-ins) and Phase 4 (backups/language cookie) ship (carried from 01-06).

## Deviations from Plan

None in code. Task 3's acceptance criteria (a result for each of checks 1-6, check 1 = pass) were not met because the user chose to defer; this is a user decision, not an executor deviation. The SC-2 gap is therefore marked unverified rather than closed.

## Known Stubs

None (no files created or modified by this plan outside planning docs).

## Threat Flags

None. T-01-43 (consent screen in Testing) is mitigated only per the user's report; the mitigation is unproven until check 1 runs.

## Self-Check: PASSED

- Run ids and head SHA taken from the orchestrator's verified Task 2 evidence; smoke.sh re-run in this segment printed SMOKE OK.
- `git rev-list --count 1a47ff0..HEAD` = 0 and no code changes by this plan, so `commits: 0` is correct.
