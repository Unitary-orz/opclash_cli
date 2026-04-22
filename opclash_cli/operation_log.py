import json
import os
from pathlib import Path


_LOGGED_COMMANDS = {
    "init",
    "init check",
    "nodes switch",
    "subscription add",
    "subscription update",
    "subscription switch",
    "service reload",
    "service restart",
}


def log_path() -> Path:
    override = os.environ.get("OPENCLASH_CLI_LOG")
    if override:
        return Path(override)
    return Path.home() / ".local" / "state" / "opclash_cli" / "operations.jsonl"


def _event(payload: dict) -> dict:
    return {
        "timestamp": payload.get("timestamp"),
        "command": payload.get("command"),
        "ok": payload.get("ok"),
        "warnings": payload.get("warnings", []),
        "audit": payload.get("audit"),
        "error": payload.get("error"),
        "data": payload.get("data", {}),
    }


def should_log_command(command: str | None) -> bool:
    return command in _LOGGED_COMMANDS


def append_operation(payload: dict) -> None:
    if not should_log_command(payload.get("command")):
        return
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(_event(payload), ensure_ascii=False) + "\n")


def read_operations(limit: int = 20) -> dict:
    path = log_path()
    if not path.exists():
        return {"items": []}

    items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {"items": list(reversed(items[-limit:]))}
