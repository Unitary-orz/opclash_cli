import pytest
import tomllib

import opclash_cli.commands.init as init_commands
from opclash_cli.main import main
from opclash_cli.commands.init import mask_secret
from opclash_cli.local_config import (
    AppConfig,
    ControllerConfig,
    ManagementConfig,
    load_config,
    normalize_management_url,
    save_config,
)


def test_save_and_load_config_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))
    config = AppConfig(
        controller=ControllerConfig(url="http://router:9090", secret="controller-secret"),
        management=ManagementConfig(url="http://router/cgi-bin/luci/rpc", username="root", password="rpc-password", ssl_verify=False),
    )

    save_config(config)
    loaded = load_config()

    assert loaded.controller.url == "http://router:9090"
    assert loaded.controller.secret == "controller-secret"
    assert loaded.management.username == "root"
    assert loaded.management.ssl_verify is False


def test_mask_secret_keeps_suffix():
    assert mask_secret("controller-secret") == "*************cret"


def test_init_command_writes_config_file(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setattr(init_commands, "default_local_management_available", lambda: False)

    exit_code = main(
        [
            "init",
            "--controller-url",
            "http://router:9090",
            "--controller-secret",
            "controller-secret",
            "--management-url",
            "http://router",
            "--management-username",
            "root",
            "--management-password",
            "rpc-password",
            "--management-insecure",
        ]
    )

    written = tomllib.loads((tmp_path / "config.toml").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert written["controller"]["url"] == "http://router:9090"
    assert written["management"]["url"] == "http://router"
    assert written["management"]["username"] == "root"
    assert written["management"]["ssl_verify"] is False


def test_init_command_defaults_to_local_management_on_router(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setattr(init_commands, "default_local_management_available", lambda: True)

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
    assert written["management"]["url"] == "local://openwrt"
    assert written["management"]["username"] == ""
    assert written["management"]["password"] == ""


def test_init_command_defaults_to_controller_only_off_router(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setattr(init_commands, "default_local_management_available", lambda: False)

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
    assert "management" not in written


def test_normalize_management_url_accepts_plain_host():
    assert normalize_management_url("http://192.168.31.166") == "http://192.168.31.166"


def test_normalize_management_url_accepts_luci_base_path():
    assert normalize_management_url("https://router/cgi-bin/luci") == "https://router/cgi-bin/luci"


def test_load_config_allows_env_override_for_ssl_verify(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setenv("OPENCLASH_MANAGEMENT_SSL_VERIFY", "0")
    save_config(
        AppConfig(
            controller=ControllerConfig(url="http://router:9090", secret="controller-secret"),
            management=ManagementConfig(url="http://router", username="root", password="rpc-password", ssl_verify=True),
        )
    )

    loaded = load_config()

    assert loaded.management.url == "http://router"
    assert loaded.management.ssl_verify is False


def test_load_config_supports_controller_only_config(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))
    (tmp_path / "config.toml").write_text(
        '[controller]\nurl = "http://router:9090"\nsecret = "controller-secret"\n',
        encoding="utf-8",
    )

    loaded = load_config()

    assert loaded.controller.url == "http://router:9090"
    assert loaded.management is None


def test_check_backends_reports_management_backend(monkeypatch):
    class FakeControllerClient:
        def get_configs(self):
            return ["/etc/openclash/config/test.yaml"]

    class FakeLuciRpcClient:
        backend_name = "ubus"

        def get_openclash_uci(self):
            return {"config_subscribe": {}}

    monkeypatch.setattr(init_commands, "ControllerClient", FakeControllerClient)
    monkeypatch.setattr(init_commands, "LuciRpcClient", FakeLuciRpcClient)

    result = init_commands.check_backends()

    assert result == {
        "controller_ok": True,
        "management_ok": True,
        "management_backend": "ubus",
    }


def test_check_backends_marks_management_unconfigured_when_not_present(tmp_path, monkeypatch):
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
        "management_ok": False,
        "management_backend": "unconfigured",
    }


def test_init_command_rejects_legacy_luci_flags():
    with pytest.raises(SystemExit) as error:
        main(["init", "--luci-url", "http://router"])

    assert error.value.code == 2
