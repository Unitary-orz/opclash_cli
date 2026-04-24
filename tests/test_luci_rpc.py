import requests

from opclash_cli.adapters.luci_rpc import _LuciJsonRpcBackend


class FakeResponse:
    def __init__(self, result: object = None) -> None:
        self._result = result if result is not None else "token-1"

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"result": self._result}


class FakeSession:
    def __init__(self) -> None:
        self.verify = True
        self.calls = []

    def post(self, url: str, json: dict, timeout: int):
        self.calls.append({"url": url, "json": json, "timeout": timeout, "verify": self.verify})
        return FakeResponse()


def test_luci_json_rpc_backend_uses_session_verify_flag():
    session = FakeSession()
    backend = _LuciJsonRpcBackend("https://router/cgi-bin/luci/rpc", "root", "secret", verify=False, session=session)

    backend.login()

    assert session.calls[0]["url"] == "https://router/cgi-bin/luci/rpc/auth"
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
        assert "OPENCLASH_LUCI_SSL_VERIFY=0" in message
        assert "/cgi-bin/luci/rpc" in message
