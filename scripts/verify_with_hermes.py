#!/usr/bin/env python3
"""End-to-end check against a REAL Hermes install.

Everything else in ``tests/`` runs against fakes. This script instead:

1. builds a throwaway ``HERMES_HOME`` (seeded from ``hermes-zephyr-testmanager.example.json``),
2. installs this plugin into it the documented way (symlink + ``plugins.enabled``),
3. loads it through Hermes's own discovery (``import model_tools``),
4. dispatches tool calls through ``model_tools.handle_function_call`` — the real path the model
   uses, including the ``pre_tool_call`` approval hook — with a faked transport so no Zephyr site
   is touched,
5. runs the plugin's real CLI command through the ``hermes`` binary.

Safety levels are exercised with the site-level key (which outranks the top-level one).

Run it with the interpreter of your Hermes install, from the repo root:

    ~/.hermes/hermes-agent/venv/bin/python scripts/verify_with_hermes.py

Exits non-zero and prints the offending output when any check fails.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1]
PLUGIN_NAME = PLUGIN_DIR.name

# The repo's own example config, so the documented example is verified too.
EXAMPLE = json.loads((PLUGIN_DIR / (PLUGIN_NAME + ".example.json")).read_text(encoding="utf-8"))
EXAMPLE["defaultSite"] = "acme"
SITE = EXAMPLE["sites"][0]
TOKEN_ENV = SITE.get("tokenEnv") or "ZEPHYR_TOKEN_" + str(SITE["name"]).upper()

CLIENT_MODULE = "hermes_plugins.hermes_zephyr_testmanager.zephyr.client"
MUTATION_TOOL = "zephyr_create_test_case"
MUTATION_ARGS = {"name": "E2E", "projectKey": "DEMO"}

# Child process: dispatch a tool call through Hermes's real handler.
PHASE_SCRIPT = textwrap.dedent(
    """
    import json
    import sys

    import model_tools  # noqa: F401 - importing it is what runs plugin discovery
    from model_tools import handle_function_call

    tool, args_json = sys.argv[1], sys.argv[2]
    fake_transport = len(sys.argv) > 3 and sys.argv[3] == "patch"
    calls = []
    if fake_transport:
        module = sys.modules[CLIENT_MODULE_LITERAL]
        def record(url, init):
            calls.append(url)
            return module.HttpResponse(
                status=200,
                body=json.dumps({"values": [], "results": [], "key": "X-1", "id": "1", "name": "e2e"}),
                headers={},
            )
        module.urllib_fetch = record

    print("RESULT:" + handle_function_call(tool, json.loads(args_json), task_id="e2e"))
    print("URLS:" + json.dumps(calls))
    """
).replace("CLIENT_MODULE_LITERAL", repr(CLIENT_MODULE))


def build_home(safety_level: str) -> Path:
    """A throwaway HERMES_HOME with this plugin installed and one site configured."""
    home = Path(tempfile.mkdtemp(prefix="hermes-zephyr-e2e-"))
    (home / "plugins").mkdir()
    os.symlink(PLUGIN_DIR, home / "plugins" / PLUGIN_NAME)
    (home / "config.yaml").write_text(
        "plugins:\n  enabled:\n    - " + PLUGIN_NAME + "\n", encoding="utf-8"
    )
    config = json.loads(json.dumps(EXAMPLE))
    config["safetyLevel"] = safety_level
    for site in config["sites"]:
        site["safetyLevel"] = safety_level
    (home / (PLUGIN_NAME + ".json")).write_text(json.dumps(config), encoding="utf-8")
    return home


def child_env(home: Path) -> dict:
    env = dict(os.environ)
    env["HERMES_HOME"] = str(home)
    env[TOKEN_ENV] = "e2e-token"
    env.pop("HTTP_PROXY", None)
    env.pop("HTTPS_PROXY", None)
    return env


def dispatch(home: Path, safety: str, tool: str, args: dict, fake_transport: bool = False) -> str:
    argv = [sys.executable, "-c", PHASE_SCRIPT, tool, json.dumps(args)]
    if fake_transport:
        argv.append("patch")
    proc = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        env=child_env(home),
        # NOT the plugin directory: Python puts cwd on sys.path, and this repo must not shadow
        # Hermes's own top-level modules.
        cwd=str(home),
        timeout=120,
    )
    if proc.returncode != 0:
        raise SystemExit(f"[{safety}] dispatch failed:\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout.strip()


def check(label: str, condition: bool, detail: str) -> None:
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}")
    if not condition:
        raise SystemExit(f"check failed: {label}\n{detail}")


def main() -> int:
    print(f"plugin: {PLUGIN_DIR}")
    home = build_home("confirm")
    try:
        print("1. real discovery + plugin list")
        listing = subprocess.run(
            ["hermes", "plugins", "list", "--plain", "--no-bundled"],
            capture_output=True,
            text=True,
            env=child_env(home),
        )
        check("`hermes plugins list` sees the plugin as enabled",
              PLUGIN_NAME in listing.stdout and "enabled" in listing.stdout,
              listing.stdout + listing.stderr)

        print("2. safetyLevel=readonly blocks the mutation")
        readonly_home = build_home("readonly")
        try:
            out = dispatch(readonly_home, "readonly", MUTATION_TOOL, MUTATION_ARGS)
            check("the handler refuses and nothing is sent",
                  "readonly" in out.lower() and json.loads(out.split("URLS:")[-1]) == [], out)
        finally:
            shutil.rmtree(readonly_home, ignore_errors=True)

        print("3. safetyLevel=confirm escalates through the approval gate")
        out = dispatch(home, "confirm", MUTATION_TOOL, MUTATION_ARGS)
        check("the hook escalates and the call does not execute",
              '"error"' in out.replace("'", '"')
              and "approval" in out.lower()
              and json.loads(out.split("URLS:")[-1]) == [],
              out)

        print("4. safetyLevel=open dispatches to the handler")
        open_home = build_home("open")
        try:
            out = dispatch(open_home, "open", MUTATION_TOOL, MUTATION_ARGS, fake_transport=True)
            urls = json.loads(out.split("URLS:")[-1])
            check("the handler runs and hits the expected endpoint",
                  len(urls) == 1 and urls[0].startswith("https://api.zephyrscale.smartbear.com/v2/"),
                  out)
            print(f"       -> {urls[0]}")
        finally:
            shutil.rmtree(open_home, ignore_errors=True)

        print("5. real CLI command (`hermes zephyr status`)")
        cli = subprocess.run(["hermes", "zephyr", "status"], capture_output=True, text=True,
                             env=child_env(home))
        check("the CLI tree resolves the configured site",
              str(SITE["name"]) in cli.stdout and TOKEN_ENV in cli.stdout,
              cli.stdout + cli.stderr)

        print("\nAll end-to-end checks passed.")
        return 0
    finally:
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
