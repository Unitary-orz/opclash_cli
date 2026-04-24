from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tomllib
from urllib.parse import urlsplit, urlunsplit


@dataclass
class ControllerConfig:
    url: str
    secret: str


@dataclass
class ManagementConfig:
    url: str
    username: str
    password: str
    ssl_verify: bool = True


@dataclass
class AppConfig:
    controller: ControllerConfig
    management: ManagementConfig | None = None


def _env_bool(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def normalize_management_url(url: str) -> str:
    if url.startswith("local://"):
        return url
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/")
    if not path:
        path = ""
    elif path.endswith("/cgi-bin/luci/rpc"):
        path = "/cgi-bin/luci/rpc"
    elif path.endswith("/cgi-bin/luci"):
        path = "/cgi-bin/luci"
    elif path.endswith("/ubus"):
        path = "/ubus"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def default_local_management_available() -> bool:
    return os.geteuid() == 0 and shutil.which("uci") is not None


def config_path() -> Path:
    override = os.environ.get("OPENCLASH_CLI_CONFIG")
    if override:
        return Path(override)
    return Path.home() / ".config" / "opclash_cli" / "config.toml"


def _dump_config(config: AppConfig) -> str:
    payload = (
        "[controller]\n"
        f'url = "{config.controller.url}"\n'
        f'secret = "{config.controller.secret}"\n\n'
    )
    if config.management is None:
        return payload
    return (
        payload
        + "[management]\n"
        + f'url = "{normalize_management_url(config.management.url)}"\n'
        + f'username = "{config.management.username}"\n'
        + f'password = "{config.management.password}"\n'
        + f"ssl_verify = {'true' if config.management.ssl_verify else 'false'}\n"
    )


def save_config(config: AppConfig) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_config(config), encoding="utf-8")
    return path


def load_config() -> AppConfig:
    data = tomllib.loads(config_path().read_text(encoding="utf-8"))
    management = None
    if "management" in data:
        management_data = dict(data["management"])
        management_data["url"] = normalize_management_url(management_data["url"])
        if "ssl_verify" not in management_data:
            management_data["ssl_verify"] = True
        env_ssl_verify = _env_bool("OPENCLASH_MANAGEMENT_SSL_VERIFY")
        if env_ssl_verify is not None:
            management_data["ssl_verify"] = env_ssl_verify
        management = ManagementConfig(**management_data)
    return AppConfig(
        controller=ControllerConfig(**data["controller"]),
        management=management,
    )


def config_exists() -> bool:
    return config_path().exists()
