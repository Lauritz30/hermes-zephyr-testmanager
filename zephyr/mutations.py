"""Mutation request construction, shared by the write handlers and the approval hook.

The titles and messages are copied from the pi extension's ``guardMutation`` call sites, so the
approval prompt the user sees is the same text.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from .safety import MutationRequest

MUTATING_TOOLS = (
    "zephyr_create_test_case",
    "zephyr_add_test_cases_to_cycle",
    "zephyr_update_test_execution_status",
)


def _text(args: Mapping[str, Any], key: str) -> str:
    value = args.get(key)
    return value if isinstance(value, str) else ""


def mutation_request(tool_name: str, args: Mapping[str, Any]) -> Optional[MutationRequest]:
    """Describe a mutating tool call in the terms the safety rules match against."""
    if tool_name == "zephyr_create_test_case":
        return MutationRequest(
            title="Create Zephyr Scale test case",
            message=f'Create test case "{_text(args, "name")}" in {_text(args, "projectKey")}?',
            action=tool_name,
        )
    if tool_name == "zephyr_add_test_cases_to_cycle":
        keys = args.get("testCaseKeys")
        count = len(keys) if isinstance(keys, (list, tuple)) else 0
        return MutationRequest(
            title="Add test cases to Zephyr Scale cycle",
            message=(
                f"Add {count} test case(s) to cycle {_text(args, 'testCycleKey')} "
                f"in {_text(args, 'projectKey')}?"
            ),
            action=tool_name,
        )
    if tool_name == "zephyr_update_test_execution_status":
        return MutationRequest(
            title="Update Zephyr Scale test execution status",
            message=(
                f"Set {_text(args, 'testExecutionIdOrKey')} status to "
                f'"{_text(args, "statusName")}"?'
            ),
            action=tool_name,
        )
    return None


__all__ = ["MUTATING_TOOLS", "mutation_request"]
