"""Shared helpers for the Zephyr Scale tool handlers."""

from __future__ import annotations

import functools
import json
from typing import Any, Dict, Mapping, Optional, Tuple

from ..client import FetchLike, ZephyrClient, create_zephyr_client
from ..config import Config, SiteConfig, load_config, resolve_site
from ..settings import config_path_override


def dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def ok_result(summary: str, data: Any = None) -> str:
    """Successful tool result: a model-facing ``summary`` plus the raw API payload."""
    return dumps({"ok": True, "summary": summary, "data": {} if data is None else data})


def error_result(message: str) -> str:
    """Error tool result. Handlers never raise — the model always gets JSON back."""
    return dumps({"ok": False, "error": message})


def guarded(handler):
    """Wrap a handler so any failure becomes an error JSON string instead of an exception."""

    @functools.wraps(handler)
    def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            return handler(*args, **kwargs)
        except Exception as error:  # noqa: BLE001 - the model needs the message, not a traceback
            return error_result(str(error) or error.__class__.__name__)

    return wrapper


def resolve_context(
    params: Mapping[str, Any],
    *,
    env: Optional[Mapping[str, str]] = None,
    token: Optional[str] = None,
    fetch: Optional[FetchLike] = None,
    config_path: Optional[str] = None,
) -> Tuple[Config, SiteConfig, ZephyrClient]:
    """Load config, resolve the requested site, and build its client."""
    config = load_config(config_path or config_path_override(), env)
    site = resolve_site(config, params.get("site"))
    client = create_zephyr_client(site, token=token, env=env, fetch=fetch)
    return config, site, client


__all__ = [
    "dumps",
    "error_result",
    "guarded",
    "ok_result",
    "resolve_context",
]
