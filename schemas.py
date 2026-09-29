"""Tool schemas — what the LLM sees."""

from __future__ import annotations

from typing import Any, Dict

SITE = {
    "type": "string",
    "description": "Site name to use; defaults to defaultSite.",
}

MAX_RESULTS = {
    "type": "integer",
    "minimum": 1,
    "maximum": 200,
    "description": "Page size (Zephyr Scale caps a page at 200).",
}

START_AT = {
    "type": "integer",
    "minimum": 0,
    "description": "Zero-based index of the first result to return.",
}

ALL_PAGES = {
    "type": "boolean",
    "description": "Follow pagination to the last page instead of returning a single page.",
}

MAX_PAGES = {"type": "integer", "minimum": 1, "maximum": 100}
MAX_ITEMS = {"type": "integer", "minimum": 1, "maximum": 10000}

DRY_RUN = {
    "type": "boolean",
    "description": "Preview the normalized request without prompting or sending it.",
}

DOCTOR: Dict[str, Any] = {
    "name": "zephyr_doctor",
    "description": (
        "Check Zephyr Scale configuration and connectivity: config file location, site resolution, "
        "token availability, and authentication. Use this first when a Zephyr Scale call fails or "
        "before reporting that Zephyr Scale is unavailable."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "site": {
                "type": "string",
                "description": "Site name to check; defaults to defaultSite.",
            }
        },
    },
}

LIST_TEST_CASES: Dict[str, Any] = {
    "name": "zephyr_list_test_cases",
    "description": (
        "List Zephyr Scale test cases for a project. Set allPages to follow pagination to the end."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "projectKey": {"type": "string", "description": "Project key, e.g. UAT."},
            "maxResults": MAX_RESULTS,
            "startAt": START_AT,
            "allPages": ALL_PAGES,
            "maxPages": MAX_PAGES,
            "maxItems": MAX_ITEMS,
            "site": SITE,
        },
        "required": ["projectKey"],
    },
}

GET_TEST_CASE: Dict[str, Any] = {
    "name": "zephyr_get_test_case",
    "description": (
        "Fetch a single Zephyr Scale test case by key, including its test script/steps."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "testCaseKey": {"type": "string", "description": "Test case key, e.g. UAT-T1."},
            "site": SITE,
        },
        "required": ["testCaseKey"],
    },
}

LIST_TEST_CYCLES: Dict[str, Any] = {
    "name": "zephyr_list_test_cycles",
    "description": (
        "List Zephyr Scale test cycles for a project. Set allPages to follow pagination to the end."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "projectKey": {"type": "string", "description": "Project key, e.g. UAT."},
            "maxResults": MAX_RESULTS,
            "startAt": START_AT,
            "allPages": ALL_PAGES,
            "maxPages": MAX_PAGES,
            "maxItems": MAX_ITEMS,
            "site": SITE,
        },
        "required": ["projectKey"],
    },
}

GET_TEST_CYCLE: Dict[str, Any] = {
    "name": "zephyr_get_test_cycle",
    "description": "Fetch a single Zephyr Scale test cycle by id or key.",
    "parameters": {
        "type": "object",
        "properties": {
            "testCycleIdOrKey": {
                "type": "string",
                "description": "Test cycle id or key, e.g. UAT-R1.",
            },
            "site": SITE,
        },
        "required": ["testCycleIdOrKey"],
    },
}

LIST_TEST_EXECUTIONS: Dict[str, Any] = {
    "name": "zephyr_list_test_executions",
    "description": (
        "List Zephyr Scale test executions, optionally scoped to a test cycle. Set allPages to "
        "follow pagination to the end."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "projectKey": {"type": "string", "description": "Project key, e.g. UAT."},
            "testCycle": {
                "type": "string",
                "description": "Test cycle id or key to filter by.",
            },
            "maxResults": MAX_RESULTS,
            "startAt": START_AT,
            "allPages": ALL_PAGES,
            "maxPages": MAX_PAGES,
            "maxItems": MAX_ITEMS,
            "site": SITE,
        },
        "required": ["projectKey"],
    },
}

GET_TEST_EXECUTION: Dict[str, Any] = {
    "name": "zephyr_get_test_execution",
    "description": "Fetch a single Zephyr Scale test execution by id or key.",
    "parameters": {
        "type": "object",
        "properties": {
            "testExecutionIdOrKey": {
                "type": "string",
                "description": "Test execution id or key, e.g. UAT-E1.",
            },
            "site": SITE,
        },
        "required": ["testExecutionIdOrKey"],
    },
}

CREATE_TEST_CASE: Dict[str, Any] = {
    "name": "zephyr_create_test_case",
    "description": (
        "Create a Zephyr Scale test case. Gated by the site's safety level "
        '(default: "confirm", which requires human approval).'
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "projectKey": {"type": "string", "description": "Project key, e.g. UAT."},
            "name": {"type": "string", "description": "Test case name."},
            "objective": {"type": "string", "description": "Test case objective."},
            "precondition": {"type": "string", "description": "Test case precondition."},
            "folderId": {
                "type": "integer",
                "description": "Folder id to file the test case under.",
            },
            "fields": {
                "type": "object",
                "description": "Additional raw Zephyr Scale fields, merged in as-is.",
            },
            "dryRun": DRY_RUN,
            "site": SITE,
        },
        "required": ["projectKey", "name"],
    },
}

ADD_TEST_CASES_TO_CYCLE: Dict[str, Any] = {
    "name": "zephyr_add_test_cases_to_cycle",
    "description": (
        "Add one or more test cases to a test cycle. Zephyr Scale associates a test case with a "
        "cycle by creating a test execution for it, so this creates one execution per test case. "
        'Gated by the site\'s safety level (default: "confirm").'
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "projectKey": {"type": "string", "description": "Project key, e.g. UAT."},
            "testCycleKey": {
                "type": "string",
                "description": "Test cycle id or key to add the test cases to.",
            },
            "testCaseKeys": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "description": 'Test case keys to add, e.g. ["UAT-T1", "UAT-T2"].',
            },
            "statusName": {
                "type": "string",
                "description": (
                    "Initial status name, e.g. Not Executed. Defaults to the project's default "
                    "status when omitted."
                ),
            },
            "environmentName": {"type": "string", "description": "Environment name, e.g. UAT."},
            "dryRun": DRY_RUN,
            "site": SITE,
        },
        "required": ["projectKey", "testCycleKey", "testCaseKeys"],
    },
}

UPDATE_TEST_EXECUTION_STATUS: Dict[str, Any] = {
    "name": "zephyr_update_test_execution_status",
    "description": (
        "Record a UAT test result by updating a test execution's status (e.g. Pass/Fail) and "
        'optional comment. Gated by the site\'s safety level (default: "confirm").'
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "testExecutionIdOrKey": {
                "type": "string",
                "description": "Test execution id or key, e.g. UAT-E1.",
            },
            "statusName": {
                "type": "string",
                "description": "Status name as configured in the project, e.g. Pass, Fail, Blocked.",
            },
            "comment": {"type": "string", "description": "Optional comment recorded with the status."},
            "dryRun": DRY_RUN,
            "site": SITE,
        },
        "required": ["testExecutionIdOrKey", "statusName"],
    },
}

TOOL_SCHEMAS = (
    DOCTOR,
    LIST_TEST_CASES,
    GET_TEST_CASE,
    LIST_TEST_CYCLES,
    GET_TEST_CYCLE,
    LIST_TEST_EXECUTIONS,
    GET_TEST_EXECUTION,
    CREATE_TEST_CASE,
    ADD_TEST_CASES_TO_CYCLE,
    UPDATE_TEST_EXECUTION_STATUS,
)

__all__ = [
    "ADD_TEST_CASES_TO_CYCLE",
    "CREATE_TEST_CASE",
    "DOCTOR",
    "GET_TEST_CASE",
    "GET_TEST_CYCLE",
    "GET_TEST_EXECUTION",
    "LIST_TEST_CASES",
    "LIST_TEST_CYCLES",
    "LIST_TEST_EXECUTIONS",
    "TOOL_SCHEMAS",
    "UPDATE_TEST_EXECUTION_STATUS",
]
