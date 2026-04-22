import json
import os
from pathlib import Path


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


def append_operation(payload: dict) -> None:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(_event(payload), ensure_ascii=False) + "\n")
