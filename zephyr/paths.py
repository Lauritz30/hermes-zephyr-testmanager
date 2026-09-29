"""Profile-aware paths for plugin state (Hermes homes, not pi homes)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional

HERMES_HOME_ENV = "HERMES_HOME"


def hermes_home(env: Optional[Mapping[str, str]] = None) -> Path:
    """Resolve the active Hermes home directory.

    Precedence:
    1. an explicit ``env`` mapping (used by tests and by callers that already hold one),
    2. ``hermes_constants.get_hermes_home()`` when the plugin runs inside Hermes — this is the
       profile/multiplex-aware answer,
    3. ``$HERMES_HOME``,
    4. ``~/.hermes``.
    """
    if env is None:
        try:  # pragma: no cover - exercised only inside a real Hermes process
            from hermes_constants import get_hermes_home

            return Path(get_hermes_home())
        except Exception:
            pass
        env = os.environ

    raw = str(env.get(HERMES_HOME_ENV) or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".hermes"


def hermes_file(file_name: str, env: Optional[Mapping[str, str]] = None) -> Path:
    """Absolute path to a named file inside the active Hermes home."""
    return hermes_home(env) / file_name
