import json
from datetime import datetime, timezone


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def emit(payload: dict, pretty: bool = False) -> None:
    if pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(json.dumps(payload, ensure_ascii=False))


def ok(command: str, data: dict, warnings: list[str] | None = None, audit: dict | None = None) -> dict:
    return {
        "ok": True,
        "command": command,
        "timestamp": _timestamp(),
        "data": data,
        "warnings": warnings or [],
        "audit": audit,
        "error": None,
    }


def fail(command: str, code: str, message: str, details: dict | None = None) -> dict:
    return {
        "ok": False,
        "command": command,
        "timestamp": _timestamp(),
        "data": {},
        "warnings": [],
        "audit": None,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }
