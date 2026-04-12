from opclash_cli.commands.subscription import add_subscription_payload, switch_config_payload
from opclash_cli.adapters.luci_rpc import LuciRpcClient


def test_add_subscription_payload_contains_required_fields():
    payload = add_subscription_payload("west2", "https://example/sub")

    assert payload["name"] == "west2"
    assert payload["address"] == "https://example/sub"
    assert payload["enabled"] == "1"


def test_switch_config_payload_sets_target_path():
    payload = switch_config_payload("/etc/openclash/config/west2.yaml")

    assert payload == {"config_path": "/etc/openclash/config/west2.yaml"}


def test_parse_uci_show_builds_section_dict():
    raw = "\n".join(
        [
            "openclash.config=openclash",
            "openclash.config.config_path='/etc/openclash/config/x-max.yaml'",
            "openclash.@config_subscribe[0]=config_subscribe",
            "openclash.@config_subscribe[0].name='west2'",
            "openclash.@config_subscribe[0].enabled='1'",
        ]
    )

    payload = LuciRpcClient.__new__(LuciRpcClient)._parse_uci_show(raw)

    assert payload["config"][".type"] == "openclash"
    assert payload["config"]["config_path"] == "/etc/openclash/config/x-max.yaml"
    assert payload["@config_subscribe[0]"][".type"] == "config_subscribe"
    assert payload["@config_subscribe[0]"]["name"] == "west2"
