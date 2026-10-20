---
phase: 01
review: 01-REVIEW.md
titles: json
findings:
  - id: WR-01
    severity: warning
    disposition: open
    title: "`latest` image tag is overwritten by a workflow_dispatch run on any branch"
  - id: WR-02
    severity: warning
    disposition: open
    title: "Supply chain: mutable action refs, and a mutable reusable-workflow ref that receives `secrets: inherit`"
  - id: WR-03
    severity: warning
    disposition: open
    title: "\"Google is the only door\" is not enforced: the CSRF-exempt token login and the connections UI are still routed"
  - id: WR-04
    severity: warning
    disposition: open
    title: "SocialApp (and other allauth models) are exposed in the admin, although the docs say adding one breaks sign-in"
  - id: WR-05
    severity: warning
    disposition: open
    title: "`promote_staff` trusts `User.email`, which allauth populates even when Google says it is unverified"
  - id: WR-06
    severity: warning
    disposition: open
    title: "`Wish.claimed_by` stores claim state on the giftee-readable Wish row"
  - id: WR-07
    severity: warning
    disposition: open
    title: "`<html lang>` is always `en`: the i18n context processor is missing"
  - id: IN-01
    severity: info
    disposition: open
    title: "No Content-Security-Policy, and inline styles would conflict with one later"
  - id: IN-02
    severity: info
    disposition: open
    title: "Landing response varies by User-Agent but sends no `Vary` header"
  - id: IN-03
    severity: info
    disposition: open
    title: "`.dockerignore` patterns are root-anchored, and base images are not digest-pinned"
  - id: IN-04
    severity: info
    disposition: open
    title: "Shell script robustness"
  - id: IN-05
    severity: info
    disposition: open
    title: "Sessions are never purged; long-lived sessions apply to superusers too"
  - id: IN-06
    severity: info
    disposition: open
    title: "`models.py` leftovers"
  - id: IN-07
    severity: info
    disposition: open
    title: "`LANGUAGES` wraps an autonym in `gettext_lazy`"
  - id: IN-08
    severity: info
    disposition: open
    title: "Authenticated visitor loses `next` on the landing page; proxy headers are trusted from the whole shared network"
open: 15
total: 15
updated: 2026-10-20T16:09:50.099Z
---
# Phase 01: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| WR-04 | warning | open | - |
| WR-05 | warning | open | - |
| WR-06 | warning | open | - |
| WR-07 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |
| IN-05 | info | open | - |
| IN-06 | info | open | - |
| IN-07 | info | open | - |
| IN-08 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
Set `deferred` by hand and put the reason in the Source cell; both are preserved.
