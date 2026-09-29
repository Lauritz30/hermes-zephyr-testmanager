---
name: zephyr-cycle-status
description: Summarize a test cycle's execution progress.
version: 1.0.0
author: Lauritz30, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [zephyr, test-management, test-cycle, uat]
---

# Zephyr Scale Cycle Status Skill

Summarize how a test cycle is going: how many executions exist, how they are distributed across
statuses, what is still unexecuted, and what failed — with the test case keys so failures can be
cross-referenced with Jira defects.

## When to Use

- "How is cycle `UAT-R1` doing?", "summarize the cycle execution progress".
- A stand-up or end-of-day check on a UAT cycle before reporting defect status.
- Don't use for: recording a result (`hermes-zephyr-testmanager:zephyr-record-result`).

## Procedure

1. Run `zephyr_list_test_executions` with `projectKey` (default `UAT` when the user does not name
   one) and `testCycle` set to the cycle id or key, with `allPages: true` so the counts cover the
   whole cycle rather than the first page.

   Completion: the tool returns `ok: true` with the executions; if it returns `ok: false`, run
   `zephyr_doctor` before reporting anything — a token or config problem is not "no executions".
2. Summarize, in this order:
   - Total executions, and the count per status (Pass / Fail / Blocked / Not Executed).
   - Every execution still "Not Executed", by test case key, so they can be prioritized.
   - Every "Fail" / "Blocked" execution, with its test case key, so each can be cross-referenced
     with the matching Jira defect.
3. Quote the cycle key and the filter you used, so the numbers can be reproduced.

## Pitfalls

- A single page is not the whole cycle; use `allPages` (or quote the page size and `isLast`) before
  stating a total.
- Status names are project-configured strings; report the names the API returned, never a mapping.
- `ok: false` is a failing call, not an empty cycle — the two must not read the same in prose.

## Verification

The reported total equals the number of executions the tool returned, every status count sums to
that total, and each Fail/Blocked entry names a test case key that appeared in the tool result.
