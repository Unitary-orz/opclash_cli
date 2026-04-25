from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess

from opclash_cli.errors import CliError


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


def _router_local_guidance() -> CliError:
    return CliError(
        "LOCAL_ROUTER_REQUIRED",
        "This command must be run locally on the router.",
        {
            "recommended_mode": "router-local",
            "guidance": "Run this command directly on the OpenWrt/iStoreOS router where OpenClash is installed.",
        },
    )


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


class LuciRpcClient:
    def __init__(self, session=None) -> None:
        if self._should_use_local_backend():
            self._backend = _OpenWrtLocalBackend()
            self.backend_name = "local"
            self.backend_url = "local://openwrt"
            return
        raise _router_local_guidance()

    def _should_use_local_backend(self) -> bool:
        return os.geteuid() == 0 and shutil.which("uci") is not None

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
