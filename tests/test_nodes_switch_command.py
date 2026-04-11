from opclash_cli.commands.nodes import build_group_detail, switch_group


class FakeControllerClient:
    def __init__(self) -> None:
        self.payload = {
            "proxies": {
                "Apple": {"type": "Selector", "now": "HK-01", "all": ["DIRECT", "HK-01"]},
            }
        }
        self.last_switch = None

    def get_proxies(self) -> dict:
        return self.payload

    def switch_proxy(self, group: str, target: str) -> dict:
        self.last_switch = (group, target)
        self.payload["proxies"]["Apple"]["now"] = target
        return self.payload["proxies"]["Apple"]


def test_build_group_detail_returns_choices():
    client = FakeControllerClient()

    result = build_group_detail(client.get_proxies(), "Apple")

    assert result == {
        "name": "Apple",
        "selected": "HK-01",
        "choices": ["DIRECT", "HK-01"],
    }


def test_switch_group_returns_before_after():
    client = FakeControllerClient()

    result = switch_group(client, "Apple", "DIRECT")

    assert result["before"]["selected"] == "HK-01"
    assert result["after"]["selected"] == "DIRECT"
    assert client.last_switch == ("Apple", "DIRECT")
