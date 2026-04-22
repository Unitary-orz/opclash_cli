from concurrent.futures import ThreadPoolExecutor, as_completed

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


def _is_real_proxy(item: dict) -> bool:
    name = item.get("name", "")
    if not name:
        return False
    if "all" in item:
        return False
    if item.get("type") in {"Direct", "Reject"}:
        return False
    if name.startswith(("Traffic:", "Expire:")):
        return False
    return True


def _real_proxy_names(payload: dict) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for provider in payload.get("providers", {}).values():
        for item in provider.get("proxies", []):
            name = item.get("name")
            if name in seen or not _is_real_proxy(item):
                continue
            seen.add(name)
            names.append(name)
    return names


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


def speedtest(group_name: str | None, limit: int, test_url: str, timeout_ms: int) -> dict:
    client = ControllerClient()
    providers = client.get_providers()
    candidates = _real_proxy_names(providers)

    if group_name is not None:
        payload = client.get_proxies()
        group_detail = build_group_detail(payload, group_name)
        candidate_set = set(candidates)
        candidates = [name for name in group_detail["choices"] if name in candidate_set]

    def _run(name: str) -> dict | None:
        try:
            result = client.proxy_delay(name, test_url, timeout_ms)
        except Exception:
            return None
        if result is None:
            return None
        delay = result.get("delay")
        if not isinstance(delay, int) or delay <= 0:
            return None
        return {"name": name, "delay_ms": delay}

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(_run, name) for name in candidates]
        for future in as_completed(futures):
            item = future.result()
            if item is not None:
                results.append(item)

    results.sort(key=lambda item: item["delay_ms"])
    return {
        "tested": len(candidates),
        "ok": len(results),
        "results": results[:limit],
    }
