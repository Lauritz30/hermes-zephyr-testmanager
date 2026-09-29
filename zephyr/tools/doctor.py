"""Doctor tool (port of ``src/tools/doctor.ts``) — config, site resolution, token, connectivity."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ..auth import token_is_set
from ..client import FetchLike
from ..config import load_config, resolve_site
from ..service import create_zephyr_service
from ..settings import config_path_override
from .shared import guarded, ok_result, resolve_context


@guarded
def zephyr_doctor(
    args: Mapping[str, Any],
    *,
    env: Optional[Mapping[str, str]] = None,
    token: Optional[str] = None,
    fetch: Optional[FetchLike] = None,
    config_path: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Check configuration and connectivity (config file, site resolution, authentication)."""
    config = load_config(config_path or config_path_override(), env, require_token=False)

    if not config.config_exists:
        return ok_result(
            f"No Zephyr Scale config found at {config.config_path}. Create it with at least one "
            'entry under "sites" (see README.md).',
            {"configured": False, "configPath": config.config_path},
        )

    site = resolve_site(config, args.get("site"))

    if not config.mock and not token_is_set(site, env):
        return ok_result(
            f'Site "{site.name}" ({site.base_url}) resolved from {config.config_path}, but '
            f"{site.api_token_env} is not set — add it to your Hermes .env.",
            {
                "configured": True,
                "mock": False,
                "site": site.name,
                "tokenEnv": site.api_token_env,
                "tokenSet": False,
            },
        )

    if config.mock:
        return ok_result(
            f'Mock mode enabled. Site "{site.name}" ({site.base_url}) resolved from config; '
            "no live Zephyr Scale request made.",
            {"configured": True, "mock": True, "site": site.name},
        )

    _, _, client = resolve_context(args, env=env, token=token, fetch=fetch, config_path=config_path)
    # No dedicated "whoami" endpoint; a minimal test case listing call verifies auth + connectivity.
    result = create_zephyr_service(client).list_test_cases(max_results=1)
    total = result.get("total")
    return ok_result(
        f"Connected to {site.base_url}. Test case listing returned "
        f"{total if total is not None else 'an unknown number of'} result(s).",
        {"configured": True, "mock": False, "site": site.name, "total": total},
    )


DOCTOR_TOOLS = {"zephyr_doctor": zephyr_doctor}
