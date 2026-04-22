import json

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
