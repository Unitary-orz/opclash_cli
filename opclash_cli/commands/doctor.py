from collections import Counter
from datetime import datetime, timedelta, timezone
import re

from opclash_cli.adapters.controller import ControllerClient
from opclash_cli.commands.init import check_backends
from opclash_cli.commands.nodes import groups as nodes_groups, providers as nodes_providers
from opclash_cli.commands.service import status as service_status
from opclash_cli.adapters.luci_rpc import LuciRpcClient
from opclash_cli.errors import CliError
from opclash_cli.commands.subscription import current_config
from opclash_cli.operation_log import read_operations


def build_network_report(controller_ok: bool, router_local_ok: bool, service_ok: bool) -> dict:
    status = "ok" if controller_ok and router_local_ok and service_ok else "degraded"
    return {
        "status": status,
        "controller_ok": controller_ok,
        "router_local_ok": router_local_ok,
        "service_ok": service_ok,
    }


def network() -> dict:
    backends = check_backends()
    service = service_status()["service"]
    return {"network": build_network_report(backends["controller_ok"], backends["router_local_ok"], service["running"])}


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


def logs(limit: int = 20) -> dict:
    return {"logs": read_operations(limit)["items"], "limit": limit}


_PLACEHOLDER_PREFIXES = ("Traffic:", "Expire:")
_USING_RE = re.compile(r" using ([^\[]+)\[(.+)\]$")
_DIAL_RE = re.compile(r"\] dial ([^(]+) \(")
_OUTER_RE = re.compile(r'time="([^"]+)" level=([a-z]+) msg="(.*)"')


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_since(value: str) -> timedelta:
    raw = value.strip().lower()
    if not raw:
        raise CliError("INVALID_SINCE", "Time window must not be empty.")
    unit = raw[-1]
    number = raw[:-1] if unit.isalpha() else raw
    if not number.isdigit():
        raise CliError("INVALID_SINCE", "Time window must be an integer optionally followed by m, h, or d.", {"since": value})
    amount = int(number)
    if amount <= 0:
        raise CliError("INVALID_SINCE", "Time window must be greater than zero.", {"since": value})
    if unit == "m" or not raw[-1].isalpha():
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    raise CliError("INVALID_SINCE", "Unsupported time window suffix.", {"since": value})


def _is_selector(item: dict) -> bool:
    return "all" in item and "now" in item


def _is_usable_choice(name: str, payload: dict) -> bool:
    if name.startswith(_PLACEHOLDER_PREFIXES):
        return False
    item = payload.get("proxies", {}).get(name, {})
    if item.get("type") in {"Direct", "Reject"}:
        return False
    return True


def _selector_names(payload: dict) -> set[str]:
    return {name for name, item in payload.get("proxies", {}).items() if _is_selector(item)}


def _selector_order(payload: dict) -> list[str]:
    return [name for name, item in payload.get("proxies", {}).items() if _is_selector(item)]


def _resolve_chain(payload: dict, start: str) -> list[str]:
    proxies = payload.get("proxies", {})
    chain = [start]
    visited = {start}
    current = start
    while True:
        item = proxies.get(current, {})
        if not _is_selector(item):
            return chain
        selected = item.get("now")
        if not isinstance(selected, str) or not selected or selected in visited:
            return chain
        chain.append(selected)
        visited.add(selected)
        current = selected


def _business_and_intermediate_groups(payload: dict) -> tuple[list[str], list[str]]:
    selector_names = _selector_names(payload)
    order = _selector_order(payload)
    referenced: set[str] = set()
    for name in selector_names:
        item = payload["proxies"][name]
        for choice in item.get("all", []):
            if choice in selector_names:
                referenced.add(choice)
    business = [name for name in order if name not in referenced]
    if not business:
        business = order[:]
    reachable: set[str] = set()
    stack = business[:]
    while stack:
        name = stack.pop()
        if name in reachable:
            continue
        reachable.add(name)
        item = payload["proxies"].get(name, {})
        for choice in item.get("all", []):
            if choice in selector_names:
                stack.append(choice)
    intermediate = [name for name in order if name in reachable and name not in business]
    return business, intermediate


def _parse_log_events(raw: str, cutoff: datetime) -> tuple[dict[tuple[str, str], int], dict[str, dict[str, Counter | int]]]:
    success_counts: dict[tuple[str, str], int] = {}
    error_counts: dict[str, dict[str, Counter | int]] = {}
    for line in raw.splitlines():
        outer = _OUTER_RE.search(line)
        if outer is None:
            continue
        ts = datetime.fromisoformat(outer.group(1).replace("Z", "+00:00"))
        if ts < cutoff:
            continue
        level = outer.group(2)
        msg = outer.group(3)
        using = _USING_RE.search(msg)
        if using is not None:
            group_name = using.group(1).strip()
            leaf_name = using.group(2).strip()
            success_counts[(group_name, leaf_name)] = success_counts.get((group_name, leaf_name), 0) + 1
        is_error = level in {"warning", "error"} or " error: " in msg.lower()
        if not is_error:
            continue
        dial = _DIAL_RE.search(msg)
        if dial is None:
            continue
        group_name = dial.group(1).strip()
        group_entry = error_counts.setdefault(group_name, {"count": 0, "types": Counter(), "upstreams": Counter()})
        group_entry["count"] += 1
        group_entry["types"][_normalize_error_type(msg)] += 1
        upstream = _extract_upstream(msg)
        if upstream:
            group_entry["upstreams"][upstream] += 1
    return success_counts, error_counts


def _extract_upstream(msg: str) -> str | None:
    marker = " error: "
    lower = msg.lower()
    if marker not in lower:
        return None
    error_text = msg[lower.index(marker) + len(marker) :]
    return error_text.split(" ", 1)[0]


def _normalize_error_type(msg: str) -> str:
    lower = msg.lower()
    if "i/o timeout" in lower or "timeout" in lower:
        return "connect-timeout"
    if "connect failed" in lower:
        return "connect-failed"
    if "context canceled" in lower:
        return "context-canceled"
    return "other"


def _classify_log_status(success_count: int, error_count: int) -> str:
    total = success_count + error_count
    if total == 0:
        return "unknown"
    ratio = error_count / total
    if error_count >= 3 and ratio >= 0.3:
        return "recently_unavailable"
    if error_count > 0:
        return "recently_degraded"
    return "healthy"


def _probe_leaf(client: ControllerClient, leaf_name: str, probe_url: str, probe_timeout_ms: int, probe_attempts: int, cache: dict[str, dict]) -> dict:
    cached = cache.get(leaf_name)
    if cached is not None:
        return cached
    delays: list[int] = []
    success_count = 0
    for _ in range(max(probe_attempts, 1)):
        try:
            result = client.proxy_delay(leaf_name, probe_url, probe_timeout_ms)
        except Exception:
            result = None
        delay = result.get("delay") if isinstance(result, dict) else None
        if isinstance(delay, int) and delay > 0:
            delays.append(delay)
            success_count += 1
    if success_count == 0:
        probe_status = "currently_unavailable"
        average_delay = None
    elif success_count < max(probe_attempts, 1):
        probe_status = "currently_degraded"
        average_delay = sum(delays) // len(delays)
    else:
        probe_status = "currently_healthy"
        average_delay = sum(delays) // len(delays)
    cache[leaf_name] = {
        "probe_status": probe_status,
        "attempts": max(probe_attempts, 1),
        "success_count": success_count,
        "average_delay_ms": average_delay,
    }
    return cache[leaf_name]


def _candidate_state(log_status: str, probe_status: str) -> str:
    if probe_status == "currently_unavailable":
        return "unavailable"
    if probe_status == "currently_degraded" or log_status in {"recently_unavailable", "recently_degraded"}:
        return "degraded"
    return "available"


def _pick_alternate(candidates: list[dict]) -> dict | None:
    available = [candidate for candidate in candidates if candidate["state"] == "available"]
    if not available:
        return None
    available.sort(key=lambda item: (item["probe"].get("average_delay_ms") is None, item["probe"].get("average_delay_ms") or 0, item["name"]))
    return available[0]


def _group_candidates(group_name: str, payload: dict, sample_size: int) -> list[tuple[str, list[str], str]]:
    item = payload["proxies"][group_name]
    selected = item["now"]
    usable = [choice for choice in item.get("all", []) if _is_usable_choice(choice, payload)]
    ordered = [selected] + [choice for choice in usable if choice != selected]
    limited = ordered[: max(sample_size, 0) + 1]
    return [(choice, _resolve_chain(payload, choice), _resolve_chain(payload, choice)[-1]) for choice in limited]


def availability(
    since: str = "30m",
    sample_size: int = 3,
    probe_url: str = "https://www.gstatic.com/generate_204",
    probe_timeout_ms: int = 3000,
    probe_attempts: int = 2,
) -> dict:
    payload = ControllerClient().get_proxies()
    business_groups, intermediate_groups = _business_and_intermediate_groups(payload)
    window = _parse_since(since)
    cutoff = _utcnow() - window
    raw_log = LuciRpcClient().read_file("/tmp/openclash.log")
    success_counts, error_counts = _parse_log_events(raw_log, cutoff)
    probe_cache: dict[str, dict] = {}
    client = ControllerClient()
    groups: list[dict] = []
    group_index: dict[str, dict] = {}

    for group_name in business_groups + intermediate_groups:
        candidates: list[dict] = []
        for index, (choice_name, path, leaf_name) in enumerate(_group_candidates(group_name, payload, sample_size)):
            success_count = success_counts.get((group_name, leaf_name), 0)
            error_count = error_counts.get(group_name, {}).get("count", 0) if index == 0 else 0
            log_status = _classify_log_status(success_count, error_count)
            probe = _probe_leaf(client, leaf_name, probe_url, probe_timeout_ms, probe_attempts, probe_cache)
            candidates.append(
                {
                    "name": choice_name,
                    "leaf": leaf_name,
                    "path": path,
                    "selected": index == 0,
                    "log_status": log_status,
                    "probe": probe,
                    "state": _candidate_state(log_status, probe["probe_status"]),
                }
            )
        selected = candidates[0]
        alternates = candidates[1:]
        best_alternate = _pick_alternate(alternates)
        if selected["probe"]["probe_status"] == "currently_unavailable":
            if best_alternate is not None:
                status = "switch-node"
            else:
                status = "fully-unavailable"
        elif selected["log_status"] == "recently_unavailable" and selected["probe"]["probe_status"] == "currently_healthy":
            status = "observe"
        elif selected["state"] == "degraded":
            status = "degraded"
        else:
            status = "healthy"
        entry = {
            "name": group_name,
            "scope": "business" if group_name in business_groups else "intermediate",
            "selected_path": _resolve_chain(payload, group_name),
            "selected_leaf": selected["leaf"],
            "status": status,
            "current": selected,
            "alternates": alternates,
            "available_alternates": [candidate["name"] for candidate in alternates if candidate["state"] == "available"],
            "log_errors": {
                "count": error_counts.get(group_name, {}).get("count", 0),
                "types": dict(error_counts.get(group_name, {}).get("types", Counter()).most_common()),
                "upstreams": dict(error_counts.get(group_name, {}).get("upstreams", Counter()).most_common(3)),
            },
        }
        groups.append(entry)
        group_index[group_name] = entry

    chains: list[dict] = []
    recommendations: list[dict] = []
    recommendation_seen: set[tuple[str, str]] = set()
    for business_group in business_groups:
        chain_groups = [name for name in _resolve_chain(payload, business_group) if name in group_index]
        actionable = next((group_index[name] for name in reversed(chain_groups) if group_index[name]["status"] == "switch-node"), None)
        if actionable is not None:
            selected = actionable["current"]
            alternate = _pick_alternate(actionable["alternates"])
            chains.append({"chain": " -> ".join(chain_groups), "status": "switch-node", "action_group": actionable["name"]})
            key = ("switch-node", actionable["name"])
            if alternate is not None and key not in recommendation_seen:
                recommendation_seen.add(key)
                recommendations.append(
                    {
                        "action": "switch-node",
                        "group": actionable["name"],
                        "from": selected["name"],
                        "to": alternate["name"],
                        "reason": "current selected leaf unavailable while an alternate candidate is available",
                    }
                )
            continue
        if any(group_index[name]["status"] == "fully-unavailable" for name in chain_groups):
            chains.append({"chain": " -> ".join(chain_groups), "status": "fallback-subscription"})
            key = ("fallback-subscription", "backup-subscription")
            if key not in recommendation_seen:
                recommendation_seen.add(key)
                recommendations.append(
                    {
                        "action": "fallback-subscription",
                        "target": "backup-subscription",
                        "reason": "at least one active chain has no available candidates in the current subscription",
                    }
                )
            continue
        if any(group_index[name]["status"] == "observe" for name in chain_groups):
            chains.append({"chain": " -> ".join(chain_groups), "status": "observe"})
        else:
            chains.append({"chain": " -> ".join(chain_groups), "status": "healthy"})

    if any(item["status"] == "fallback-subscription" for item in chains):
        summary_status = "fallback-subscription"
    elif any(item["status"] == "switch-node" for item in chains):
        summary_status = "switch-node"
    elif any(item["status"] == "observe" for item in chains):
        summary_status = "observe"
    else:
        summary_status = "healthy"

    unavailable_groups = [group["name"] for group in groups if group["current"]["probe"]["probe_status"] == "currently_unavailable"]
    fully_unavailable_groups = [group["name"] for group in groups if group["status"] == "fully-unavailable"]
    return {
        "summary": {
            "status": summary_status,
            "window": since,
            "business_groups_checked": len(business_groups),
            "intermediate_groups_checked": len(intermediate_groups),
            "unavailable_groups": unavailable_groups,
            "fully_unavailable_groups": fully_unavailable_groups,
            "broken_chains": [item["chain"] for item in chains if item["status"] in {"switch-node", "fallback-subscription"}],
        },
        "groups": groups,
        "chains": chains,
        "recommendations": recommendations,
    }
