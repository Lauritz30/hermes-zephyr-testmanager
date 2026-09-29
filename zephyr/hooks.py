"""``pre_tool_call`` hook: turns the safety decision into a Hermes approval directive.

Hermes has no ``ctx.ui.confirm`` for plugins. The documented steering shape is a ``pre_tool_call``
hook returning ``{"action": "block" | "approve", "message": ...}``:

- ``readonly`` -> ``block`` (the tool never runs),
- ``confirm``  -> ``approve`` (escalates to the same human-approval gate as dangerous shell commands:
  it prompts in interactive sessions, honors ``approvals.cron_mode`` for cron, and fails closed when
  nobody can answer),
- ``open`` -> no directive (proceeds).
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from .config import load_config, resolve_site
from .mutations import MUTATING_TOOLS, mutation_request
from .safety import mutation_directive
from .settings import config_path_override

logger = logging.getLogger(__name__)


def pre_tool_call(
    tool_name: str = "",
    args: Optional[Mapping[str, Any]] = None,
    **kwargs: Any,
) -> Optional[dict]:
    """Gate our mutating tools; every other tool call is left untouched."""
    if tool_name not in MUTATING_TOOLS:
        return None

    payload: Mapping[str, Any] = args or {}
    request = mutation_request(tool_name, payload)
    if request is None:
        return None

    try:
        config = load_config(config_path_override(), require_token=False)
        site = resolve_site(config, payload.get("site"))
        return mutation_directive(config, site, request)
    except Exception as error:  # noqa: BLE001 - a broken config must not veto every tool call
        logger.debug("hermes-zephyr-testmanager: approval hook skipped (%s)", error)
        return None


__all__ = ["pre_tool_call"]
