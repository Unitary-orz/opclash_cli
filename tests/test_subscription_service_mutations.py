from pathlib import Path

import opclash_cli.commands.subscription as subscription_commands
from opclash_cli.commands.subscription import add_subscription_payload, switch_config_payload
from opclash_cli.errors import CliError


def test_add_subscription_payload_contains_required_fields():
    payload = add_subscription_payload("west2", "https://example/sub")

    assert payload["name"] == "west2"
    assert payload["address"] == "https://example/sub"
    assert payload["enabled"] == "1"


def test_switch_config_payload_sets_target_path():
    payload = switch_config_payload("/etc/openclash/config/west2.yaml")

    assert payload == {"config_path": "/etc/openclash/config/west2.yaml"}


class FakeConfigEntry:
    def __init__(self, path: str) -> None:
        self.path = path
        self.size = 1
        self.mtime = "2026-04-11T00:00:00Z"


class FakeLuciRpcClient:
    def __init__(self) -> None:
        self.current_path = "/etc/openclash/config/current.yaml"
        self.set_calls = []
        self.committed = False
        self.reloaded = False

    def list_config_files(self, directory: str):
        assert directory == str(Path("/etc/openclash/config/missing.yaml").parent)
        return [FakeConfigEntry("/etc/openclash/config/current.yaml")]

    def get_openclash_uci(self) -> dict:
        return {"config": {"config_path": self.current_path}}

    def set_uci(self, config_name: str, section: str, option: str, value: str) -> bool:
        self.set_calls.append((config_name, section, option, value))
        self.current_path = value
        return True

    def commit_uci(self, config_name: str) -> bool:
        self.committed = True
        return True

    def service_exec(self, command: str) -> str:
        self.reloaded = True
        return "ok"


def test_switch_config_rejects_missing_target(monkeypatch):
    fake_client = FakeLuciRpcClient()
    monkeypatch.setattr(subscription_commands, "LuciRpcClient", lambda: fake_client)

    try:
        subscription_commands.switch_config("/etc/openclash/config/missing.yaml", "test")
        raise AssertionError("expected CliError")
    except CliError as error:
        assert error.code == "CONFIG_NOT_FOUND"

    assert fake_client.set_calls == []
    assert fake_client.committed is False
    assert fake_client.reloaded is False
