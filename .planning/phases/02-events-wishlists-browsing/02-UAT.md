---
status: testing
phase: 02-events-wishlists-browsing
source: [02-VERIFICATION.md]
started: 2026-11-08T20:30:00Z
updated: 2026-11-08T20:30:00Z
---

## Current Test

number: 1
name: Live invite round trip on a real phone
expected: |
  A signed-out relative opens an invite link on a phone, signs in with Google, lands on the confirm page, and joins only after pressing Join
awaiting: user response (deferred by user on 2026-11-08 to continue to phase 3; deployed in run 42517981439)

## Tests

### 1. Live invite round trip on a real phone
expected: A signed-out relative opens an invite link on a phone, signs in with Google, lands on the confirm page, and joins only after pressing Join
result: [pending]

### 2. Chat-app link preview of an invite link
expected: Pasting an invite link into a family chat shows no event data in the preview and joins nobody
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
