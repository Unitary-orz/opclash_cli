from opclash_cli.commands.init import check_backends
from opclash_cli.commands.nodes import groups as nodes_groups, providers as nodes_providers
from opclash_cli.commands.service import status as service_status
from opclash_cli.commands.subscription import current_config


def build_network_report(controller_ok: bool, luci_ok: bool, service_ok: bool) -> dict:
    status = "ok" if controller_ok and luci_ok and service_ok else "degraded"
    return {
        "status": status,
        "controller_ok": controller_ok,
        "luci_ok": luci_ok,
        "service_ok": service_ok,
    }


def network() -> dict:
    backends = check_backends()
    service = service_status()["service"]
    return {"network": build_network_report(backends["controller_ok"], backends["luci_ok"], service["running"])}


def runtime() -> dict:
    groups = nodes_groups()["groups"]
    providers = nodes_providers()["providers"]
    return {
        "runtime": {
            "groups_readable": True,
            "providers_readable": True,
            "group_count": len(groups),
            "provider_count": len(providers),
        }
    }


def config() -> dict:
    current = current_config()["config_path"]
    return {"config": {"current_path": current, "backends": check_backends()}}
