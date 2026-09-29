"""Approval-hook tests — the ``pre_tool_call`` directive that gates writes."""

from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from tests.plugin import load_plugin, site_payload, write_config

plugin = load_plugin()
hooks = plugin.zephyr.hooks
settings = plugin.zephyr.settings


class PreToolCallTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="hermes-zephyr-hooks-")
        self.dir = Path(self._tmp.name)
        self.hook = hooks.pre_tool_call
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(settings.set_config_path, None)

    def use_config(self, **overrides) -> None:
        settings.set_config_path(write_config(self.dir, site_payload(**overrides)))

    def test_the_hook_accepts_kwargs_for_forward_compatibility(self) -> None:
        parameters = inspect.signature(self.hook).parameters
        self.assertTrue(any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()))

    def test_non_zephyr_and_read_only_tools_are_untouched(self) -> None:
        self.assertIsNone(self.hook("terminal", {"command": "ls"}))
        self.assertIsNone(self.hook("zephyr_list_test_cases", {"projectKey": "UAT"}))
        self.assertIsNone(self.hook())

    def test_confirm_mode_escalates_to_the_approval_gate(self) -> None:
        self.use_config()
        directive = self.hook(
            "zephyr_create_test_case", {"projectKey": "UAT", "name": "Login works"}
        )

        self.assertEqual(directive["action"], "approve")
        self.assertEqual(directive["message"], 'Create test case "Login works" in UAT?')
        self.assertEqual(directive["rule_key"], "zephyr_create_test_case:acme")

    def test_the_cycle_and_status_messages_match_the_pi_source(self) -> None:
        self.use_config()
        cycle = self.hook(
            "zephyr_add_test_cases_to_cycle",
            {"projectKey": "UAT", "testCycleKey": "UAT-R1", "testCaseKeys": ["UAT-T1", "UAT-T2"]},
        )
        self.assertEqual(cycle["message"], "Add 2 test case(s) to cycle UAT-R1 in UAT?")

        status = self.hook(
            "zephyr_update_test_execution_status",
            {"testExecutionIdOrKey": "UAT-E1", "statusName": "Pass"},
        )
        self.assertEqual(status["message"], 'Set UAT-E1 status to "Pass"?')

    def test_open_mode_leaves_the_call_alone(self) -> None:
        self.use_config(safetyLevel="open")
        self.assertIsNone(
            self.hook("zephyr_update_test_execution_status", {"testExecutionIdOrKey": "UAT-E1", "statusName": "Pass"})
        )

    def test_readonly_blocks_the_call(self) -> None:
        self.use_config(safetyLevel="readonly")
        directive = self.hook(
            "zephyr_update_test_execution_status",
            {"testExecutionIdOrKey": "UAT-E1", "statusName": "Pass"},
        )

        self.assertEqual(directive["action"], "block")
        self.assertRegex(directive["message"], 'safetyLevel is "readonly" for site "acme"')

    def test_a_site_level_readonly_override_blocks_an_open_global_level(self) -> None:
        settings.set_config_path(
            write_config(self.dir, {**site_payload(safetyLevel="readonly"), "safetyLevel": "open"})
        )
        directive = self.hook(
            "zephyr_create_test_case", {"projectKey": "UAT", "name": "Login works"}
        )
        self.assertEqual(directive["action"], "block")

    def test_every_mutating_tool_has_a_describable_request(self) -> None:
        mutations = plugin.zephyr.mutations
        for tool_name in mutations.MUTATING_TOOLS:
            with self.subTest(tool=tool_name):
                self.assertIsNotNone(
                    mutations.mutation_request(tool_name, {"name": "x", "testCaseKeys": []})
                )

    def test_non_mutating_tools_have_no_request(self) -> None:
        mutations = plugin.zephyr.mutations
        self.assertIsNone(mutations.mutation_request("zephyr_get_test_case", {}))
        self.assertIsNone(mutations.mutation_request("zephyr_doctor", {}))

    def test_unconfigured_sites_never_veto_a_tool_call(self) -> None:
        settings.set_config_path(str(self.dir / "missing.json"))
        self.assertIsNone(
            self.hook("zephyr_create_test_case", {"projectKey": "UAT", "name": "Login works"})
        )

    def test_a_broken_config_does_not_break_unrelated_tool_calls(self) -> None:
        broken = self.dir / "broken.json"
        broken.write_text("{ not json", encoding="utf-8")
        settings.set_config_path(str(broken))
        self.assertIsNone(
            self.hook("zephyr_update_test_execution_status", {"testExecutionIdOrKey": "UAT-E1", "statusName": "Pass"})
        )

    def test_a_missing_token_does_not_stop_the_hook_from_gating(self) -> None:
        # The hook loads with require_token=False, so a site without its token still resolves and
        # the write is still escalated (the missing token is reported by zephyr_doctor/status).
        settings.set_config_path(write_config(self.dir, site_payload()))
        directive = self.hook("zephyr_create_test_case", {"projectKey": "UAT", "name": "x"})
        self.assertEqual(directive["action"], "approve")


if __name__ == "__main__":
    unittest.main()
