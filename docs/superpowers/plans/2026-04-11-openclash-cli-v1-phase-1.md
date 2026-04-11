# OpenClash CLI v1 Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first shippable `opclash_cli` that can save remote connection settings locally, manage subscriptions and active configs over LuCI JSON-RPC, manage runtime groups and nodes over the controller API, and provide basic service and doctor commands with stable JSON output.

**Architecture:** The CLI uses two remote backends: a controller adapter for runtime state and node switching, and a LuCI JSON-RPC adapter for OpenClash management tasks such as subscription reads, config switching, service control, and log reads. The command layer stays thin and returns one JSON envelope shape for both success and failure so the companion skill can drive it deterministically.

**Tech Stack:** Python 3.11, `argparse`, `requests`, `tomli-w`, `pytest`

---

## File Structure

- Create: `pyproject.toml`
  - Package metadata, dependencies, pytest config, console entry point
- Create: `.gitignore`
  - Ignore Python caches, virtualenvs, local config overrides
- Create: `opclash_cli/__init__.py`
  - Package marker and version string
- Create: `opclash_cli/output.py`
  - Shared JSON success/error envelope helpers
- Create: `opclash_cli/errors.py`
  - Typed CLI exceptions with machine-readable error codes
- Create: `opclash_cli/local_config.py`
  - Read/write local config file and return masked summaries
- Create: `opclash_cli/adapters/controller.py`
  - Controller API login/header handling, runtime reads, node switch
- Create: `opclash_cli/adapters/luci_rpc.py`
  - LuCI JSON-RPC login and `auth` / `uci` / `sys` / `fs` calls
- Create: `opclash_cli/commands/init.py`
  - `init`, `init show`, `init check`
- Create: `opclash_cli/commands/nodes.py`
  - `nodes groups`, `nodes group`, `nodes switch`, `nodes providers`
- Create: `opclash_cli/commands/subscription.py`
  - `subscription list`, `add`, `current`, `configs`, `switch`
- Create: `opclash_cli/commands/service.py`
  - `service status`, `reload`, `restart`, `logs`
- Create: `opclash_cli/commands/doctor.py`
  - `doctor network`, `runtime`, `config`
- Create: `opclash_cli/main.py`
  - CLI parser and subcommand dispatch
- Create: `skills/opclash_cli/SKILL.md`
  - AI usage order and command guidance
- Create: `tests/test_bootstrap_cli.py`
  - Base CLI and JSON envelope tests
- Create: `tests/test_init_commands.py`
  - Local config and `init` command tests
- Create: `tests/test_nodes_read_commands.py`
  - Controller-backed read command tests
- Create: `tests/test_nodes_switch_command.py`
  - Group switch tests
- Create: `tests/test_subscription_service_read_commands.py`
  - LuCI-backed read command tests
- Create: `tests/test_subscription_service_mutations.py`
  - Subscription add/switch and service action tests
- Create: `tests/test_doctor_and_skill.py`
  - Doctor command and skill doc tests

## Phase Boundary

This plan intentionally implements the stable Phase 1 slice:

- Included: `init`, `subscription list/add/current/configs/switch`, `nodes groups/group/providers/switch`, `service status/reload/restart/logs`, `doctor network/runtime/config`
- Deferred to Phase 2: `subscription update`

The deferred item is omitted on purpose because the remote “update this subscription now” entrypoint is more version-sensitive than the rest of the CRUD and switch flow. Phase 1 should ship without guessing that backend.

### Task 1: Bootstrap Package And Base JSON Contract

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `opclash_cli/__init__.py`
- Create: `opclash_cli/errors.py`
- Create: `opclash_cli/output.py`
- Create: `opclash_cli/local_config.py`
- Create: `opclash_cli/main.py`
- Test: `tests/test_bootstrap_cli.py`

- [ ] **Step 1: Write the failing test for the base error envelope**

```python
import json

from opclash_cli.main import main


def test_init_show_returns_missing_config_error(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))

    exit_code = main(["init", "show"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["command"] == "init show"
    assert payload["error"]["code"] == "LOCAL_CONFIG_MISSING"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_bootstrap_cli.py::test_init_show_returns_missing_config_error -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'opclash_cli'`

- [ ] **Step 3: Write the minimal bootstrap implementation**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "opclash_cli"
version = "0.1.0"
description = "Remote OpenClash management CLI"
requires-python = ">=3.11"
dependencies = [
  "requests>=2.32.0",
  "tomli-w>=1.0.0",
]

[project.scripts]
opclash_cli = "opclash_cli.main:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

```gitignore
# .gitignore
__pycache__/
.pytest_cache/
.venv/
*.pyc
```

```python
# opclash_cli/__init__.py
__all__ = ["__version__"]

__version__ = "0.1.0"
```

```python
# opclash_cli/errors.py
class CliError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
```

```python
# opclash_cli/output.py
import json


def emit(payload: dict, pretty: bool = False) -> None:
    if pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(json.dumps(payload, ensure_ascii=False))


def ok(command: str, data: dict, warnings: list[str] | None = None, audit: dict | None = None) -> dict:
    return {
        "ok": True,
        "command": command,
        "timestamp": "1970-01-01T00:00:00Z",
        "data": data,
        "warnings": warnings or [],
        "audit": audit,
        "error": None,
    }


def fail(command: str, code: str, message: str, details: dict | None = None) -> dict:
    return {
        "ok": False,
        "command": command,
        "timestamp": "1970-01-01T00:00:00Z",
        "data": {},
        "warnings": [],
        "audit": None,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }
```

```python
# opclash_cli/local_config.py
import os
from pathlib import Path


def config_path() -> Path:
    override = os.environ.get("OPENCLASH_CLI_CONFIG")
    if override:
        return Path(override)
    return Path.home() / ".config" / "opclash_cli" / "config.toml"


def config_exists() -> bool:
    return config_path().exists()
```

```python
# opclash_cli/main.py
import argparse

from opclash_cli.local_config import config_exists
from opclash_cli.output import emit, fail


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opclash_cli")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init")
    init_subparsers = init_parser.add_subparsers(dest="init_command")
    init_subparsers.add_parser("show")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init" and args.init_command == "show":
        if not config_exists():
            emit(fail("init show", "LOCAL_CONFIG_MISSING", "Local config file was not found"))
            return 1

    parser.print_help()
    return 0
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_bootstrap_cli.py::test_init_show_returns_missing_config_error -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
if [ ! -d .git ]; then git init; fi
git add pyproject.toml .gitignore opclash_cli/__init__.py opclash_cli/errors.py opclash_cli/output.py opclash_cli/local_config.py opclash_cli/main.py tests/test_bootstrap_cli.py
git commit -m "chore: scaffold openclash cli package"
```

### Task 2: Implement Local Config And Init Commands

**Files:**
- Modify: `opclash_cli/local_config.py`
- Create: `opclash_cli/commands/init.py`
- Modify: `opclash_cli/main.py`
- Test: `tests/test_init_commands.py`

- [ ] **Step 1: Write the failing tests for config persistence, `init` write, and masked output**

```python
import tomllib

from opclash_cli.main import main
from opclash_cli.commands.init import mask_secret
from opclash_cli.local_config import AppConfig, ControllerConfig, LuciConfig, load_config, save_config


def test_save_and_load_config_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))
    config = AppConfig(
        controller=ControllerConfig(url="http://router:9090", secret="controller-secret"),
        luci=LuciConfig(url="http://router/cgi-bin/luci/rpc", username="root", password="rpc-password"),
    )

    save_config(config)
    loaded = load_config()

    assert loaded.controller.url == "http://router:9090"
    assert loaded.controller.secret == "controller-secret"
    assert loaded.luci.username == "root"


def test_mask_secret_keeps_suffix():
    assert mask_secret("controller-secret") == "***************cret"


def test_init_command_writes_config_file(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))

    exit_code = main(
        [
            "init",
            "--controller-url",
            "http://router:9090",
            "--controller-secret",
            "controller-secret",
            "--luci-url",
            "http://router/cgi-bin/luci/rpc",
            "--luci-username",
            "root",
            "--luci-password",
            "rpc-password",
        ]
    )

    written = tomllib.loads((tmp_path / "config.toml").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert written["controller"]["url"] == "http://router:9090"
    assert written["luci"]["username"] == "root"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_init_commands.py -v`
Expected: FAIL with `ImportError` for `AppConfig`, `save_config`, or missing `init` arguments

- [ ] **Step 3: Write the minimal implementation for config persistence and `init show`**

```python
# opclash_cli/local_config.py
from dataclasses import dataclass
import os
from pathlib import Path
import tomllib

import tomli_w


@dataclass
class ControllerConfig:
    url: str
    secret: str


@dataclass
class LuciConfig:
    url: str
    username: str
    password: str


@dataclass
class AppConfig:
    controller: ControllerConfig
    luci: LuciConfig


def config_path() -> Path:
    override = os.environ.get("OPENCLASH_CLI_CONFIG")
    if override:
        return Path(override)
    return Path.home() / ".config" / "opclash_cli" / "config.toml"


def save_config(config: AppConfig) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "controller": {"url": config.controller.url, "secret": config.controller.secret},
        "luci": {"url": config.luci.url, "username": config.luci.username, "password": config.luci.password},
    }
    path.write_text(tomli_w.dumps(payload), encoding="utf-8")
    return path


def load_config() -> AppConfig:
    data = tomllib.loads(config_path().read_text(encoding="utf-8"))
    return AppConfig(
        controller=ControllerConfig(**data["controller"]),
        luci=LuciConfig(**data["luci"]),
    )


def config_exists() -> bool:
    return config_path().exists()
```

```python
# opclash_cli/commands/init.py
from opclash_cli.local_config import AppConfig, ControllerConfig, LuciConfig, load_config, save_config


def mask_secret(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]


def show_config() -> dict:
    config = load_config()
    return {
        "controller": {
            "url": config.controller.url,
            "secret": mask_secret(config.controller.secret),
        },
        "luci": {
            "url": config.luci.url,
            "username": config.luci.username,
            "password": mask_secret(config.luci.password),
        },
    }


def write_config(
    controller_url: str,
    controller_secret: str,
    luci_url: str,
    luci_username: str,
    luci_password: str,
) -> dict:
    config = AppConfig(
        controller=ControllerConfig(url=controller_url, secret=controller_secret),
        luci=LuciConfig(url=luci_url, username=luci_username, password=luci_password),
    )
    path = save_config(config)
    return {"config_path": str(path)}
```

```python
# opclash_cli/main.py
from opclash_cli.commands.init import show_config, write_config
from opclash_cli.output import emit, fail, ok


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opclash_cli")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--controller-url")
    init_parser.add_argument("--controller-secret")
    init_parser.add_argument("--luci-url")
    init_parser.add_argument("--luci-username")
    init_parser.add_argument("--luci-password")
    init_subparsers = init_parser.add_subparsers(dest="init_command")
    init_subparsers.add_parser("show")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init" and args.init_command is None:
        emit(
            ok(
                "init",
                write_config(
                    args.controller_url,
                    args.controller_secret,
                    args.luci_url,
                    args.luci_username,
                    args.luci_password,
                ),
            )
        )
        return 0

    if args.command == "init" and args.init_command == "show":
        if not config_exists():
            emit(fail("init show", "LOCAL_CONFIG_MISSING", "Local config file was not found"))
            return 1
        emit(ok("init show", show_config()))
        return 0

    parser.print_help()
    return 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_bootstrap_cli.py tests/test_init_commands.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add opclash_cli/local_config.py opclash_cli/commands/init.py opclash_cli/main.py tests/test_init_commands.py
git commit -m "feat: add local config persistence and init commands"
```

### Task 3: Add Controller Reads For Nodes And Providers

**Files:**
- Create: `opclash_cli/adapters/controller.py`
- Create: `opclash_cli/commands/nodes.py`
- Modify: `opclash_cli/main.py`
- Test: `tests/test_nodes_read_commands.py`

- [ ] **Step 1: Write the failing tests for `nodes groups` and `nodes providers`**

```python
from opclash_cli.commands.nodes import summarize_groups, summarize_providers


def test_summarize_groups_returns_selected_proxy_names():
    payload = {
        "proxies": {
            "Apple": {"type": "Selector", "now": "DIRECT", "all": ["DIRECT", "HK-01"]},
            "Final": {"type": "Selector", "now": "Proxies", "all": ["Proxies", "DIRECT"]},
            "HK-01": {"type": "VMess"},
        }
    }

    result = summarize_groups(payload)

    assert result == [
        {"name": "Apple", "selected": "DIRECT", "choices": ["DIRECT", "HK-01"]},
        {"name": "Final", "selected": "Proxies", "choices": ["Proxies", "DIRECT"]},
    ]


def test_summarize_providers_returns_provider_counts():
    payload = {
        "providers": {
            "airport-a": {"proxies": [{"name": "HK-01"}, {"name": "JP-01"}], "updatedAt": "2026-04-11T00:00:00Z"}
        }
    }

    result = summarize_providers(payload)

    assert result == [
        {"name": "airport-a", "count": 2, "updated_at": "2026-04-11T00:00:00Z"}
    ]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_nodes_read_commands.py -v`
Expected: FAIL with `ImportError` for `opclash_cli.commands.nodes`

- [ ] **Step 3: Write the minimal controller adapter and read commands**

```python
# opclash_cli/adapters/controller.py
import requests

from opclash_cli.local_config import load_config


class ControllerClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._config = load_config().controller
        self._session = session or requests.Session()

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._config.secret}"}

    def get_configs(self) -> dict:
        response = self._session.get(f"{self._config.url}/configs", headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_proxies(self) -> dict:
        response = self._session.get(f"{self._config.url}/proxies", headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_providers(self) -> dict:
        response = self._session.get(f"{self._config.url}/providers/proxies", headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()
```

```python
# opclash_cli/commands/nodes.py
from opclash_cli.adapters.controller import ControllerClient


def summarize_groups(payload: dict) -> list[dict]:
    result = []
    for name, item in payload.get("proxies", {}).items():
        if "all" not in item or "now" not in item:
            continue
        result.append({"name": name, "selected": item["now"], "choices": item["all"]})
    return result


def summarize_providers(payload: dict) -> list[dict]:
    result = []
    for name, item in payload.get("providers", {}).items():
        result.append(
            {
                "name": name,
                "count": len(item.get("proxies", [])),
                "updated_at": item.get("updatedAt"),
            }
        )
    return result


def groups() -> dict:
    return {"groups": summarize_groups(ControllerClient().get_proxies())}


def providers() -> dict:
    return {"providers": summarize_providers(ControllerClient().get_providers())}
```

```python
# opclash_cli/main.py
from opclash_cli.commands.nodes import groups as nodes_groups, providers as nodes_providers


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opclash_cli")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init")
    init_subparsers = init_parser.add_subparsers(dest="init_command")
    init_subparsers.add_parser("show")

    nodes_parser = subparsers.add_parser("nodes")
    nodes_subparsers = nodes_parser.add_subparsers(dest="nodes_command")
    nodes_subparsers.add_parser("groups")
    nodes_subparsers.add_parser("providers")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "nodes" and args.nodes_command == "groups":
        emit(ok("nodes groups", nodes_groups()))
        return 0

    if args.command == "nodes" and args.nodes_command == "providers":
        emit(ok("nodes providers", nodes_providers()))
        return 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_nodes_read_commands.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add opclash_cli/adapters/controller.py opclash_cli/commands/nodes.py opclash_cli/main.py tests/test_nodes_read_commands.py
git commit -m "feat: add controller-backed node read commands"
```

### Task 4: Implement Group Inspection And Node Switching

**Files:**
- Modify: `opclash_cli/adapters/controller.py`
- Modify: `opclash_cli/commands/nodes.py`
- Modify: `opclash_cli/main.py`
- Test: `tests/test_nodes_switch_command.py`

- [ ] **Step 1: Write the failing tests for `nodes group` and `nodes switch`**

```python
from opclash_cli.commands.nodes import build_group_detail, switch_group


class FakeControllerClient:
    def __init__(self) -> None:
        self.payload = {
            "proxies": {
                "Apple": {"type": "Selector", "now": "HK-01", "all": ["DIRECT", "HK-01"]},
            }
        }
        self.last_switch = None

    def get_proxies(self) -> dict:
        return self.payload

    def switch_proxy(self, group: str, target: str) -> dict:
        self.last_switch = (group, target)
        self.payload["proxies"]["Apple"]["now"] = target
        return self.payload["proxies"]["Apple"]


def test_build_group_detail_returns_choices():
    client = FakeControllerClient()

    result = build_group_detail(client.get_proxies(), "Apple")

    assert result == {
        "name": "Apple",
        "selected": "HK-01",
        "choices": ["DIRECT", "HK-01"],
    }


def test_switch_group_returns_before_after():
    client = FakeControllerClient()

    result = switch_group(client, "Apple", "DIRECT")

    assert result["before"]["selected"] == "HK-01"
    assert result["after"]["selected"] == "DIRECT"
    assert client.last_switch == ("Apple", "DIRECT")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_nodes_switch_command.py -v`
Expected: FAIL with `ImportError` or missing `switch_group`

- [ ] **Step 3: Write the minimal implementation for group detail and switching**

```python
# opclash_cli/adapters/controller.py
    def switch_proxy(self, group: str, target: str) -> dict:
        response = self._session.put(
            f"{self._config.url}/proxies/{group}",
            headers=self.headers,
            json={"name": target},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
```

```python
# opclash_cli/commands/nodes.py
from opclash_cli.errors import CliError


def build_group_detail(payload: dict, group_name: str) -> dict:
    item = payload.get("proxies", {}).get(group_name)
    if not item or "all" not in item or "now" not in item:
        raise CliError("GROUP_NOT_FOUND", f"Group '{group_name}' was not found")
    return {"name": group_name, "selected": item["now"], "choices": item["all"]}


def group(group_name: str) -> dict:
    payload = ControllerClient().get_proxies()
    return {"group": build_group_detail(payload, group_name)}


def switch_group(client: ControllerClient, group_name: str, target: str) -> dict:
    before = build_group_detail(client.get_proxies(), group_name)
    if target not in before["choices"]:
        raise CliError("NODE_NOT_FOUND", f"Node '{target}' is not available in group '{group_name}'")
    client.switch_proxy(group_name, target)
    after = build_group_detail(client.get_proxies(), group_name)
    return {"before": before, "after": after}


def switch(group_name: str, target: str, reason: str) -> dict:
    client = ControllerClient()
    result = switch_group(client, group_name, target)
    result["audit"] = {"action": "nodes.switch", "reason": reason}
    return result
```

```python
# opclash_cli/main.py
    group_parser = nodes_subparsers.add_parser("group")
    group_parser.add_argument("--name", required=True)
    switch_parser = nodes_subparsers.add_parser("switch")
    switch_parser.add_argument("--group", required=True)
    switch_parser.add_argument("--target", required=True)
    switch_parser.add_argument("--reason", required=True)

    if args.command == "nodes" and args.nodes_command == "group":
        emit(ok("nodes group", group(args.name)))
        return 0

    if args.command == "nodes" and args.nodes_command == "switch":
        result = switch(args.group, args.target, args.reason)
        emit(ok("nodes switch", {"before": result["before"], "after": result["after"]}, audit=result["audit"]))
        return 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_nodes_read_commands.py tests/test_nodes_switch_command.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add opclash_cli/adapters/controller.py opclash_cli/commands/nodes.py opclash_cli/main.py tests/test_nodes_switch_command.py
git commit -m "feat: add group inspection and node switching"
```

### Task 5: Add LuCI RPC Adapter And Read-Only Subscription And Service Commands

**Files:**
- Create: `opclash_cli/adapters/luci_rpc.py`
- Create: `opclash_cli/commands/subscription.py`
- Create: `opclash_cli/commands/service.py`
- Modify: `opclash_cli/main.py`
- Test: `tests/test_subscription_service_read_commands.py`

- [ ] **Step 1: Write the failing tests for subscription reads and service status**

```python
from opclash_cli.commands.service import summarize_status
from opclash_cli.commands.subscription import summarize_subscriptions


def test_summarize_subscriptions_filters_config_subscribe_sections():
    payload = {
        "cfg1": {".type": "config_subscribe", "name": "west2", "address": "https://example/sub", "enabled": "1"},
        "cfg2": {".type": "other", "name": "ignore-me"},
    }

    result = summarize_subscriptions(payload)

    assert result == [
        {"section": "cfg1", "name": "west2", "address": "https://example/sub", "enabled": True}
    ]


def test_summarize_status_marks_running_when_status_output_contains_running():
    result = summarize_status("openclash is running")
    assert result == {"running": True, "raw": "openclash is running"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_subscription_service_read_commands.py -v`
Expected: FAIL with `ImportError` for `subscription` or `service` modules

- [ ] **Step 3: Write the minimal LuCI RPC adapter and read commands**

```python
# opclash_cli/adapters/luci_rpc.py
import requests

from opclash_cli.local_config import load_config


class LuciRpcClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._config = load_config().luci
        self._session = session or requests.Session()
        self._token: str | None = None

    def login(self) -> str:
        response = self._session.post(
            f"{self._config.url}/auth",
            json={"id": 1, "method": "login", "params": [self._config.username, self._config.password]},
            timeout=10,
        )
        response.raise_for_status()
        self._token = response.json()["result"]
        return self._token

    def call(self, library: str, method: str, params: list[object]) -> object:
        token = self._token or self.login()
        response = self._session.post(
            f"{self._config.url}/{library}?auth={token}",
            json={"id": 1, "method": method, "params": params},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["result"]

    def get_openclash_uci(self) -> dict:
        return self.call("uci", "get_all", ["openclash"])

    def service_exec(self, command: str) -> str:
        return self.call("sys", "exec", [command])
```

```python
# opclash_cli/commands/subscription.py
from opclash_cli.adapters.luci_rpc import LuciRpcClient


def summarize_subscriptions(payload: dict) -> list[dict]:
    result = []
    for section, item in payload.items():
        if item.get(".type") != "config_subscribe":
            continue
        result.append(
            {
                "section": section,
                "name": item.get("name", ""),
                "address": item.get("address", ""),
                "enabled": str(item.get("enabled", "0")) == "1",
            }
        )
    return result


def list_subscriptions() -> dict:
    return {"subscriptions": summarize_subscriptions(LuciRpcClient().get_openclash_uci())}


def current_config() -> dict:
    payload = LuciRpcClient().get_openclash_uci()
    return {"config_path": payload["config"]["config_path"]}
```

```python
# opclash_cli/commands/service.py
from opclash_cli.adapters.luci_rpc import LuciRpcClient


def summarize_status(raw: str) -> dict:
    return {"running": "running" in raw.lower(), "raw": raw.strip()}


def status() -> dict:
    raw = LuciRpcClient().service_exec("/etc/init.d/openclash status")
    return {"service": summarize_status(raw)}
```

```python
# opclash_cli/main.py
from opclash_cli.commands.service import status as service_status
from opclash_cli.commands.subscription import current_config, list_subscriptions

    subscription_parser = subparsers.add_parser("subscription")
    subscription_subparsers = subscription_parser.add_subparsers(dest="subscription_command")
    subscription_subparsers.add_parser("list")
    subscription_subparsers.add_parser("current")

    service_parser = subparsers.add_parser("service")
    service_subparsers = service_parser.add_subparsers(dest="service_command")
    service_subparsers.add_parser("status")

    if args.command == "subscription" and args.subscription_command == "list":
        emit(ok("subscription list", list_subscriptions()))
        return 0

    if args.command == "subscription" and args.subscription_command == "current":
        emit(ok("subscription current", current_config()))
        return 0

    if args.command == "service" and args.service_command == "status":
        emit(ok("service status", service_status()))
        return 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_subscription_service_read_commands.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add opclash_cli/adapters/luci_rpc.py opclash_cli/commands/subscription.py opclash_cli/commands/service.py opclash_cli/main.py tests/test_subscription_service_read_commands.py
git commit -m "feat: add luci-backed subscription and service reads"
```

### Task 6: Add Subscription Mutation, Config Switching, Service Actions, And Logs

**Files:**
- Modify: `opclash_cli/adapters/luci_rpc.py`
- Modify: `opclash_cli/commands/subscription.py`
- Modify: `opclash_cli/commands/service.py`
- Modify: `opclash_cli/main.py`
- Test: `tests/test_subscription_service_mutations.py`

- [ ] **Step 1: Write the failing tests for add, switch, reload, restart, and logs**

```python
from opclash_cli.commands.subscription import add_subscription_payload, switch_config_payload


def test_add_subscription_payload_contains_required_fields():
    payload = add_subscription_payload("west2", "https://example/sub")

    assert payload["name"] == "west2"
    assert payload["address"] == "https://example/sub"
    assert payload["enabled"] == "1"


def test_switch_config_payload_sets_target_path():
    payload = switch_config_payload("/etc/openclash/config/west2.yaml")

    assert payload == {"config_path": "/etc/openclash/config/west2.yaml"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_subscription_service_mutations.py -v`
Expected: FAIL with missing `add_subscription_payload` or `switch_config_payload`

- [ ] **Step 3: Write the minimal implementation for subscription add/switch and service actions**

```python
# opclash_cli/adapters/luci_rpc.py
import base64

    def add_uci_section(self, config_name: str, section_type: str) -> str:
        return self.call("uci", "add", [config_name, section_type])

    def set_uci(self, config_name: str, section: str, option: str, value: str) -> bool:
        return self.call("uci", "set", [config_name, section, option, value])

    def commit_uci(self, config_name: str) -> bool:
        return self.call("uci", "commit", [config_name])

    def read_file(self, path: str) -> str:
        encoded = self.call("fs", "readfile", [path])
        return base64.b64decode(encoded).decode("utf-8", errors="replace")
```

```python
# opclash_cli/commands/subscription.py
from opclash_cli.errors import CliError


def add_subscription_payload(name: str, url: str) -> dict:
    return {"name": name, "address": url, "enabled": "1"}


def switch_config_payload(path: str) -> dict:
    return {"config_path": path}


def add_subscription(name: str, url: str, reason: str) -> dict:
    client = LuciRpcClient()
    section = client.add_uci_section("openclash", "config_subscribe")
    payload = add_subscription_payload(name, url)
    for option, value in payload.items():
        client.set_uci("openclash", section, option, value)
    client.commit_uci("openclash")
    return {
        "subscription": {"section": section, **payload},
        "audit": {"action": "subscription.add", "reason": reason},
    }


def switch_config(path: str, reason: str) -> dict:
    client = LuciRpcClient()
    payload = client.get_openclash_uci()
    current = payload["config"]["config_path"]
    if path == current:
        raise CliError("VERIFY_FAILED", "Target config is already active")
    client.set_uci("openclash", "config", "config_path", switch_config_payload(path)["config_path"])
    client.commit_uci("openclash")
    client.service_exec("/etc/init.d/openclash reload")
    refreshed = client.get_openclash_uci()["config"]["config_path"]
    return {
        "before": {"config_path": current},
        "after": {"config_path": refreshed},
        "audit": {"action": "subscription.switch", "reason": reason},
    }
```

```python
# opclash_cli/commands/service.py
def reload(reason: str) -> dict:
    raw = LuciRpcClient().service_exec("/etc/init.d/openclash reload")
    return {"result": raw.strip(), "audit": {"action": "service.reload", "reason": reason}}


def restart(reason: str) -> dict:
    raw = LuciRpcClient().service_exec("/etc/init.d/openclash restart")
    return {"result": raw.strip(), "audit": {"action": "service.restart", "reason": reason}}


def logs() -> dict:
    raw = LuciRpcClient().read_file("/tmp/openclash.log")
    return {"tail": raw.splitlines()[-50:]}
```

```python
# opclash_cli/main.py
from opclash_cli.commands.subscription import add_subscription, config_files, switch_config

    add_parser = subscription_subparsers.add_parser("add")
    add_parser.add_argument("--name", required=True)
    add_parser.add_argument("--url", required=True)
    add_parser.add_argument("--reason", required=True)

    configs_parser = subscription_subparsers.add_parser("configs")
    configs_parser.add_argument("--directory", default="/etc/openclash/config")

    switch_parser = subscription_subparsers.add_parser("switch")
    switch_parser.add_argument("--config", required=True)
    switch_parser.add_argument("--reason", required=True)

    service_reload = service_subparsers.add_parser("reload")
    service_reload.add_argument("--reason", required=True)
    service_restart = service_subparsers.add_parser("restart")
    service_restart.add_argument("--reason", required=True)
    service_subparsers.add_parser("logs")

    if args.command == "subscription" and args.subscription_command == "add":
        result = add_subscription(args.name, args.url, args.reason)
        emit(ok("subscription add", {"subscription": result["subscription"]}, audit=result["audit"]))
        return 0

    if args.command == "subscription" and args.subscription_command == "configs":
        emit(ok("subscription configs", config_files(args.directory)))
        return 0

    if args.command == "subscription" and args.subscription_command == "switch":
        result = switch_config(args.config, args.reason)
        emit(ok("subscription switch", {"before": result["before"], "after": result["after"]}, audit=result["audit"]))
        return 0

    if args.command == "service" and args.service_command == "reload":
        result = reload(args.reason)
        emit(ok("service reload", {"result": result["result"]}, audit=result["audit"]))
        return 0

    if args.command == "service" and args.service_command == "restart":
        result = restart(args.reason)
        emit(ok("service restart", {"result": result["result"]}, audit=result["audit"]))
        return 0

    if args.command == "service" and args.service_command == "logs":
        emit(ok("service logs", logs()))
        return 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_subscription_service_read_commands.py tests/test_subscription_service_mutations.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add opclash_cli/adapters/luci_rpc.py opclash_cli/commands/subscription.py opclash_cli/commands/service.py opclash_cli/main.py tests/test_subscription_service_mutations.py
git commit -m "feat: add subscription mutations and service actions"
```

### Task 7: Add Config Listing, Init Check, Doctor Commands, And The AI Skill

**Files:**
- Modify: `opclash_cli/commands/init.py`
- Modify: `opclash_cli/commands/subscription.py`
- Create: `opclash_cli/commands/doctor.py`
- Modify: `opclash_cli/main.py`
- Create: `skills/opclash_cli/SKILL.md`
- Test: `tests/test_doctor_and_skill.py`

- [ ] **Step 1: Write the failing tests for `init check`, `doctor`, and config listing**

```python
from opclash_cli.commands.doctor import build_network_report
from opclash_cli.commands.subscription import summarize_config_files


def test_summarize_config_files_returns_name_size_and_mtime():
    entries = [
        {"name": "west2.yaml", "size": 12345, "mtime": "2026-04-11T00:00:00Z"},
        {"name": "backup.yaml", "size": 100, "mtime": "2026-04-10T00:00:00Z"},
    ]

    result = summarize_config_files(entries)

    assert result[0]["path"] == "/etc/openclash/config/west2.yaml"
    assert result[0]["size"] == 12345


def test_build_network_report_marks_both_backends_ok():
    result = build_network_report(True, True, True)
    assert result["status"] == "ok"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_doctor_and_skill.py -v`
Expected: FAIL with missing `summarize_config_files` or `build_network_report`

- [ ] **Step 3: Write the minimal implementation for doctor, config listing, and the skill**

```python
# opclash_cli/commands/subscription.py
def summarize_config_files(entries: list[dict], directory: str = "/etc/openclash/config") -> list[dict]:
    return [
        {
            "path": f"{directory}/{entry['name']}",
            "size": entry["size"],
            "mtime": entry["mtime"],
        }
        for entry in entries
    ]


def config_files(directory: str) -> dict:
    raw = LuciRpcClient().service_exec(f"ls -l --full-time {directory}/*.yaml")
    entries = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 9:
            continue
        entries.append(
            {
                "name": parts[-1].split("/")[-1],
                "size": int(parts[4]),
                "mtime": f"{parts[5]}T{parts[6].split('.')[0]}Z",
            }
        )
    return {"configs": summarize_config_files(entries, directory)}
```

```python
# opclash_cli/commands/init.py
from opclash_cli.adapters.controller import ControllerClient
from opclash_cli.adapters.luci_rpc import LuciRpcClient


def check_backends() -> dict:
    try:
        controller_ok = bool(ControllerClient().get_configs())
    except Exception:
        controller_ok = False
    try:
        luci_ok = isinstance(LuciRpcClient().get_openclash_uci(), dict)
    except Exception:
        luci_ok = False
    return {"controller_ok": controller_ok, "luci_ok": luci_ok}
```

```python
# opclash_cli/commands/doctor.py
from opclash_cli.commands.init import check_backends
from opclash_cli.commands.nodes import groups as nodes_groups, providers as nodes_providers
from opclash_cli.commands.service import status as service_status
from opclash_cli.commands.subscription import current_config


def build_network_report(controller_ok: bool, luci_ok: bool, service_ok: bool) -> dict:
    status = "ok" if controller_ok and luci_ok and service_ok else "degraded"
    return {
        "status": status,
        "controller_ok": controller_ok,
        "luci_ok": luci_ok,
        "service_ok": service_ok,
    }


def network() -> dict:
    backends = check_backends()
    service = service_status()["service"]
    return {"network": build_network_report(backends["controller_ok"], backends["luci_ok"], service["running"])}


def runtime() -> dict:
    groups = nodes_groups()["groups"]
    providers = nodes_providers()["providers"]
    return {"runtime": {"groups_readable": True, "providers_readable": True, "group_count": len(groups), "provider_count": len(providers)}}


def config() -> dict:
    current = current_config()["config_path"]
    return {"config": {"current_path": current, "backends": check_backends()}}
```

```text
# skills/opclash_cli/SKILL.md
---
name: opclash_cli
description: Use the local opclash_cli in a fixed order for OpenClash remote management.
---

## Rule

Always run `opclash_cli init check` first.

## Command order

- Subscription work: `init check` -> `subscription list` -> `subscription current` -> `subscription configs`
- Node work: `init check` -> `nodes groups` -> `nodes group --name ...`
- Service or network issues: `init check` -> `service status` -> `doctor network` -> `doctor config`

## Mutation rule

- Every mutation command must include `--reason`
- After `nodes switch`, rerun `nodes group --name ...`
- After `subscription switch`, rerun `subscription current` and `service status`
- After `service reload` or `service restart`, rerun `service status`
```

```python
# opclash_cli/main.py
from opclash_cli.commands.doctor import config as doctor_config, network as doctor_network, runtime as doctor_runtime
from opclash_cli.commands.init import check_backends

    init_subparsers.add_parser("check")

    doctor_parser = subparsers.add_parser("doctor")
    doctor_subparsers = doctor_parser.add_subparsers(dest="doctor_command")
    doctor_subparsers.add_parser("network")
    doctor_subparsers.add_parser("runtime")
    doctor_subparsers.add_parser("config")

    if args.command == "init" and args.init_command == "check":
        emit(ok("init check", check_backends()))
        return 0

    if args.command == "doctor" and args.doctor_command == "network":
        emit(ok("doctor network", doctor_network()))
        return 0

    if args.command == "doctor" and args.doctor_command == "runtime":
        emit(ok("doctor runtime", doctor_runtime()))
        return 0

    if args.command == "doctor" and args.doctor_command == "config":
        emit(ok("doctor config", doctor_config()))
        return 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest -v`
Expected: PASS with all tests green

- [ ] **Step 5: Commit**

```bash
git add opclash_cli/commands/init.py opclash_cli/commands/subscription.py opclash_cli/commands/doctor.py opclash_cli/main.py skills/opclash_cli/SKILL.md tests/test_doctor_and_skill.py
git commit -m "feat: add doctor commands and ai skill"
```
