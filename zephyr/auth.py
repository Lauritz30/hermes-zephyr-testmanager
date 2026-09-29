"""Credential handling: the ``Authorization: Bearer`` header + the ``.env`` variable holding a token.

Hermes keeps secrets in ``.env`` (never in ``config.yaml`` and never in a plugin's own JSON
config), so a site record names *which* environment variable holds its Zephyr Scale API access
token instead of carrying the token itself.
"""

from __future__ import annotations

import os
import re
from typing import Mapping, Optional

from .errors import ConfigError

DEFAULT_TOKEN_ENV = "ZEPHYR_TOKEN"

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")


def token_env_suffix(site_name: str) -> str:
    """Environment-variable-safe suffix for a site name (``client-xyz`` -> ``CLIENT_XYZ``)."""
    cleaned = _NON_ALNUM.sub("_", str(site_name or "").strip()).strip("_").upper()
    return cleaned or "DEFAULT"


def token_env_name(site_name: str, override: Optional[str] = None) -> str:
    """Environment variable holding a site's API token.

    An explicit per-site ``tokenEnv`` wins; otherwise ``ZEPHYR_TOKEN_<SITE>`` (e.g. the site
    ``acme`` reads ``ZEPHYR_TOKEN_ACME``).
    """
    if override and str(override).strip():
        return str(override).strip()
    return f"{DEFAULT_TOKEN_ENV}_{token_env_suffix(site_name)}"


def resolve_token(
    site: object,
    env: Optional[Mapping[str, str]] = None,
    token: Optional[str] = None,
) -> str:
    """Token for ``site``: an explicit ``token`` argument, else its configured env var."""
    if token:
        return str(token)

    environ: Mapping[str, str] = os.environ if env is None else env
    name = token_env_name(
        str(getattr(site, "name", "") or ""),
        getattr(site, "token_env", None),
    )
    value = str(environ.get(name) or "").strip()
    if not value:
        raise ConfigError(
            f'No API token for Zephyr Scale site "{getattr(site, "name", "")}": set {name} in '
            f"{_env_file_hint(environ)} (or point the site's \"tokenEnv\" at another variable)."
        )
    return value


def _env_file_hint(environ: Mapping[str, str]) -> str:
    home = str(environ.get("HERMES_HOME") or "").strip()
    return f"{home}/.env" if home else "your Hermes .env"


def token_is_set(site: object, env: Optional[Mapping[str, str]] = None) -> bool:
    """Whether the site's token env var carries a non-empty value."""
    environ: Mapping[str, str] = os.environ if env is None else env
    name = token_env_name(str(getattr(site, "name", "") or ""), getattr(site, "token_env", None))
    return bool(str(environ.get(name) or "").strip())


def build_bearer_auth_header(api_token: Optional[str]) -> str:
    """Build the ``Authorization: Bearer *** header value for a Zephyr Scale API access token."""
    if not api_token:
        raise ValueError("build_bearer_auth_header requires an apiToken.")
    return f"Bearer {api_token}"
