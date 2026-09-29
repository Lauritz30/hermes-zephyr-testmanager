"""Client tests (port of ``test/client.test.ts``) — no network, injected transport."""

from __future__ import annotations

import unittest
from unittest import mock

from tests.plugin import RecordingFetch, load_plugin, respond, respond_sequence

plugin = load_plugin()
client_mod = plugin.zephyr.client
config_mod = plugin.zephyr.config

SITE = config_mod.SiteConfig(name="example")
ENV = {"ZEPHYR_TOKEN_EXAMPLE": "token"}


def make_client(fetch, **kwargs):
    return client_mod.create_zephyr_client(SITE, env=ENV, fetch=fetch, sleep=lambda _s: None, **kwargs)


class RequestTests(unittest.TestCase):
    def test_get_builds_the_url_and_bearer_header_and_returns_parsed_json(self) -> None:
        fetch = respond(200, {"values": [], "total": 0})
        result = make_client(fetch).get("/testcases", {"projectKey": "UAT"})

        self.assertEqual(
            fetch.urls[0],
            "https://api.zephyrscale.smartbear.com/v2/testcases?projectKey=UAT",
        )
        self.assertEqual(fetch.last_init["headers"]["Authorization"], "Bearer token")
        self.assertEqual(fetch.last_init["headers"]["Accept"], "application/json")
        self.assertEqual(fetch.last_init["method"], "GET")
        self.assertEqual(result, {"values": [], "total": 0})

    def test_trailing_slashes_on_the_base_url_are_normalized(self) -> None:
        site = config_mod.SiteConfig(name="example", base_url="https://api.zephyrscale.smartbear.com/v2/")
        fetch = respond(200, {})
        client_mod.create_zephyr_client(site, env=ENV, fetch=fetch).get("/testcases")
        self.assertEqual(fetch.urls[0], "https://api.zephyrscale.smartbear.com/v2/testcases")

    def test_a_custom_base_url_is_used_as_is(self) -> None:
        site = config_mod.SiteConfig(name="example", base_url="https://eu.example.com/v2")
        fetch = respond(200, {})
        client_mod.create_zephyr_client(site, env=ENV, fetch=fetch).get("/testcycles")
        self.assertEqual(fetch.urls[0], "https://eu.example.com/v2/testcycles")

    def test_query_serialization_repeats_arrays_and_skips_none(self) -> None:
        fetch = respond(200, {})
        make_client(fetch).get(
            "/testcases", {"projectKey": "UAT", "status": ["Pass", "Fail"], "missing": None}
        )

        query = fetch.query()
        self.assertEqual(query["projectKey"], ["UAT"])
        self.assertEqual(query["status"], ["Pass", "Fail"])
        self.assertNotIn("missing", query)

    def test_post_sends_a_json_body_and_content_type(self) -> None:
        fetch = respond(200, {"key": "UAT-T1"})
        make_client(fetch).post("/testcases", {"projectKey": "UAT", "name": "Login works"})

        self.assertEqual(fetch.last_init["method"], "POST")
        self.assertEqual(fetch.last_init["headers"]["Content-Type"], "application/json")
        self.assertEqual(fetch.json_body(), {"projectKey": "UAT", "name": "Login works"})

    def test_get_omits_content_type(self) -> None:
        fetch = respond(200, {})
        make_client(fetch).get("/testcases")
        self.assertNotIn("Content-Type", fetch.last_init["headers"])

    def test_204_resolves_to_none(self) -> None:
        fetch = respond(204, None)
        self.assertIsNone(make_client(fetch).put("/testexecutions/UAT-E1", {"statusName": "Pass"}))


class ErrorTests(unittest.TestCase):
    def test_non_2xx_raises_with_status_and_body(self) -> None:
        fetch = respond(401, {"errorMessage": "Unauthorized"})
        with self.assertRaises(client_mod.ZephyrApiError) as caught:
            make_client(fetch).get("/testcases")

        self.assertEqual(caught.exception.status, 401)
        self.assertEqual(caught.exception.body, {"errorMessage": "Unauthorized"})
        self.assertRegex(str(caught.exception), "authentication failed")
        self.assertRegex(str(caught.exception), "ZEPHYR_TOKEN_EXAMPLE")

    def test_403_and_404_have_actionable_messages(self) -> None:
        for status, fragment in ((403, "denied the request"), (404, "not found")):
            with self.subTest(status=status):
                with self.assertRaises(client_mod.ZephyrApiError) as caught:
                    make_client(respond(status, {})).get("/testcases/NOPE-T1")
                self.assertRegex(str(caught.exception), fragment)

    def test_a_generic_error_carries_the_status_and_detail(self) -> None:
        fetch = respond(500, {"message": "boom"})
        with self.assertRaises(client_mod.ZephyrApiError) as caught:
            make_client(fetch).get("/testcases")

        self.assertEqual(caught.exception.status, 500)
        self.assertRegex(str(caught.exception), "Zephyr Scale API request failed: 500 boom")

    def test_non_json_error_bodies_are_preserved(self) -> None:
        fetch = RecordingFetch(
            lambda _url, _init: client_mod.HttpResponse(status=502, body="<html>bad gateway</html>")
        )
        with self.assertRaises(client_mod.ZephyrApiError) as caught:
            make_client(fetch).get("/testcases")
        self.assertEqual(caught.exception.body, {"raw": "<html>bad gateway</html>"})


class RetryTests(unittest.TestCase):
    def test_429_is_retried_after_retry_after(self) -> None:
        fetch = respond_sequence((429, None), (200, {"values": []}))
        result = make_client(fetch).get("/testcases")

        self.assertEqual(len(fetch.calls), 2)
        self.assertEqual(result, {"values": []})

    def test_retry_gives_up_after_the_configured_attempts(self) -> None:
        fetch = respond(429, {"errorMessage": "rate limited"}, {"retry-after": "0"})
        with self.assertRaises(client_mod.ZephyrApiError) as caught:
            make_client(fetch).get("/testcases")

        self.assertEqual(len(fetch.calls), client_mod.MAX_RETRIES + 1)
        self.assertEqual(caught.exception.status, 429)

    def test_retry_after_defaults_to_one_second(self) -> None:
        slept: list = []
        fetch = respond_sequence((429, None), (200, {}))
        client = client_mod.create_zephyr_client(SITE, env=ENV, fetch=fetch, sleep=slept.append)
        client.get("/testcases")
        self.assertEqual(slept, [1.0])

    def test_a_retry_after_header_value_is_used_when_present(self) -> None:
        slept: list = []
        responses = [
            client_mod.HttpResponse(429, "", {"retry-after": "2"}),
            client_mod.HttpResponse(200, "{}", {}),
        ]
        fetch = RecordingFetch(lambda _url, _init: responses.pop(0))
        client_mod.create_zephyr_client(
            SITE, env=ENV, fetch=fetch, sleep=slept.append
        ).get("/testcases")
        self.assertEqual(slept, [2.0])

    def test_an_invalid_retry_after_falls_back_to_one_second(self) -> None:
        slept: list = []
        responses = [
            client_mod.HttpResponse(429, "", {"retry-after": "soon"}),
            client_mod.HttpResponse(200, "{}", {}),
        ]
        fetch = RecordingFetch(lambda _url, _init: responses.pop(0))
        client_mod.create_zephyr_client(
            SITE, env=ENV, fetch=fetch, sleep=slept.append
        ).get("/testcases")
        self.assertEqual(slept, [1.0])


class ProxyPassthroughTests(unittest.TestCase):
    def test_proxy_url_from_the_environment_is_passed_to_the_transport(self) -> None:
        fetch = respond(200, {})
        with mock.patch.dict("os.environ", {"HTTPS_PROXY": "http://proxy.example.com:8080"}, clear=True):
            make_client(fetch).get("/testcases")
        self.assertEqual(fetch.last_init["proxy"], "http://proxy.example.com:8080")

    def test_no_proxy_is_passed_when_unset(self) -> None:
        fetch = respond(200, {})
        with mock.patch.dict("os.environ", {}, clear=True):
            make_client(fetch).get("/testcases")
        self.assertIsNone(fetch.last_init["proxy"])


class MessageTests(unittest.TestCase):
    def test_messages_adapt_to_the_environment_variable_token(self) -> None:
        self.assertEqual(
            client_mod.message_for_status(401, {}, token_env="ZEPHYR_TOKEN_ACME"),
            "Zephyr Scale authentication failed (401). Check the ZEPHYR_TOKEN_ACME variable.",
        )
        self.assertEqual(
            client_mod.message_for_status(403, None),
            "Zephyr Scale denied the request (403 Forbidden).",
        )
        self.assertEqual(
            client_mod.message_for_status(404, {"errorMessage": "no such case"}),
            "Zephyr Scale resource not found (404). no such case",
        )
        self.assertEqual(
            client_mod.message_for_status(429, {}, token_env="ZEPHYR_TOKEN_ACME"),
            "Zephyr Scale API request failed: 429",
        )


if __name__ == "__main__":
    unittest.main()
