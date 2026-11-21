import tomllib

import pytest

from vpnlab import render
from vpnlab.config import load_config

RELAYS = {
    "relay1": "0xc8e2faf5b2d4afd01f5ca86666f04045199926cd",
    "relay2": "0x826d7d57a992ede72e0da79176e4cf3731a7f0dc",
}
EXIT = "0xa532c96b39275210a3756c93f84338bd4661a55d"


def test_address_bytes_is_the_20_bytes_of_the_address():
    values = render.address_bytes(RELAYS["relay1"])
    assert len(values) == 20
    assert values[:3] == [200, 226, 250]
    assert bytes(values).hex() == RELAYS["relay1"][2:]


def test_address_bytes_refuses_other_lengths():
    with pytest.raises(ValueError):
        render.address_bytes("0x1234")


def test_exit_config_lists_only_the_relays_as_byte_arrays():
    text = render.exit_config(load_config(), RELAYS)
    assert "announce: false" in text
    assert text.count("            - [") == len(RELAYS)
    assert "- [200, 226, 250," in text
    assert "min_open_channels: 2" in text and "target_open_channels: 2" in text
    assert '"0xc8e2' not in text  # hoprd rejects hex strings in the allowlist
    assert text.count("blokli_url: https://blokli.piz-palu.gnosisvpn.io") == 2  # node and payment pool


def test_client_config_pins_exit_and_restricts_channels():
    parsed = tomllib.loads(render.client_config(EXIT, RELAYS))
    assert parsed["destinations"]["lab"] == {"address": EXIT, "path": {"hops": 1}, "meta": {"location": "vpn-lab exit"}}
    assert parsed["strategy"]["channel_allowlist"] == {"enabled": True, "peers": list(RELAYS.values())}
    assert parsed["strategy"]["min_open_channels"] == parsed["strategy"]["target_open_channels"] == 2


def test_relay_env_announces_and_exit_env_does_not():
    common = {"password": "pw", "api_token": "tok", "safe": "0xs", "module": "0xm"}
    relay = render.hoprd_env(load_config(), public_ip="203.0.113.5", **common)
    exit_node = render.hoprd_env(load_config(), public_ip=None, **common)
    assert "HOPRD_ANNOUNCE=1" in relay and "HOPRD_HOST=203.0.113.5:9091" in relay
    assert "HOPRD_ANNOUNCE" not in exit_node and "HOPRD_HOST" not in exit_node
    assert "CURVY_ZK_KEYS_DIR=" in exit_node and "CURVY_ZK_KEYS_DIR" not in relay
