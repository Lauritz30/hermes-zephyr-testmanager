"""Registration tests — what ``register(ctx)`` wires into Hermes."""

from __future__ import annotations

import argparse
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.plugin import (
    PLUGIN_ROOT,
    FakeCtx,
    capture_stdout,
    iter_skill_files,
    load_plugin,
    parse_provides_hooks,
    parse_provides_tools,
    site_payload,
    write_config,
)

plugin = load_plugin()
settings = plugin.zephyr.settings


class RegisterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx = FakeCtx()
        plugin.register(self.ctx)
        self.addCleanup(settings.set_config_path, None)

    def test_every_schema_is_registered_as_a_zephyr_tool(self) -> None:
        schema_names = {schema["name"] for schema in plugin.schemas.TOOL_SCHEMAS}
        self.assertEqual(set(self.ctx.tools), schema_names)
        for name, entry in self.ctx.tools.items():
            with self.subTest(tool=name):
                self.assertEqual(entry["toolset"], plugin.TOOLSET)
                self.assertEqual(entry["toolset"], "zephyr")
                self.assertEqual(entry["schema"]["name"], name)
                self.assertTrue(callable(entry["handler"]))
                self.assertIn("description", entry["schema"])
                self.assertIn("parameters", entry["schema"])

    def test_the_manifest_declares_exactly_the_registered_tools(self) -> None:
        manifest = (PLUGIN_ROOT / "plugin.yaml").read_text(encoding="utf-8")
        declared = set(parse_provides_tools(manifest))
        self.assertEqual(declared, set(self.ctx.tools))

    def test_the_manifest_declares_exactly_the_registered_hook(self) -> None:
        manifest = (PLUGIN_ROOT / "plugin.yaml").read_text(encoding="utf-8")
        self.assertEqual(set(parse_provides_hooks(manifest)), set(self.ctx.hooks))

    def test_every_handler_is_named_and_exported_by_the_tools_module(self) -> None:
        for name in self.ctx.tools:
            with self.subTest(tool=name):
                self.assertTrue(hasattr(plugin.zephyr.tools, name))
                self.assertIs(plugin.zephyr.tools.HANDLERS[name], self.ctx.tools[name]["handler"])

    def test_a_handler_accepts_a_positional_args_dict(self) -> None:
        import inspect

        for name, entry in self.ctx.tools.items():
            with self.subTest(tool=name):
                parameters = list(inspect.signature(entry["handler"]).parameters)
                self.assertTrue(parameters, msg="handler takes an args dict")

    def test_the_approval_hook_is_registered(self) -> None:
        self.assertEqual(self.ctx.hooks["pre_tool_call"], [plugin.zephyr.hooks.pre_tool_call])

    def test_slash_commands_are_registered(self) -> None:
        self.assertEqual(sorted(self.ctx.commands), ["zephyr-doctor", "zephyr-status"])
        for entry in self.ctx.commands.values():
            self.assertTrue(callable(entry["handler"]))
            self.assertTrue(entry["description"])

    def test_the_cli_command_tree_is_registered(self) -> None:
        self.assertIn("zephyr", self.ctx.cli_commands)
        self.assertTrue(callable(self.ctx.cli_commands["zephyr"]["setup_fn"]))
        self.assertTrue(callable(self.ctx.cli_commands["zephyr"]["handler_fn"]))

    def test_bundled_skills_are_registered(self) -> None:
        expected = {path.parent.name for path in plugin.SKILLS_DIR.glob("*/SKILL.md")}
        self.assertTrue(expected)
        self.assertEqual(set(self.ctx.skills), expected)
        for path in self.ctx.skills.values():
            self.assertTrue(path.exists())

    def test_bundled_skills_declare_the_expected_frontmatter(self) -> None:
        for path in iter_skill_files():
            with self.subTest(skill=path.parent.name):
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---\n"))
                description = re.search(r"^description: (.+)$", text, re.MULTILINE)
                self.assertIsNotNone(description)
                self.assertLessEqual(len(description.group(1)), 60)
                self.assertTrue(description.group(1).endswith("."))
                self.assertIn("author: Lauritz30, Hermes Agent", text)
                self.assertIn("license: MIT", text)

    def test_a_schema_handler_mismatch_fails_registration_loudly(self) -> None:
        incomplete = dict(plugin.zephyr.tools.HANDLERS)
        incomplete.pop("zephyr_add_test_cases_to_cycle")
        with mock.patch.object(plugin, "HANDLERS", incomplete):
            with self.assertRaisesRegex(RuntimeError, "zephyr_add_test_cases_to_cycle"):
                plugin.register(FakeCtx())

    def test_an_extra_handler_without_a_schema_fails_registration_loudly(self) -> None:
        broken = dict(plugin.zephyr.tools.HANDLERS)
        broken["zephyr_not_a_tool"] = broken["zephyr_doctor"]
        with mock.patch.object(plugin, "HANDLERS", broken):
            with self.assertRaisesRegex(RuntimeError, "zephyr_not_a_tool"):
                plugin.register(FakeCtx())

    def test_config_path_setting_is_honoured(self) -> None:
        ctx = FakeCtx(config={"config_path": "/tmp/custom-zephyr.json"})
        plugin.register(ctx)
        self.assertEqual(settings.config_path_override(), "/tmp/custom-zephyr.json")

    def test_the_plugin_directory_is_a_real_package(self) -> None:
        self.assertTrue((PLUGIN_ROOT / "__init__.py").exists())
        self.assertTrue((PLUGIN_ROOT / "plugin.yaml").exists())


class SurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="hermes-zephyr-surfaces-")
        self.dir = Path(self._tmp.name)
        self.ctx = FakeCtx()
        plugin.register(self.ctx)
        self.addCleanup(settings.set_config_path, None)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_status_command_reports_a_configured_site(self) -> None:
        settings.set_config_path(write_config(self.dir, site_payload()))
        with mock.patch.dict("os.environ", {"ZEPHYR_TOKEN_ACME": "test-token"}):
            text = self.ctx.commands["zephyr-status"]["handler"]("")

        self.assertIn("✓ Zephyr · acme (confirm)", text)
        self.assertIn("Token: ZEPHYR_TOKEN_ACME (set)", text)
        self.assertIn("Safety level: confirm", text)

    def test_status_command_reports_missing_token_without_leaking_it(self) -> None:
        settings.set_config_path(write_config(self.dir, site_payload()))
        with mock.patch.dict("os.environ", {}, clear=True):
            text = self.ctx.commands["zephyr-status"]["handler"]("")

        self.assertIn("Token: ZEPHYR_TOKEN_ACME (MISSING)", text)
        self.assertNotIn("test-token", text)

    def test_status_command_handles_an_unconfigured_home(self) -> None:
        settings.set_config_path(str(self.dir / "missing.json"))
        text = self.ctx.commands["zephyr-status"]["handler"]("")

        self.assertIn("Zephyr · not configured", text)
        self.assertIn("No config file at", text)

    def test_status_command_accepts_a_site_argument(self) -> None:
        payload = site_payload()
        payload["sites"].append({"name": "other", "baseUrl": "https://other.example.com/v2"})
        settings.set_config_path(write_config(self.dir, payload))

        text = self.ctx.commands["zephyr-status"]["handler"]("other")
        self.assertIn("✓ Zephyr · other (confirm)", text)

    def test_status_command_reports_mock_mode(self) -> None:
        settings.set_config_path(write_config(self.dir, {**site_payload(), "mock": True}))
        text = self.ctx.commands["zephyr-status"]["handler"]("")
        self.assertIn("Mock mode: on", text)

    def test_doctor_command_reports_the_missing_config(self) -> None:
        settings.set_config_path(str(self.dir / "missing.json"))
        self.assertIn(
            "No Zephyr Scale config found", self.ctx.commands["zephyr-doctor"]["handler"]("")
        )

    def test_doctor_command_surfaces_a_broken_config_as_an_error(self) -> None:
        broken = self.dir / "broken.json"
        broken.write_text("{ not json", encoding="utf-8")
        settings.set_config_path(str(broken))
        self.assertIn("❌", self.ctx.commands["zephyr-doctor"]["handler"](""))

    def test_cli_tree_exposes_status_doctor_and_config_path(self) -> None:
        settings.set_config_path(write_config(self.dir, site_payload()))
        parser = argparse.ArgumentParser(prog="hermes")
        subparsers = parser.add_subparsers(dest="command")
        zephyr_parser = subparsers.add_parser("zephyr")
        self.ctx.cli_commands["zephyr"]["setup_fn"](zephyr_parser)

        with mock.patch.dict("os.environ", {"ZEPHYR_TOKEN_ACME": "test-token"}):
            status_args = parser.parse_args(["zephyr", "status"])
            output = capture_stdout(lambda: status_args.func(status_args))
        self.assertIn("acme", output)

        path_args = parser.parse_args(["zephyr", "config-path"])
        self.assertIn("zephyr.json", capture_stdout(lambda: path_args.func(path_args)))

    def test_cli_tree_without_a_subcommand_prints_usage(self) -> None:
        parser = argparse.ArgumentParser(prog="hermes")
        subparsers = parser.add_subparsers(dest="command")
        zephyr_parser = subparsers.add_parser("zephyr")
        self.ctx.cli_commands["zephyr"]["setup_fn"](zephyr_parser)

        args = parser.parse_args(["zephyr"])
        self.assertIn("Usage: hermes zephyr", capture_stdout(lambda: args.func(args)))

    def test_a_registered_tool_is_callable_through_the_plugin(self) -> None:
        settings.set_config_path(str(self.dir / "missing.json"))
        handler = self.ctx.tools["zephyr_doctor"]["handler"]
        self.assertIn("No Zephyr Scale config found", handler({}))

    def test_a_registered_tool_never_raises(self) -> None:
        settings.set_config_path(str(self.dir / "missing.json"))
        handler = self.ctx.tools["zephyr_get_test_case"]["handler"]
        self.assertIn("No Zephyr Scale site configured", handler({"testCaseKey": "UAT-T1"}))


if __name__ == "__main__":
    unittest.main()
