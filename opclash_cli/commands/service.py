from opclash_cli.adapters.luci_rpc import LuciRpcClient


def summarize_status(raw: str) -> dict:
    return {"running": "running" in raw.lower(), "raw": raw.strip()}


def status() -> dict:
    raw = LuciRpcClient().service_exec("/etc/init.d/openclash status")
    return {"service": summarize_status(raw)}


def reload() -> dict:
    raw = LuciRpcClient().service_exec("/etc/init.d/openclash reload")
    return {"result": raw.strip(), "audit": None}


def restart() -> dict:
    raw = LuciRpcClient().service_exec("/etc/init.d/openclash restart")
    return {"result": raw.strip(), "audit": None}


def logs(limit: int = 50, grep: str | None = None) -> dict:
    raw = LuciRpcClient().read_file("/tmp/openclash.log")
    lines = raw.splitlines()
    total = len(lines)
    if grep:
        needle = grep.lower()
        lines = [line for line in lines if needle in line.lower()]
    limit = max(limit, 0)
    return {
        "tail": lines[-limit:] if limit else [],
        "limit": limit,
        "grep": grep,
        "total": total,
        "matched": len(lines),
    }
