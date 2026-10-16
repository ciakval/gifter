# Phase 1: Google Sign-in Live - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-16
**Phase:** 01-google-sign-in-live
**Areas discussed:** Landing & first screen

---

## Landing & first screen

### Signed-out landing page

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal | Logo/name, one sentence, big "Sign in with Google" button | ✓ |
| Short explainer | Minimal + 3 short steps reassuring about secrecy | |
| Sign-in only | Just the Google button, no copy | |

**User's choice:** Minimal

### Post-sign-in landing (Phase 1)

| Option | Description | Selected |
|--------|-------------|----------|
| Placeholder home | "Hi <name>, you're signed in" + sign-out, on the page Phase 2 turns into "My events" | ✓ |
| Back to landing | Same page, button swapped for "Signed in as … · Sign out" | |

**User's choice:** Placeholder home

### Sign-in flow

| Option | Description | Selected |
|--------|-------------|----------|
| Direct from button | POST form straight to Google; protected pages redirect to landing with `next` | ✓ |
| allauth login page | Separate /accounts/login/ page with the Google button | |
| You decide | Claude picks during planning | |

**User's choice:** Direct from button

### Phase 1 language

| Option | Description | Selected |
|--------|-------------|----------|
| English now, CZ later | Wrap strings, ship English, LocaleMiddleware set up; Czech in Phase 4 | ✓ |
| Czech for these few pages | Translate Phase 1 strings now + language switcher | |

**User's choice:** English now, CZ later

---

## Claude's Discretion

- In-app browser hint (detection scope, banner vs interstitial, copy-link / intent link)
- Accounts & admin (display name, session length, admin path, staff)
- Dev & deploy setup (repo layout, local dev OAuth, staging, CI gates)

## Deferred Ideas

None.
