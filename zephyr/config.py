"""Site configuration: load/validate ``<HERMES_HOME>/hermes-zephyr-testmanager.json``.

The file holds non-secret site metadata only (name, base URL, safety level); the API token lives in
an environment variable — see :mod:`zephyr.auth`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .auth import token_env_name
from .errors import ConfigError
from .paths import hermes_file

CONFIG_FILE_NAME = "hermes-zephyr-testmanager.json"
DEFAULT_BASE_URL = "https://api.zephyrscale.smartbear.com/v2"
SAFETY_LEVELS = ("open", "confirm", "readonly")
DEFAULT_SAFETY_LEVEL = "confirm"

__all__ = [
    "CONFIG_FILE_NAME",
    "DEFAULT_BASE_URL",
    "ConfigError",
    "Config",
    "SiteConfig",
    "config_summary",
    "default_config_path",
    "load_config",
    "resolve_safety_level",
    "resolve_site",
]


@dataclass(frozen=True)
class SiteConfig:
    """A single Zephyr Scale site/profile entry."""

    name: str
    base_url: str = DEFAULT_BASE_URL
    token_env: Optional[str] = None
    safety_level: Optional[str] = None

    @property
    def api_token_env(self) -> str:
        """Environment variable that holds this site's API access token."""
        return token_env_name(self.name, self.token_env)


@dataclass(frozen=True)
class Config:
    """Parsed and validated contents of the user-level config file."""

    sites: Sequence[SiteConfig] = field(default_factory=tuple)
    default_site: Optional[str] = None
    safety_level: str = DEFAULT_SAFETY_LEVEL
    mock: bool = False
    config_path: str = ""
    config_exists: bool = False

    def site_names(self) -> List[str]:
        return [site.name for site in self.sites]


def default_config_path(env: Optional[Mapping[str, str]] = None) -> Path:
    """Absolute path to the user-level site config (``<HERMES_HOME>/hermes-zephyr-testmanager.json``)."""
    return hermes_file(CONFIG_FILE_NAME, env)


def _string(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def _parse_site(
    raw: Any, path: str, mock: bool, env: Mapping[str, str], require_token: bool = True
) -> SiteConfig:
    if not isinstance(raw, dict):
        raise ConfigError(f'Config {path}: every entry in "sites" must be an object.')

    name = _string(raw.get("name"))
    base_url = _string(raw.get("baseUrl"))
    token_env = _string(raw.get("tokenEnv"))
    safety_level = _string(raw.get("safetyLevel"))

    if not name:
        raise ConfigError(f'Config {path}: every entry in "sites" requires a "name".')

    site = SiteConfig(
        name=name,
        base_url=base_url or DEFAULT_BASE_URL,
        token_env=token_env,
        safety_level=safety_level,
    )

    if require_token and not mock and not str(env.get(site.api_token_env) or "").strip():
        raise ConfigError(
            f'Config {path}: site "{name}" requires an API token in the environment variable '
            f"{site.api_token_env} (put it in your Hermes .env)."
        )
    return site


def load_config(
    path: Optional[Any] = None,
    env: Optional[Mapping[str, str]] = None,
    *,
    require_token: bool = True,
) -> Config:
    """Load and validate the site config.

    Returns a not-configured stub when no config file exists yet, so ``zephyr_doctor`` can report a
    clear setup message instead of raising.

    ``require_token`` (default) rejects a site whose token env var is unset — the fail-fast path for
    tool calls. Surfaces that *report* configuration instead of acting on it (status, doctor, the
    approval hook) pass ``False`` so site metadata stays readable and the missing token is reported
    rather than thrown.
    """
    environ: Mapping[str, str] = os.environ if env is None else env
    target = Path(path) if path is not None else default_config_path(environ)

    if not target.exists():
        return Config(config_path=str(target), config_exists=False)

    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ConfigError(f"Failed to parse {target}: {error}") from error

    if not isinstance(raw, dict):
        raise ConfigError(f"Config {target}: top level must be a JSON object.")

    raw_sites = raw.get("sites")
    sites = [
        _parse_site(entry, str(target), bool(raw.get("mock")), environ, require_token)
        for entry in (raw_sites if isinstance(raw_sites, list) else [])
    ]

    default_site = _string(raw.get("defaultSite")) or (sites[0].name if sites else None)
    safety_level = raw.get("safetyLevel")
    if safety_level not in ("open", "readonly"):
        safety_level = DEFAULT_SAFETY_LEVEL

    return Config(
        sites=sites,
        default_site=default_site,
        safety_level=safety_level,
        mock=bool(raw.get("mock")),
        config_path=str(target),
        config_exists=True,
    )


def resolve_site(config: Config, name: Optional[str] = None) -> SiteConfig:
    """Resolve the effective site, falling back to ``default_site`` when ``name`` is omitted."""
    site_name = name or config.default_site
    if not site_name:
        raise ConfigError(
            f"No Zephyr Scale site configured. Add one to {config.config_path} "
            "(see README.md for the expected shape)."
        )
    for site in config.sites:
        if site.name == site_name:
            return site
    known = ", ".join(config.site_names()) or "(none configured)"
    raise ConfigError(f'Unknown Zephyr Scale site "{site_name}". Configured sites: {known}.')


def resolve_safety_level(config: Config, site: Optional[SiteConfig] = None) -> str:
    """Cascading safety level: site override > global config > default ``"confirm"``."""
    if site is not None and site.safety_level in SAFETY_LEVELS:
        return site.safety_level
    return config.safety_level if config.safety_level in SAFETY_LEVELS else DEFAULT_SAFETY_LEVEL


def config_summary(config: Config) -> Dict[str, Any]:
    """Serializable, secret-free view of the loaded config (used by the status surfaces)."""
    return {
        "configPath": config.config_path,
        "configExists": config.config_exists,
        "defaultSite": config.default_site,
        "safetyLevel": config.safety_level,
        "mock": config.mock,
        "sites": [
            {
                "name": site.name,
                "baseUrl": site.base_url,
                "tokenEnv": site.api_token_env,
                "safetyLevel": resolve_safety_level(config, site),
            }
            for site in config.sites
        ],
    }
