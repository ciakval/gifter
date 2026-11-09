---
status: testing
phase: 03-secret-claims-gift-lifecycle
source: [03-VERIFICATION.md]
started: 2026-11-09T12:00:00Z
updated: 2026-11-09T12:00:00Z
---

## Current Test

number: 1
name: Two people claim the same wish at once on phones
expected: |
  Exactly one claim wins; the other person sees "Someone just took it"
awaiting: user response (deferred by user on 2026-11-09 to continue to phase 4; deployed in run 42687462016)

## Tests

### 1. Two people claim the same wish at once on phones
expected: Exactly one claim wins; the other person sees "Someone just took it"
result: [pending]

### 2. Giftee walk-through on production while friends claim and chip in
expected: A non-staff giftee sees no sign of whether or by whom their wishes are claimed; the staff author's admin has no Delete button or bulk delete action and answers 403 on user delete URLs
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
