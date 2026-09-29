"""Errors shared by the config, client, and safety layers."""

from __future__ import annotations


class ConfigError(Exception):
    """Raised for a missing, malformed, or unresolvable site configuration."""
