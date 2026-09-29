"""Tool handler tests — every Zephyr Scale tool exercised through the injected transport seam."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Optional

from tests.plugin import TOKEN_ENV, load_plugin, respond, respond_sequence, site_payload, write_config

plugin = load_plugin()
tools = plugin.zephyr.tools

BASE = "https://api.zephyrscale.smartbear.com/v2"


class ToolTestCase(unittest.TestCase):
    """Base class: temp config handling plus handler invocation helpers."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="hermes-zephyr-tools-")
        self.dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def config_path(self, **site_overrides: Any) -> str:
        return write_config(self.dir, site_payload(**site_overrides))

    def write(self, payload: Dict[str, Any]) -> str:
        return write_config(self.dir, payload)

    def call(self, handler, args: Dict[str, Any], fetch, path: Optional[str] = None):
        result = handler(
            args, config_path=path if path is not None else self.config_path(), env=TOKEN_ENV, fetch=fetch
        )
        return json.loads(result)


class ListToolTests(ToolTestCase):
    def test_list_test_cases_summarizes_a_page(self) -> None:
        fetch = respond(
            200,
            {"values": [{"key": "UAT-T1", "name": "A"}, {"key": "UAT-T2", "name": "B"}], "total": 2, "isLast": True},
        )
        payload = self.call(tools.zephyr_list_test_cases, {"projectKey": "UAT"}, fetch)

        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["summary"], "2 of 2 result(s) (isLast: true).\nUAT-T1: A\nUAT-T2: B"
        )
        self.assertEqual(payload["data"]["values"][0]["key"], "UAT-T1")
        self.assertEqual(fetch.urls[0], f"{BASE}/testcases?projectKey=UAT")

    def test_an_unpaged_response_reports_unknown_total_and_is_last(self) -> None:
        fetch = respond(200, {"values": [{"key": "UAT-T1", "name": "A"}]})
        payload = self.call(tools.zephyr_list_test_cases, {"projectKey": "UAT"}, fetch)
        self.assertEqual(payload["summary"], "1 of ? result(s) (isLast: unknown).\nUAT-T1: A")

    def test_an_empty_page_reports_zero_results(self) -> None:
        payload = self.call(tools.zephyr_list_test_cases, {"projectKey": "UAT"}, respond(200, {"values": [], "total": 0}))
        self.assertEqual(payload["summary"], "0 of 0 result(s) (isLast: unknown).\n")

    def test_the_page_window_is_forwarded_as_query_params(self) -> None:
        fetch = respond(200, {"values": []})
        self.call(
            tools.zephyr_list_test_cases,
            {"projectKey": "UAT", "maxResults": 50, "startAt": 10},
            fetch,
        )
        query = fetch.query()
        self.assertEqual(query["projectKey"], ["UAT"])
        self.assertEqual(query["maxResults"], ["50"])
        self.assertEqual(query["startAt"], ["10"])

    def test_all_pages_follows_pagination_to_the_last_page(self) -> None:
        fetch = respond_sequence(
            (200, {"values": [{"key": "UAT-T1", "name": "A"}], "total": 2, "isLast": False}),
            (200, {"values": [{"key": "UAT-T2", "name": "B"}], "total": 2, "isLast": True}),
        )
        payload = self.call(
            tools.zephyr_list_test_cases, {"projectKey": "UAT", "allPages": True, "maxItems": 10}, fetch
        )

        self.assertEqual(len(fetch.calls), 2)
        self.assertIn("UAT-T2: B", payload["summary"])
        self.assertEqual(fetch.query(1)["startAt"], ["1"])

    def test_list_test_cycles_uses_the_cycles_endpoint(self) -> None:
        fetch = respond(200, {"values": [{"key": "UAT-R1", "name": "Cycle"}], "total": 1, "isLast": True})
        payload = self.call(tools.zephyr_list_test_cycles, {"projectKey": "UAT"}, fetch)

        self.assertEqual(fetch.urls[0], f"{BASE}/testcycles?projectKey=UAT")
        self.assertEqual(payload["summary"], "1 of 1 result(s) (isLast: true).\nUAT-R1: Cycle")

    def test_list_test_executions_summarizes_key_and_status(self) -> None:
        fetch = respond(
            200,
            {
                "values": [
                    {"key": "UAT-E1", "testCaseKey": "UAT-T1", "testExecutionStatus": {"name": "Pass"}},
                    {"id": 7, "testCaseKey": "UAT-T2", "testExecutionStatus": {"name": "Fail"}},
                ],
                "total": 2,
                "isLast": True,
            },
        )
        payload = self.call(
            tools.zephyr_list_test_executions, {"projectKey": "UAT", "testCycle": "UAT-R1"}, fetch
        )

        self.assertEqual(
            payload["summary"],
            "2 of 2 result(s) (isLast: true).\nUAT-E1: UAT-T1 — Pass\n7: UAT-T2 — Fail",
        )
        self.assertEqual(fetch.query()["testCycle"], ["UAT-R1"])

    def test_an_execution_without_a_status_reports_unknown(self) -> None:
        fetch = respond(200, {"values": [{"key": "UAT-E1", "testCaseKey": "UAT-T1"}], "total": 1, "isLast": True})
        payload = self.call(tools.zephyr_list_test_executions, {"projectKey": "UAT"}, fetch)
        self.assertEqual(payload["summary"], "1 of 1 result(s) (isLast: true).\nUAT-E1: UAT-T1 — unknown status")


class GetToolTests(ToolTestCase):
    def test_get_test_case_returns_key_and_name(self) -> None:
        fetch = respond(200, {"key": "UAT-T1", "name": "Login works"})
        payload = self.call(tools.zephyr_get_test_case, {"testCaseKey": "UAT-T1"}, fetch)

        self.assertEqual(payload["summary"], "UAT-T1: Login works")
        self.assertEqual(fetch.urls[0], f"{BASE}/testcases/UAT-T1")

    def test_get_test_case_url_encodes_the_key(self) -> None:
        fetch = respond(200, {"key": "UAT T1", "name": "x"})
        self.call(tools.zephyr_get_test_case, {"testCaseKey": "UAT T1"}, fetch)
        self.assertEqual(fetch.urls[0], f"{BASE}/testcases/UAT%20T1")

    def test_get_test_cycle_uses_the_cycles_endpoint(self) -> None:
        fetch = respond(200, {"key": "UAT-R1", "name": "Cycle"})
        payload = self.call(tools.zephyr_get_test_cycle, {"testCycleIdOrKey": "UAT-R1"}, fetch)

        self.assertEqual(payload["summary"], "UAT-R1: Cycle")
        self.assertEqual(fetch.urls[0], f"{BASE}/testcycles/UAT-R1")

    def test_get_test_execution_reports_the_status(self) -> None:
        fetch = respond(200, {"key": "UAT-E1", "testCaseKey": "UAT-T1", "testExecutionStatus": {"name": "Blocked"}})
        payload = self.call(tools.zephyr_get_test_execution, {"testExecutionIdOrKey": "UAT-E1"}, fetch)

        self.assertEqual(payload["summary"], "UAT-E1: UAT-T1 — Blocked")
        self.assertEqual(fetch.urls[0], f"{BASE}/testexecutions/UAT-E1")


class WriteToolTests(ToolTestCase):
    def open_config(self) -> str:
        return self.config_path(safetyLevel="open")

    def readonly_config(self) -> str:
        return self.config_path(safetyLevel="readonly")

    def test_create_test_case_posts_the_expected_body(self) -> None:
        fetch = respond(201, {"key": "UAT-T9"})
        payload = self.call(
            tools.zephyr_create_test_case,
            {"projectKey": "UAT", "name": "Login works", "objective": "Verify login", "folderId": 12},
            fetch,
            path=self.open_config(),
        )

        self.assertEqual(payload["summary"], "Created test case UAT-T9.")
        self.assertEqual(fetch.urls[0], f"{BASE}/testcases")
        self.assertEqual(fetch.last_init["method"], "POST")
        self.assertEqual(
            fetch.json_body(),
            {"projectKey": "UAT", "name": "Login works", "objective": "Verify login", "folderId": 12},
        )

    def test_create_test_case_merges_raw_fields(self) -> None:
        fetch = respond(201, {"key": "UAT-T9"})
        self.call(
            tools.zephyr_create_test_case,
            {"projectKey": "UAT", "name": "Login works", "fields": {"priority": "High"}},
            fetch,
            path=self.open_config(),
        )
        self.assertEqual(fetch.json_body()["priority"], "High")

    def test_create_test_case_dry_run_previews_without_sending(self) -> None:
        fetch = respond(201, {"key": "UAT-T9"})
        payload = self.call(
            tools.zephyr_create_test_case,
            {"projectKey": "UAT", "name": "Login works", "dryRun": True},
            fetch,
            path=self.open_config(),
        )

        self.assertRegex(payload["summary"], "^Dry-run: would create test case")
        self.assertTrue(payload["data"]["dryRun"])
        self.assertEqual(fetch.calls, [])

    def test_dry_run_needs_no_confirmation_even_on_a_readonly_site(self) -> None:
        fetch = respond(201, {"key": "UAT-T9"})
        payload = self.call(
            tools.zephyr_create_test_case,
            {"projectKey": "UAT", "name": "Login works", "dryRun": True},
            fetch,
            path=self.readonly_config(),
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(fetch.calls, [])

    def test_readonly_sites_block_create(self) -> None:
        fetch = respond(201, {"key": "UAT-T9"})
        payload = self.call(
            tools.zephyr_create_test_case,
            {"projectKey": "UAT", "name": "Login works"},
            fetch,
            path=self.readonly_config(),
        )

        self.assertFalse(payload["ok"])
        self.assertRegex(payload["error"], 'safetyLevel is "readonly"')
        self.assertEqual(fetch.calls, [])

    def test_add_test_cases_to_cycle_posts_one_execution_per_case(self) -> None:
        fetch = respond_sequence((200, {"key": "UAT-E1"}), (200, {"id": 42}))
        payload = self.call(
            tools.zephyr_add_test_cases_to_cycle,
            {"projectKey": "UAT", "testCycleKey": "UAT-R1", "testCaseKeys": ["UAT-T1", "UAT-T2"]},
            fetch,
            path=self.open_config(),
        )

        self.assertEqual(fetch.urls, [f"{BASE}/testexecutions", f"{BASE}/testexecutions"])
        self.assertEqual(
            payload["summary"],
            "Added 2 test case(s) to cycle UAT-R1.\nUAT-T1 -> execution UAT-E1\nUAT-T2 -> execution 42",
        )

    def test_add_test_cases_dry_run_previews_every_request(self) -> None:
        fetch = respond(200, {"key": "UAT-E1"})
        payload = self.call(
            tools.zephyr_add_test_cases_to_cycle,
            {
                "projectKey": "UAT",
                "testCycleKey": "UAT-R1",
                "testCaseKeys": ["UAT-T1", "UAT-T2"],
                "statusName": "Not Executed",
                "dryRun": True,
            },
            fetch,
            path=self.open_config(),
        )

        self.assertRegex(payload["summary"], "^Dry-run: would add 2 test case")
        self.assertEqual(len(payload["data"]), 2)
        self.assertEqual(fetch.calls, [])

    def test_add_test_cases_is_blocked_on_a_readonly_site(self) -> None:
        fetch = respond(200, {"key": "UAT-E1"})
        payload = self.call(
            tools.zephyr_add_test_cases_to_cycle,
            {"projectKey": "UAT", "testCycleKey": "UAT-R1", "testCaseKeys": ["UAT-T1"]},
            fetch,
            path=self.readonly_config(),
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(fetch.calls, [])

    def test_update_test_execution_status_puts_the_status(self) -> None:
        fetch = respond(204, None)
        payload = self.call(
            tools.zephyr_update_test_execution_status,
            {"testExecutionIdOrKey": "UAT-E1", "statusName": "Pass", "comment": "looks good"},
            fetch,
            path=self.open_config(),
        )

        self.assertEqual(payload["summary"], 'Updated UAT-E1 to "Pass".')
        self.assertEqual(fetch.urls[0], f"{BASE}/testexecutions/UAT-E1")
        self.assertEqual(fetch.last_init["method"], "PUT")
        self.assertEqual(fetch.json_body(), {"statusName": "Pass", "comment": "looks good"})

    def test_update_test_execution_dry_run_does_not_send(self) -> None:
        fetch = respond(204, None)
        payload = self.call(
            tools.zephyr_update_test_execution_status,
            {"testExecutionIdOrKey": "UAT-E1", "statusName": "Pass", "dryRun": True},
            fetch,
            path=self.readonly_config(),
        )

        self.assertRegex(payload["summary"], "^Dry-run: would update UAT-E1")
        self.assertEqual(fetch.calls, [])

    def test_update_test_execution_is_blocked_on_a_readonly_site(self) -> None:
        fetch = respond(204, None)
        payload = self.call(
            tools.zephyr_update_test_execution_status,
            {"testExecutionIdOrKey": "UAT-E1", "statusName": "Pass"},
            fetch,
            path=self.readonly_config(),
        )

        self.assertFalse(payload["ok"])
        self.assertRegex(payload["error"], 'safetyLevel is "readonly"')
        self.assertEqual(fetch.calls, [])


class DoctorTests(ToolTestCase):
    def test_missing_config_is_reported_not_raised(self) -> None:
        payload = self.call(tools.zephyr_doctor, {}, respond(200, {}), path=str(self.dir / "nope.json"))
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["data"]["configured"])
        self.assertIn("No Zephyr Scale config found", payload["summary"])

    def test_mock_mode_skips_the_live_request(self) -> None:
        path = self.write({**site_payload(), "mock": True})
        fetch = respond(200, {})
        data = json.loads(tools.zephyr_doctor({}, config_path=path, env={}, fetch=fetch))

        self.assertTrue(data["ok"])
        self.assertTrue(data["data"]["mock"])
        self.assertIn("Mock mode enabled", data["summary"])
        self.assertEqual(fetch.calls, [])

    def test_a_missing_token_is_reported_with_the_variable_name(self) -> None:
        fetch = respond(200, {})
        payload = json.loads(tools.zephyr_doctor({}, config_path=self.config_path(), env={}, fetch=fetch))

        self.assertTrue(payload["ok"])
        self.assertFalse(payload["data"]["tokenSet"])
        self.assertIn("ZEPHYR_TOKEN_ACME is not set", payload["summary"])
        self.assertEqual(fetch.calls, [])

    def test_the_live_check_reports_the_result_total(self) -> None:
        fetch = respond(200, {"values": [{"key": "UAT-T1"}], "total": 1, "isLast": True})
        payload = self.call(tools.zephyr_doctor, {}, fetch)

        self.assertEqual(
            payload["summary"],
            f"Connected to {BASE}. Test case listing returned 1 result(s).",
        )
        self.assertEqual(fetch.urls[0], f"{BASE}/testcases?maxResults=1")

    def test_a_health_check_without_a_total_says_so(self) -> None:
        fetch = respond(200, {"values": []})
        payload = self.call(tools.zephyr_doctor, {}, fetch)
        self.assertIn("an unknown number of result(s)", payload["summary"])

    def test_an_unknown_site_is_reported_as_an_error(self) -> None:
        payload = self.call(tools.zephyr_doctor, {"site": "nope"}, respond(200, {}))
        self.assertFalse(payload["ok"])
        self.assertRegex(payload["error"], 'Unknown Zephyr Scale site "nope"')


class ErrorPathTests(ToolTestCase):
    def test_unknown_site_is_reported_as_an_error(self) -> None:
        payload = self.call(
            tools.zephyr_get_test_case, {"testCaseKey": "UAT-T1", "site": "nope"}, respond(200, {})
        )
        self.assertFalse(payload["ok"])
        self.assertRegex(payload["error"], 'Unknown Zephyr Scale site "nope"')

    def test_api_failures_become_error_results(self) -> None:
        fetch = respond(401, {"errorMessage": "Unauthorized"})
        payload = self.call(tools.zephyr_get_test_case, {"testCaseKey": "UAT-T1"}, fetch)

        self.assertFalse(payload["ok"])
        self.assertRegex(payload["error"], "authentication failed")
        self.assertRegex(payload["error"], "ZEPHYR_TOKEN_ACME")

    def test_missing_token_is_reported_before_any_request(self) -> None:
        fetch = respond(200, {})
        payload = json.loads(
            tools.zephyr_get_test_case({"testCaseKey": "UAT-T1"}, config_path=self.config_path(), env={}, fetch=fetch)
        )
        self.assertFalse(payload["ok"])
        self.assertRegex(payload["error"], "ZEPHYR_TOKEN_ACME")
        self.assertEqual(fetch.calls, [])

    def test_a_custom_token_env_variable_is_honoured(self) -> None:
        path = self.write(site_payload(tokenEnv="MY_ZEPHYR_TOKEN"))
        fetch = respond(200, {"key": "UAT-T1", "name": "A"})
        result = tools.zephyr_get_test_case(
            {"testCaseKey": "UAT-T1"}, config_path=path, env={"MY_ZEPHYR_TOKEN": "t"}, fetch=fetch
        )
        self.assertTrue(json.loads(result)["ok"])


if __name__ == "__main__":
    unittest.main()
