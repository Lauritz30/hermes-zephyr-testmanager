"""A single mutable place for plugin configuration resolved at registration time.

The plugin reads its optional ``config_path`` setting from Hermes's plugin config namespace, which
belongs at registration time but is needed by helpers deeper in the stack; keeping it here avoids
threading the value through every call site.
"""

from __future__ import annotations

from typing import Optional

_CONFIG_PATH: dict = {"value": None}


def set_config_path(value: Optional[str]) -> None:
    """Record the configured config-file override (``None``/empty clears it)."""
    cleaned = str(value).strip() if value else ""
    _CONFIG_PATH["value"] = cleaned or None


def config_path_override() -> Optional[str]:
    """Configured config-file override, or ``None`` to use the Hermes-home default."""
    return _CONFIG_PATH["value"]


__all__ = ["config_path_override", "set_config_path"]
