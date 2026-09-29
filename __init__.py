"""hermes-zephyr-testmanager — Zephyr Scale Cloud API integration plugin for Hermes Agent.

The plugin registers Zephyr Scale tools, the ``pre_tool_call`` approval hook that gates writes, two
slash commands (``/zephyr-status``, ``/zephyr-doctor``), a ``hermes zephyr`` CLI command tree, and the
bundled test-management skills ported from the original prompt templates.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from . import schemas
from .zephyr import hooks as zephyr_hooks
from .zephyr.config import Config, SiteConfig, default_config_path, load_config, resolve_site
from .zephyr.settings import config_path_override, set_config_path
from .zephyr.status import format_status
from .zephyr.tools import HANDLERS, zephyr_doctor

logger = logging.getLogger(__name__)

TOOLSET = "zephyr"
SKILLS_DIR = Path(__file__).parent / "skills"

__all__ = ["TOOLSET", "register"]


def _schema_map() -> Dict[str, Dict[str, Any]]:
    return {schema["name"]: schema for schema in schemas.TOOL_SCHEMAS}


def _resolve_configured_site(raw_args: str = "") -> tuple:
    """Best-effort ``(config, site)`` resolution for the status surfaces.

    Loaded with ``require_token=False``: status *reports* token availability instead of failing on
    it, so a misconfigured site still prints what is wrong.
    """
    config: Config = load_config(config_path_override(), require_token=False)
    site: Optional[SiteConfig] = None
    try:
        site = resolve_site(config, (raw_args or "").strip() or None)
    except Exception as error:  # noqa: BLE001 - status must render the failure, not raise
        logger.debug("hermes-zephyr-testmanager: site resolution for status failed (%s)", error)
    return config, site


def _status_command(raw_args: str = "") -> str:
    """``/zephyr-status`` — connection status, replacing the pi extension's footer label."""
    config, site = _resolve_configured_site(raw_args)
    return format_status(config, site)


def _doctor_command(raw_args: str = "") -> str:
    """``/zephyr-doctor`` — configuration and connectivity check."""
    args: Dict[str, Any] = {}
    if (raw_args or "").strip():
        args["site"] = raw_args.strip()
    payload = json.loads(zephyr_doctor(args))
    if payload.get("ok"):
        return str(payload.get("summary", ""))
    return f"❌ {payload.get('error')}"


def _cli_zephyr(args: argparse.Namespace) -> None:
    """``hermes zephyr <subcommand>`` handler."""
    action = getattr(args, "zephyr_command", None)
    if action == "status":
        config, site = _resolve_configured_site(getattr(args, "site", "") or "")
        print(format_status(config, site))
    elif action == "doctor":
        value = getattr(args, "site", None)
        print(_doctor_command(value or ""))
    elif action == "config-path":
        print(config_path_override() or str(default_config_path()))
    else:
        print("Usage: hermes zephyr <status|doctor|config-path>")


def _setup_cli(subparser: argparse.ArgumentParser) -> None:
    """Build the ``hermes zephyr`` argparse tree."""
    subs = subparser.add_subparsers(dest="zephyr_command")
    status = subs.add_parser("status", help="Show the current Zephyr Scale connection status")
    status.add_argument("site", nargs="?", help="Site name; defaults to defaultSite")
    doctor = subs.add_parser("doctor", help="Check Zephyr Scale configuration and connectivity")
    doctor.add_argument("site", nargs="?", help="Site name; defaults to defaultSite")
    subs.add_parser("config-path", help="Print the resolved config file path")
    subparser.set_defaults(func=_cli_zephyr)


def _register_skills(ctx: Any) -> None:
    """Expose ``skills/*/SKILL.md`` as namespaced plugin skills."""
    if not SKILLS_DIR.is_dir():
        return
    for child in sorted(SKILLS_DIR.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.exists():
            try:
                ctx.register_skill(child.name, skill_md)
            except Exception as error:  # noqa: BLE001 - skills are additive, never fatal
                logger.warning(
                    "hermes-zephyr-testmanager: could not register skill %s (%s)", child.name, error
                )


def register(ctx: Any) -> None:
    """Wire the plugin: tools, approval hook, slash commands, CLI tree, bundled skills."""
    set_config_path(ctx.get_config("config_path", default=""))

    handler_map = dict(HANDLERS)
    schema_map = _schema_map()

    missing_handlers = sorted(set(schema_map) - set(handler_map))
    missing_schemas = sorted(set(handler_map) - set(schema_map))
    if missing_handlers or missing_schemas:
        raise RuntimeError(
            "hermes-zephyr-testmanager: schema/handler mismatch — "
            f"schemas without handlers: {missing_handlers}; handlers without schemas: {missing_schemas}"
        )

    for name, schema in schema_map.items():
        ctx.register_tool(name=name, toolset=TOOLSET, schema=schema, handler=handler_map[name])

    ctx.register_hook("pre_tool_call", zephyr_hooks.pre_tool_call)

    ctx.register_command(
        "zephyr-status",
        handler=_status_command,
        description="Show the current Zephyr Scale connection status (site, safety level)",
    )
    ctx.register_command(
        "zephyr-doctor",
        handler=_doctor_command,
        description="Check Zephyr Scale configuration, auth, and connection health",
    )

    ctx.register_cli_command(
        name="zephyr",
        help="Zephyr Scale integration (hermes-zephyr-testmanager)",
        setup_fn=_setup_cli,
        handler_fn=_cli_zephyr,
    )

    _register_skills(ctx)
