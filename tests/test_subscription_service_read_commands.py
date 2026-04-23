from opclash_cli.commands.service import summarize_status
import opclash_cli.commands.subscription as subscription_commands
from opclash_cli.commands.subscription import parse_subscription_userinfo, summarize_subscriptions


def test_summarize_subscriptions_redacts_addresses_by_default():
    payload = {
        "cfg1": {
            ".type": "config_subscribe",
            "name": "west2",
            "address": "https://example.com/subscribe/token-123?target=clash",
            "enabled": "1",
        },
        "cfg2": {".type": "other", "name": "ignore-me"},
    }

    result = summarize_subscriptions(payload)

    assert result == [
        {
            "section": "cfg1",
            "name": "west2",
            "address": "https://example.com/***",
            "enabled": True,
        }
    ]


def test_summarize_subscriptions_can_return_raw_addresses_for_internal_use():
    payload = {
        "cfg1": {
            ".type": "config_subscribe",
            "name": "west2",
            "address": "https://example.com/subscribe/token-123?target=clash",
            "enabled": "1",
        },
    }

    result = summarize_subscriptions(payload, redact_addresses=False)

    assert result[0]["address"] == "https://example.com/subscribe/token-123?target=clash"


def test_summarize_status_marks_running_when_status_output_contains_running():
    result = summarize_status("openclash is running")
    assert result == {"running": True, "raw": "openclash is running"}


def test_parse_subscription_userinfo_calculates_remaining_quota():
    result = parse_subscription_userinfo(
        "upload=171995290170; download=910639877591; total=1288490188800; expire=1793605602"
    )

    assert result["upload_bytes"] == 171995290170
    assert result["download_bytes"] == 910639877591
    assert result["used_bytes"] == 1082635167761
    assert result["remain_bytes"] == 205855021039
    assert result["total_bytes"] == 1288490188800
    assert result["remain_percent"] == 16.0
    assert result["expire"] == "2026-11-02T07:46:42Z"


class FakeUsageLuciRpcClient:
    def __init__(self) -> None:
        self.commands = []

    def get_openclash_uci(self) -> dict:
        return {
            "@config_subscribe[0]": {
                ".type": "config_subscribe",
                "name": "x-max",
                "address": "https://example.test/sub",
                "enabled": "1",
                "sub_ua": "clash.meta",
            },
            "@config_subscribe[1]": {
                ".type": "config_subscribe",
                "name": "disabled",
                "address": "https://example.test/disabled",
                "enabled": "0",
            },
        }

    def service_exec(self, command: str, timeout: int = 10) -> str:
        self.commands.append(command)
        if "clash.meta" in command:
            return "HTTP/2 403\nhttp_code=403\n"
        return (
            "HTTP/2 200\n"
            "subscription-userinfo: upload=10; download=20; total=100; expire=1793605602\n"
            "http_code=200\n"
        )


def test_subscription_usage_uses_subscription_user_agent_then_quantumultx(monkeypatch):
    fake_client = FakeUsageLuciRpcClient()
    monkeypatch.setattr(subscription_commands, "LuciRpcClient", lambda: fake_client)

    result = subscription_commands.subscription_usage("x-max")

    assert result["summary"] == {"total": 1, "ok": 1, "failed": 0, "skipped": 0}
    assert result["items"][0]["name"] == "x-max"
    assert result["items"][0]["status"] == "ok"
    assert result["items"][0]["source"] == "subscription-userinfo"
    assert result["items"][0]["user_agent"] == "Quantumultx"
    assert result["items"][0]["quota"]["remain_bytes"] == 70
    assert len(fake_client.commands) == 2


def test_subscription_usage_skips_disabled_subscriptions(monkeypatch):
    fake_client = FakeUsageLuciRpcClient()
    monkeypatch.setattr(subscription_commands, "LuciRpcClient", lambda: fake_client)

    result = subscription_commands.subscription_usage(None)

    by_name = {item["name"]: item for item in result["items"]}
    assert by_name["disabled"]["status"] == "skipped"
    assert by_name["disabled"]["reason"] == "disabled"


def test_subscription_usage_does_not_leak_address_when_curl_fails(monkeypatch):
    class FailingUsageLuciRpcClient(FakeUsageLuciRpcClient):
        def service_exec(self, command: str, timeout: int = 10) -> str:
            raise RuntimeError("curl failed for https://secret.example/sub-token")

    fake_client = FailingUsageLuciRpcClient()
    monkeypatch.setattr(subscription_commands, "LuciRpcClient", lambda: fake_client)

    result = subscription_commands.subscription_usage("x-max")

    assert result["items"][0]["status"] == "failed"
    assert "secret.example" not in str(result)
    assert result["items"][0]["attempts"][0]["error"] == "RuntimeError"
