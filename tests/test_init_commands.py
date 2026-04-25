import pytest
import tomllib

import opclash_cli.commands.init as init_commands
from opclash_cli.main import main
from opclash_cli.commands.init import mask_secret
from opclash_cli.local_config import AppConfig, ControllerConfig, load_config, save_config


def test_save_and_load_config_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))
    config = AppConfig(
        controller=ControllerConfig(url="http://router:9090", secret="controller-secret"),
    )

    save_config(config)
    loaded = load_config()

    assert loaded.controller.url == "http://router:9090"
    assert loaded.controller.secret == "controller-secret"


def test_mask_secret_keeps_suffix():
    assert mask_secret("controller-secret") == "*************cret"


def test_init_command_writes_controller_only_config_file(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))

    exit_code = main(
        [
            "init",
            "--controller-url",
            "http://router:9090",
            "--controller-secret",
            "controller-secret",
        ]
    )

    written = tomllib.loads((tmp_path / "config.toml").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert written == {
        "controller": {
            "url": "http://router:9090",
            "secret": "controller-secret",
        }
    }


def test_load_config_supports_controller_only_config(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))
    (tmp_path / "config.toml").write_text(
        '[controller]\nurl = "http://router:9090"\nsecret = "controller-secret"\n',
        encoding="utf-8",
    )

    loaded = load_config()

    assert loaded.controller.url == "http://router:9090"


def test_check_backends_reports_router_local_status(monkeypatch):
    class FakeControllerClient:
        def get_configs(self):
            return ["/etc/openclash/config/test.yaml"]

    class FakeLuciRpcClient:
        backend_name = "local"

        def get_openclash_uci(self):
            return {"config_subscribe": {}}

    monkeypatch.setattr(init_commands, "ControllerClient", FakeControllerClient)
    monkeypatch.setattr(init_commands, "LuciRpcClient", FakeLuciRpcClient)
    monkeypatch.setattr(init_commands, "default_local_management_available", lambda: True)

    result = init_commands.check_backends()

    assert result == {
        "controller_ok": True,
        "router_local_ok": True,
        "router_local_backend": "local",
    }


def test_check_backends_marks_router_local_unavailable_off_router(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))
    (tmp_path / "config.toml").write_text(
        '[controller]\nurl = "http://router:9090"\nsecret = "controller-secret"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(init_commands, "default_local_management_available", lambda: False)

    class FakeControllerClient:
        def get_configs(self):
            return ["/etc/openclash/config/test.yaml"]

    monkeypatch.setattr(init_commands, "ControllerClient", FakeControllerClient)

    result = init_commands.check_backends()

    assert result == {
        "controller_ok": True,
        "router_local_ok": False,
        "router_local_backend": "unavailable",
    }


def test_init_command_rejects_removed_management_flags():
    with pytest.raises(SystemExit) as error:
        main(["init", "--management-url", "http://router"])

    assert error.value.code == 2
