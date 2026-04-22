import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import shlex
import shutil
import subprocess

import requests

from opclash_cli.local_config import load_config


@dataclass
class ConfigFileEntry:
    path: str
    size: int
    mtime: str


class _OpenWrtLocalBackend:
    def run(self, command: list[str]) -> str:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout

    def get_openclash_uci(self) -> dict:
        payload: dict[str, dict] = {}
        for line in self.run(["uci", "-q", "show", "openclash"]).splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            if not key.startswith("openclash."):
                continue
            section_and_option = key[len("openclash.") :]
            if "." in section_and_option:
                section, option = section_and_option.split(".", 1)
                payload.setdefault(section, {})[option] = raw_value.strip("'")
            else:
                payload.setdefault(section_and_option, {})[".type"] = raw_value.strip("'")
        return payload

    def service_exec(self, command: str) -> str:
        return self.run(["/bin/sh", "-c", command])

    def add_uci_section(self, config_name: str, section_type: str) -> str:
        return self.run(["uci", "add", config_name, section_type]).strip()

    def set_uci(self, config_name: str, section: str, option: str, value: str) -> bool:
        subprocess.run(
            ["uci", "set", f"{config_name}.{section}.{option}={value}"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True

    def commit_uci(self, config_name: str) -> bool:
        subprocess.run(["uci", "commit", config_name], check=True, capture_output=True, text=True)
        return True

    def read_file(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8", errors="replace")

    def list_config_files(self, directory: str) -> list[ConfigFileEntry]:
        entries = []
        for path in sorted(Path(directory).glob("*.yaml")):
            stat = path.stat()
            entries.append(
                ConfigFileEntry(
                    path=str(path),
                    size=stat.st_size,
                    mtime=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
                )
            )
        return entries


class _LuciJsonRpcBackend:
    def __init__(self, url: str, username: str, password: str, session: requests.Session | None = None) -> None:
        self._url = url
        self._username = username
        self._password = password
        self._session = session or requests.Session()
        self._token: str | None = None

    def login(self) -> str:
        response = self._session.post(
            f"{self._url}/auth",
            json={"id": 1, "method": "login", "params": [self._username, self._password]},
            timeout=10,
        )
        response.raise_for_status()
        self._token = response.json()["result"]
        return self._token

    def call(self, library: str, method: str, params: list[object]) -> object:
        token = self._token or self.login()
        response = self._session.post(
            f"{self._url}/{library}?auth={token}",
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

    def list_config_files(self, directory: str) -> list[ConfigFileEntry]:
        quoted = shlex.quote(directory)
        raw = self.service_exec(
            f"for f in {quoted}/*.yaml; do "
            f'[ -e "$f" ] || continue; '
            f'stat -c "%n|%s|%Y" "$f"; '
            f"done"
        )
        entries = []
        for line in raw.splitlines():
            parts = line.split("|")
            if len(parts) != 3:
                continue
            entries.append(
                ConfigFileEntry(
                    path=parts[0],
                    size=int(parts[1]),
                    mtime=datetime.fromtimestamp(int(parts[2]), timezone.utc).isoformat().replace("+00:00", "Z"),
                )
            )
        return entries


class LuciRpcClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        config = load_config().luci
        if self._should_use_local_backend():
            self._backend = _OpenWrtLocalBackend()
        else:
            self._backend = _LuciJsonRpcBackend(config.url, config.username, config.password, session=session)

    def _should_use_local_backend(self) -> bool:
        return os.geteuid() == 0 and shutil.which("uci") is not None

    def get_openclash_uci(self) -> dict:
        return self._backend.get_openclash_uci()

    def service_exec(self, command: str) -> str:
        return self._backend.service_exec(command)

    def add_uci_section(self, config_name: str, section_type: str) -> str:
        return self._backend.add_uci_section(config_name, section_type)

    def set_uci(self, config_name: str, section: str, option: str, value: str) -> bool:
        return self._backend.set_uci(config_name, section, option, value)

    def commit_uci(self, config_name: str) -> bool:
        return self._backend.commit_uci(config_name)

    def read_file(self, path: str) -> str:
        return self._backend.read_file(path)

    def list_config_files(self, directory: str) -> list[ConfigFileEntry]:
        return self._backend.list_config_files(directory)
