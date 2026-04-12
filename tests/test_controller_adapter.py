from opclash_cli.adapters.controller import ControllerClient


class _Config:
    url = "http://127.0.0.1:9090"
    secret = ""


def test_controller_headers_omit_bearer_when_secret_empty():
    client = ControllerClient.__new__(ControllerClient)
    client._config = _Config()

    assert client.headers == {}
