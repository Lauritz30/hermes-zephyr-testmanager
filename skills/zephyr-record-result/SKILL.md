---
name: zephyr-record-result
description: Record a UAT test result against a test execution.
version: 1.0.0
author: Lauritz30, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [zephyr, test-management, uat, test-execution]
---

# Zephyr Scale Record Result Skill

Record a UAT test result (Pass / Fail / Blocked / …) against one test execution, with an optional
comment, and report the new status.

## When to Use

- "Mark `UAT-E1` as Pass", "record the result of this execution".
- After executing a UAT test case and deciding its outcome.
- Don't use for: cycle progress summaries (`hermes-zephyr-testmanager:zephyr-cycle-status`).

## Procedure

1. Confirm the target and the outcome: the test execution id or key and the status name, plus any
   comment the user gave (pass "none provided" through as *no comment* rather than the literal
   string).
2. Call `zephyr_update_test_execution_status` with `testExecutionIdOrKey`, `statusName`, and
   `comment` when there is one.

   Completion: the tool returns `ok: true` and echoes the execution and the new status.
3. Report the execution key and the new status back to the user.

## Pitfalls

- The status name must be one the project configures (`Pass`, `Fail`, `Blocked`, …); the API rejects
  unknown names. Call `zephyr_get_test_execution` first if you are unsure.
- Writes are gated by the site's `safetyLevel`: `confirm` (the default) requires human approval and
  `readonly` blocks the call outright, in which case the tool returns `ok: false` with a
  `safetyLevel` message — report it, do not retry blindly.
- Set `dryRun: true` to see the normalized request without sending it.
- Never invent an execution key: use one that came from a tool result in this session.

## Verification

The tool result's `summary` names the same execution key and status that were requested, and the
comment (if any) is echoed in the request the tool reports.
