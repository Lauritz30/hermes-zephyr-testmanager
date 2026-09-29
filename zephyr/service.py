"""Zephyr Scale service layer (port of ``src/service.ts``).

Thin, typed-ish helpers over the client: the list/get/create/update calls the tools need, plus the
pagination follower the ``allPages`` flag uses and the dry-run previews.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

DEFAULT_MAX_PAGES = 100
DEFAULT_MAX_ITEMS = 10000

__all__ = [
    "DEFAULT_MAX_ITEMS",
    "DEFAULT_MAX_PAGES",
    "ZephyrPage",
    "ZephyrService",
    "create_zephyr_service",
    "encode_path_part",
    "fetch_all",
    "page",
]


def encode_path_part(value: Any) -> str:
    """URL-encode one path segment (the ``encodeURIComponent`` equivalent)."""
    return urllib.parse.quote(str(value if value is not None else ""), safe="")


def page(result: Any) -> Dict[str, Any]:
    """Normalize one Zephyr paged response into ``{"values", "total", "isLast"}``."""
    payload: Mapping[str, Any] = result if isinstance(result, Mapping) else {}
    values = payload.get("values")
    return {
        "values": list(values) if isinstance(values, list) else [],
        "total": payload.get("total"),
        "isLast": payload.get("isLast"),
    }


def fetch_all(
    fetch_page: Callable[..., Dict[str, Any]],
    *,
    start_at: Optional[int] = None,
    max_pages: Optional[int] = None,
    max_items: Optional[int] = None,
) -> Dict[str, Any]:
    """Follow a paged call until the API marks the last page, the page cap, or the item cap."""
    values: List[Any] = []
    total: Optional[int] = None
    is_last = False
    pages = 0
    offset = start_at or 0
    page_limit = max_pages if max_pages is not None else DEFAULT_MAX_PAGES
    item_limit = max_items if max_items is not None else DEFAULT_MAX_ITEMS

    while not is_last and pages < page_limit and len(values) < item_limit:
        result = fetch_page(start_at=offset)
        chunk = list(result.get("values") or [])
        remaining = item_limit - len(values)
        values.extend(chunk[:remaining])
        if result.get("total") is not None:
            total = result["total"]
        pages += 1
        is_last = result.get("isLast") is True or not chunk or len(values) >= item_limit
        if not is_last:
            offset += len(chunk)
            if result.get("total") is not None and offset >= result["total"]:
                is_last = True

    return {"values": values, "total": total, "isLast": is_last}


class ZephyrService:
    """The read/write operations the Zephyr tools expose, over one client."""

    def __init__(self, client: Any) -> None:
        self.client = client

    # -- reads -------------------------------------------------------------------------------------

    def list_test_cases(
        self,
        project_key: Optional[str] = None,
        max_results: Optional[int] = None,
        start_at: Optional[int] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        return page(
            self.client.get(
                "/testcases",
                {"projectKey": project_key, "maxResults": max_results, "startAt": start_at},
            )
        )

    def list_all_test_cases(
        self,
        project_key: Optional[str] = None,
        max_results: Optional[int] = None,
        start_at: Optional[int] = None,
        max_pages: Optional[int] = None,
        max_items: Optional[int] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        return fetch_all(
            lambda **kwargs: self.list_test_cases(
                project_key=project_key, max_results=max_results, **kwargs
            ),
            start_at=start_at,
            max_pages=max_pages,
            max_items=max_items,
        )

    def get_test_case(self, test_case_key: str) -> Any:
        return self.client.get(f"/testcases/{encode_path_part(test_case_key)}")

    def list_test_cycles(
        self,
        project_key: Optional[str] = None,
        max_results: Optional[int] = None,
        start_at: Optional[int] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        return page(
            self.client.get(
                "/testcycles",
                {"projectKey": project_key, "maxResults": max_results, "startAt": start_at},
            )
        )

    def list_all_test_cycles(
        self,
        project_key: Optional[str] = None,
        max_results: Optional[int] = None,
        start_at: Optional[int] = None,
        max_pages: Optional[int] = None,
        max_items: Optional[int] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        return fetch_all(
            lambda **kwargs: self.list_test_cycles(
                project_key=project_key, max_results=max_results, **kwargs
            ),
            start_at=start_at,
            max_pages=max_pages,
            max_items=max_items,
        )

    def get_test_cycle(self, test_cycle_id_or_key: str) -> Any:
        return self.client.get(f"/testcycles/{encode_path_part(test_cycle_id_or_key)}")

    def list_test_executions(
        self,
        project_key: Optional[str] = None,
        test_cycle: Optional[str] = None,
        max_results: Optional[int] = None,
        start_at: Optional[int] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        return page(
            self.client.get(
                "/testexecutions",
                {
                    "projectKey": project_key,
                    "testCycle": test_cycle,
                    "maxResults": max_results,
                    "startAt": start_at,
                },
            )
        )

    def list_all_test_executions(
        self,
        project_key: Optional[str] = None,
        test_cycle: Optional[str] = None,
        max_results: Optional[int] = None,
        start_at: Optional[int] = None,
        max_pages: Optional[int] = None,
        max_items: Optional[int] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        return fetch_all(
            lambda **kwargs: self.list_test_executions(
                project_key=project_key, test_cycle=test_cycle, max_results=max_results, **kwargs
            ),
            start_at=start_at,
            max_pages=max_pages,
            max_items=max_items,
        )

    def get_test_execution(self, test_execution_id_or_key: str) -> Any:
        return self.client.get(f"/testexecutions/{encode_path_part(test_execution_id_or_key)}")

    # -- writes ------------------------------------------------------------------------------------

    def create_test_case(
        self,
        project_key: Optional[str] = None,
        name: Optional[str] = None,
        objective: Optional[str] = None,
        precondition: Optional[str] = None,
        folder_id: Optional[int] = None,
        fields: Optional[Mapping[str, Any]] = None,
        dry_run: bool = False,
        **_: Any,
    ) -> Any:
        body: Dict[str, Any] = {"projectKey": project_key, "name": name}
        if objective:
            body["objective"] = objective
        if precondition:
            body["precondition"] = precondition
        if folder_id is not None:
            body["folderId"] = folder_id
        if isinstance(fields, Mapping):
            body.update(dict(fields))
        if dry_run:
            return {"dryRun": True, "method": "POST", "path": "/testcases", "body": body}
        return self.client.post("/testcases", body)

    def add_test_cases_to_cycle(
        self,
        project_key: Optional[str] = None,
        test_cycle_key: Optional[str] = None,
        test_case_keys: Optional[Sequence[str]] = None,
        status_name: Optional[str] = None,
        environment_name: Optional[str] = None,
        dry_run: bool = False,
        **_: Any,
    ) -> Any:
        previews: List[Dict[str, Any]] = []
        for test_case_key in list(test_case_keys or ()):
            body: Dict[str, Any] = {
                "projectKey": project_key,
                "testCaseKey": test_case_key,
                "testCycleKey": test_cycle_key,
            }
            if status_name:
                body["statusName"] = status_name
            if environment_name:
                body["environmentName"] = environment_name
            previews.append(
                {"dryRun": True, "method": "POST", "path": "/testexecutions", "body": body}
            )
        if dry_run:
            return previews

        created: List[Dict[str, str]] = []
        for preview in previews:
            execution = self.client.post(preview["path"], preview["body"]) or {}
            execution_key = (
                execution.get("key") if execution.get("key") is not None else execution.get("id")
            )
            created.append(
                {
                    "testCaseKey": str(preview["body"]["testCaseKey"]),
                    "executionKey": str(execution_key),
                }
            )
        return {"testCycleKey": test_cycle_key, "created": created}

    def update_test_execution(
        self,
        test_execution_id_or_key: Optional[str] = None,
        status_name: Optional[str] = None,
        comment: Optional[str] = None,
        dry_run: bool = False,
        **_: Any,
    ) -> Any:
        path = f"/testexecutions/{encode_path_part(test_execution_id_or_key)}"
        body: Dict[str, Any] = {"statusName": status_name}
        if comment:
            body["comment"] = comment
        if dry_run:
            return {"dryRun": True, "method": "PUT", "path": path, "body": body}
        self.client.put(path, body)
        return {"testExecutionIdOrKey": test_execution_id_or_key, "statusName": status_name}


def create_zephyr_service(client: Any) -> ZephyrService:
    """Create the service layer over one Zephyr Scale client."""
    return ZephyrService(client)
