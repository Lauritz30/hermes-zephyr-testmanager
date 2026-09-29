"""Service tests (port of ``test/service.test.ts``) — a fake client, no network."""

from __future__ import annotations

import unittest

from tests.plugin import load_plugin

plugin = load_plugin()
service_mod = plugin.zephyr.service


class FakeClient:
    """Records calls and returns canned responses — the service never sees a socket."""

    def __init__(self, get=None, post=None, put=None) -> None:
        self.base_url = "https://example.test"
        self.get_calls = []
        self.post_calls = []
        self.put_calls = []
        self._get = get or (lambda _path, _query=None: {"values": [], "total": 0, "isLast": True})
        self._post = post or (lambda _path, _body=None: {"id": "created"})
        self._put = put or (lambda _path, _body=None: None)

    def get(self, path, query=None):
        self.get_calls.append((path, query))
        return self._get(path, query)

    def post(self, path, body=None):
        self.post_calls.append((path, body))
        return self._post(path, body)

    def put(self, path, body=None):
        self.put_calls.append((path, body))
        return self._put(path, body)


def service(client):
    return service_mod.create_zephyr_service(client)


class PaginationTests(unittest.TestCase):
    def test_list_all_test_cases_follows_pages_until_the_api_marks_the_last_one(self) -> None:
        queries = []

        def get(_path, query=None):
            queries.append(query)
            if query["startAt"] == 0:
                return {"values": [{"key": "CASE-1"}], "total": 2, "isLast": False}
            return {"values": [{"key": "CASE-2"}], "total": 2, "isLast": True}

        result = service(FakeClient(get=get)).list_all_test_cases(
            project_key="PROJ", max_results=1
        )

        self.assertEqual([item["key"] for item in result["values"]], ["CASE-1", "CASE-2"])
        self.assertEqual(
            queries,
            [
                {"projectKey": "PROJ", "maxResults": 1, "startAt": 0},
                {"projectKey": "PROJ", "maxResults": 1, "startAt": 1},
            ],
        )
        self.assertTrue(result["isLast"])
        self.assertEqual(result["total"], 2)

    def test_an_empty_page_ends_pagination(self) -> None:
        calls = []

        def get(_path, query=None):
            calls.append(query["startAt"])
            return {"values": [], "total": 5}

        result = service(FakeClient(get=get)).list_all_test_cases(project_key="PROJ")
        self.assertEqual(calls, [0])
        self.assertEqual(result["values"], [])

    def test_max_items_caps_the_result_and_stops_the_loop(self) -> None:
        calls = []

        def get(_path, query=None):
            calls.append(query["startAt"])
            return {"values": [{"key": "A"}, {"key": "B"}], "total": 10, "isLast": False}

        result = service(FakeClient(get=get)).list_all_test_cases(project_key="PROJ", max_items=3)
        self.assertEqual([item["key"] for item in result["values"]], ["A", "B", "A"])
        self.assertEqual(calls, [0, 2])
        self.assertTrue(result["isLast"])

    def test_max_pages_caps_the_number_of_requests(self) -> None:
        calls = []

        def get(_path, query=None):
            calls.append(query["startAt"])
            return {"values": [{"key": "A"}], "total": 100, "isLast": False}

        result = service(FakeClient(get=get)).list_all_test_cases(project_key="PROJ", max_pages=2)
        self.assertEqual(calls, [0, 1])
        self.assertEqual(len(result["values"]), 2)
        self.assertFalse(result["isLast"])

    def test_pagination_stops_when_start_at_reaches_the_reported_total(self) -> None:
        calls = []

        def get(_path, query=None):
            calls.append(query["startAt"])
            return {"values": [{"key": "A"}], "total": 1, "isLast": False}

        service(FakeClient(get=get)).list_all_test_cases(project_key="PROJ")
        self.assertEqual(calls, [0])


class ListQueryTests(unittest.TestCase):
    def test_test_cases_query_carries_the_project_and_page_window(self) -> None:
        client = FakeClient()
        service(client).list_test_cases(project_key="PROJ", max_results=50, start_at=10)
        self.assertEqual(
            client.get_calls[0],
            ("/testcases", {"projectKey": "PROJ", "maxResults": 50, "startAt": 10}),
        )

    def test_test_cycles_query_can_omit_the_page_window(self) -> None:
        client = FakeClient()
        service(client).list_test_cycles(project_key="PROJ")
        self.assertEqual(
            client.get_calls[0],
            ("/testcycles", {"projectKey": "PROJ", "maxResults": None, "startAt": None}),
        )

    def test_test_executions_query_carries_the_cycle_filter(self) -> None:
        client = FakeClient()
        service(client).list_test_executions(project_key="PROJ", test_cycle="PROJ-R1")
        self.assertEqual(
            client.get_calls[0],
            (
                "/testexecutions",
                {"projectKey": "PROJ", "testCycle": "PROJ-R1", "maxResults": None, "startAt": None},
            ),
        )

    def test_a_non_object_page_body_normalizes_to_an_empty_page(self) -> None:
        client = FakeClient(get=lambda _path, _query=None: None)
        self.assertEqual(
            service(client).list_test_cases(project_key="PROJ"),
            {"values": [], "total": None, "isLast": None},
        )


class GetterTests(unittest.TestCase):
    def test_getters_url_encode_the_identifier(self) -> None:
        client = FakeClient()
        svc = service(client)
        svc.get_test_case("PROJ T1")
        svc.get_test_cycle("PROJ/R1")
        svc.get_test_execution("PROJ-E1")

        self.assertEqual([path for path, _ in client.get_calls], [
            "/testcases/PROJ%20T1",
            "/testcycles/PROJ%2FR1",
            "/testexecutions/PROJ-E1",
        ])

    def test_encode_path_part_is_the_encode_uri_component_equivalent(self) -> None:
        self.assertEqual(service_mod.encode_path_part("PROJ-T1"), "PROJ-T1")
        self.assertEqual(service_mod.encode_path_part("a b"), "a%20b")


class CreateTestCaseTests(unittest.TestCase):
    def test_dry_run_returns_the_normalized_payload_without_posting(self) -> None:
        client = FakeClient()

        result = service(client).create_test_case(
            project_key="PROJ",
            name="Login works",
            folder_id=12,
            fields={"priority": "High"},
            dry_run=True,
        )

        self.assertEqual(
            result,
            {
                "dryRun": True,
                "method": "POST",
                "path": "/testcases",
                "body": {
                    "projectKey": "PROJ",
                    "name": "Login works",
                    "folderId": 12,
                    "priority": "High",
                },
            },
        )
        self.assertEqual(client.post_calls, [])

    def test_the_live_call_posts_the_merged_body(self) -> None:
        client = FakeClient(post=lambda _path, _body=None: {"key": "PROJ-T9"})
        service(client).create_test_case(
            project_key="PROJ",
            name="Login works",
            objective="Verify login",
            precondition="User exists",
            folder_id=12,
            fields={"priority": "High"},
        )

        path, body = client.post_calls[0]
        self.assertEqual(path, "/testcases")
        self.assertEqual(
            body,
            {
                "projectKey": "PROJ",
                "name": "Login works",
                "objective": "Verify login",
                "precondition": "User exists",
                "folderId": 12,
                "priority": "High",
            },
        )


class AddTestCasesToCycleTests(unittest.TestCase):
    def test_dry_run_returns_one_preview_per_test_case_without_posting(self) -> None:
        client = FakeClient()

        previews = service(client).add_test_cases_to_cycle(
            project_key="PROJ",
            test_cycle_key="PROJ-R1",
            test_case_keys=["PROJ-T1", "PROJ-T2"],
            status_name="Not Executed",
            dry_run=True,
        )

        self.assertEqual(len(previews), 2)
        self.assertEqual(previews[0]["path"], "/testexecutions")
        self.assertEqual(
            previews[0]["body"],
            {
                "projectKey": "PROJ",
                "testCaseKey": "PROJ-T1",
                "testCycleKey": "PROJ-R1",
                "statusName": "Not Executed",
            },
        )
        self.assertEqual(client.post_calls, [])

    def test_the_live_call_posts_one_execution_per_test_case(self) -> None:
        executions = [{"key": "PROJ-E1"}, {"id": 42}]
        client = FakeClient(post=lambda _path, _body=None: executions.pop(0))

        result = service(client).add_test_cases_to_cycle(
            project_key="PROJ",
            test_cycle_key="PROJ-R1",
            test_case_keys=["PROJ-T1", "PROJ-T2"],
            environment_name="UAT",
        )

        self.assertEqual(
            result,
            {
                "testCycleKey": "PROJ-R1",
                "created": [
                    {"testCaseKey": "PROJ-T1", "executionKey": "PROJ-E1"},
                    {"testCaseKey": "PROJ-T2", "executionKey": "42"},
                ],
            },
        )
        self.assertEqual([path for path, _ in client.post_calls], ["/testexecutions"] * 2)
        self.assertEqual(client.post_calls[0][1]["environmentName"], "UAT")


class UpdateTestExecutionTests(unittest.TestCase):
    def test_dry_run_previews_the_normalized_request(self) -> None:
        client = FakeClient()

        preview = service(client).update_test_execution(
            test_execution_id_or_key="PROJ-E1", status_name="Pass", comment="ok", dry_run=True
        )

        self.assertEqual(
            preview,
            {
                "dryRun": True,
                "method": "PUT",
                "path": "/testexecutions/PROJ-E1",
                "body": {"statusName": "Pass", "comment": "ok"},
            },
        )
        self.assertEqual(client.put_calls, [])

    def test_the_live_call_puts_the_status_and_returns_a_confirmation(self) -> None:
        client = FakeClient()
        result = service(client).update_test_execution(
            test_execution_id_or_key="PROJ-E1", status_name="Pass"
        )

        self.assertEqual(client.put_calls[0], ("/testexecutions/PROJ-E1", {"statusName": "Pass"}))
        self.assertEqual(
            result, {"testExecutionIdOrKey": "PROJ-E1", "statusName": "Pass"}
        )


if __name__ == "__main__":
    unittest.main()
