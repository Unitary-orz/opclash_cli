from opclash_cli.commands.doctor import build_network_report
from opclash_cli.commands.subscription import summarize_config_files


def test_summarize_config_files_returns_name_size_and_mtime():
    entries = [
        {"name": "west2.yaml", "size": 12345, "mtime": "2026-04-11T00:00:00Z"},
        {"name": "backup.yaml", "size": 100, "mtime": "2026-04-10T00:00:00Z"},
    ]

    result = summarize_config_files(entries)

    assert result[0]["path"] == "/etc/openclash/config/west2.yaml"
    assert result[0]["size"] == 12345


def test_build_network_report_marks_both_backends_ok():
    result = build_network_report(True, True, True)
    assert result["status"] == "ok"
