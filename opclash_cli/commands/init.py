from opclash_cli.local_config import AppConfig, ControllerConfig, LuciConfig, load_config, save_config
from opclash_cli.adapters.controller import ControllerClient
from opclash_cli.adapters.luci_rpc import LuciRpcClient


def mask_secret(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]


def show_config() -> dict:
    config = load_config()
    return {
        "controller": {
            "url": config.controller.url,
            "secret": mask_secret(config.controller.secret),
        },
        "luci": {
            "url": config.luci.url,
            "username": config.luci.username,
            "password": mask_secret(config.luci.password),
        },
    }


def write_config(
    controller_url: str,
    controller_secret: str,
    luci_url: str,
    luci_username: str,
    luci_password: str,
) -> dict:
    config = AppConfig(
        controller=ControllerConfig(url=controller_url, secret=controller_secret),
        luci=LuciConfig(url=luci_url, username=luci_username, password=luci_password),
    )
    path = save_config(config)
    return {"config_path": str(path)}


def check_backends() -> dict:
    try:
        controller_ok = bool(ControllerClient().get_configs())
    except Exception:
        controller_ok = False
    try:
        luci_ok = isinstance(LuciRpcClient().get_openclash_uci(), dict)
    except Exception:
        luci_ok = False
    return {"controller_ok": controller_ok, "luci_ok": luci_ok}
