from opclash_cli.commands.nodes import summarize_groups, summarize_providers


def test_summarize_groups_returns_selected_proxy_names():
    payload = {
        "proxies": {
            "Apple": {"type": "Selector", "now": "DIRECT", "all": ["DIRECT", "HK-01"]},
            "Final": {"type": "Selector", "now": "Proxies", "all": ["Proxies", "DIRECT"]},
            "HK-01": {"type": "VMess"},
        }
    }

    result = summarize_groups(payload)

    assert result == [
        {"name": "Apple", "selected": "DIRECT", "choices": ["DIRECT", "HK-01"]},
        {"name": "Final", "selected": "Proxies", "choices": ["Proxies", "DIRECT"]},
    ]


def test_summarize_providers_returns_provider_counts():
    payload = {
        "providers": {
            "airport-a": {"proxies": [{"name": "HK-01"}, {"name": "JP-01"}], "updatedAt": "2026-04-11T00:00:00Z"}
        }
    }

    result = summarize_providers(payload)

    assert result == [
        {"name": "airport-a", "count": 2, "updated_at": "2026-04-11T00:00:00Z"}
    ]
