"""Minimal Zephyr Scale Cloud REST API v2 client (port of ``src/client.ts``).

The transport is an injectable ``fetch(url, init) -> HttpResponse`` callable, so tests drive the
client without a network — the same seam the TypeScript original used.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Union

from .auth import build_bearer_auth_header, resolve_token
from .config import DEFAULT_BASE_URL
from .proxy import get_proxy_url

DEFAULT_TIMEOUT = 30.0
RETRYABLE_STATUS = 429
MAX_RETRIES = 2

QueryValue = Union[str, int, float, bool, Sequence[Any], None]


class ZephyrApiError(Exception):
    """A non-2xx Zephyr Scale response, or a transport failure."""

    def __init__(self, message: str, *, status: Optional[int] = None, body: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


@dataclass(frozen=True)
class HttpResponse:
    """Structural response the client touches — real responses and test doubles both satisfy it."""

    status: int
    body: str = ""
    headers: Mapping[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def header(self, name: str, default: Optional[str] = None) -> Optional[str]:
        lowered = {str(key).lower(): value for key, value in self.headers.items()}
        return lowered.get(name.lower(), default)


FetchLike = Callable[[str, Dict[str, Any]], HttpResponse]


def urllib_fetch(url: str, init: Dict[str, Any]) -> HttpResponse:
    """Default transport: ``urllib`` with optional proxy handling from the environment."""
    request = urllib.request.Request(
        url,
        data=init.get("body"),
        headers=dict(init.get("headers") or {}),
        method=init.get("method") or "GET",
    )
    proxy = init.get("proxy")
    handlers = (
        [urllib.request.ProxyHandler({"http": proxy, "https": proxy})] if proxy else []
    )
    opener = urllib.request.build_opener(*handlers)
    timeout = init.get("timeout", DEFAULT_TIMEOUT)
    try:
        with opener.open(request, timeout=timeout) as response:
            return HttpResponse(
                status=int(getattr(response, "status", response.getcode())),
                body=response.read().decode("utf-8", "replace"),
                headers={str(key).lower(): value for key, value in response.headers.items()},
            )
    except urllib.error.HTTPError as error:
        return HttpResponse(
            status=int(error.code),
            body=error.read().decode("utf-8", "replace"),
            headers={str(key).lower(): value for key, value in (error.headers or {}).items()},
        )
    except urllib.error.URLError as error:
        raise ZephyrApiError(f"Zephyr Scale request to {url} failed: {error.reason}") from error
    except OSError as error:  # pragma: no cover - socket-level failure
        raise ZephyrApiError(f"Zephyr Scale request to {url} failed: {error}") from error


def build_query_string(query: Optional[Mapping[str, QueryValue]]) -> str:
    """Serialize query params, skipping ``None`` and repeating array values as separate keys."""
    if not query:
        return ""
    pairs: list = []
    for key, value in query.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            pairs.extend((key, item) for item in value if item is not None)
        else:
            pairs.append((key, value))
    encoded = urllib.parse.urlencode(pairs, doseq=True)
    return f"?{encoded}" if encoded else ""


def _strip_trailing_slashes(url: str) -> str:
    return url.rstrip("/")


def _extract_error_detail(body: Any) -> Optional[str]:
    if not isinstance(body, dict):
        return None
    for key in ("errorMessage", "message"):
        value = body.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def message_for_status(status: int, body: Any, *, token_env: str = "") -> str:
    """Human-readable message for the statuses Zephyr Scale reports most often.

    Mitigates the pi wording, with the token hint pointing at the ``.env`` variable that replaced the
    inline ``apiToken`` config field.
    """
    detail = _extract_error_detail(body)
    suffix = f" {detail}" if detail else ""
    if status == 401:
        hint = f" Check the {token_env} variable." if token_env else ""
        return f"Zephyr Scale authentication failed (401).{hint}{suffix}"
    if status == 403:
        return f"Zephyr Scale denied the request (403 Forbidden).{suffix}"
    if status == 404:
        return f"Zephyr Scale resource not found (404).{suffix}"
    return f"Zephyr Scale API request failed: {status}{suffix}"


def _parse_body(text: str) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return {"raw": text}


def _retry_after_seconds(response: HttpResponse) -> float:
    raw = response.header("retry-after")
    try:
        parsed = float(raw) if raw is not None else 1.0
    except (TypeError, ValueError):
        return 1.0
    return parsed if parsed >= 0 else 1.0


class ZephyrClient:
    """JSON-in/JSON-out wrapper over one Zephyr Scale site/profile."""

    def __init__(
        self,
        site: Any,
        *,
        token: Optional[str] = None,
        env: Optional[Mapping[str, str]] = None,
        fetch: Optional[FetchLike] = None,
        timeout: float = DEFAULT_TIMEOUT,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.site = site
        self.timeout = timeout
        self._sleep = sleep
        self._fetch: FetchLike = fetch or urllib_fetch
        self.token_env = getattr(site, "api_token_env", "") or ""
        self.base_url = _strip_trailing_slashes(
            str(getattr(site, "base_url", "") or DEFAULT_BASE_URL)
        )
        self._auth_header = build_bearer_auth_header(resolve_token(site, env, token))

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: Optional[Mapping[str, QueryValue]] = None,
        body: Any = None,
    ) -> Any:
        url = f"{self.base_url}{path}{build_query_string(query)}"
        headers = {
            "Authorization": self._auth_header,
            "Accept": "application/json",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"

        attempt = 0
        while True:
            response = self._fetch(
                url,
                {
                    "method": method,
                    "headers": headers,
                    "body": json.dumps(body).encode("utf-8") if body is not None else None,
                    "timeout": self.timeout,
                    "proxy": get_proxy_url(),
                },
            )
            if response.status == RETRYABLE_STATUS and attempt < MAX_RETRIES:
                attempt += 1
                self._sleep(_retry_after_seconds(response))
                continue

            if response.status == 204:
                return None

            parsed = _parse_body(response.body)
            if not response.ok:
                raise ZephyrApiError(
                    message_for_status(response.status, parsed, token_env=self.token_env),
                    status=response.status,
                    body=parsed,
                )
            return parsed

    def get(self, path: str, query: Optional[Mapping[str, QueryValue]] = None) -> Any:
        return self._request("GET", path, query=query)

    def post(self, path: str, body: Any = None, query: Optional[Mapping[str, QueryValue]] = None) -> Any:
        return self._request("POST", path, query=query, body=body)

    def put(self, path: str, body: Any = None, query: Optional[Mapping[str, QueryValue]] = None) -> Any:
        return self._request("PUT", path, query=query, body=body)


def create_zephyr_client(
    site: Any,
    *,
    token: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    fetch: Optional[FetchLike] = None,
    timeout: float = DEFAULT_TIMEOUT,
    sleep: Callable[[float], None] = time.sleep,
) -> ZephyrClient:
    """Create a Zephyr Scale Cloud REST API v2 client for one site."""
    return ZephyrClient(site, token=token, env=env, fetch=fetch, timeout=timeout, sleep=sleep)


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
    "FetchLike",
    "HttpResponse",
    "MAX_RETRIES",
    "RETRYABLE_STATUS",
    "ZephyrApiError",
    "ZephyrClient",
    "build_query_string",
    "create_zephyr_client",
    "message_for_status",
    "urllib_fetch",
]
