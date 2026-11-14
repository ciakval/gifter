---
status: testing
phase: 05-secret-discussions
source: [05-VERIFICATION.md]
started: 2026-11-14T11:27:11Z
updated: 2026-11-14T11:27:11Z
---

## Current Test

number: 1
name: Czech copy review of the new Phase 5 strings
expected: |
  A Czech-speaking relative reads each string (thread headings 'Diskuse' / 'Diskuse o této osobě', markers 'Nové od tvé poslední návštěvy' / 'Nové', plurals 1 komentář / 2 komentáře / 5 komentářů, 'Komentář byl smazán.', and the three Discussions paragraphs in the Czech privacy policy) and finds them natural and correctly toned.
awaiting: user response

## Tests

### 1. Czech copy review of the new Phase 5 strings
expected: A Czech-speaking relative finds every new string natural and correctly toned; plural forms read correctly for 1, 2-4 and 5+.
result: [pending]

### 2. Post-deploy production UAT with two givers (B, C) and giftee A on real phones
expected: All seven steps pass on gifter.remesh.cz — (1) B posts 'test ahoj' on A's wish via Discuss; (2) C sees 'New since your last visit' + 'Discussion (1 comment)', opens it, marker clears; (3) A sees no trace anywhere and B's thread URL gives Not Found; (4) B posts in 'Discussion about this person', A still sees nothing; (5) B deletes own comment, C cannot; (6) Czech labels and plurals read naturally; (7) /privacy/ Discussions section reads well in both languages.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
