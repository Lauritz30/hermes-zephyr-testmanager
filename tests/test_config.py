"""Config tests (port of ``test/config.test.ts`` plus the .env token rules)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.plugin import TOKEN_ENV, load_plugin, site_payload, write_config

plugin = load_plugin()
config_mod = plugin.zephyr.config


class LoadConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="hermes-zephyr-test-")
        self.dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_missing_file_yields_a_not_configured_stub(self) -> None:
        config = config_mod.load_config(self.dir / "missing.json", TOKEN_ENV)
        self.assertFalse(config.config_exists)
        self.assertEqual(list(config.sites), [])

    def test_parses_a_valid_config_and_applies_the_default_base_url(self) -> None:
        path = write_config(self.dir, site_payload(baseUrl=None))
        config = config_mod.load_config(path, TOKEN_ENV)
        self.assertTrue(config.config_exists)
        self.assertEqual(config.sites[0].base_url, config_mod.DEFAULT_BASE_URL)
        self.assertEqual(config.default_site, "acme")
        self.assertEqual(config.safety_level, "confirm")
        self.assertFalse(config.mock)

    def test_respects_a_custom_base_url_override(self) -> None:
        path = write_config(self.dir, site_payload(baseUrl="https://custom.example.com/v2"))
        self.assertEqual(
            config_mod.load_config(path, TOKEN_ENV).sites[0].base_url,
            "https://custom.example.com/v2",
        )

    def test_default_site_falls_back_to_the_first_site(self) -> None:
        payload = site_payload()
        payload.pop("defaultSite")
        config = config_mod.load_config(write_config(self.dir, payload), TOKEN_ENV)
        self.assertEqual(config.default_site, "acme")

    def test_rejects_a_site_with_no_name(self) -> None:
        payload = site_payload()
        payload["sites"][0].pop("name")
        with self.assertRaisesRegex(config_mod.ConfigError, 'requires a "name"'):
            config_mod.load_config(write_config(self.dir, payload), TOKEN_ENV)

    def test_rejects_a_non_object_site_entry(self) -> None:
        with self.assertRaisesRegex(config_mod.ConfigError, "must be an object"):
            config_mod.load_config(write_config(self.dir, {"sites": ["acme"]}), TOKEN_ENV)

    def test_rejects_a_non_object_top_level(self) -> None:
        path = self.dir / "list.json"
        path.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(config_mod.ConfigError, "top level must be a JSON object"):
            config_mod.load_config(path, TOKEN_ENV)

    def test_a_non_list_sites_value_is_treated_as_empty(self) -> None:
        path = write_config(self.dir, {"sites": {"name": "acme"}})
        config = config_mod.load_config(path, TOKEN_ENV)
        self.assertTrue(config.config_exists)
        self.assertEqual(list(config.sites), [])

    def test_rejects_a_site_whose_token_env_var_is_unset(self) -> None:
        path = write_config(self.dir, site_payload())
        with self.assertRaisesRegex(config_mod.ConfigError, "ZEPHYR_TOKEN_ACME"):
            config_mod.load_config(path, {})

    def test_allows_a_missing_token_in_mock_mode(self) -> None:
        payload = site_payload()
        payload["mock"] = True
        config = config_mod.load_config(write_config(self.dir, payload), {})
        self.assertTrue(config.mock)
        self.assertTrue(config.config_exists)

    def test_a_custom_token_env_names_its_own_variable(self) -> None:
        payload = site_payload(tokenEnv="MY_ZEPHYR_TOKEN")
        config = config_mod.load_config(write_config(self.dir, payload), {"MY_ZEPHYR_TOKEN": "t"})
        self.assertEqual(config.sites[0].api_token_env, "MY_ZEPHYR_TOKEN")

    def test_require_token_false_loads_site_metadata_without_a_token(self) -> None:
        path = write_config(self.dir, site_payload())
        config = config_mod.load_config(path, {}, require_token=False)

        self.assertEqual(config.sites[0].name, "acme")
        self.assertEqual(config_mod.resolve_site(config).name, "acme")

    def test_an_unknown_safety_level_falls_back_to_confirm(self) -> None:
        payload = site_payload()
        payload["safetyLevel"] = "whatever"
        config = config_mod.load_config(write_config(self.dir, payload), TOKEN_ENV)
        self.assertEqual(config.safety_level, "confirm")

    def test_open_and_readonly_global_levels_are_honoured(self) -> None:
        for level in ("open", "readonly"):
            with self.subTest(level=level):
                payload = site_payload()
                payload["safetyLevel"] = level
                config = config_mod.load_config(write_config(self.dir, payload), TOKEN_ENV)
                self.assertEqual(config.safety_level, level)

    def test_malformed_json_raises(self) -> None:
        path = self.dir / "broken.json"
        path.write_text("{ not json", encoding="utf-8")
        with self.assertRaises(config_mod.ConfigError):
            config_mod.load_config(str(path), TOKEN_ENV)


class ResolveSiteTests(unittest.TestCase):
    def _config(self, **overrides):
        payload = site_payload(**overrides)
        payload["sites"].append({"name": "other", "baseUrl": "https://other.example.com/v2"})
        return config_mod.load_config(
            write_config(Path(tempfile.mkdtemp()), payload),
            {**TOKEN_ENV, "ZEPHYR_TOKEN_OTHER": "other-token"},
        )

    def test_finds_the_named_site_and_falls_back_to_the_default(self) -> None:
        config = self._config()
        self.assertEqual(config_mod.resolve_site(config).name, "acme")
        self.assertEqual(config_mod.resolve_site(config, "other").name, "other")

    def test_unknown_site_lists_the_configured_names(self) -> None:
        with self.assertRaisesRegex(config_mod.ConfigError, "Configured sites: acme, other"):
            config_mod.resolve_site(self._config(), "nope")

    def test_no_sites_configured_is_an_error(self) -> None:
        config = config_mod.Config(sites=(), default_site=None, config_path="/tmp/x.json")
        with self.assertRaisesRegex(config_mod.ConfigError, "No Zephyr Scale site configured"):
            config_mod.resolve_site(config)

    def test_site_names_lists_every_configured_site(self) -> None:
        self.assertEqual(self._config().site_names(), ["acme", "other"])


class SafetyLevelResolutionTests(unittest.TestCase):
    def test_site_override_beats_the_global_level(self) -> None:
        site = config_mod.SiteConfig(name="acme", safety_level="open")
        self.assertEqual(
            config_mod.resolve_safety_level(config_mod.Config(safety_level="confirm"), site), "open"
        )
        self.assertEqual(
            config_mod.resolve_safety_level(config_mod.Config(safety_level="confirm")), "confirm"
        )
        self.assertEqual(
            config_mod.resolve_safety_level(config_mod.Config(safety_level="readonly"), site), "open"
        )

    def test_an_unknown_site_level_falls_back_to_the_global_one(self) -> None:
        site = config_mod.SiteConfig(name="acme", safety_level="whatever")
        self.assertEqual(
            config_mod.resolve_safety_level(config_mod.Config(safety_level="readonly"), site),
            "readonly",
        )


class SummaryTests(unittest.TestCase):
    def test_summary_reports_token_env_names_but_never_values(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        config = config_mod.load_config(write_config(tmp, site_payload()), TOKEN_ENV)
        summary = config_mod.config_summary(config)

        self.assertEqual(summary["sites"][0]["tokenEnv"], "ZEPHYR_TOKEN_ACME")
        self.assertEqual(summary["sites"][0]["baseUrl"], config_mod.DEFAULT_BASE_URL)
        self.assertNotIn("test-token", json.dumps(summary))


if __name__ == "__main__":
    unittest.main()
