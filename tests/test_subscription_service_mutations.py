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


class FakeUpdateLuciRpcClient:
    def __init__(self) -> None:
        self.update_target = None
        self._config_list_calls = 0
        self._log_reads = 0
        self._before_log = "existing log line\n"
        self._after_log = "\n".join(
            [
                "existing log line",
                "2026-04-22 11:24:40 Start Updating Config File【west0109_clash】...",
                "2026-04-22 11:24:42 Config File【west0109_clash】No Change, Do Nothing!",
                "2026-04-22 11:24:42 Start Updating Config File【west0109】...",
                "2026-04-22 11:24:43 Error:【west0109】Update Error, Please Try Again Later...",
                "2026-04-22 11:24:52 Start Updating Config File【west2】...",
                "2026-04-22 11:24:55 Config File【west2】Update Successful!",
            ]
        )

    def get_openclash_uci(self) -> dict:
        return {
            "config": {"config_path": "/etc/openclash/config/current.yaml"},
            "@config_subscribe[0]": {
                ".type": "config_subscribe",
                "name": "west2",
                "address": "https://example/sub",
                "enabled": "1",
            },
            "@config_subscribe[1]": {
                ".type": "config_subscribe",
                "name": "west0109",
                "address": "https://example/sub-2",
                "enabled": "1",
            },
            "@config_subscribe[2]": {
                ".type": "config_subscribe",
                "name": "west0109_clash",
                "address": "https://example/sub-3",
                "enabled": "1",
            },
            "@config_subscribe[3]": {
                ".type": "config_subscribe",
                "name": "disabled-west",
                "address": "https://example/sub-4",
                "enabled": "0",
            },
        }

    def list_config_files(self, directory: str):
        self._config_list_calls += 1
        west2 = FakeConfigEntry("/etc/openclash/config/west2.yaml")
        west0109_clash = FakeConfigEntry("/etc/openclash/config/west0109_clash.yaml")
        current = FakeConfigEntry("/etc/openclash/config/current.yaml")
        if self._config_list_calls == 1:
            west2.mtime = "2026-04-11T00:00:00Z"
        else:
            west2.mtime = "2026-04-22T03:24:55Z"
        return [current, west2, west0109_clash]

    def update_subscription(self, target: str | None = None) -> str:
        self.update_target = target
        return "updated"

    def read_file(self, path: str) -> str:
        assert path == "/tmp/openclash.log"
        self._log_reads += 1
        if self._log_reads == 1:
            return self._before_log
        return self._after_log


def test_update_subscription_without_target_updates_all(monkeypatch):
    fake_client = FakeUpdateLuciRpcClient()
    monkeypatch.setattr(subscription_commands, "LuciRpcClient", lambda: fake_client)

    result = subscription_commands.update_subscription(None, None, "refresh all")

    assert fake_client.update_target is None
    assert result["target"] == {"mode": "all"}
    assert result["summary"] == {
        "overall_status": "partial",
        "total": 4,
        "updated_count": 1,
        "unchanged_count": 1,
        "failed_count": 1,
        "skipped_count": 1,
    }
    by_name = {item["name"]: item for item in result["items"]}
    assert by_name["west2"]["status"] == "updated"
    assert by_name["west2"]["evidence"]["config_path"] == "/etc/openclash/config/west2.yaml"
    assert by_name["west2"]["evidence"]["config_changed"] is True
    assert by_name["west0109_clash"]["status"] == "unchanged"
    assert by_name["west0109"]["status"] == "failed"
    assert by_name["disabled-west"]["status"] == "skipped"
    assert result["suggested_commands"] == [
        {
            "command": "opclash_cli service logs",
            "purpose": "查看 OpenClash 最近的订阅更新日志",
        },
        {
            "command": "opclash_cli subscription list",
            "purpose": "确认失败项对应的订阅名称和地址",
        },
    ]
    assert result["audit"]["action"] == "subscription.update"


def test_update_subscription_by_name_targets_single_subscription(monkeypatch):
    fake_client = FakeUpdateLuciRpcClient()
    monkeypatch.setattr(subscription_commands, "LuciRpcClient", lambda: fake_client)

    result = subscription_commands.update_subscription("west2", None, "refresh one")

    assert fake_client.update_target == "west2"
    assert result["target"] == {"mode": "single", "name": "west2", "section": "@config_subscribe[0]"}
    assert result["items"] == [
        {
            "name": "west2",
            "section": "@config_subscribe[0]",
            "enabled": True,
            "status": "updated",
            "evidence": {
                "source": "openclash.log",
                "matched_lines": [
                    "2026-04-22 11:24:52 Start Updating Config File【west2】...",
                    "2026-04-22 11:24:55 Config File【west2】Update Successful!",
                ],
                "config_path": "/etc/openclash/config/west2.yaml",
                "config_changed": True,
                "before_mtime": "2026-04-11T00:00:00Z",
                "after_mtime": "2026-04-22T03:24:55Z",
            },
        }
    ]
    assert result["summary"]["overall_status"] == "success"
    assert result["suggested_commands"] == []


def test_update_subscription_rejects_missing_subscription_name(monkeypatch):
    fake_client = FakeUpdateLuciRpcClient()
    monkeypatch.setattr(subscription_commands, "LuciRpcClient", lambda: fake_client)

    try:
        subscription_commands.update_subscription("missing", None, "refresh one")
        raise AssertionError("expected CliError")
    except CliError as error:
        assert error.code == "SUBSCRIPTION_NOT_FOUND"
