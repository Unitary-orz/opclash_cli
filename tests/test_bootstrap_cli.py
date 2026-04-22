import json
import tomllib
from pathlib import Path
import sys

from opclash_cli.errors import CliError
from opclash_cli.main import main


def test_init_show_returns_missing_config_error(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))

    exit_code = main(["init", "show"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["command"] == "init show"
    assert payload["error"]["code"] == "LOCAL_CONFIG_MISSING"


def test_cli_error_is_rendered_as_json_error(capsys, monkeypatch):
    def raise_group_not_found(name: str) -> dict:
        raise CliError("GROUP_NOT_FOUND", f"Group '{name}' was not found")

    monkeypatch.setattr("opclash_cli.main.node_group", raise_group_not_found)

    exit_code = main(["nodes", "group", "--name", "missing"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["command"] == "nodes group"
    assert payload["error"]["code"] == "GROUP_NOT_FOUND"


def test_mutation_commands_do_not_require_reason(capsys, monkeypatch):
    monkeypatch.setattr(
        "opclash_cli.main.switch_node",
        lambda group, target: {"before": {"selected": "HK-01"}, "after": {"selected": target}, "audit": None},
    )
    monkeypatch.setattr(
        "opclash_cli.main.add_subscription",
        lambda name, url: {"subscription": {"name": name, "address": url}, "audit": None},
    )
    monkeypatch.setattr(
        "opclash_cli.main.update_subscription",
        lambda name, config: {
            "target": {"mode": "all"},
            "items": [],
            "summary": {"overall_status": "success", "total": 0, "updated_count": 0, "unchanged_count": 0, "failed_count": 0, "skipped_count": 0},
            "before": {"config_path": "/etc/openclash/config/current.yaml"},
            "after": {"config_path": "/etc/openclash/config/current.yaml"},
            "suggested_commands": [],
            "audit": None,
        },
    )
    monkeypatch.setattr(
        "opclash_cli.main.switch_config",
        lambda config: {"before": {"config_path": "a"}, "after": {"config_path": config}, "audit": None},
    )
    monkeypatch.setattr("opclash_cli.main.service_reload", lambda: {"result": "ok", "audit": None})
    monkeypatch.setattr("opclash_cli.main.service_restart", lambda: {"result": "ok", "audit": None})

    commands = [
        ["nodes", "switch", "--group", "Apple", "--target", "DIRECT"],
        ["subscription", "add", "--name", "west2", "--url", "https://example/sub"],
        ["subscription", "update"],
        ["subscription", "switch", "--config", "/etc/openclash/config/west2.yaml"],
        ["service", "reload"],
        ["service", "restart"],
    ]

    for argv in commands:
        exit_code = main(argv)
        payload = json.loads(capsys.readouterr().out)
        assert exit_code == 0
        assert payload["ok"] is True


def test_doctor_logs_returns_local_operation_log(capsys, monkeypatch):
    monkeypatch.setattr(
        "opclash_cli.main.doctor_logs",
        lambda limit: {"items": [{"command": "init check", "ok": True}], "limit": limit},
    )

    exit_code = main(["doctor", "logs", "--limit", "5"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["command"] == "doctor logs"
    assert payload["data"] == {"items": [{"command": "init check", "ok": True}], "limit": 5}


def test_nodes_speedtest_returns_sorted_results(capsys, monkeypatch):
    monkeypatch.setattr(
        "opclash_cli.main.nodes_speedtest",
        lambda group, limit, test_url, timeout: {
            "tested": 2,
            "ok": 2,
            "results": [
                {"name": "JP-01", "delay_ms": 70},
                {"name": "HK-01", "delay_ms": 90},
            ],
        },
    )

    exit_code = main(
        [
            "nodes",
            "speedtest",
            "--group",
            "Apple",
            "--limit",
            "2",
            "--url",
            "https://www.gstatic.com/generate_204",
            "--timeout",
            "5000",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["command"] == "nodes speedtest"
    assert payload["data"]["results"][0] == {"name": "JP-01", "delay_ms": 70}


def test_version_command_returns_metadata(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))

    exit_code = main(["version"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["command"] == "version"
    assert payload["data"]["version"] == "0.1.0"
    assert payload["data"]["python"] == sys.version.split()[0]


def test_global_version_prints_plain_text(capsys):
    exit_code = main(["--version"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "opclash_cli 0.1.0"


def test_completion_bash_outputs_script(capsys):
    exit_code = main(["completion", "bash"])

    assert exit_code == 0
    assert "complete -F _opclash_cli_complete opclash_cli" in capsys.readouterr().out


def test_dry_run_skips_mutation_execution(capsys, monkeypatch):
    called = {"switch": False}

    def fail_if_called(group: str, target: str) -> dict:
        called["switch"] = True
        raise AssertionError("mutation should not execute during dry-run")

    monkeypatch.setattr("opclash_cli.main.switch_node", fail_if_called)

    exit_code = main(["nodes", "switch", "--group", "Apple", "--target", "DIRECT", "--dry-run"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert called["switch"] is False
    assert payload["data"]["dry_run"] is True
    assert payload["data"]["params"] == {"group": "Apple", "target": "DIRECT"}


def test_confirmation_can_abort_mutation(capsys, monkeypatch):
    monkeypatch.setattr("opclash_cli.main._stdin_isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")

    exit_code = main(["service", "restart"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["error"]["code"] == "CONFIRM_ABORTED"


def test_yes_skips_confirmation(capsys, monkeypatch):
    monkeypatch.setattr("opclash_cli.main._stdin_isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(AssertionError("input should not be called")))
    monkeypatch.setattr("opclash_cli.main.service_restart", lambda: {"result": "ok", "audit": None})

    exit_code = main(["service", "restart", "--yes"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ok"] is True


def test_pyproject_includes_cli_subpackages():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    packages = pyproject.get("tool", {}).get("setuptools", {}).get("packages")

    assert packages != ["opclash_cli"]
