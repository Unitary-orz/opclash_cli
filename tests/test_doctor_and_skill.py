from datetime import datetime
import json

from opclash_cli.commands.doctor import build_network_report
from opclash_cli.commands.subscription import summarize_config_files
from opclash_cli.output import emit, ok


def test_summarize_config_files_returns_name_size_and_mtime():
    entries = [
        {"path": "/etc/openclash/config/west2.yaml", "size": 12345, "mtime": "2026-04-11T00:00:00Z"},
        {"path": "/etc/openclash/config/backup.yaml", "size": 100, "mtime": "2026-04-10T00:00:00Z"},
    ]

    result = summarize_config_files(entries)

    assert result[0]["path"] == "/etc/openclash/config/west2.yaml"
    assert result[0]["size"] == 12345


def test_build_network_report_marks_both_backends_ok():
    result = build_network_report(True, True, True)
    assert result["status"] == "ok"


def test_ok_uses_real_utc_timestamp():
    payload = ok("demo", {})

    assert payload["timestamp"] != "1970-01-01T00:00:00Z"
    assert payload["timestamp"].endswith("Z")
    datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))


def test_emit_writes_operation_log(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPENCLASH_CLI_LOG", str(tmp_path / "operations.jsonl"))

    payload = ok("demo", {"value": 1})
    emit(payload)

    captured = json.loads(capsys.readouterr().out)
    log_lines = (tmp_path / "operations.jsonl").read_text(encoding="utf-8").splitlines()

    assert captured["command"] == "demo"
    assert len(log_lines) == 1
    logged = json.loads(log_lines[0])
    assert logged["command"] == "demo"
    assert logged["ok"] is True
