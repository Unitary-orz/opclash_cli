import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import shlex
import shutil
import subprocess
from urllib.parse import urlsplit, urlunsplit

import requests

from opclash_cli.errors import CliError
from opclash_cli.local_config import load_config


@dataclass
class ConfigFileEntry:
    path: str
    size: int
    mtime: str


def _parse_uci_show(raw: str) -> dict:
    payload: dict[str, dict] = {}
    for line in raw.splitlines():
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


def _wrap_ssl_error(error: requests.exceptions.SSLError) -> requests.exceptions.SSLError:
    return requests.exceptions.SSLError(
        f"{error}. OpenWrt management endpoints often live at /ubus or /cgi-bin/luci/rpc. "
        "If your router uses a self-signed certificate, set "
        "OPENCLASH_MANAGEMENT_SSL_VERIFY=0 or re-run init with --management-insecure."
    )


def _management_guidance(code: str, message: str, details: dict | None = None) -> CliError:
    payload = {
        "recommended_mode": "local-management",
        "guidance": "This command is best run locally on the router, or configure advanced remote management explicitly.",
    }
    if details:
        payload.update(details)
    return CliError(code, message, payload)


def _candidate_backends(url: str) -> list[tuple[str, str]]:
    parsed = urlsplit(url)
    origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    path = parsed.path.rstrip("/")
    candidates: list[tuple[str, str]] = []

    def add(name: str, candidate_url: str) -> None:
        entry = (name, candidate_url)
        if entry not in candidates:
            candidates.append(entry)

    if not path:
        add("ubus", f"{origin}/ubus")
        add("luci_rpc", f"{origin}/cgi-bin/luci/rpc")
        return candidates
    if path.endswith("/ubus"):
        add("ubus", urlunsplit((parsed.scheme, parsed.netloc, "/ubus", parsed.query, parsed.fragment)))
        add("luci_rpc", f"{origin}/cgi-bin/luci/rpc")
        return candidates
    if path.endswith("/cgi-bin/luci/rpc"):
        add("luci_rpc", urlunsplit((parsed.scheme, parsed.netloc, "/cgi-bin/luci/rpc", parsed.query, parsed.fragment)))
        add("ubus", f"{origin}/ubus")
        return candidates
    if path.endswith("/cgi-bin/luci"):
        add("luci_rpc", urlunsplit((parsed.scheme, parsed.netloc, "/cgi-bin/luci/rpc", parsed.query, parsed.fragment)))
        add("ubus", f"{origin}/ubus")
        return candidates
    add("ubus", f"{origin}/ubus")
    add("luci_rpc", url)
    return candidates


class _OpenWrtLocalBackend:
    def run(self, command: list[str], timeout: int | None = None) -> str:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return completed.stdout

    def get_openclash_uci(self) -> dict:
        return _parse_uci_show(self.run(["uci", "-q", "show", "openclash"]))

    def service_exec(self, command: str, timeout: int | None = None) -> str:
        return self.run(["/bin/sh", "-c", command], timeout=timeout)

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

    def delete_uci_section(self, config_name: str, section: str) -> bool:
        subprocess.run(["uci", "delete", f"{config_name}.{section}"], check=True, capture_output=True, text=True)
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

    def update_subscription(self, target: str | None = None) -> str:
        command = ["/usr/share/openclash/openclash.sh"]
        if target:
            command.append(target)
        return self.run(command, timeout=300)


class _LuciJsonRpcBackend:
    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        verify: bool = True,
        session: requests.Session | None = None,
    ) -> None:
        self._url = url
        self._username = username
        self._password = password
        self._session = session or requests.Session()
        self._session.verify = verify
        self._token: str | None = None

    def login(self) -> str:
        try:
            response = self._session.post(
                f"{self._url}/auth",
                json={"id": 1, "method": "login", "params": [self._username, self._password]},
                timeout=10,
            )
        except requests.exceptions.SSLError as error:
            raise _wrap_ssl_error(error) from error
        response.raise_for_status()
        self._token = response.json()["result"]
        return self._token

    def call(self, library: str, method: str, params: list[object], timeout: int = 10) -> object:
        token = self._token or self.login()
        response = self._session.post(
            f"{self._url}/{library}?auth={token}",
            json={"id": 1, "method": method, "params": params},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()["result"]

    def get_openclash_uci(self) -> dict:
        return self.call("uci", "get_all", ["openclash"])

    def service_exec(self, command: str, timeout: int = 10) -> str:
        return self.call("sys", "exec", [command], timeout=timeout)

    def add_uci_section(self, config_name: str, section_type: str) -> str:
        return self.call("uci", "add", [config_name, section_type])

    def set_uci(self, config_name: str, section: str, option: str, value: str) -> bool:
        return self.call("uci", "set", [config_name, section, option, value])

    def commit_uci(self, config_name: str) -> bool:
        return self.call("uci", "commit", [config_name])

    def delete_uci_section(self, config_name: str, section: str) -> bool:
        return self.call("uci", "delete", [config_name, section])

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

    def update_subscription(self, target: str | None = None) -> str:
        command = "/usr/share/openclash/openclash.sh"
        if target:
            command = f"{command} {shlex.quote(target)}"
        return self.service_exec(command, timeout=300)


class _UbusJsonRpcBackend:
    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        verify: bool = True,
        session: requests.Session | None = None,
    ) -> None:
        self._url = url
        self._username = username
        self._password = password
        self._session = session or requests.Session()
        self._session.verify = verify
        self._token: str | None = None

    def login(self) -> str:
        try:
            response = self._session.post(
                self._url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "call",
                    "params": [
                        "00000000000000000000000000000000",
                        "session",
                        "login",
                        {"username": self._username, "password": self._password},
                    ],
                },
                timeout=10,
            )
        except requests.exceptions.SSLError as error:
            raise _wrap_ssl_error(error) from error
        response.raise_for_status()
        result = response.json()["result"]
        if not isinstance(result, list) or not result:
            raise _management_guidance(
                "MANAGEMENT_UNAVAILABLE",
                "Remote management returned an unexpected ubus login response.",
                {"backend": "ubus"},
            )
        if result[0] != 0:
            raise _management_guidance(
                "MANAGEMENT_AUTH_FAILED",
                "Remote management login was denied.",
                {"backend": "ubus", "status": result[0]},
            )
        if len(result) < 2 or "ubus_rpc_session" not in result[1]:
            raise _management_guidance(
                "MANAGEMENT_UNAVAILABLE",
                "Remote management did not return a usable ubus session.",
                {"backend": "ubus"},
            )
        self._token = result[1]["ubus_rpc_session"]
        return self._token

    def call(self, object_name: str, method: str, params: dict[str, object] | None = None, timeout: int = 10) -> dict:
        token = self._token or self.login()
        response = self._session.post(
            self._url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "call",
                "params": [token, object_name, method, params or {}],
            },
            timeout=timeout,
        )
        response.raise_for_status()
        result = response.json()["result"]
        if not isinstance(result, list) or len(result) != 2:
            raise RuntimeError("unexpected ubus response payload")
        if result[0] != 0:
            raise RuntimeError(f"ubus call failed with code {result[0]}")
        return result[1]

    def get_openclash_uci(self) -> dict:
        return _parse_uci_show(self.service_exec("uci -q show openclash"))

    def service_exec(self, command: str, timeout: int = 10) -> str:
        result = self.call(
            "file",
            "exec",
            {"command": "/bin/sh", "params": ["-c", command]},
            timeout=timeout,
        )
        if result.get("code", 0) != 0:
            stderr = str(result.get("stderr", "")).strip()
            raise RuntimeError(stderr or f"remote command failed: {command}")
        return str(result.get("stdout", ""))

    def add_uci_section(self, config_name: str, section_type: str) -> str:
        return self.service_exec(
            f"uci add {shlex.quote(config_name)} {shlex.quote(section_type)}"
        ).strip()

    def set_uci(self, config_name: str, section: str, option: str, value: str) -> bool:
        self.service_exec(
            "uci set "
            f"{shlex.quote(config_name)}.{shlex.quote(section)}.{shlex.quote(option)}="
            f"{shlex.quote(value)}"
        )
        return True

    def commit_uci(self, config_name: str) -> bool:
        self.service_exec(f"uci commit {shlex.quote(config_name)}")
        return True

    def delete_uci_section(self, config_name: str, section: str) -> bool:
        self.service_exec(f"uci delete {shlex.quote(config_name)}.{shlex.quote(section)}")
        return True

    def read_file(self, path: str) -> str:
        encoded = self.service_exec(f"base64 {shlex.quote(path)}")
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

    def update_subscription(self, target: str | None = None) -> str:
        command = "/usr/share/openclash/openclash.sh"
        if target:
            command = f"{command} {shlex.quote(target)}"
        return self.service_exec(command, timeout=300)


class LuciRpcClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        config = load_config().management
        if self._should_use_local_backend():
            self._backend = _OpenWrtLocalBackend()
            self.backend_name = "local"
            self.backend_url = config.url if config is not None else "local://openwrt"
        else:
            if config is None:
                raise _management_guidance(
                    "MANAGEMENT_NOT_CONFIGURED",
                    "Remote management is not configured.",
                )
            self._backend, self.backend_name, self.backend_url = self._select_remote_backend(config, session)

    def _should_use_local_backend(self) -> bool:
        return os.geteuid() == 0 and shutil.which("uci") is not None

    def _select_remote_backend(self, config, session: requests.Session | None):
        last_error: Exception | None = None
        attempts: list[dict] = []
        auth_error: CliError | None = None
        for backend_name, candidate_url in _candidate_backends(config.url):
            if backend_name == "ubus":
                backend = _UbusJsonRpcBackend(
                    candidate_url,
                    config.username,
                    config.password,
                    verify=config.ssl_verify,
                    session=session,
                )
            else:
                backend = _LuciJsonRpcBackend(
                    candidate_url,
                    config.username,
                    config.password,
                    verify=config.ssl_verify,
                    session=session,
                )
            try:
                backend.login()
                return backend, backend_name, candidate_url
            except CliError as error:
                last_error = error
                attempts.append({"backend": backend_name, "url": candidate_url, "code": error.code})
                if error.code == "MANAGEMENT_AUTH_FAILED" and auth_error is None:
                    auth_error = error
                continue
            except requests.exceptions.SSLError:
                raise
            except requests.exceptions.HTTPError as error:
                last_error = error
                status_code = getattr(error.response, "status_code", None)
                attempts.append({"backend": backend_name, "url": candidate_url, "http_status": status_code})
                if status_code in {404, 405}:
                    continue
                continue
            except (KeyError, ValueError, RuntimeError, requests.exceptions.RequestException) as error:
                last_error = error
                attempts.append({"backend": backend_name, "url": candidate_url, "error": type(error).__name__})
                continue
        if auth_error is not None:
            raise _management_guidance(
                auth_error.code,
                auth_error.message,
                {"attempts": attempts},
            )
        if last_error is not None:
            raise _management_guidance(
                "MANAGEMENT_UNAVAILABLE",
                "Remote management is unavailable.",
                {"attempts": attempts, "last_error": type(last_error).__name__},
            )
        raise _management_guidance(
            "MANAGEMENT_UNAVAILABLE",
            "No usable OpenWrt management backend was found.",
            {"attempts": attempts},
        )

    def get_openclash_uci(self) -> dict:
        return self._backend.get_openclash_uci()

    def service_exec(self, command: str, timeout: int = 10) -> str:
        return self._backend.service_exec(command, timeout=timeout)

    def add_uci_section(self, config_name: str, section_type: str) -> str:
        return self._backend.add_uci_section(config_name, section_type)

    def set_uci(self, config_name: str, section: str, option: str, value: str) -> bool:
        return self._backend.set_uci(config_name, section, option, value)

    def commit_uci(self, config_name: str) -> bool:
        return self._backend.commit_uci(config_name)

    def delete_uci_section(self, config_name: str, section: str) -> bool:
        return self._backend.delete_uci_section(config_name, section)

    def read_file(self, path: str) -> str:
        return self._backend.read_file(path)

    def list_config_files(self, directory: str) -> list[ConfigFileEntry]:
        return self._backend.list_config_files(directory)

    def update_subscription(self, target: str | None = None) -> str:
        return self._backend.update_subscription(target)
