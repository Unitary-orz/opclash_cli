from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tomllib


@dataclass
class ControllerConfig:
    url: str
    secret: str


@dataclass
class AppConfig:
    controller: ControllerConfig


def default_local_management_available() -> bool:
    return os.geteuid() == 0 and shutil.which("uci") is not None


def config_path() -> Path:
    override = os.environ.get("OPENCLASH_CLI_CONFIG")
    if override:
        return Path(override)
    return Path.home() / ".config" / "opclash_cli" / "config.toml"


def _dump_config(config: AppConfig) -> str:
    return (
        "[controller]\n"
        f'url = "{config.controller.url}"\n'
        f'secret = "{config.controller.secret}"\n'
    )


def save_config(config: AppConfig) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_config(config), encoding="utf-8")
    return path


def load_config() -> AppConfig:
    data = tomllib.loads(config_path().read_text(encoding="utf-8"))
    return AppConfig(controller=ControllerConfig(**data["controller"]))


def config_exists() -> bool:
    return config_path().exists()
