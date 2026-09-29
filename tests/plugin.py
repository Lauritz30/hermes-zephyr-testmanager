"""Test support: load the plugin exactly like Hermes's loader and provide fakes.

Hermes imports a directory plugin as ``hermes_plugins.<slug>`` with the plugin directory as the
package path, so the tests reproduce that shape instead of relying on a friendly directory name
(``hermes-zephyr-testmanager`` is not importable as-is).
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import types
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
NS_PARENT = "hermes_plugins"
MODULE_NAME = f"{NS_PARENT}.hermes_zephyr_testmanager"

SITE_DEFAULTS: Dict[str, Any] = {
    "name": "acme",
    "baseUrl": "https://api.zephyrscale.smartbear.com/v2",
}
TOKEN_ENV = {"ZEPHYR_TOKEN_ACME": "test-token"}


def load_plugin(name: str = MODULE_NAME):
    """Import the plugin directory as a package (cached, like the real loader)."""
    if name in sys.modules:
        return sys.modules[name]
    if NS_PARENT not in sys.modules:
        namespace = types.ModuleType(NS_PARENT)
        namespace.__path__ = []  # type: ignore[attr-defined]
        namespace.__package__ = NS_PARENT
        sys.modules[NS_PARENT] = namespace
    spec = importlib.util.spec_from_file_location(
        name, PLUGIN_ROOT / "__init__.py", submodule_search_locations=[str(PLUGIN_ROOT)]
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = name
    module.__path__ = [str(PLUGIN_ROOT)]  # type: ignore[attr-defined]
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_config(directory: Path, payload: Mapping[str, Any], name: str = "zephyr.json") -> str:
    """Write a site config file and return its path."""
    path = Path(directory) / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def site_payload(**overrides: Any) -> Dict[str, Any]:
    """A valid single-site config payload."""
    site = dict(SITE_DEFAULTS)
    site.update(overrides)
    return {"defaultSite": site["name"], "sites": [site]}


class FakeCtx:
    """Stand-in for Hermes's ``PluginContext``, recording what ``register(ctx)`` wired up."""

    def __init__(self, config: Optional[Mapping[str, Any]] = None) -> None:
        self.config: Dict[str, Any] = dict(config or {})
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.hooks: Dict[str, List[Callable]] = {}
        self.commands: Dict[str, Dict[str, Any]] = {}
        self.cli_commands: Dict[str, Dict[str, Any]] = {}
        self.skills: Dict[str, Path] = {}

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set_config(self, key: str, value: Any) -> None:
        self.config[key] = value

    def register_tool(self, name: str, toolset: str, schema: dict, handler: Callable, **kwargs: Any):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler, **kwargs}

    def register_hook(self, hook_name: str, callback: Callable):
        self.hooks.setdefault(hook_name, []).append(callback)

    def register_command(self, name: str, handler: Callable, description: str = "", **kwargs: Any):
        self.commands[name] = {"handler": handler, "description": description}

    def register_cli_command(self, name: str, help: str = "", setup_fn: Callable = None, handler_fn: Callable = None, **kwargs: Any):  # noqa: A002
        self.cli_commands[name] = {"help": help, "setup_fn": setup_fn, "handler_fn": handler_fn}

    def register_skill(self, name: str, path: Any):
        self.skills[name] = Path(path)


class RecordingFetch:
    """Fetch seam double: records ``(url, init)`` and returns canned responses."""

    def __init__(self, handler: Callable[[str, Dict[str, Any]], Any]) -> None:
        self._handler = handler
        self.calls: List[Tuple[str, Dict[str, Any]]] = []

    def __call__(self, url: str, init: Dict[str, Any]):
        self.calls.append((url, init))
        return self._handler(url, init)

    @property
    def urls(self) -> List[str]:
        return [url for url, _ in self.calls]

    @property
    def last_init(self) -> Dict[str, Any]:
        return self.calls[-1][1]

    def json_body(self, index: int = -1) -> Any:
        return json.loads(self.calls[index][1]["body"].decode("utf-8"))

    def query(self, index: int = -1) -> Mapping[str, List[str]]:
        from urllib.parse import parse_qs, urlparse

        return parse_qs(urlparse(self.calls[index][0]).query)


def respond(status: int, body: Any = None, headers: Optional[Mapping[str, str]] = None):
    """Build a fake fetch returning one JSON response (repeated for every call)."""
    from zephyr.client import HttpResponse

    text = "" if body is None else json.dumps(body)
    return RecordingFetch(lambda _url, _init: HttpResponse(status=status, body=text, headers=dict(headers or {})))


def respond_sequence(*responses: Tuple[int, Any]):
    """Build a fake fetch that returns each ``(status, body)`` tuple in order."""
    from zephyr.client import HttpResponse

    queue = list(responses)

    def handler(_url: str, _init: Dict[str, Any]):
        status, body = queue.pop(0)
        return HttpResponse(status=status, body="" if body is None else json.dumps(body))

    return RecordingFetch(handler)


def capture_stdout(callable_obj: Callable[[], None]) -> str:
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        callable_obj()
    return buffer.getvalue()


def parse_provides_tools(manifest_text: str) -> Sequence[str]:
    """Read the ``provides_tools`` list out of ``plugin.yaml`` without a YAML dependency."""
    names: List[str] = []
    inside = False
    for line in manifest_text.splitlines():
        if re.match(r"^provides_tools:\s*$", line):
            inside = True
            continue
        if inside:
            match = re.match(r"^\s+-\s+(\S+)\s*$", line)
            if match:
                names.append(match.group(1))
            elif line.strip() and not line.startswith(" "):
                break
    return names


def parse_provides_hooks(manifest_text: str) -> Sequence[str]:
    """Read the ``provides_hooks`` list out of ``plugin.yaml`` without a YAML dependency."""
    names: List[str] = []
    inside = False
    for line in manifest_text.splitlines():
        if re.match(r"^provides_hooks:\s*$", line):
            inside = True
            continue
        if inside:
            match = re.match(r"^\s+-\s+(\S+)\s*$", line)
            if match:
                names.append(match.group(1))
            elif line.strip() and not line.startswith(" "):
                break
    return names


def iter_skill_files() -> Iterable[Path]:
    return sorted((PLUGIN_ROOT / "skills").glob("*/SKILL.md"))
