from opclash_cli.adapters.controller import ControllerClient
from opclash_cli.errors import CliError


def summarize_groups(payload: dict) -> list[dict]:
    result = []
    for name, item in payload.get("proxies", {}).items():
        if "all" not in item or "now" not in item:
            continue
        result.append({"name": name, "selected": item["now"], "choices": item["all"]})
    return result


def summarize_providers(payload: dict) -> list[dict]:
    result = []
    for name, item in payload.get("providers", {}).items():
        result.append(
            {
                "name": name,
                "count": len(item.get("proxies", [])),
                "updated_at": item.get("updatedAt"),
            }
        )
    return result


def groups() -> dict:
    return {"groups": summarize_groups(ControllerClient().get_proxies())}


def providers() -> dict:
    return {"providers": summarize_providers(ControllerClient().get_providers())}


def build_group_detail(payload: dict, group_name: str) -> dict:
    item = payload.get("proxies", {}).get(group_name)
    if not item or "all" not in item or "now" not in item:
        raise CliError("GROUP_NOT_FOUND", f"Group '{group_name}' was not found")
    return {"name": group_name, "selected": item["now"], "choices": item["all"]}


def group(group_name: str) -> dict:
    payload = ControllerClient().get_proxies()
    return {"group": build_group_detail(payload, group_name)}


def switch_group(client: ControllerClient, group_name: str, target: str) -> dict:
    before = build_group_detail(client.get_proxies(), group_name)
    if target not in before["choices"]:
        raise CliError("NODE_NOT_FOUND", f"Node '{target}' is not available in group '{group_name}'")
    client.switch_proxy(group_name, target)
    after = build_group_detail(client.get_proxies(), group_name)
    return {"before": before, "after": after}


def switch(group_name: str, target: str) -> dict:
    client = ControllerClient()
    result = switch_group(client, group_name, target)
    result["audit"] = None
    return result
