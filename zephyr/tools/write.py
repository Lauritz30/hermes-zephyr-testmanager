"""Safety-gated write tools (port of ``src/tools/write.ts``)."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ..client import FetchLike
from ..mutations import mutation_request
from ..safety import guard_mutation
from ..service import create_zephyr_service
from .shared import guarded, ok_result, resolve_context


def _guard(args: Mapping[str, Any], tool_name: str, config, site) -> str:
    """Handler-side safety enforcement (the hook is the first line, this is the guarantee)."""
    request = mutation_request(tool_name, args)
    if request is None:  # pragma: no cover - every write tool has a request builder
        return "proceed"
    return guard_mutation(config, site, request)


@guarded
def zephyr_create_test_case(
    args: Mapping[str, Any],
    *,
    env: Optional[Mapping[str, str]] = None,
    token: Optional[str] = None,
    fetch: Optional[FetchLike] = None,
    config_path: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Create a Zephyr Scale test case. Gated by safetyLevel (default: confirm)."""
    config, site, client = resolve_context(
        args, env=env, token=token, fetch=fetch, config_path=config_path
    )
    dry_run = bool(args.get("dryRun"))
    if not dry_run:
        _guard(args, "zephyr_create_test_case", config, site)

    created = create_zephyr_service(client).create_test_case(
        project_key=args.get("projectKey"),
        name=args.get("name"),
        objective=args.get("objective"),
        precondition=args.get("precondition"),
        folder_id=args.get("folderId"),
        fields=args.get("fields") if isinstance(args.get("fields"), Mapping) else None,
        dry_run=dry_run,
    )
    if isinstance(created, Mapping) and created.get("dryRun"):
        return ok_result(
            f'Dry-run: would create test case "{args.get("name")}" in {args.get("projectKey")}.',
            created,
        )
    created = created if isinstance(created, Mapping) else {}
    return ok_result(f"Created test case {created.get('key') or created.get('id')}.", created)


@guarded
def zephyr_add_test_cases_to_cycle(
    args: Mapping[str, Any],
    *,
    env: Optional[Mapping[str, str]] = None,
    token: Optional[str] = None,
    fetch: Optional[FetchLike] = None,
    config_path: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Add one or more test cases to a test cycle (one test execution per test case)."""
    config, site, client = resolve_context(
        args, env=env, token=token, fetch=fetch, config_path=config_path
    )
    dry_run = bool(args.get("dryRun"))
    if not dry_run:
        _guard(args, "zephyr_add_test_cases_to_cycle", config, site)

    test_case_keys = args.get("testCaseKeys")
    keys = list(test_case_keys) if isinstance(test_case_keys, (list, tuple)) else []
    result = create_zephyr_service(client).add_test_cases_to_cycle(
        project_key=args.get("projectKey"),
        test_cycle_key=args.get("testCycleKey"),
        test_case_keys=keys,
        status_name=args.get("statusName"),
        environment_name=args.get("environmentName"),
        dry_run=dry_run,
    )
    if isinstance(result, list):
        return ok_result(
            f"Dry-run: would add {len(keys)} test case(s) to cycle {args.get('testCycleKey')}.",
            result,
        )
    created = list((result or {}).get("created") or [])
    summary = "\n".join(
        f"{item.get('testCaseKey')} -> execution {item.get('executionKey')}" for item in created
    )
    return ok_result(
        f"Added {len(created)} test case(s) to cycle {args.get('testCycleKey')}.\n{summary}",
        {"testCycleKey": args.get("testCycleKey"), "created": created},
    )


@guarded
def zephyr_update_test_execution_status(
    args: Mapping[str, Any],
    *,
    env: Optional[Mapping[str, str]] = None,
    token: Optional[str] = None,
    fetch: Optional[FetchLike] = None,
    config_path: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Record a UAT test result by updating a test execution's status and optional comment."""
    config, site, client = resolve_context(
        args, env=env, token=token, fetch=fetch, config_path=config_path
    )
    dry_run = bool(args.get("dryRun"))
    if not dry_run:
        _guard(args, "zephyr_update_test_execution_status", config, site)

    updated = create_zephyr_service(client).update_test_execution(
        test_execution_id_or_key=str(args.get("testExecutionIdOrKey") or ""),
        status_name=args.get("statusName"),
        comment=args.get("comment"),
        dry_run=dry_run,
    )
    if dry_run:
        return ok_result(
            f'Dry-run: would update {args.get("testExecutionIdOrKey")} to '
            f'"{args.get("statusName")}".',
            updated,
        )
    return ok_result(
        f'Updated {args.get("testExecutionIdOrKey")} to "{args.get("statusName")}".', updated
    )


WRITE_TOOLS = {
    "zephyr_create_test_case": zephyr_create_test_case,
    "zephyr_add_test_cases_to_cycle": zephyr_add_test_cases_to_cycle,
    "zephyr_update_test_execution_status": zephyr_update_test_execution_status,
}
