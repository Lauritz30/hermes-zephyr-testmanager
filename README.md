# hermes-zephyr-testmanager

Zephyr Scale Cloud (REST API v2) integration for [Hermes Agent](https://hermes-agent.nousresearch.com/docs/) — test cases, test cycles, test executions, and safety-gated test-management writes for UAT workflows.

Hermes port of [`pi-zephyr-testmanager`](https://github.com/Lauritz30/pi-zephyr-testmanager): the tool surface, safety model, and prompt templates are preserved; the pi extension API, TUI footer/card, and inline-token config are replaced by the Hermes plugin API, slash commands, skills, and `.env`-stored tokens.

> Status: standalone Hermes plugin (Python, stdlib only — no runtime dependencies).
>
> **The tool paths below reflect the publicly documented Zephyr Scale Cloud REST API v2 shape. Confirm `/testexecutions` update semantics and field names against your tenant's API docs before relying on write tools in production.**

## Installation

A Hermes plugin is a directory containing `plugin.yaml` plus `__init__.py`. Install this repo as a plugin directory:

```bash
git clone https://github.com/Lauritz30/hermes-zephyr-testmanager.git ~/Projects/hermes-zephyr-testmanager
ln -s ~/Projects/hermes-zephyr-testmanager ~/.hermes/plugins/hermes-zephyr-testmanager
hermes plugins enable hermes-zephyr-testmanager
hermes plugins list          # expect: hermes-zephyr-testmanager — 10 tools, 1 hook
```

`hermes plugins install <git-url>` also works for a published copy. Validate a checkout without installing it:

```bash
hermes plugins doctor ~/Projects/hermes-zephyr-testmanager --ci
```

## Quick start

1. Generate a Zephyr Scale API access token (Jira profile → Zephyr Scale API Access Tokens).
2. Put it in your Hermes `.env` (never in a config file, never in `config.yaml`):

   ```bash
   hermes config set ZEPHYR_TOKEN_ACME "your-zephyr-scale-api-token"
   ```

3. Create the site config at `$HERMES_HOME/hermes-zephyr-testmanager.json` (default `~/.hermes/hermes-zephyr-testmanager.json`) — copy `hermes-zephyr-testmanager.example.json`.
4. Verify with `/zephyr-doctor` in a session, or `hermes zephyr doctor` in a terminal.

### Example configuration

```json
{
  "defaultSite": "acme",
  "safetyLevel": "confirm",
  "sites": [
    {
      "name": "acme",
      "baseUrl": "https://api.zephyrscale.smartbear.com/v2"
    }
  ]
}
```

The token is **not** in this file. The site `acme` reads `ZEPHYR_TOKEN_ACME`; any site can name a different variable with `"tokenEnv": "MY_VARIABLE"`. The derived name is `ZEPHYR_TOKEN_<SITE>` with non-alphanumerics replaced by `_` and upper-cased (`client-xyz` → `ZEPHYR_TOKEN_CLIENT_XYZ`).

`baseUrl` defaults to `https://api.zephyrscale.smartbear.com/v2` and only needs to be set to override it (e.g. a different regional endpoint).

### Multi-site

```json
{
  "defaultSite": "acme",
  "sites": [
    { "name": "acme", "baseUrl": "https://api.zephyrscale.smartbear.com/v2" },
    { "name": "client-xyz", "baseUrl": "https://api.zephyrscale.smartbear.com/v2", "safetyLevel": "readonly" }
  ]
}
```

Each site needs its own `.env` variable: `ZEPHYR_TOKEN_ACME`, `ZEPHYR_TOKEN_CLIENT_XYZ`.

### Mock mode

Set `"mock": true` in the config to let `zephyr_doctor` validate the config shape without a token or a live request.

## Tools

### Read

| Tool | Description |
| --- | --- |
| `zephyr_doctor` | Verify configuration, token availability, and connection health |
| `zephyr_list_test_cases` | List test cases for a project (single page or `allPages`) |
| `zephyr_get_test_case` | Fetch a single test case, including its test script/steps |
| `zephyr_list_test_cycles` | List test cycles for a project |
| `zephyr_get_test_cycle` | Fetch a single test cycle by id or key |
| `zephyr_list_test_executions` | List test executions, optionally scoped to a test cycle |
| `zephyr_get_test_execution` | Fetch a single test execution by id or key |

### Write (safety-gated)

| Tool | Description |
| --- | --- |
| `zephyr_create_test_case` | Create a test case |
| `zephyr_add_test_cases_to_cycle` | Add one or more test cases to a test cycle (creates a test execution per test case) |
| `zephyr_update_test_execution_status` | Record a result (e.g. Pass/Fail) on a test execution, with an optional comment |

Every tool returns a JSON string: `{"ok": true, "summary": "...", "data": {...}}` on success, `{"ok": false, "error": "..."}` on failure. Handlers never raise — a failing call is always a result the model can read.

Every write tool also accepts `dryRun: true`, which returns the normalized request without prompting or sending it.

## Commands

| Surface | Command | Description |
| --- | --- | --- |
| In-session | `/zephyr-status` | Migration-free status: resolved site, token variable, safety level, config path |
| In-session | `/zephyr-doctor` | Configuration, token, and connectivity check |
| Terminal | `hermes zephyr status [site]` | Same status output |
| Terminal | `hermes zephyr doctor [site]` | Same doctor output |
| Terminal | `hermes zephyr config-path` | Print the resolved config file path |

The pi extension rendered a TUI footer label and a connection card. Hermes has no plugin footer API, so that information moved to the status surfaces above.

## Skills (ported prompt templates)

| Skill | Description |
| --- | --- |
| `hermes-zephyr-testmanager:zephyr-cycle-status` | Summarize a test cycle's execution progress |
| `hermes-zephyr-testmanager:zephyr-record-result` | Record a UAT test result against a test execution |

Load them with `skill_view("hermes-zephyr-testmanager:zephyr-cycle-status")`.

## Safety model

| Level | Behavior |
| --- | --- |
| `open` | Write tools run without approval |
| `confirm` (default) | The `pre_tool_call` hook escalates every write to Hermes's human-approval gate |
| `readonly` | All write tools blocked — by the hook *and* inside the handler |

Resolution order: per-site `safetyLevel` override > global config `safetyLevel` > default `"confirm"`.

In `confirm` mode the approval gate prompts in interactive sessions, honors `approvals.cron_mode` for cron runs, and **fails closed** when nobody can answer (a background/headless run without an approval bridge) — the same "blocked, no UI to prompt" behavior the pi extension had. `readonly` blocks mutations even when they are otherwise allowed, and `dryRun` previews never mutate, so they need no approval.

The pi extension also had no `headlessApprovals` rules; this port keeps that surface out rather than inventing one. Use a site-level `"safetyLevel": "open"` for unattended automation, or run it under `approvals.cron_mode`.

## Configuration reference

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `sites` | array | — | List of `{ name, baseUrl?, tokenEnv?, safetyLevel? }` |
| `defaultSite` | string | first site | Site used when a tool call omits `site` |
| `safetyLevel` | string | `"confirm"` | Global default: `"open"`, `"confirm"`, or `"readonly"` |
| `mock` | boolean | `false` | Skip live requests in `zephyr_doctor` for offline testing |

The plugin's own setting `plugins.entries.hermes-zephyr-testmanager.settings.config_path` overrides the config file location.

## Network egress and corporate proxies

Requests go directly to `api.zephyrscale.smartbear.com` over HTTPS and need no extra config when outbound internet access is available. Behind an egress proxy, set `HTTPS_PROXY` (or `HTTP_PROXY`) in the environment — the client picks it up with no extra config. `NO_PROXY` is not handled by the plugin's transport.

To separate a proxy/firewall problem from a config problem, test raw connectivity first:

```bash
curl -v -H "Authorization: Bearer $ZEPHYR_TOKEN_ACME" \
  https://api.zephyrscale.smartbear.com/v2/testcases?maxResults=1
```

## Architecture

```
hermes-zephyr-testmanager/
├── plugin.yaml                  # Hermes manifest: tools, hook, config schema
├── __init__.py                  # register(ctx): tools, hook, slash commands, CLI, skills
├── schemas.py                   # tool schemas (what the LLM reads)
├── zephyr/
│   ├── config.py                # site config load/validate + safety-level resolution
│   ├── auth.py                  # Bearer auth header + token env-var resolution
│   ├── client.py                # urllib client with an injectable transport, 429 retry, error mapping
│   ├── service.py               # test case/cycle/execution calls, pagination, dry-run previews
│   ├── proxy.py                 # HTTPS_PROXY/HTTP_PROXY resolution
│   ├── safety.py                # pure mutation decision (proceed / escalate / block)
│   ├── mutations.py             # mutation descriptors shared by handlers and the hook
│   ├── hooks.py                 # pre_tool_call -> block/approve directive
│   ├── status.py                # status label + report text
│   ├── settings.py              # registration-time plugin settings
│   ├── paths.py                 # profile-aware Hermes home resolution
│   └── tools/                   # doctor, read, write handlers
├── skills/                      # ported prompt templates
└── tests/                       # stdlib unittest suite (no network)
```

There is deliberately no top-level `tools.py`: a module with that name in the plugin directory
would shadow Hermes's own `tools` package for any process started with this directory on
`sys.path`. The handler surface lives at `zephyr/tools/` (`HANDLERS` maps every tool name to its
callable).

## Development

```bash
python3 -m unittest discover -v          # unit tests (no live network)
hermes plugins doctor . --ci             # load the plugin through the real Hermes loader
~/.hermes/hermes-agent/venv/bin/python scripts/verify_with_hermes.py   # end-to-end against Hermes
```

Tests require nothing beyond the standard library. `tests/plugin.py` imports the plugin directory the same way Hermes's loader does (`hermes_plugins.hermes_zephyr_testmanager`), so registration tests exercise the real shape.

`scripts/verify_with_hermes.py` goes further: it installs the plugin into a throwaway `HERMES_HOME` (seeded from the example config), loads it through Hermes's real discovery, dispatches tool calls through `model_tools.handle_function_call` (including the `pre_tool_call` approval hook, at `readonly`, `confirm`, and `open`), and runs `hermes zephyr status`. It needs a Hermes install and fakes the HTTP transport, so no Zephyr site is touched.

## Requirements

- Hermes Agent with plugin support (tools + `pre_tool_call` hooks)
- Python 3.10+ to run under Hermes; the code and tests also run on 3.9
- A Zephyr Scale Cloud site and an API access token

## License

MIT — see [LICENSE](LICENSE).
