"""Mutation gating (port of ``src/safety.ts``).

The decision is a pure function of the resolved safety level, so it is testable on its own and
reusable by both the tool handlers (which block ``readonly`` sites) and the ``pre_tool_call`` hook
(which turns ``confirm`` into a Hermes human-approval escalation).

The pi extension had no ``headlessApprovals`` rules (and no ``ctx.ui.confirm`` in Hermes), so the
``confirm`` level resolves to an escalation of Hermes's own approval gate — the same "blocked, no UI
to prompt" outcome the pi extension produced in headless runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import Config, SiteConfig, resolve_safety_level

PROCEED = "proceed"
ESCALATE = "escalate"
BLOCK = "block"


class SafetyBlockedError(Exception):
    """Raised when a mutation is refused by policy (never by the human-approval gate)."""


@dataclass(frozen=True)
class MutationRequest:
    """What the caller wants to do, in the terms the safety rules match against."""

    title: str
    message: str
    action: Optional[str] = None


def resolve_mutation_decision(config: Config, site: SiteConfig, request: MutationRequest) -> str:
    """Resolve a mutation to :data:`PROCEED`, :data:`ESCALATE`, or :data:`BLOCK`.

    - ``readonly``: always blocked.
    - ``open``: proceeds without any approval.
    - ``confirm`` (default): escalated to Hermes's human-approval gate, which prompts in interactive
      sessions and fails closed when nobody can answer.
    """
    level = resolve_safety_level(config, site)
    if level == "readonly":
        return BLOCK
    if level == "open":
        return PROCEED
    return ESCALATE


def blocked_message(site: SiteConfig, request: MutationRequest) -> str:
    """The pi extension's ``readonly`` refusal text, verbatim."""
    return (
        f'Blocked: safetyLevel is "readonly" for site "{site.name}". '
        f"{request.title} was not performed."
    )


def guard_mutation(config: Config, site: SiteConfig, request: MutationRequest) -> str:
    """Handler-side enforcement: raise :class:`SafetyBlockedError` when policy blocks the call.

    Returns the resolved decision so callers can report it. Escalations are handled by the
    ``pre_tool_call`` hook (Hermes's approval gate), so an escalated call proceeds here.
    """
    decision = resolve_mutation_decision(config, site, request)
    if decision == BLOCK:
        raise SafetyBlockedError(blocked_message(site, request))
    return decision


def mutation_directive(config: Config, site: SiteConfig, request: MutationRequest) -> Optional[dict]:
    """Map a mutation onto a Hermes ``pre_tool_call`` directive (``None`` = no intervention)."""
    decision = resolve_mutation_decision(config, site, request)
    if decision == BLOCK:
        return {"action": "block", "message": blocked_message(site, request)}
    if decision == ESCALATE:
        return {
            "action": "approve",
            "message": request.message,
            "rule_key": f"{request.action or request.title}:{site.name}",
        }
    return None


__all__ = [
    "BLOCK",
    "ESCALATE",
    "PROCEED",
    "MutationRequest",
    "SafetyBlockedError",
    "blocked_message",
    "guard_mutation",
    "mutation_directive",
    "resolve_mutation_decision",
]
