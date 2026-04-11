from opclash_cli.adapters.luci_rpc import LuciRpcClient


def summarize_status(raw: str) -> dict:
    return {"running": "running" in raw.lower(), "raw": raw.strip()}


def status() -> dict:
    raw = LuciRpcClient().service_exec("/etc/init.d/openclash status")
    return {"service": summarize_status(raw)}


def reload(reason: str) -> dict:
    raw = LuciRpcClient().service_exec("/etc/init.d/openclash reload")
    return {"result": raw.strip(), "audit": {"action": "service.reload", "reason": reason}}


def restart(reason: str) -> dict:
    raw = LuciRpcClient().service_exec("/etc/init.d/openclash restart")
    return {"result": raw.strip(), "audit": {"action": "service.restart", "reason": reason}}


def logs() -> dict:
    raw = LuciRpcClient().read_file("/tmp/openclash.log")
    return {"tail": raw.splitlines()[-50:]}
