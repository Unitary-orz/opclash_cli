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


def logs() -> dict:
    raw = LuciRpcClient().read_file("/tmp/openclash.log")
    return {"tail": raw.splitlines()[-50:]}
