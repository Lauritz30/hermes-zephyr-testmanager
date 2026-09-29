"""Safety-gate tests (port of ``test/safety.test.ts``).

The pi extension prompted through ``ctx.ui.confirm``; the Hermes port resolves a decision that the
``pre_tool_call`` hook turns into a block/approve directive. The rules, their precedence, and the
mutation texts are the same, so the original cases are preserved against the new shape.
"""

from __future__ import annotations

import unittest

from tests.plugin import load_plugin

plugin = load_plugin()
safety = plugin.zephyr.safety
config_mod = plugin.zephyr.config

GLOBAL = config_mod.Config(safety_level="confirm")


def site(safety_level=None) -> config_mod.SiteConfig:
    return config_mod.SiteConfig(name="acme", safety_level=safety_level)


def request(**overrides) -> safety.MutationRequest:
    payload = {"title": "t", "message": "m"}
    payload.update(overrides)
    return safety.MutationRequest(**payload)


class DecisionTests(unittest.TestCase):
    def test_readonly_blocks_unconditionally(self) -> None:
        with self.assertRaises(safety.SafetyBlockedError):
            safety.guard_mutation(GLOBAL, site("readonly"), request())
        self.assertEqual(
            safety.resolve_mutation_decision(GLOBAL, site("readonly"), request()), safety.BLOCK
        )

    def test_open_proceeds_without_prompting(self) -> None:
        self.assertEqual(
            safety.resolve_mutation_decision(GLOBAL, site("open"), request()), safety.PROCEED
        )

    def test_confirm_escalates_to_the_approval_gate(self) -> None:
        self.assertEqual(
            safety.resolve_mutation_decision(GLOBAL, site("confirm"), request()), safety.ESCALATE
        )

    def test_the_global_level_applies_when_the_site_has_none(self) -> None:
        readonly_global = config_mod.Config(safety_level="readonly")
        self.assertEqual(
            safety.resolve_mutation_decision(readonly_global, site(), request()), safety.BLOCK
        )
        open_global = config_mod.Config(safety_level="open")
        self.assertEqual(
            safety.resolve_mutation_decision(open_global, site(), request()), safety.PROCEED
        )

    def test_site_level_overrides_the_global_level(self) -> None:
        strict = config_mod.Config(safety_level="readonly")
        self.assertEqual(
            safety.resolve_mutation_decision(strict, site("open"), request()), safety.PROCEED
        )

    def test_guard_returns_the_decision_for_allowed_calls(self) -> None:
        self.assertEqual(safety.guard_mutation(GLOBAL, site("open"), request()), safety.PROCEED)
        self.assertEqual(safety.guard_mutation(GLOBAL, site("confirm"), request()), safety.ESCALATE)

    def test_blocked_message_names_the_site_and_the_action(self) -> None:
        with self.assertRaisesRegex(
            safety.SafetyBlockedError, 'safetyLevel is "readonly" for site "acme"'
        ):
            safety.guard_mutation(GLOBAL, site("readonly"), request(title="Create test case"))

    def test_the_blocked_message_keeps_the_pi_wording(self) -> None:
        message = safety.blocked_message(
            site(), request(title="Update Zephyr Scale test execution status")
        )
        self.assertEqual(
            message,
            'Blocked: safetyLevel is "readonly" for site "acme". '
            "Update Zephyr Scale test execution status was not performed.",
        )


class DirectiveTests(unittest.TestCase):
    def test_readonly_produces_a_block_directive(self) -> None:
        directive = safety.mutation_directive(
            GLOBAL, site("readonly"), request(title="Create test case")
        )
        self.assertEqual(directive["action"], "block")
        self.assertRegex(directive["message"], "Create test case was not performed")

    def test_confirm_produces_an_approve_directive_with_a_rule_key(self) -> None:
        directive = safety.mutation_directive(
            GLOBAL,
            site("confirm"),
            request(message='Create test case "Login works" in PROJ?', action="zephyr_create_test_case"),
        )
        self.assertEqual(directive["action"], "approve")
        self.assertEqual(directive["message"], 'Create test case "Login works" in PROJ?')
        self.assertEqual(directive["rule_key"], "zephyr_create_test_case:acme")

    def test_open_produces_no_directive(self) -> None:
        self.assertIsNone(safety.mutation_directive(GLOBAL, site("open"), request()))

    def test_a_request_without_an_action_falls_back_to_the_title_in_the_rule_key(self) -> None:
        directive = safety.mutation_directive(
            GLOBAL, site("confirm"), request(title="Do the thing")
        )
        self.assertEqual(directive["rule_key"], "Do the thing:acme")


if __name__ == "__main__":
    unittest.main()
