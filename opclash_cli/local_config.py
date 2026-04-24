from dataclasses import dataclass
import os
from pathlib import Path
import tomllib
from urllib.parse import urlsplit, urlunsplit


@dataclass
class ControllerConfig:
    url: str
    secret: str


@dataclass
class LuciConfig:
    url: str
    username: str
    password: str
    ssl_verify: bool = True


@dataclass
class AppConfig:
    controller: ControllerConfig
    luci: LuciConfig


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


def normalize_luci_rpc_url(url: str) -> str:
    if url.startswith("local://"):
        return url
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/")
    if not path:
        path = "/cgi-bin/luci/rpc"
    elif path == "/cgi-bin/luci":
        path = "/cgi-bin/luci/rpc"
    elif path.endswith("/cgi-bin/luci/rpc"):
        path = path
    elif path.endswith("/cgi-bin/luci"):
        path = f"{path}/rpc"
    else:
        path = f"{path}/cgi-bin/luci/rpc"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def config_path() -> Path:
    override = os.environ.get("OPENCLASH_CLI_CONFIG")
    if override:
        return Path(override)
    return Path.home() / ".config" / "opclash_cli" / "config.toml"


def _dump_config(config: AppConfig) -> str:
    return (
        "[controller]\n"
        f'url = "{config.controller.url}"\n'
        f'secret = "{config.controller.secret}"\n\n'
        "[luci]\n"
        f'url = "{normalize_luci_rpc_url(config.luci.url)}"\n'
        f'username = "{config.luci.username}"\n'
        f'password = "{config.luci.password}"\n'
        f"ssl_verify = {'true' if config.luci.ssl_verify else 'false'}\n"
    )


def save_config(config: AppConfig) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_config(config), encoding="utf-8")
    return path


def load_config() -> AppConfig:
    data = tomllib.loads(config_path().read_text(encoding="utf-8"))
    luci_data = dict(data["luci"])
    luci_data["url"] = normalize_luci_rpc_url(luci_data["url"])
    if "ssl_verify" not in luci_data:
        luci_data["ssl_verify"] = True
    env_ssl_verify = _env_bool("OPENCLASH_LUCI_SSL_VERIFY")
    if env_ssl_verify is not None:
        luci_data["ssl_verify"] = env_ssl_verify
    return AppConfig(
        controller=ControllerConfig(**data["controller"]),
        luci=LuciConfig(**luci_data),
    )


def config_exists() -> bool:
    return config_path().exists()
