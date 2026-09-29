"""Read-only Zephyr Scale tools (port of ``src/tools/read.ts``)."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from ..client import FetchLike
from ..service import ZephyrService, create_zephyr_service
from .shared import guarded, ok_result, resolve_context


def _item_text(item: Any, key: str) -> Any:
    return item.get(key) if isinstance(item, Mapping) else None


def _first_of(item: Any, *keys: str) -> Any:
    for key in keys:
        value = _item_text(item, key)
        if value is not None:
            return value
    return None


def summarize_page(result: Mapping[str, Any], format_item: Callable[[Any], str]) -> str:
    """Format one page of Zephyr paged results (values/total/isLast) into a readable summary."""
    values = list(result.get("values") or [])
    lines = "\n".join(format_item(item) for item in values)
    total = result.get("total")
    is_last = result.get("isLast")
    is_last_text = "unknown" if is_last is None else ("true" if is_last else "false")
    return (
        f"{len(values)} of {total if total is not None else '?'} result(s) "
        f"(isLast: {is_last_text}).\n{lines}"
    )


def _case_line(item: Any) -> str:
    return f"{_item_text(item, 'key')}: {_item_text(item, 'name')}"


def _execution_line(item: Any) -> str:
    status = _item_text(item, "testExecutionStatus")
    status_name = _item_text(status, "name") if status is not None else None
    return (
        f"{_first_of(item, 'key', 'id')}: {_item_text(item, 'testCaseKey')} — "
        f"{status_name or 'unknown status'}"
    )


def _pagination_options(args: Mapping[str, Any]) -> dict:
    return {
        "max_results": args.get("maxResults"),
        "start_at": args.get("startAt"),
        "max_pages": args.get("maxPages"),
        "max_items": args.get("maxItems"),
    }


def _list(
    service: ZephyrService,
    args: Mapping[str, Any],
    single: str,
    every: str,
    **extra: Any
) -> dict:
    method = getattr(service, every) if args.get("allPages") else getattr(service, single)
    return method(**_pagination_options(args), **extra)


@guarded
def zephyr_list_test_cases(
    args: Mapping[str, Any],
    *,
    env: Optional[Mapping[str, str]] = None,
    token: Optional[str] = None,
    fetch: Optional[FetchLike] = None,
    config_path: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """List Zephyr Scale test cases for a project."""
    _, _, client = resolve_context(args, env=env, token=token, fetch=fetch, config_path=config_path)
    service = create_zephyr_service(client)
    result = _list(
        service, args, "list_test_cases", "list_all_test_cases", project_key=args.get("projectKey")
    )
    return ok_result(summarize_page(result, _case_line), result)


@guarded
def zephyr_get_test_case(
    args: Mapping[str, Any],
    *,
    env: Optional[Mapping[str, str]] = None,
    token: Optional[str] = None,
    fetch: Optional[FetchLike] = None,
    config_path: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Fetch a single Zephyr Scale test case by key, including its test script/steps."""
    _, _, client = resolve_context(args, env=env, token=token, fetch=fetch, config_path=config_path)
    test_case = create_zephyr_service(client).get_test_case(str(args.get("testCaseKey") or "")) or {}
    return ok_result(
        f"{_item_text(test_case, 'key')}: {_item_text(test_case, 'name')}", test_case
    )


@guarded
def zephyr_list_test_cycles(
    args: Mapping[str, Any],
    *,
    env: Optional[Mapping[str, str]] = None,
    token: Optional[str] = None,
    fetch: Optional[FetchLike] = None,
    config_path: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """List Zephyr Scale test cycles for a project."""
    _, _, client = resolve_context(args, env=env, token=token, fetch=fetch, config_path=config_path)
    service = create_zephyr_service(client)
    result = _list(
        service, args, "list_test_cycles", "list_all_test_cycles", project_key=args.get("projectKey")
    )
    return ok_result(summarize_page(result, _case_line), result)


@guarded
def zephyr_get_test_cycle(
    args: Mapping[str, Any],
    *,
    env: Optional[Mapping[str, str]] = None,
    token: Optional[str] = None,
    fetch: Optional[FetchLike] = None,
    config_path: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Fetch a single Zephyr Scale test cycle by id or key."""
    _, _, client = resolve_context(args, env=env, token=token, fetch=fetch, config_path=config_path)
    cycle = (
        create_zephyr_service(client).get_test_cycle(str(args.get("testCycleIdOrKey") or "")) or {}
    )
    return ok_result(f"{_item_text(cycle, 'key')}: {_item_text(cycle, 'name')}", cycle)


@guarded
def zephyr_list_test_executions(
    args: Mapping[str, Any],
    *,
    env: Optional[Mapping[str, str]] = None,
    token: Optional[str] = None,
    fetch: Optional[FetchLike] = None,
    config_path: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """List Zephyr Scale test executions, optionally scoped to a test cycle."""
    _, _, client = resolve_context(args, env=env, token=token, fetch=fetch, config_path=config_path)
    service = create_zephyr_service(client)
    result = _list(
        service,
        args,
        "list_test_executions",
        "list_all_test_executions",
        project_key=args.get("projectKey"),
        test_cycle=args.get("testCycle"),
    )
    return ok_result(summarize_page(result, _execution_line), result)


@guarded
def zephyr_get_test_execution(
    args: Mapping[str, Any],
    *,
    env: Optional[Mapping[str, str]] = None,
    token: Optional[str] = None,
    fetch: Optional[FetchLike] = None,
    config_path: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Fetch a single Zephyr Scale test execution by id or key."""
    _, _, client = resolve_context(args, env=env, token=token, fetch=fetch, config_path=config_path)
    execution = (
        create_zephyr_service(client).get_test_execution(
            str(args.get("testExecutionIdOrKey") or "")
        )
        or {}
    )
    return ok_result(_execution_line(execution), execution)


READ_TOOLS = {
    "zephyr_list_test_cases": zephyr_list_test_cases,
    "zephyr_get_test_case": zephyr_get_test_case,
    "zephyr_list_test_cycles": zephyr_list_test_cycles,
    "zephyr_get_test_cycle": zephyr_get_test_cycle,
    "zephyr_list_test_executions": zephyr_list_test_executions,
    "zephyr_get_test_execution": zephyr_get_test_execution,
}
