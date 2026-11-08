---
status: testing
phase: 01-google-sign-in-live
source: [01-VERIFICATION.md]
started: 2026-11-08T18:30:00Z
updated: 2026-11-08T18:30:00Z
---

## Current Test

number: 1
name: Never-test-user sign-in, then admin bounce
expected: |
  Signs in with no Google testing or blocked screen, greeted by name on /events/; /gifter-admin/ does not admit it
awaiting: user response (deferred by user on 2026-11-08: "I want the app to start being usable asap")

## Tests

### 1. Never-test-user sign-in (SC-2, AUTH-01), then confirm that account is bounced from /gifter-admin/ to /events/
expected: Signs in with no Google testing or blocked screen, greeted by name on /events/; /gifter-admin/ does not admit it
result: [pending]

### 2. Session survives the redeploys and a browser restart; sign out and sign in again
expected: Session survives the redeploys and the browser restart with no new Google prompt; Sign out returns to the landing page and /events/ then redirects to sign-in
result: [pending]

### 3. Landing page, /events/ and the footer Privacy policy link on a phone
expected: Readable and tappable at phone width
result: [pending]

### 4. https://gifter.remesh.cz inside the real Messenger and Instagram in-app browsers
expected: The "Open Gifter in your browser" hint shows instead of the Google button; the menu wording in the copy matches the real apps; Copy link works; Continue anyway shows the Google button
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
