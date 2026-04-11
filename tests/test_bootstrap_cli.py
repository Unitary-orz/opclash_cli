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
