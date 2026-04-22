from opclash_cli.adapters.luci_rpc import LuciRpcClient
from opclash_cli.errors import CliError


def summarize_subscriptions(payload: dict) -> list[dict]:
    result = []
    for section, item in payload.items():
        if item.get(".type") != "config_subscribe":
            continue
        result.append(
            {
                "section": section,
                "name": item.get("name", ""),
                "address": item.get("address", ""),
                "enabled": str(item.get("enabled", "0")) == "1",
            }
        )
    return result


def list_subscriptions() -> dict:
    return {"subscriptions": summarize_subscriptions(LuciRpcClient().get_openclash_uci())}


def current_config() -> dict:
    payload = LuciRpcClient().get_openclash_uci()
    return {"config_path": payload["config"]["config_path"]}


def add_subscription_payload(name: str, url: str) -> dict:
    return {"name": name, "address": url, "enabled": "1"}


def switch_config_payload(path: str) -> dict:
    return {"config_path": path}


def add_subscription(name: str, url: str, reason: str) -> dict:
    client = LuciRpcClient()
    section = client.add_uci_section("openclash", "config_subscribe")
    payload = add_subscription_payload(name, url)
    for option, value in payload.items():
        client.set_uci("openclash", section, option, value)
    client.commit_uci("openclash")
    return {
        "subscription": {"section": section, **payload},
        "audit": {"action": "subscription.add", "reason": reason},
    }


def switch_config(path: str, reason: str) -> dict:
    client = LuciRpcClient()
    payload = client.get_openclash_uci()
    current = payload["config"]["config_path"]
    if path == current:
        raise CliError("VERIFY_FAILED", "Target config is already active")
    client.set_uci("openclash", "config", "config_path", switch_config_payload(path)["config_path"])
    client.commit_uci("openclash")
    client.service_exec("/etc/init.d/openclash reload")
    refreshed = client.get_openclash_uci()["config"]["config_path"]
    return {
        "before": {"config_path": current},
        "after": {"config_path": refreshed},
        "audit": {"action": "subscription.switch", "reason": reason},
    }


def summarize_config_files(entries: list[dict], directory: str = "/etc/openclash/config") -> list[dict]:
    return [
        {
            "path": entry["path"],
            "size": entry["size"],
            "mtime": entry["mtime"],
        }
        for entry in entries
    ]


def config_files(directory: str) -> dict:
    entries = [
        {"path": entry.path, "size": entry.size, "mtime": entry.mtime}
        for entry in LuciRpcClient().list_config_files(directory)
    ]
    return {"configs": summarize_config_files(entries, directory)}
