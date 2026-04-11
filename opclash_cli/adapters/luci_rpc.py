import base64

import requests

from opclash_cli.local_config import load_config


class LuciRpcClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._config = load_config().luci
        self._session = session or requests.Session()
        self._token: str | None = None

    def login(self) -> str:
        response = self._session.post(
            f"{self._config.url}/auth",
            json={"id": 1, "method": "login", "params": [self._config.username, self._config.password]},
            timeout=10,
        )
        response.raise_for_status()
        self._token = response.json()["result"]
        return self._token

    def call(self, library: str, method: str, params: list[object]) -> object:
        token = self._token or self.login()
        response = self._session.post(
            f"{self._config.url}/{library}?auth={token}",
            json={"id": 1, "method": method, "params": params},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["result"]

    def get_openclash_uci(self) -> dict:
        return self.call("uci", "get_all", ["openclash"])

    def service_exec(self, command: str) -> str:
        return self.call("sys", "exec", [command])

    def add_uci_section(self, config_name: str, section_type: str) -> str:
        return self.call("uci", "add", [config_name, section_type])

    def set_uci(self, config_name: str, section: str, option: str, value: str) -> bool:
        return self.call("uci", "set", [config_name, section, option, value])

    def commit_uci(self, config_name: str) -> bool:
        return self.call("uci", "commit", [config_name])

    def read_file(self, path: str) -> str:
        encoded = self.call("fs", "readfile", [path])
        return base64.b64decode(encoded).decode("utf-8", errors="replace")
