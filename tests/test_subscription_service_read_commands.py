from opclash_cli.commands.service import summarize_status
from opclash_cli.commands.subscription import summarize_subscriptions


def test_summarize_subscriptions_filters_config_subscribe_sections():
    payload = {
        "cfg1": {".type": "config_subscribe", "name": "west2", "address": "https://example/sub", "enabled": "1"},
        "cfg2": {".type": "other", "name": "ignore-me"},
    }

    result = summarize_subscriptions(payload)

    assert result == [
        {"section": "cfg1", "name": "west2", "address": "https://example/sub", "enabled": True}
    ]


def test_summarize_status_marks_running_when_status_output_contains_running():
    result = summarize_status("openclash is running")
    assert result == {"running": True, "raw": "openclash is running"}
