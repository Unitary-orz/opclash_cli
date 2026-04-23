from pathlib import Path
import re
import shlex
from typing import Callable
from urllib.parse import urlsplit
from datetime import datetime, timezone

from opclash_cli.adapters.luci_rpc import LuciRpcClient
from opclash_cli.errors import CliError
from opclash_cli.subscription_archive import archive_subscription


def mask_subscription_address(address: str) -> str:
    if not address:
        return ""
    parsed = urlsplit(address)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}/***"
    return "***"


def summarize_subscriptions(payload: dict, redact_addresses: bool = True) -> list[dict]:
    result = []
    for section, item in payload.items():
        if item.get(".type") != "config_subscribe":
            continue
        address = item.get("address", "")
        result.append(
            {
                "section": section,
                "name": item.get("name", ""),
                "address": mask_subscription_address(address) if redact_addresses else address,
                "enabled": str(item.get("enabled", "0")) == "1",
            }
        )
    return result


def _raw_subscription_entries(payload: dict) -> list[dict]:
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
                "sub_ua": item.get("sub_ua") or "Clash",
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
                "command": "opclash_cli sub list",
                "purpose": "确认失败项对应的订阅名称和地址",
            }
        )
    return commands


_OPENCLASH_FIREWALL_CHAINS = ("openclash", "openclash_mangle")


def _check_openclash_firewall_chains(client: LuciRpcClient) -> dict:
    chains = {}
    for chain in _OPENCLASH_FIREWALL_CHAINS:
        command = (
            f"nft list chain inet fw4 {shlex.quote(chain)} >/dev/null 2>&1 "
            "&& printf present || printf missing"
        )
        try:
            chains[chain] = client.service_exec(command, timeout=10).strip() == "present"
        except Exception:
            chains[chain] = False
    return {"healthy": all(chains.values()), "chains": chains}


def _repair_openclash_firewall_if_needed(client: LuciRpcClient) -> dict:
    before = _check_openclash_firewall_chains(client)
    result = {
        "checked": True,
        "status": "healthy" if before["healthy"] else "missing_chains",
        "repaired": False,
        "before": before,
        "after": before,
        "repair_command": None,
    }
    if before["healthy"]:
        return result

    repair_command = "/etc/init.d/openclash reload manual"
    try:
        client.service_exec(repair_command, timeout=60)
    except Exception as error:
        after = _check_openclash_firewall_chains(client)
        return {
            **result,
            "status": "repair_failed",
            "after": after,
            "repair_command": repair_command,
            "repair_error": type(error).__name__,
        }

    after = _check_openclash_firewall_chains(client)
    return {
        **result,
        "status": "repaired" if after["healthy"] else "still_missing_chains",
        "repaired": after["healthy"],
        "after": after,
        "repair_command": repair_command,
    }


def find_subscription(payload: dict, name: str) -> dict:
    for subscription in summarize_subscriptions(payload, redact_addresses=False):
        if subscription["name"] == name:
            return subscription
    raise CliError("SUBSCRIPTION_NOT_FOUND", f"Subscription '{name}' was not found")


def _find_raw_subscription(payload: dict, name: str) -> dict:
    for subscription in _raw_subscription_entries(payload):
        if subscription["name"] == name:
            return subscription
    raise CliError("SUBSCRIPTION_NOT_FOUND", f"Subscription '{name}' was not found")


def parse_subscription_userinfo(header: str) -> dict:
    values: dict[str, int] = {}
    for part in header.split(";"):
        if "=" not in part:
            continue
        key, raw_value = part.strip().split("=", 1)
        key = key.strip().lower()
        try:
            values[key] = int(raw_value.strip())
        except ValueError:
            continue

    upload = values.get("upload", 0)
    download = values.get("download", 0)
    total = values.get("total")
    expire = values.get("expire")
    used = upload + download
    remain = total - used if total is not None else None
    remain_percent = round((remain / total) * 100, 1) if remain is not None and total and total > 0 else None
    expire_iso = (
        datetime.fromtimestamp(expire, timezone.utc).isoformat().replace("+00:00", "Z")
        if expire is not None
        else None
    )
    expired = datetime.now(timezone.utc).timestamp() > expire if expire is not None and expire != 0 else False
    return {
        "upload_bytes": upload,
        "download_bytes": download,
        "used_bytes": used,
        "remain_bytes": remain,
        "total_bytes": total,
        "remain_percent": remain_percent,
        "expire_epoch": expire,
        "expire": expire_iso,
        "expired": expired,
    }


def _parse_sub_info_response(raw: str) -> tuple[int | None, str | None]:
    http_code = None
    code_matches = re.findall(r"http_code=(\d+)", raw)
    if code_matches:
        http_code = int(code_matches[-1])
    userinfo = None
    for line in raw.splitlines():
        if line.lower().startswith("subscription-userinfo:"):
            userinfo = line.split(":", 1)[1].strip()
            break
    return http_code, userinfo


def _query_subscription_userinfo(client: LuciRpcClient, address: str, user_agents: list[str]) -> dict:
    attempts = []
    for user_agent in user_agents:
        write_out = shlex.quote("http_code=%{http_code}\n")
        command = (
            "curl -sLI -X GET -m 10 "
            f"-w {write_out} "
            f"-H {shlex.quote('User-Agent: ' + user_agent)} "
            f"{shlex.quote(address)}"
        )
        try:
            raw = client.service_exec(command, timeout=20)
        except Exception as error:
            attempts.append({"user_agent": user_agent, "error": type(error).__name__})
            continue
        http_code, userinfo = _parse_sub_info_response(raw)
        attempts.append({"user_agent": user_agent, "http_code": http_code, "has_userinfo": bool(userinfo)})
        if http_code == 200 and userinfo:
            return {
                "ok": True,
                "user_agent": user_agent,
                "http_code": http_code,
                "userinfo": userinfo,
                "attempts": attempts,
            }
    return {"ok": False, "attempts": attempts}


def _usage_summary(items: list[dict]) -> dict:
    return {
        "total": len(items),
        "ok": sum(1 for item in items if item["status"] == "ok"),
        "failed": sum(1 for item in items if item["status"] == "failed"),
        "skipped": sum(1 for item in items if item["status"] == "skipped"),
    }


def subscription_usage(name: str | None = None) -> dict:
    client = LuciRpcClient()
    payload = client.get_openclash_uci()
    subscriptions = _raw_subscription_entries(payload)
    if name:
        subscriptions = [_find_raw_subscription(payload, name)]
        target = {"mode": "single", "name": name}
    else:
        target = {"mode": "all"}

    items = []
    for subscription in subscriptions:
        base_item = {
            "name": subscription["name"],
            "section": subscription["section"],
            "enabled": subscription["enabled"],
        }
        if not subscription["enabled"]:
            items.append({**base_item, "status": "skipped", "reason": "disabled"})
            continue
        if not subscription["address"]:
            items.append({**base_item, "status": "failed", "reason": "missing_address"})
            continue

        user_agents = [subscription["sub_ua"] or "Clash"]
        if "Quantumultx" not in user_agents:
            user_agents.append("Quantumultx")
        query = _query_subscription_userinfo(client, subscription["address"], user_agents)
        if query["ok"]:
            items.append(
                {
                    **base_item,
                    "status": "ok",
                    "source": "subscription-userinfo",
                    "user_agent": query["user_agent"],
                    "http_code": query["http_code"],
                    "quota": parse_subscription_userinfo(query["userinfo"]),
                    "attempts": query["attempts"],
                }
            )
        else:
            items.append(
                {
                    **base_item,
                    "status": "failed",
                    "reason": "subscription_userinfo_not_found",
                    "attempts": query["attempts"],
                }
            )

    return {"target": target, "items": items, "summary": _usage_summary(items)}


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
    return {
        "removed": subscription,
        "archive": archive,
        "audit": None,
    }


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
    def notify(message: str) -> None:
        if progress is not None:
            progress(message)

    notify("Starting subscription update")
    client = LuciRpcClient()
    payload = client.get_openclash_uci()
    target: str | None = None
    target_details: dict
    subscriptions = summarize_subscriptions(payload, redact_addresses=False)

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
    notify("Running OpenClash update script")
    try:
        client.update_subscription(target)
    except Exception as error:
        raise CliError("SERVICE_OPERATION_FAILED", "Subscription update failed", {"details": str(error)}) from error

    notify("Collecting update results")
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
    notify("Checking OpenClash firewall rules")
    firewall = _repair_openclash_firewall_if_needed(client)
    notify(
        "Subscription update finished: "
        f"{summary['updated_count']} updated, "
        f"{summary['unchanged_count']} unchanged, "
        f"{summary['failed_count']} failed, "
        f"{summary['skipped_count']} skipped"
    )
    return {
        "target": target_details,
        "items": items,
        "summary": summary,
        "before": before,
        "after": {"config_path": refreshed["config"]["config_path"]},
        "firewall": firewall,
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
    return {
        "before": {"config_path": current},
        "after": {"config_path": refreshed},
        "changed": True,
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
