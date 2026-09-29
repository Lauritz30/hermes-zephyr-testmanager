"""Auth and credential-env tests (port of ``test/auth.test.ts``)."""

from __future__ import annotations

import unittest

from tests.plugin import load_plugin

plugin = load_plugin()
auth = plugin.zephyr.auth
config_mod = plugin.zephyr.config


class BuildBearerAuthHeaderTests(unittest.TestCase):
    def test_wraps_the_token(self) -> None:
        self.assertEqual(auth.build_bearer_auth_header("abc123"), "Bearer abc123")

    def test_raises_when_the_token_is_missing(self) -> None:
        for value in (None, ""):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "requires an apiToken"):
                    auth.build_bearer_auth_header(value)


class TokenEnvTests(unittest.TestCase):
    def test_site_name_maps_to_an_env_var(self) -> None:
        self.assertEqual(auth.token_env_name("acme"), "ZEPHYR_TOKEN_ACME")
        self.assertEqual(auth.token_env_name("client-xyz"), "ZEPHYR_TOKEN_CLIENT_XYZ")

    def test_non_alphanumerics_become_underscores_and_are_upper_cased(self) -> None:
        self.assertEqual(auth.token_env_suffix("client xyz"), "CLIENT_XYZ")
        self.assertEqual(auth.token_env_suffix("  "), "DEFAULT")

    def test_explicit_override_wins(self) -> None:
        self.assertEqual(auth.token_env_name("acme", "MY_ZEPHYR_TOKEN"), "MY_ZEPHYR_TOKEN")

    def test_resolve_token_reads_the_environment(self) -> None:
        site = config_mod.SiteConfig(name="acme")
        self.assertEqual(auth.resolve_token(site, {"ZEPHYR_TOKEN_ACME": " tok "}), "tok")

    def test_resolve_token_raises_with_the_variable_name(self) -> None:
        site = config_mod.SiteConfig(name="acme")
        with self.assertRaisesRegex(config_mod.ConfigError, "ZEPHYR_TOKEN_ACME"):
            auth.resolve_token(site, {})

    def test_explicit_token_argument_wins(self) -> None:
        site = config_mod.SiteConfig(name="acme")
        self.assertEqual(auth.resolve_token(site, {}, "explicit"), "explicit")

    def test_token_is_set_reports_availability_without_reading_the_value(self) -> None:
        site = config_mod.SiteConfig(name="acme")
        self.assertTrue(auth.token_is_set(site, {"ZEPHYR_TOKEN_ACME": "t"}))
        self.assertFalse(auth.token_is_set(site, {}))
        self.assertFalse(auth.token_is_set(site, {"ZEPHYR_TOKEN_ACME": "   "}))


if __name__ == "__main__":
    unittest.main()
