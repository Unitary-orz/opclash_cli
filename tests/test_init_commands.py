import tomllib

from opclash_cli.main import main
from opclash_cli.commands.init import mask_secret
from opclash_cli.local_config import (
    AppConfig,
    ControllerConfig,
    LuciConfig,
    load_config,
    normalize_luci_rpc_url,
    save_config,
)


def test_save_and_load_config_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))
    config = AppConfig(
        controller=ControllerConfig(url="http://router:9090", secret="controller-secret"),
        luci=LuciConfig(url="http://router/cgi-bin/luci/rpc", username="root", password="rpc-password", ssl_verify=False),
    )

    save_config(config)
    loaded = load_config()

    assert loaded.controller.url == "http://router:9090"
    assert loaded.controller.secret == "controller-secret"
    assert loaded.luci.username == "root"
    assert loaded.luci.ssl_verify is False


def test_mask_secret_keeps_suffix():
    assert mask_secret("controller-secret") == "*************cret"


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
            "http://router",
            "--luci-username",
            "root",
            "--luci-password",
            "rpc-password",
            "--luci-insecure",
        ]
    )

    written = tomllib.loads((tmp_path / "config.toml").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert written["controller"]["url"] == "http://router:9090"
    assert written["luci"]["url"] == "http://router/cgi-bin/luci/rpc"
    assert written["luci"]["username"] == "root"
    assert written["luci"]["ssl_verify"] is False


def test_normalize_luci_rpc_url_accepts_plain_host():
    assert normalize_luci_rpc_url("http://192.168.31.166") == "http://192.168.31.166/cgi-bin/luci/rpc"


def test_normalize_luci_rpc_url_accepts_luci_base_path():
    assert normalize_luci_rpc_url("https://router/cgi-bin/luci") == "https://router/cgi-bin/luci/rpc"


def test_load_config_allows_env_override_for_ssl_verify(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setenv("OPENCLASH_LUCI_SSL_VERIFY", "0")
    save_config(
        AppConfig(
            controller=ControllerConfig(url="http://router:9090", secret="controller-secret"),
            luci=LuciConfig(url="http://router", username="root", password="rpc-password", ssl_verify=True),
        )
    )

    loaded = load_config()

    assert loaded.luci.url == "http://router/cgi-bin/luci/rpc"
    assert loaded.luci.ssl_verify is False
