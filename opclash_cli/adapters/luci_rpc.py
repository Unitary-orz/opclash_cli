import base64
import subprocess
from urllib.parse import urlparse

import requests

from opclash_cli.local_config import load_config


class LuciRpcClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._config = load_config().luci
        self._session = session or requests.Session()
        self._token: str | None = None
        self._parsed_url = urlparse(self._config.url)

    @property
    def _request_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {"timeout": 10}
        # iStoreOS/OpenWrt commonly serves LuCI only via local self-signed HTTPS.
        if self._parsed_url.scheme == "https":
            kwargs["verify"] = False
        return kwargs

    def _uses_local_backend(self) -> bool:
        return self._parsed_url.scheme == "local"

    def _uses_ubus(self) -> bool:
        return self._parsed_url.path.rstrip("/") == "/ubus"

    def _run_local(self, command: list[str]) -> str:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return result.stdout

    def _parse_uci_show(self, raw: str) -> dict:
        payload: dict[str, dict[str, object]] = {}
        for line in raw.splitlines():
            if "=" not in line or "." not in line:
                continue
            left, right = line.split("=", 1)
            _, remainder = left.split(".", 1)
            if "." in remainder:
                section, option = remainder.split(".", 1)
                payload.setdefault(section, {})[option] = right.strip().strip("'")
                continue
            payload.setdefault(remainder, {})[".type"] = right.strip().strip("'")
        return payload

    def login(self) -> str:
        if self._uses_local_backend():
            self._token = "local"
            return self._token

        if self._uses_ubus():
            response = self._session.post(
                self._config.url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "call",
                    "params": ["00000000000000000000000000000000", "session", "login", {"username": self._config.username, "password": self._config.password}],
                },
                **self._request_kwargs,
            )
            response.raise_for_status()
            self._token = response.json()["result"][1]["ubus_rpc_session"]
            return self._token

        response = self._session.post(
            f"{self._config.url}/auth",
            json={"id": 1, "method": "login", "params": [self._config.username, self._config.password]},
            **self._request_kwargs,
        )
        response.raise_for_status()
        self._token = response.json()["result"]
        return self._token

    def call(self, library: str, method: str, params: list[object]) -> object:
        token = self._token or self.login()
        if self._uses_local_backend():
            if library == "uci" and method == "get_all":
                return self._parse_uci_show(self._run_local(["uci", "show", str(params[0])]))
            if library == "uci" and method == "add":
                return self._run_local(["uci", "add", str(params[0]), str(params[1])]).strip()
            if library == "uci" and method == "set":
                self._run_local(["uci", "set", f"{params[0]}.{params[1]}.{params[2]}={params[3]}"])
                return True
            if library == "uci" and method == "commit":
                self._run_local(["uci", "commit", str(params[0])])
                return True
            if library == "sys" and method == "exec":
                return self._run_local(["/bin/sh", "-c", str(params[0])])
            if library == "fs" and method == "readfile":
                return base64.b64encode(self._run_local(["/bin/cat", str(params[0])]).encode("utf-8")).decode("ascii")
            raise ValueError(f"Unsupported local backend call: {library}.{method}")

        if self._uses_ubus():
            ubus_object = {"sys": "file", "fs": "file"}.get(library, library)
            ubus_method = {"exec": "exec", "readfile": "read"}.get(method, method)
            ubus_params: object
            if ubus_object == "uci":
                if method == "get_all":
                    ubus_method = "get"
                    ubus_params = {"config": params[0]}
                elif method == "add":
                    ubus_params = {"config": params[0], "type": params[1]}
                elif method == "set":
                    ubus_params = {
                        "config": params[0],
                        "section": params[1],
                        "values": {params[2]: params[3]},
                    }
                elif method == "commit":
                    ubus_params = {"config": params[0]}
                else:
                    ubus_params = params
            elif ubus_object == "file" and ubus_method == "exec":
                ubus_params = {"command": "/bin/sh", "params": ["-lc", str(params[0])]}
            elif ubus_object == "file" and ubus_method == "read":
                ubus_params = {"path": str(params[0]), "base64": True}
            else:
                ubus_params = params

            response = self._session.post(
                self._config.url,
                json={"jsonrpc": "2.0", "id": 1, "method": "call", "params": [token, ubus_object, ubus_method, ubus_params]},
                **self._request_kwargs,
            )
            response.raise_for_status()
            result = response.json()["result"][1]
            if ubus_object == "file" and ubus_method == "exec":
                return result.get("stdout", "")
            if ubus_object == "file" and ubus_method == "read":
                return result.get("data", "")
            if ubus_object == "uci" and method == "add":
                return result.get("section")
            return result

        response = self._session.post(
            f"{self._config.url}/{library}?auth={token}",
            json={"id": 1, "method": method, "params": params},
            **self._request_kwargs,
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
