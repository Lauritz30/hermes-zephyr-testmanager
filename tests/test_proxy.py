"""Proxy resolution tests (port of ``test/proxy.test.ts``)."""

from __future__ import annotations

import unittest

from tests.plugin import load_plugin

proxy = load_plugin().zephyr.proxy


class GetProxyUrlTests(unittest.TestCase):
    def test_returns_none_when_no_proxy_is_configured(self) -> None:
        self.assertIsNone(proxy.get_proxy_url({}))

    def test_reads_https_proxy(self) -> None:
        self.assertEqual(
            proxy.get_proxy_url({"HTTPS_PROXY": "http://proxy.example.com:8080"}),
            "http://proxy.example.com:8080",
        )

    def test_falls_back_through_lowercase_and_http_variants(self) -> None:
        self.assertEqual(proxy.get_proxy_url({"https_proxy": "http://p:1"}), "http://p:1")
        self.assertEqual(proxy.get_proxy_url({"HTTP_PROXY": "http://p:2"}), "http://p:2")
        self.assertEqual(proxy.get_proxy_url({"http_proxy": "http://p:3"}), "http://p:3")

    def test_prefers_https_proxy_over_http_proxy(self) -> None:
        value = proxy.get_proxy_url(
            {"HTTPS_PROXY": "http://secure:8080", "HTTP_PROXY": "http://plain:8080"}
        )
        self.assertEqual(value, "http://secure:8080")

    def test_blank_values_are_ignored(self) -> None:
        self.assertEqual(
            proxy.get_proxy_url({"HTTPS_PROXY": "   ", "HTTP_PROXY": "http://p:9"}), "http://p:9"
        )


if __name__ == "__main__":
    unittest.main()
