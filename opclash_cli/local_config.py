from dataclasses import dataclass
import os
from pathlib import Path
import tomllib


@dataclass
class ControllerConfig:
    url: str
    secret: str


@dataclass
class LuciConfig:
    url: str
    username: str
    password: str


@dataclass
class AppConfig:
    controller: ControllerConfig
    luci: LuciConfig


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
        f'url = "{config.luci.url}"\n'
        f'username = "{config.luci.username}"\n'
        f'password = "{config.luci.password}"\n'
    )


def save_config(config: AppConfig) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_config(config), encoding="utf-8")
    return path


def load_config() -> AppConfig:
    data = tomllib.loads(config_path().read_text(encoding="utf-8"))
    return AppConfig(
        controller=ControllerConfig(**data["controller"]),
        luci=LuciConfig(**data["luci"]),
    )


def config_exists() -> bool:
    return config_path().exists()
