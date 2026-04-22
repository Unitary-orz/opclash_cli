import json
import os
from datetime import datetime, timezone
from pathlib import Path


def subscription_archive_path() -> Path:
    override = os.environ.get("OPENCLASH_CLI_SUBSCRIPTION_ARCHIVE")
    if override:
        return Path(override)
    return Path.home() / ".local" / "state" / "opclash_cli" / "subscription-archive.jsonl"


def archive_subscription(action: str, subscription: dict) -> dict:
    path = subscription_archive_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "action": action,
        "subscription": subscription,
    }
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")
    return {"path": str(path)}
