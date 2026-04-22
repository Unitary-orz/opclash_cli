import json
import tomllib
from pathlib import Path

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


def test_pyproject_includes_cli_subpackages():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    packages = pyproject.get("tool", {}).get("setuptools", {}).get("packages")

    assert packages != ["opclash_cli"]
