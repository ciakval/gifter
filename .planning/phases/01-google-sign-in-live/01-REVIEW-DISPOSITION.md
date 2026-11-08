---
phase: 01
review: 01-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: fixed
    title: "`latest` image tag is overwritten by a workflow_dispatch run on any branch"
  - id: WR-02
    severity: warning
    disposition: deferred
    title: "Supply chain: mutable action refs, and a mutable reusable-workflow ref that receives `secrets: inherit`"
  - id: WR-03
    severity: warning
    disposition: fixed
    title: "\"Google is the only door\" is not enforced: the CSRF-exempt token login and the connections UI are still routed"
  - id: WR-04
    severity: warning
    disposition: fixed
    title: "SocialApp (and other allauth models) are exposed in the admin, although the docs say adding one breaks sign-in"
  - id: WR-05
    severity: warning
    disposition: fixed
    title: "`promote_staff` trusts `User.email`, which allauth populates even when Google says it is unverified"
  - id: WR-06
    severity: warning
    disposition: deferred
    title: "`Wish.claimed_by` stores claim state on the giftee-readable Wish row"
  - id: WR-07
    severity: warning
    disposition: deferred
    title: "`<html lang>` is always `en`: the i18n context processor is missing"
  - id: IN-01
    severity: info
    disposition: deferred
    title: "No Content-Security-Policy, and inline styles would conflict with one later"
  - id: IN-02
    severity: info
    disposition: deferred
    title: "Landing response varies by User-Agent but sends no `Vary` header"
  - id: IN-03
    severity: info
    disposition: deferred
    title: "`.dockerignore` patterns are root-anchored, and base images are not digest-pinned"
  - id: IN-04
    severity: info
    disposition: deferred
    title: "Shell script robustness"
  - id: IN-05
    severity: info
    disposition: deferred
    title: "Sessions are never purged; long-lived sessions apply to superusers too"
  - id: IN-06
    severity: info
    disposition: deferred
    title: "`models.py` leftovers"
  - id: IN-07
    severity: info
    disposition: deferred
    title: "`LANGUAGES` wraps an autonym in `gettext_lazy`"
  - id: IN-08
    severity: info
    disposition: deferred
    title: "Authenticated visitor loses `next` on the landing page; proxy headers are trusted from the whole shared network"
open: 0
total: 15
updated: 2026-11-08T17:49:00.000Z
---
# Phase 01: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | fixed | 01-06 |
| WR-02 | warning | deferred | partial: action SHAs pinned in 01-06; secrets: inherit + @v1 kept — bombur-deploy declares no workflow_call secrets (T-01-35); follow-up: declare DEPLOY_SSH_KEY in ciakval/bombur-deploy then map explicitly |
| WR-03 | warning | fixed | 01-07 |
| WR-04 | warning | fixed | 01-07 |
| WR-05 | warning | fixed | 01-07 |
| WR-06 | warning | deferred | Phase 2, replace Wish.claimed_by with a Claim model before any wish UI |
| WR-07 | warning | deferred | Phase 4, with the I18N-01 language switcher |
| IN-01 | info | deferred | Phase 4 hardening, CSP after inline styles are gone |
| IN-02 | info | deferred | backlog, no shared cache in front of the app |
| IN-03 | info | deferred | backlog, .dockerignore globs and image digests |
| IN-04 | info | deferred | backlog, smoke script portability |
| IN-05 | info | deferred | Phase 4 ops, clearsessions and staff session age |
| IN-06 | info | deferred | Phase 2, together with WR-06 |
| IN-07 | info | deferred | Phase 4, language switcher |
| IN-08 | info | deferred | Phase 2, invite flow keeps a safe next for signed-in visitors; proxy network trust note |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved.
