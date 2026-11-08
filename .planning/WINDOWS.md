---
schema_version: 1
open_count: 1
waived_count: 0
fixed_count: 0
total_count: 1
last_updated: 2026-11-08T17:43:42.800Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 01 | deviation | .github/workflows/deploy.yml |  | WR-02 partial: secrets: inherit kept because bombur-deploy v1 declares no workflow_call secrets; follow-up: declare DEPLOY_SSH_KEY there, then map explicitly | open |  | 2026-11-08T17:43:42.800Z |  |

````json
[
  {
    "id": 1,
    "kind": "deviation",
    "phase": "01",
    "file": ".github/workflows/deploy.yml",
    "line": null,
    "description": "WR-02 partial: secrets: inherit kept because bombur-deploy v1 declares no workflow_call secrets; follow-up: declare DEPLOY_SSH_KEY there, then map explicitly",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-11-08T17:43:42.800Z",
    "resolved_at": null,
    "milestone": null
  }
]
````
