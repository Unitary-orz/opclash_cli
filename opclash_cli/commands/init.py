from opclash_cli.local_config import (
    AppConfig,
    ControllerConfig,
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
    return {
        "controller": {
            "url": config.controller.url,
            "secret": mask_secret(config.controller.secret),
        },
        "router_local": {
            "recommended": True,
            "available": default_local_management_available(),
        },
    }


def write_config(
    controller_url: str,
    controller_secret: str,
) -> dict:
    config = AppConfig(
        controller=ControllerConfig(url=controller_url, secret=controller_secret),
    )
    path = save_config(config)
    return {
        "config_path": str(path),
        "controller_configured": True,
        "router_local_recommended": True,
        "router_local_available": default_local_management_available(),
        "recommended_mode": "router-local" if default_local_management_available() else "controller-only",
    }


def check_backends() -> dict:
    try:
        controller_ok = bool(ControllerClient().get_configs())
    except Exception:
        controller_ok = False

    if not default_local_management_available():
        return {
            "controller_ok": controller_ok,
            "router_local_ok": False,
            "router_local_backend": "unavailable",
        }

    try:
        client = LuciRpcClient()
        router_local_ok = isinstance(client.get_openclash_uci(), dict)
        router_local_backend = getattr(client, "backend_name", "unknown")
    except Exception:
        router_local_ok = False
        router_local_backend = "unavailable"

    return {
        "controller_ok": controller_ok,
        "router_local_ok": router_local_ok,
        "router_local_backend": router_local_backend,
    }
