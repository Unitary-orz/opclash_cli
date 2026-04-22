from opclash_cli.commands.nodes import build_group_detail, switch_group
from opclash_cli.adapters.controller import ControllerClient


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


class FakePutResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        if self._payload is None:
            raise AssertionError("json() should not be called for empty responses")
        return self._payload


class FakePutSession:
    def __init__(self, response: FakePutResponse) -> None:
        self.response = response

    def put(self, url: str, headers: dict[str, str], json: dict[str, str], timeout: int) -> FakePutResponse:
        return self.response


def test_switch_proxy_accepts_204_without_json(monkeypatch):
    monkeypatch.setattr(
        "opclash_cli.adapters.controller.load_config",
        lambda: type("Config", (), {"controller": type("Controller", (), {"url": "http://127.0.0.1:9090", "secret": "s"})()})(),
    )
    client = ControllerClient(session=FakePutSession(FakePutResponse(204)))

    result = client.switch_proxy("Apple", "DIRECT")

    assert result == {}
