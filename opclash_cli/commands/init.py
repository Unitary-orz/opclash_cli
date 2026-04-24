from opclash_cli.local_config import (
    AppConfig,
    ControllerConfig,
    ManagementConfig,
    default_local_management_available,
    load_config,
    save_config,
)
from opclash_cli.adapters.controller import ControllerClient
from opclash_cli.adapters.luci_rpc import LuciRpcClient


def mask_secret(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]


def show_config() -> dict:
    config = load_config()
    payload = {
        "controller": {
            "url": config.controller.url,
            "secret": mask_secret(config.controller.secret),
        },
    }
    if config.management is None:
        payload["management"] = {"configured": False}
        return payload
    payload["management"] = {
        "configured": True,
        "mode": "local" if config.management.url.startswith("local://") else "remote",
        "url": config.management.url,
        "username": config.management.username,
        "password": mask_secret(config.management.password),
        "ssl_verify": config.management.ssl_verify,
    }
    return payload


def write_config(
    controller_url: str,
    controller_secret: str,
    management_url: str | None,
    management_username: str | None,
    management_password: str | None,
    management_ssl_verify: bool = True,
) -> dict:
    management = None
    if management_url:
        management = ManagementConfig(
            url=management_url,
            username=management_username or "",
            password=management_password or "",
            ssl_verify=management_ssl_verify,
        )
    elif default_local_management_available():
        management = ManagementConfig(
            url="local://openwrt",
            username="",
            password="",
            ssl_verify=True,
        )
    config = AppConfig(
        controller=ControllerConfig(url=controller_url, secret=controller_secret),
        management=management,
    )
    path = save_config(config)
    if management is None:
        recommended_mode = "controller-only"
        management_mode = None
    elif management.url.startswith("local://"):
        recommended_mode = "local-management"
        management_mode = "local"
    else:
        recommended_mode = "remote-management-advanced"
        management_mode = "remote"
    return {
        "config_path": str(path),
        "controller_configured": True,
        "management_configured": management is not None,
        "management_mode": management_mode,
        "recommended_mode": recommended_mode,
    }


def check_backends() -> dict:
    try:
        controller_ok = bool(ControllerClient().get_configs())
    except Exception:
        controller_ok = False
    config = load_config()
    management_backend = "unconfigured" if config.management is None else "unavailable"
    if config.management is None and not default_local_management_available():
        return {
            "controller_ok": controller_ok,
            "management_ok": False,
            "management_backend": management_backend,
        }
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
