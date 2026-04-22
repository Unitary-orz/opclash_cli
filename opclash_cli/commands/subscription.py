from pathlib import Path
import re

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


def _snapshot_config_files(client: LuciRpcClient, directory: str = "/etc/openclash/config") -> dict[str, dict]:
    snapshot: dict[str, dict] = {}
    for entry in client.list_config_files(directory):
        snapshot[entry.path] = {"path": entry.path, "size": entry.size, "mtime": entry.mtime}
    return snapshot


def _match_config_entry(name: str, before: dict[str, dict], after: dict[str, dict]) -> tuple[dict | None, dict | None]:
    stem = Path(name).stem

    def _find(entries: dict[str, dict]) -> dict | None:
        for candidate in entries.values():
            if Path(candidate["path"]).stem == stem:
                return candidate
        return None

    return _find(before), _find(after)


def _log_delta(before_log: str, after_log: str) -> list[str]:
    before_lines = before_log.splitlines()
    after_lines = after_log.splitlines()
    if len(after_lines) >= len(before_lines) and after_lines[: len(before_lines)] == before_lines:
        return after_lines[len(before_lines) :]
    return after_lines


def _parse_update_blocks(lines: list[str]) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    current_name: str | None = None
    for line in lines:
        match = re.search(r"Start Updating Config File【(.+?)】\.\.\.", line)
        if match:
            current_name = match.group(1)
            blocks.setdefault(current_name, []).append(line)
            continue
        if current_name is not None:
            blocks[current_name].append(line)
    return blocks


def _classify_block(lines: list[str]) -> str:
    if any("Update Successful!" in line for line in lines):
        return "updated"
    if any("No Change, Do Nothing!" in line for line in lines):
        return "unchanged"
    if any(
        marker in line
        for line in lines
        for marker in ("Update Error", "Subscribed Failed", "Download Failed", "Error:")
    ):
        return "failed"
    return "failed"


def _matched_log_lines(lines: list[str], status: str) -> list[str]:
    matched = [line for line in lines if "Start Updating Config File【" in line]
    if status == "updated":
        matched.extend(line for line in lines if "Update Successful!" in line)
    elif status == "unchanged":
        matched.extend(line for line in lines if "No Change, Do Nothing!" in line)
    else:
        matched.extend(
            line
            for line in lines
            if "Update Error" in line or "Subscribed Failed" in line or "Download Failed" in line or "Error:" in line
        )
    if not matched and lines:
        matched.append(lines[-1])
    return matched[:4]


def _build_item_evidence(
    name: str,
    lines: list[str],
    status: str,
    before_configs: dict[str, dict],
    after_configs: dict[str, dict],
) -> dict:
    before_entry, after_entry = _match_config_entry(name, before_configs, after_configs)
    evidence = {
        "source": "openclash.log",
        "matched_lines": _matched_log_lines(lines, status),
    }
    config_entry = after_entry or before_entry
    if config_entry is not None:
        evidence["config_path"] = config_entry["path"]
        evidence["config_changed"] = before_entry != after_entry
        evidence["before_mtime"] = before_entry["mtime"] if before_entry is not None else None
        evidence["after_mtime"] = after_entry["mtime"] if after_entry is not None else None
    return evidence


def _summarize_outcomes(items: list[dict]) -> dict:
    counts = {"updated": 0, "unchanged": 0, "failed": 0, "skipped": 0}
    for item in items:
        counts[item["status"]] += 1
    actionable_total = len(items) - counts["skipped"]
    if actionable_total == 0 or counts["failed"] == 0:
        overall_status = "success"
    elif counts["failed"] == actionable_total:
        overall_status = "failed"
    else:
        overall_status = "partial"
    return {
        "overall_status": overall_status,
        "total": len(items),
        "updated_count": counts["updated"],
        "unchanged_count": counts["unchanged"],
        "failed_count": counts["failed"],
        "skipped_count": counts["skipped"],
    }


def _suggested_commands(summary: dict, target: dict) -> list[dict]:
    if summary["failed_count"] == 0:
        return []
    commands = [
        {
            "command": "opclash_cli service logs",
            "purpose": "查看 OpenClash 最近的订阅更新日志",
        }
    ]
    if target["mode"] == "all":
        commands.append(
            {
                "command": "opclash_cli subscription list",
                "purpose": "确认失败项对应的订阅名称和地址",
            }
        )
    return commands


def find_subscription(payload: dict, name: str) -> dict:
    for subscription in summarize_subscriptions(payload):
        if subscription["name"] == name:
            return subscription
    raise CliError("SUBSCRIPTION_NOT_FOUND", f"Subscription '{name}' was not found")


def add_subscription(name: str, url: str) -> dict:
    client = LuciRpcClient()
    section = client.add_uci_section("openclash", "config_subscribe")
    payload = add_subscription_payload(name, url)
    for option, value in payload.items():
        client.set_uci("openclash", section, option, value)
    client.commit_uci("openclash")
    return {
        "subscription": {"section": section, **payload},
        "audit": None,
    }


def update_subscription(name: str | None, config: str | None) -> dict:
    client = LuciRpcClient()
    payload = client.get_openclash_uci()
    target: str | None = None
    target_details: dict
    subscriptions = summarize_subscriptions(payload)

    if name:
        subscription = find_subscription(payload, name)
        target = name
        target_details = {"mode": "single", "name": subscription["name"], "section": subscription["section"]}
        item_seeds = [subscription]
    elif config:
        config_paths = {entry.path for entry in client.list_config_files(str(Path(config).parent))}
        if config not in config_paths:
            raise CliError("CONFIG_NOT_FOUND", f"Config '{config}' was not found")
        target = config
        target_details = {"mode": "single", "config_path": config}
        item_seeds = [{"name": Path(config).stem, "section": None, "enabled": True}]
    else:
        target_details = {"mode": "all"}
        item_seeds = subscriptions

    before = {"config_path": payload["config"]["config_path"]}
    before_log = client.read_file("/tmp/openclash.log")
    before_configs = _snapshot_config_files(client)
    try:
        client.update_subscription(target)
    except Exception as error:
        raise CliError("SERVICE_OPERATION_FAILED", "Subscription update failed", {"details": str(error)}) from error

    after_log = client.read_file("/tmp/openclash.log")
    after_configs = _snapshot_config_files(client)
    blocks = _parse_update_blocks(_log_delta(before_log, after_log))
    items = []
    for seed in item_seeds:
        if target_details["mode"] == "all" and not seed["enabled"]:
            items.append(
                {
                    "name": seed["name"],
                    "section": seed["section"],
                    "enabled": seed["enabled"],
                    "status": "skipped",
                    "evidence": {
                        "source": "subscription.config",
                        "matched_lines": [],
                    },
                }
            )
            continue

        block_lines = blocks.get(seed["name"], [])
        status = _classify_block(block_lines) if block_lines else "failed"
        items.append(
            {
                "name": seed["name"],
                "section": seed["section"],
                "enabled": seed["enabled"],
                "status": status,
                "evidence": _build_item_evidence(seed["name"], block_lines, status, before_configs, after_configs),
            }
        )

    refreshed = client.get_openclash_uci()
    summary = _summarize_outcomes(items)
    return {
        "target": target_details,
        "items": items,
        "summary": summary,
        "before": before,
        "after": {"config_path": refreshed["config"]["config_path"]},
        "suggested_commands": _suggested_commands(summary, target_details),
        "audit": None,
    }


def switch_config(path: str) -> dict:
    client = LuciRpcClient()
    config_paths = {entry.path for entry in client.list_config_files(str(Path(path).parent))}
    if path not in config_paths:
        raise CliError("CONFIG_NOT_FOUND", f"Config '{path}' was not found")
    payload = client.get_openclash_uci()
    current = payload["config"]["config_path"]
    if path == current:
        raise CliError("VERIFY_FAILED", "Target config is already active")
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
    return {
        "before": {"config_path": current},
        "after": {"config_path": refreshed},
        "audit": None,
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
