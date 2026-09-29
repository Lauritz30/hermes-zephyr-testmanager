"""Corporate egress proxy resolution (port of ``src/proxy.ts``).

The client reads the proxy from the environment so requests work from inside a container behind a
corporate egress proxy; ``NO_PROXY`` handling is left to the transport.
"""

from __future__ import annotations

import os
from typing import Mapping, Optional

PROXY_ENV_VARS = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy")


def get_proxy_url(env: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """First configured proxy URL, or ``None`` when no proxy env var is set."""
    environ: Mapping[str, str] = os.environ if env is None else env
    for name in PROXY_ENV_VARS:
        value = str(environ.get(name) or "").strip()
        if value:
            return value
    return None
