from opclash_cli.errors import CliError
import opclash_cli.commands.nodes as nodes_commands
from opclash_cli.commands.nodes import summarize_groups, summarize_providers


def test_summarize_groups_returns_selected_proxy_names():
    payload = {
        "proxies": {
            "Apple": {"type": "Selector", "now": "DIRECT", "all": ["DIRECT", "HK-01"]},
            "Final": {"type": "Selector", "now": "Proxies", "all": ["Proxies", "DIRECT"]},
            "HK-01": {"type": "VMess"},
        }
    }

    result = summarize_groups(payload)

    assert result == [
        {"name": "Apple", "selected": "DIRECT", "choices": ["DIRECT", "HK-01"]},
        {"name": "Final", "selected": "Proxies", "choices": ["Proxies", "DIRECT"]},
    ]


def test_summarize_providers_returns_provider_counts():
    payload = {
        "providers": {
            "airport-a": {"proxies": [{"name": "HK-01"}, {"name": "JP-01"}], "updatedAt": "2026-04-11T00:00:00Z"}
        }
    }

    result = summarize_providers(payload)

    assert result == [
        {"name": "airport-a", "count": 2, "updated_at": "2026-04-11T00:00:00Z"}
    ]


class FakeSpeedtestControllerClient:
    def get_proxies(self) -> dict:
        return {
            "proxies": {
                "Apple": {
                    "type": "Selector",
                    "now": "HK-01",
                    "all": ["DIRECT", "Traffic: 1 GB", "HK-01", "JP-01", "Missing-01"],
                }
            }
        }

    def get_providers(self) -> dict:
        return {
            "providers": {
                "default": {
                    "proxies": [
                        {"name": "DIRECT", "type": "Direct"},
                        {"name": "Traffic: 1 GB", "type": "Shadowsocks"},
                        {"name": "Expire: 2026-05-11", "type": "Shadowsocks"},
                        {"name": "HK-01", "type": "Shadowsocks"},
                        {"name": "JP-01", "type": "Shadowsocks"},
                        {"name": "US-01", "type": "Shadowsocks"},
                    ]
                }
            }
        }

    def proxy_delay(self, name: str, test_url: str, timeout_ms: int) -> dict | None:
        delays = {
            "HK-01": {"delay": 90},
            "JP-01": {"delay": 70},
            "US-01": None,
        }
        return delays.get(name)


def test_speedtest_sorts_leaf_nodes_by_delay(monkeypatch):
    monkeypatch.setattr(nodes_commands, "ControllerClient", lambda: FakeSpeedtestControllerClient())

    result = nodes_commands.speedtest(None, 2, "https://www.gstatic.com/generate_204", 5000)

    assert result == {
        "tested": 3,
        "ok": 2,
        "results": [
            {"name": "JP-01", "delay_ms": 70},
            {"name": "HK-01", "delay_ms": 90},
        ],
    }


def test_speedtest_filters_group_choices(monkeypatch):
    monkeypatch.setattr(nodes_commands, "ControllerClient", lambda: FakeSpeedtestControllerClient())

    result = nodes_commands.speedtest("Apple", 10, "https://www.gstatic.com/generate_204", 5000)

    assert result["tested"] == 2
    assert [item["name"] for item in result["results"]] == ["JP-01", "HK-01"]


def test_speedtest_rejects_missing_group(monkeypatch):
    monkeypatch.setattr(nodes_commands, "ControllerClient", lambda: FakeSpeedtestControllerClient())

    try:
        nodes_commands.speedtest("Missing", 10, "https://www.gstatic.com/generate_204", 5000)
        raise AssertionError("expected CliError")
    except CliError as error:
        assert error.code == "GROUP_NOT_FOUND"
