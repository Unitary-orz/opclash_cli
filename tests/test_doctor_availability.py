from datetime import datetime, timedelta, timezone

import opclash_cli.commands.doctor as doctor_commands


class FakeAvailabilityControllerClient:
    def __init__(self, delays: dict[str, list[int | None]]) -> None:
        self._delays = {name: list(values) for name, values in delays.items()}

    def get_proxies(self) -> dict:
        return {
            "proxies": {
                "Final": {"type": "Selector", "now": "Proxies", "all": ["Proxies", "DIRECT"]},
                "Apple": {"type": "Selector", "now": "Proxies", "all": ["Proxies", "DIRECT"]},
                "OpenAI": {"type": "Selector", "now": "JP", "all": ["JP", "SG"]},
                "Proxies": {"type": "Selector", "now": "SG", "all": ["SG", "JP"]},
                "SG": {
                    "type": "Selector",
                    "now": "🇸🇬 Singapore | 06",
                    "all": ["🇸🇬 Singapore | 06", "🇸🇬 Singapore | 03", "🇸🇬 Singapore | 04"],
                },
                "JP": {"type": "Selector", "now": "🇯🇵 Japan | 07", "all": ["🇯🇵 Japan | 07"]},
                "DIRECT": {"type": "Direct"},
                "🇸🇬 Singapore | 06": {"type": "Trojan", "alive": True},
                "🇸🇬 Singapore | 03": {"type": "Trojan", "alive": True},
                "🇸🇬 Singapore | 04": {"type": "Trojan", "alive": True},
                "🇯🇵 Japan | 07": {"type": "Trojan", "alive": True},
            }
        }

    def proxy_delay(self, name: str, test_url: str, timeout_ms: int) -> dict | None:
        values = self._delays[name]
        value = values.pop(0) if values else None
        if value is None:
            return None
        return {"delay": value}


class FakeAvailabilityLuciRpcClient:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def read_file(self, path: str) -> str:
        assert path == "/tmp/openclash.log"
        return "\n".join(self._lines)


def _log_line(ts: datetime, level: str, msg: str) -> str:
    return f'time="{ts.isoformat().replace("+00:00", "Z")}" level={level} msg="{msg}"'


def _recent_logs(now: datetime) -> list[str]:
    start = now - timedelta(minutes=10)
    return [
        _log_line(
            start,
            "warning",
            "[TCP] dial Final (match Match/) 100.64.0.1:1000(curl) --> github.com:443 error: oss-cn-guangzhou.example:20022 connect error: connect failed: dial tcp 1.1.1.1:443: i/o timeout",
        ),
        _log_line(
            start + timedelta(minutes=1),
            "warning",
            "[TCP] dial Final (match Match/) 100.64.0.1:1001(curl) --> youtube.com:443 error: oss-cn-guangzhou.example:20022 connect error: connect failed: dial tcp 1.1.1.1:443: i/o timeout",
        ),
        _log_line(
            start + timedelta(minutes=2),
            "warning",
            "[UDP] dial Apple (match DomainSuffix/apple.com) 192.168.1.8:2000 --> time.apple.com:123 error: oss-cn-guangzhou.example:20022 connect error: connect failed: dial tcp 1.1.1.1:443: i/o timeout",
        ),
        _log_line(
            start + timedelta(minutes=3),
            "warning",
            "[TCP] dial Apple (match DomainSuffix/apple.com) 192.168.1.8:2001 --> gsp-ssl.ls.apple.com:443 error: oss-cn-guangzhou.example:20022 connect error: connect failed: dial tcp 1.1.1.1:443: i/o timeout",
        ),
        _log_line(
            start + timedelta(minutes=4),
            "warning",
            "[TCP] dial Apple (match DomainSuffix/apple.com) 192.168.1.8:2002 --> captive.apple.com:80 error: oss-cn-guangzhou.example:20022 connect error: connect failed: dial tcp 1.1.1.1:443: i/o timeout",
        ),
        _log_line(
            start + timedelta(minutes=5),
            "info",
            "[TCP] 100.64.0.1:1003 --> api.openai.com:443 match DomainKeyword(openai) using OpenAI[🇯🇵 Japan | 07]",
        ),
        _log_line(
            start + timedelta(minutes=6),
            "info",
            "[TCP] 100.64.0.1:1004 --> github.com:443 match DomainSuffix(github.com) using Proxies[🇸🇬 Singapore | 06]",
        ),
    ]


def test_availability_reports_switchable_group_when_current_leaf_is_unavailable(monkeypatch):
    now = datetime(2026, 4, 30, 5, 40, tzinfo=timezone.utc)
    controller = FakeAvailabilityControllerClient(
        {
            "🇸🇬 Singapore | 06": [None, None],
            "🇸🇬 Singapore | 03": [120, 110],
            "🇸🇬 Singapore | 04": [None, None],
            "🇯🇵 Japan | 07": [90, 95],
        }
    )
    luci = FakeAvailabilityLuciRpcClient(_recent_logs(now))

    monkeypatch.setattr(doctor_commands, "_utcnow", lambda: now)
    monkeypatch.setattr(doctor_commands, "ControllerClient", lambda: controller)
    monkeypatch.setattr(doctor_commands, "LuciRpcClient", lambda: luci)

    result = doctor_commands.availability("30m", 2, "https://www.gstatic.com/generate_204", 3000, 2)

    assert result["summary"]["status"] == "switch-node"
    assert "SG" in result["summary"]["unavailable_groups"]
    assert any(item["chain"] == "Final -> Proxies -> SG" for item in result["chains"] if item["status"] == "switch-node")
    assert result["recommendations"] == [
        {
            "action": "switch-node",
            "group": "SG",
            "from": "🇸🇬 Singapore | 06",
            "to": "🇸🇬 Singapore | 03",
            "reason": "current selected leaf unavailable while an alternate candidate is available",
        }
    ]


def test_availability_reports_fallback_subscription_when_group_has_no_available_candidates(monkeypatch):
    now = datetime(2026, 4, 30, 5, 40, tzinfo=timezone.utc)
    controller = FakeAvailabilityControllerClient(
        {
            "🇸🇬 Singapore | 06": [None, None],
            "🇸🇬 Singapore | 03": [None, None],
            "🇸🇬 Singapore | 04": [None, None],
            "🇯🇵 Japan | 07": [None, None],
        }
    )
    luci = FakeAvailabilityLuciRpcClient(_recent_logs(now))

    monkeypatch.setattr(doctor_commands, "_utcnow", lambda: now)
    monkeypatch.setattr(doctor_commands, "ControllerClient", lambda: controller)
    monkeypatch.setattr(doctor_commands, "LuciRpcClient", lambda: luci)

    result = doctor_commands.availability("30m", 2, "https://www.gstatic.com/generate_204", 3000, 2)

    assert result["summary"]["status"] == "fallback-subscription"
    assert "SG" in result["summary"]["fully_unavailable_groups"]
    assert any(item["chain"] == "Final -> Proxies -> SG" for item in result["chains"] if item["status"] == "fallback-subscription")
    assert result["recommendations"] == [
        {
            "action": "fallback-subscription",
            "target": "backup-subscription",
            "reason": "at least one active chain has no available candidates in the current subscription",
        }
    ]
