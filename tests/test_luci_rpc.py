import pytest

from opclash_cli.adapters.luci_rpc import LuciRpcClient
from opclash_cli.errors import CliError


def test_luci_rpc_client_requires_router_local_execution(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        (
            "[controller]\n"
            'url = "http://router:9090"\n'
            'secret = "controller-secret"\n'
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(config_path))
    monkeypatch.setattr(LuciRpcClient, "_should_use_local_backend", lambda self: False)

    with pytest.raises(CliError) as error:
        LuciRpcClient()

    assert error.value.code == "LOCAL_ROUTER_REQUIRED"
    assert error.value.details["recommended_mode"] == "router-local"


def test_luci_rpc_client_uses_local_backend_when_router_tools_exist(monkeypatch):
    monkeypatch.setattr(LuciRpcClient, "_should_use_local_backend", lambda self: True)

    client = LuciRpcClient()

    assert client.backend_name == "local"
