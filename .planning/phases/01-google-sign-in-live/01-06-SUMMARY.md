---
phase: 01-google-sign-in-live
plan: 06
subsystem: auth
tags: [privacy-policy, google-branding, github-actions, sha-pinning, smoke-test, gap-closure]
status: complete

requires:
  - phase: 01-google-sign-in-live
    provides: "01-01 landing and Google sign-in, 01-03 in-app hint, 01-05 live pipeline and smoke scripts"
provides:
  - "Public /privacy/ page (login_not_required), honest about Phase 1 data only, fully wrapped for translation"
  - "Footer link to /privacy/ on every page extending gifter/base.html (landing, home, allauth pages, the policy itself)"
  - "GIFTER_CONTACT_EMAIL env setting (mailto link, or ask-the-inviter fallback); no address in any tracked file"
  - "SOCIALACCOUNT_STORE_TOKENS = False pinned by a mocked sign-in test"
  - "deploy.yml: latest tag only on main, all third-party actions SHA-pinned with version comments, contents: read defaults"
  - "scripts/smoke.sh checks (h) /privacy/ and (i) landing footer link"
  - "DEPLOYMENT.md Branding step with exact field values, contact setting, privacy-page rule"
affects: [01-07, 01-08, phase-02, phase-03, phase-04]

actuals:
  tokens: 5300
  tasks: 3
  commits: 5

plan_head_before: 534c381b80e70d1f0a4c0dd61222a93a593f2bbc
plan_head_after: c494f2f79cab929034021cbcf363b15a5eba6dd6
commits: 5

tech-stack:
  added: []
  patterns:
    - "Public pages use @login_not_required and read only constants/settings, never user or wish data"
    - "Privacy policy is updated BEFORE any feature that stores or shows new data kinds ships (bump PRIVACY_POLICY_UPDATED)"
    - "Third-party actions pinned as OWNER/REPO@SHA  # vX.Y.Z"

key-files:
  created:
    - gifter/templates/gifter/privacy.html
    - gifter/tests/test_privacy.py
  modified:
    - gifter/views.py
    - gifter/urls.py
    - gifter/templates/gifter/base.html
    - web/settings.py
    - .env.example
    - DEPLOYMENT.md
    - .github/workflows/deploy.yml
    - scripts/smoke.sh

key-decisions:
  - "Keep secrets: inherit and the @v1 ref on the bombur-deploy call: v1 declares no workflow_call secrets, and ciakval is its only collaborator"
  - "Policy copy avoids the words claim, chip and member (even inside 'remember') so a test can prove it describes no unbuilt features"
  - "Footer is a separate <footer> after the body block so templates overriding body keep it; landing content untouched (D-01)"

requirements-completed: [AUTH-01, OPS-02, OPS-03]

coverage:
  - id: D1
    description: "Anonymous visitor reads /privacy/ (200, no redirect) with honest Phase 1 content, no user data, no third-party assets, contact variants"
    requirement: AUTH-01
    verification:
      - kind: test
        ref: "gifter/tests/test_privacy.py#PrivacyPageTests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every page, including the landing page, links to /privacy/ in the footer"
    requirement: AUTH-01
    verification:
      - kind: test
        ref: "gifter/tests/test_privacy.py#FooterLinkTests"
        status: pass
    human_judgment: false
  - id: D3
    description: "No Google tokens stored: setting pinned False and a mocked sign-in leaves zero SocialToken rows"
    requirement: AUTH-01
    verification:
      - kind: test
        ref: "gifter/tests/test_privacy.py#NoStoredTokensTests"
        status: pass
    human_judgment: false
  - id: D4
    description: "Contact address comes only from GIFTER_CONTACT_EMAIL; documented in .env.example and DEPLOYMENT.md"
    requirement: OPS-02
    verification:
      - kind: command
        ref: "grep -cE 'mailto:[A-Za-z0-9]' privacy.html -> 0; test_contact_email_is_a_mailto_link"
        status: pass
    human_judgment: false
  - id: D5
    description: "deploy.yml: latest only for refs/heads/main, 7 action steps SHA-pinned with version comments, contents: read at workflow and test-job level"
    requirement: OPS-03
    verification:
      - kind: command
        ref: "structure check (python equivalent of the plan's ruby script) -> WORKFLOW OK; version-comment grep -> 0 missing"
        status: pass
    human_judgment: false
  - id: D6
    description: "Production image passes smoke including (h) /privacy/ and (i) landing link"
    requirement: OPS-03
    verification:
      - kind: command
        ref: "bash scripts/container-smoke.sh -> PASS (h), PASS (i), CONTAINER SMOKE OK"
        status: pass
    human_judgment: false
  - id: D7
    description: "Whether the policy wording satisfies Google's Branding review and reads well to relatives"
    requirement: AUTH-01
    human_judgment: true
    rationale: "Outcome depends on Google's reviewer and on the user's reading; verified live in plan 01-08"
---

# Phase 1 Plan 06: Public privacy page and pipeline hardening Summary

**Public, honest `/privacy/` page (linked from every footer, contact from env) as the prerequisite for publishing the Google consent screen, plus a deploy.yml with `latest` only from main, SHA-pinned actions and read-only default permissions.**

## Performance

- **Duration:** about 3 min wall clock for the agent run
- **Started:** 2026-11-08T17:39:29Z
- **Completed:** 2026-11-08T17:42:40Z (clock of the executing session)
- **Tasks:** 3 (tracer, TDD footer, CI hardening)
- **Files:** 2 created, 8 modified

## Accomplishments

- `/privacy/` is public, translatable (wrap check ALL WRAPPED), says what Phase 1 stores (Google account ID, name, email and verified flag, profile picture address, join and last sign-in times), that no tokens are kept, EU hosting, no sale or sharing, and how to request deletion. It does not mention wishes, claims or members.
- Footer link on every page; landing content unchanged.
- `GIFTER_CONTACT_EMAIL` setting with `.env.example` line and DEPLOYMENT.md docs; `SOCIALACCOUNT_STORE_TOKENS = False` with a mocked sign-in test.
- DEPLOYMENT.md has the Google Branding step with exact fields (app name, home page, privacy link, authorized domain `remesh.cz`, no logo) before Publish.
- WR-01 closed; WR-02 closed for action pins and permissions, partially for `secrets: inherit` (see below).

## Task Commits

1. **Task 1 (tracer): /privacy/ end to end** - `5baa09e` (feat)
2. **Task 2 RED: footer tests, 5 failing** - `6ab3c51` (test)
3. **Task 2 GREEN: footer in base.html** - `39ee9d3` (feat)
4. **Task 2: Branding steps, contact setting docs, privacy rule** - `43bd69f` (docs)
5. **Task 3: deploy.yml hardening and smoke (h)/(i)** - `c494f2f` (ci)

The tracer gate ran in yolo/end-of-phase mode: the `<verify>` commands were re-run end to end (privacy tests, full suite, wrap check) and passed before expansion.

## Resolved action pins (WR-02)

| Action | Commit SHA | Comment |
|---|---|---|
| actions/checkout (2 steps) | d23441a48e516b6c34aea4fa41551a30e30af803 | v6.1.0 |
| docker/setup-buildx-action | 8d2750c68a42422c14e847fe6c8ac0403b4cbd6f | v3.12.0 |
| docker/login-action | 8aa5831fb8d48d8f76594c7ddde61ae58019f550 | v4.8.0 |
| docker/metadata-action | dc802804100637a589fabce1cb79ff13a1411302 | v6.2.0 |
| docker/build-push-action | c3c9e263c25d99ce0380d002d59b67737d91b0dc | v7.4.0 |
| astral-sh/setup-uv (unchanged) | 1c37ad07a6a961277cf70c0d37d6f313000f5884 | v10.3.0 |

All major tags are lightweight tags (`.object.type` is `commit`), so `commits/vN` and `git/ref/tags/vN` agreed; no peeling was needed. Majors were not upgraded.

## bombur-deploy findings (T-01-35, accepted)

- `ciakval/bombur-deploy` at v1 (`2839093b05e2008a6c52967d4cc0d731aa49fdf6`) declares only `inputs` under `workflow_call`, no `secrets:`. `secrets: inherit` therefore stays, with a comment containing "declares no workflow_call secrets".
- Collaborators: only `ciakval`, so the `@v1` ref stays (no pin to the commit).
- Secret names (never values): repo-level secrets none; `production` environment secret `DEPLOY_SSH_KEY`.
- **Follow-up:** declare `DEPLOY_SSH_KEY` in `ciakval/bombur-deploy` `workflow_call.secrets`, then map it explicitly in gifter's `deploy.yml` in place of `secrets: inherit`.

## Notes for later phases

- **Phase 2** must update `/privacy/` (and bump `PRIVACY_POLICY_UPDATED`) BEFORE wishlists, events and member lists ship. **Phase 3** before claims and chip-ins. **Phase 4** for backups and the language cookie. The rule is recorded in DEPLOYMENT.md "Rules and gotchas".
- Plan 01-08 must set `GIFTER_CONTACT_EMAIL` on the server `.env` if the user wants a contact address, deploy, fill in Branding with `https://gifter.remesh.cz/privacy/`, then publish.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `ruby` not installed, so the plan's WORKFLOW OK check could not run as written**
- **Found during:** Task 3 verify
- **Issue:** `ruby: command not found`
- **Fix:** Ran an equivalent structure check with `uv run --with pyyaml python` (ephemeral environment, no project dependency added): top-level and test-job permissions, exactly 7 action steps all pinned to 40-hex SHAs, deploy call ref. Printed "WORKFLOW OK (python equivalent)".
- **Files modified:** none
- **Commit:** n/a

**2. [Rule 3 - Blocking] `uv sync` recreated `.venv`**
- **Found during:** Task 1 verify
- **Issue:** uv removed and recreated `.venv` (now Python 3.15) on first run; dependencies identical per `uv.lock`; no tracked file changed.
- **Fix:** None needed. Full suite (56 tests) passes.

The `check --deploy` gate needed `PUBLIC_HOSTS`, `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` set (as CI does with dummy values); run that way it reported no issues.

**Total deviations:** 2 auto-fixed (both environment, Rule 3). **Impact:** none on scope or results.

## Known Stubs

None.

## Threat Flags

None. The new public endpoint `/privacy/` and its mitigations (T-01-31 to T-01-36) are covered by the plan's threat model.

## Issues Encountered

None.

## Next Phase Readiness

Ready for 01-07 (Google-only door hardening) and 01-08 (deploy, Branding, publish, human checks). Nothing was pushed; 01-08 deploys.

## Self-Check: PASSED

- Created files exist: gifter/templates/gifter/privacy.html, gifter/tests/test_privacy.py
- Commits reachable from HEAD: 5baa09e, 6ab3c51, 39ee9d3, 43bd69f, c494f2f
- Full suite 56 tests OK; makemigrations clean; `check --deploy --fail-level WARNING` clean; container-smoke printed PASS (h), PASS (i), CONTAINER SMOKE OK
