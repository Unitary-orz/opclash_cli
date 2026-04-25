from pathlib import Path
from typing import Callable

from opclash_cli.adapters.luci_rpc import LuciRpcClient
from opclash_cli.errors import CliError
from opclash_cli.subscription_archive import archive_subscription
from opclash_cli import subscription_services as services


add_subscription_payload = services.add_subscription_payload
find_subscription = services.find_subscription
mask_subscription_address = services.mask_subscription_address
parse_subscription_userinfo = services.parse_subscription_userinfo
summarize_config_files = services.summarize_config_files
summarize_subscriptions = services.summarize_subscriptions
switch_config_payload = services.switch_config_payload


def __getattr__(name: str):
    if name.startswith("_") or name.startswith("STATUS_") or name.startswith("REASON_"):
        try:
            return getattr(services, name)
        except AttributeError:
            pass
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def list_subscriptions() -> dict:
    return {"subscriptions": summarize_subscriptions(LuciRpcClient().get_openclash_uci())}


def current_config() -> dict:
    payload = LuciRpcClient().get_openclash_uci()
    return {"config_path": payload["config"]["config_path"]}


def subscription_usage(name: str | None = None) -> dict:
    return services.SubscriptionUsageService(LuciRpcClient()).usage(name)


def add_subscription(name: str, url: str) -> dict:
    client = LuciRpcClient()
    section = client.add_uci_section("openclash", "config_subscribe")
    payload = add_subscription_payload(name, url)
    for option, value in payload.items():
        client.set_uci("openclash", section, option, value)
    client.commit_uci("openclash")
    return {"subscription": {"section": section, **payload}, "audit": None}


def _ensure_unique_subscription_name(subscriptions: list[dict], current_name: str, next_name: str) -> None:
    for subscription in subscriptions:
        if subscription["name"] == next_name and subscription["name"] != current_name:
            raise CliError("SUBSCRIPTION_NAME_CONFLICT", f"Subscription '{next_name}' already exists")


def _subscription_after_update(subscription: dict, **changes: object) -> dict:
    return {**subscription, **changes}


def remove_subscription(name: str) -> dict:
    client = LuciRpcClient()
    payload = client.get_openclash_uci()
    subscription = find_subscription(payload, name)
    archive = archive_subscription("remove", subscription)
    client.delete_uci_section("openclash", subscription["section"])
    client.commit_uci("openclash")
    return {"removed": subscription, "archive": archive, "audit": None}


def _set_subscription_enabled(name: str, enabled: bool) -> dict:
    client = LuciRpcClient()
    payload = client.get_openclash_uci()
    subscription = find_subscription(payload, name)
    before = subscription
    after = _subscription_after_update(subscription, enabled=enabled)
    if before["enabled"] != enabled:
        client.set_uci("openclash", subscription["section"], "enabled", "1" if enabled else "0")
        client.commit_uci("openclash")
    return {"before": before, "after": after, "audit": None}


def enable_subscription(name: str) -> dict:
    return _set_subscription_enabled(name, True)


def disable_subscription(name: str) -> dict:
    return _set_subscription_enabled(name, False)


def rename_subscription(name: str, new_name: str) -> dict:
    client = LuciRpcClient()
    payload = client.get_openclash_uci()
    subscriptions = summarize_subscriptions(payload)
    subscription = find_subscription(payload, name)
    _ensure_unique_subscription_name(subscriptions, subscription["name"], new_name)
    before = subscription
    after = _subscription_after_update(subscription, name=new_name)
    if subscription["name"] != new_name:
        client.set_uci("openclash", subscription["section"], "name", new_name)
        client.commit_uci("openclash")
    return {"before": before, "after": after, "audit": None}


def update_subscription(name: str | None, config: str | None, progress: Callable[[str], None] | None = None) -> dict:
    return services.SubscriptionUpdateService(LuciRpcClient(), progress=progress).update(name, config)


def _config_path_exists(client: LuciRpcClient, path: str) -> bool:
    return path in {entry.path for entry in client.list_config_files(str(Path(path).parent))}


def switch_config(path: str) -> dict:
    client = LuciRpcClient()
    if not _config_path_exists(client, path):
        raise CliError("CONFIG_NOT_FOUND", f"Config '{path}' was not found")

    payload = client.get_openclash_uci()
    current = payload["config"]["config_path"]
    if path == current:
        return {
            "before": {"config_path": current},
            "after": {"config_path": current},
            "changed": False,
            "message": "Target config is already active",
            "audit": None,
        }

    client.set_uci("openclash", "config", "config_path", switch_config_payload(path)["config_path"])
    client.commit_uci("openclash")
    client.service_exec("/etc/init.d/openclash reload")
    refreshed = client.get_openclash_uci()["config"]["config_path"]
    if refreshed != path:
        raise CliError(
            "VERIFY_FAILED",
            "Config switch did not take effect",
            {"expected": path, "actual": refreshed},
        )
    return {"before": {"config_path": current}, "after": {"config_path": refreshed}, "changed": True, "audit": None}


def config_files(directory: str) -> dict:
    entries = [
        {"path": entry.path, "size": entry.size, "mtime": entry.mtime}
        for entry in LuciRpcClient().list_config_files(directory)
    ]
    return {"configs": summarize_config_files(entries)}
