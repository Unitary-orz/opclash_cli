from opclash_cli.local_config import AppConfig, ControllerConfig, ManagementConfig, load_config, save_config
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
        "management": {
            "url": config.management.url,
            "username": config.management.username,
            "password": mask_secret(config.management.password),
            "ssl_verify": config.management.ssl_verify,
        },
    }


def write_config(
    controller_url: str,
    controller_secret: str,
    management_url: str,
    management_username: str,
    management_password: str,
    management_ssl_verify: bool = True,
) -> dict:
    config = AppConfig(
        controller=ControllerConfig(url=controller_url, secret=controller_secret),
        management=ManagementConfig(
            url=management_url,
            username=management_username,
            password=management_password,
            ssl_verify=management_ssl_verify,
        ),
    )
    path = save_config(config)
    return {"config_path": str(path)}


def check_backends() -> dict:
    try:
        controller_ok = bool(ControllerClient().get_configs())
    except Exception:
        controller_ok = False
    management_backend = "unavailable"
    try:
        client = LuciRpcClient()
        management_ok = isinstance(client.get_openclash_uci(), dict)
        management_backend = getattr(client, "backend_name", "unknown")
    except Exception:
        management_ok = False
    return {
        "controller_ok": controller_ok,
        "management_ok": management_ok,
        "management_backend": management_backend,
    }
