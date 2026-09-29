"""Connection status reporting.

The pi extension rendered a TUI footer label and a persistent connection card; Hermes has no plugin
footer API, so the same information is served through the ``/zephyr-status`` slash command, the
``hermes zephyr status`` CLI command, and ``zephyr_doctor``.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Mapping, Optional

from .config import Config, SiteConfig, config_summary, resolve_safety_level


def build_status_label(config: Config, site: Optional[SiteConfig]) -> str:
    """Compact label, e.g. ``✓ Zephyr · my-site (confirm)`` (the pi footer label, text-for-text)."""
    if site is None:
        return "Zephyr · not configured"
    return f"✓ Zephyr · {site.name} ({resolve_safety_level(config, site)})"


def status_report(
    config: Config,
    site: Optional[SiteConfig],
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Secret-free status payload: where the config is, which site resolved, token availability."""
    environ: Mapping[str, str] = os.environ if env is None else env
    payload: Dict[str, Any] = dict(config_summary(config))
    payload["label"] = build_status_label(config, site)

    if site is None:
        payload.update({"configured": False, "tokenSet": False, "tokenEnv": None})
        return payload

    payload.update(
        {
            "configured": True,
            "site": site.name,
            "baseUrl": site.base_url,
            "tokenEnv": site.api_token_env,
            "tokenSet": bool(str(environ.get(site.api_token_env) or "").strip()),
            "safetyLevel": resolve_safety_level(config, site),
        }
    )
    return payload


def format_status(config: Config, site: Optional[SiteConfig], env: Optional[Mapping[str, str]] = None) -> str:
    """Multi-line human-readable status text for the CLI and slash-command surfaces."""
    report = status_report(config, site, env)
    lines = [report["label"]]

    if not report["configured"]:
        if not report["configExists"]:
            lines.append(f"No config file at {report['configPath']} — create it to add a site.")
        else:
            lines.append(f"Configured sites: {', '.join(report['sites'] or []) or '(none)'}")
        return "\n".join(lines)

    lines.append(f"Site: {report['site']} ({report['baseUrl']})")
    token_state = "set" if report["tokenSet"] else "MISSING"
    lines.append(f"Token: {report['tokenEnv']} ({token_state})")
    lines.append(f"Safety level: {report['safetyLevel']}")
    lines.append(f"Config: {report['configPath']}")
    if report["mock"]:
        lines.append("Mock mode: on (no live requests)")
    return "\n".join(lines)


__all__ = ["build_status_label", "format_status", "status_report"]
