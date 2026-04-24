import requests
import pytest

from opclash_cli.adapters.luci_rpc import LuciRpcClient, _LuciJsonRpcBackend, _UbusJsonRpcBackend
from opclash_cli.errors import CliError


class FakeResponse:
    def __init__(self, result: object = None, status_code: int = 200) -> None:
        self._result = result if result is not None else "token-1"
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f"{self.status_code} Client Error", response=self
            )

    def json(self) -> dict:
        return {"result": self._result}


class FakeSession:
    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self.verify = True
        self.calls = []
        self._responses = list(responses or [FakeResponse()])

    def post(self, url: str, json: dict, timeout: int):
        self.calls.append({"url": url, "json": json, "timeout": timeout, "verify": self.verify})
        if not self._responses:
            raise AssertionError(f"unexpected request: {url}")
        response = self._responses.pop(0)
        response.raise_for_status()
        return response


def test_luci_json_rpc_backend_uses_session_verify_flag():
    session = FakeSession()
    backend = _LuciJsonRpcBackend("https://router/cgi-bin/luci/rpc", "root", "secret", verify=False, session=session)

    backend.login()

    assert session.calls[0]["url"] == "https://router/cgi-bin/luci/rpc/auth"
    assert session.calls[0]["verify"] is False


def test_ubus_backend_uses_session_verify_flag():
    session = FakeSession(
        [
            FakeResponse(result=[0, {"ubus_rpc_session": "token-1"}]),
        ]
    )
    backend = _UbusJsonRpcBackend("https://router/ubus", "root", "secret", verify=False, session=session)

    backend.login()

    assert session.calls[0]["url"] == "https://router/ubus"
    assert session.calls[0]["verify"] is False


def test_luci_json_rpc_backend_wraps_ssl_errors_with_cli_guidance():
    class SslFailSession(FakeSession):
        def post(self, url: str, json: dict, timeout: int):
            raise requests.exceptions.SSLError("self signed certificate")

    backend = _LuciJsonRpcBackend(
        "https://192.168.31.166/cgi-bin/luci/rpc",
        "root",
        "secret",
        verify=True,
        session=SslFailSession(),
    )

    try:
        backend.login()
        raise AssertionError("expected SSLError")
    except requests.exceptions.SSLError as error:
        message = str(error)
        assert "self signed certificate" in message
        assert "OPENCLASH_MANAGEMENT_SSL_VERIFY=0" in message
        assert "/cgi-bin/luci/rpc" in message


def test_luci_rpc_client_prefers_ubus_for_plain_host(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        (
            "[controller]\n"
            'url = "http://router:9090"\n'
            'secret = "controller-secret"\n\n'
            "[management]\n"
            'url = "https://router"\n'
            'username = "root"\n'
            'password = "secret"\n'
            "ssl_verify = false\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(config_path))
    monkeypatch.setattr(LuciRpcClient, "_should_use_local_backend", lambda self: False)

    session = FakeSession(
        [
            FakeResponse(result=[0, {"ubus_rpc_session": "token-1"}]),
            FakeResponse(result=[0, {"code": 0, "stdout": "openclash.config=config\n", "stderr": ""}]),
        ]
    )

    client = LuciRpcClient(session=session)
    uci = client.get_openclash_uci()

    assert client.backend_name == "ubus"
    assert uci == {"config": {".type": "config"}}
    assert session.calls[0]["url"] == "https://router/ubus"


def test_luci_rpc_client_falls_back_from_luci_rpc_to_ubus(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        (
            "[controller]\n"
            'url = "http://router:9090"\n'
            'secret = "controller-secret"\n\n'
            "[management]\n"
            'url = "https://router/cgi-bin/luci/rpc"\n'
            'username = "root"\n'
            'password = "secret"\n'
            "ssl_verify = false\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENCLASH_CLI_CONFIG", str(config_path))
    monkeypatch.setattr(LuciRpcClient, "_should_use_local_backend", lambda self: False)

    session = FakeSession(
        [
            FakeResponse(status_code=404),
            FakeResponse(result=[0, {"ubus_rpc_session": "token-1"}]),
            FakeResponse(result=[0, {"code": 0, "stdout": "openclash.foo=bar\n", "stderr": ""}]),
        ]
    )

    client = LuciRpcClient(session=session)
    uci = client.get_openclash_uci()

    assert client.backend_name == "ubus"
    assert uci == {"foo": {".type": "bar"}}
    assert session.calls[0]["url"] == "https://router/cgi-bin/luci/rpc/auth"
    assert session.calls[1]["url"] == "https://router/ubus"


def test_ubus_backend_returns_cli_error_for_permission_denied():
    session = FakeSession([FakeResponse(result=[6])])
    backend = _UbusJsonRpcBackend("https://router/ubus", "root", "secret", verify=False, session=session)

    with pytest.raises(CliError) as error:
        backend.login()

    assert error.value.code == "MANAGEMENT_AUTH_FAILED"
    assert error.value.details["backend"] == "ubus"
