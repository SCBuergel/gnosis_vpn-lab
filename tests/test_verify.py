import json

from vpnlab import verify

EXIT_KEY = "0x75dab2977987a7447f6feb74f5cae9511d2c15bd93c9734d5a718794a818eea7"
CLIENT_KEY = "0x0ade976afe6a1e6f8bb0087a9708fa974805660b30b0fa4ca3bbd37d949a2437"
EXIT = "0xa532c96b39275210a3756c93f84338bd4661a55d"
CLIENT = "0x7f2665228570f3300973b550754186080283d437"
RELAYS = {
    "relay1": "0xc8e2faf5b2d4afd01f5ca86666f04045199926cd",
    "relay2": "0x826d7d57a992ede72e0da79176e4cf3731a7f0dc",
}
FOREIGN = "0x1111111111111111111111111111111111111111"


def planner_line(source, destination, paths):
    candidates = ", ".join(f'("validated path [{relay}, {end}]", 0.2)' for relay, end in paths)
    return (
        "2026-11-21T22:19:01.010780Z DEBUG routing.resolve: hopr_transport::path::planner: rebuilt weighted path "
        f'collection kind="fill" source={source} destination={destination} hops=1 candidates=[{candidates}]'
    )


def check(lines):
    return verify.planner_paths(
        lines, exit_packet_key=EXIT_KEY, exit_address=EXIT, client_address=CLIENT, relays=RELAYS
    )


def test_paths_through_lab_relays_pass():
    report = check(
        [
            planner_line(CLIENT_KEY, EXIT_KEY, [(RELAYS["relay1"], EXIT), (RELAYS["relay2"], EXIT)]),
            planner_line(EXIT_KEY, CLIENT_KEY, [(RELAYS["relay2"], CLIENT)]),
            "2026-11-21T22:19:02Z INFO something else",
        ]
    )
    assert report["ok"] is True
    assert report["forward"] == {"sets": 1, "relays": {"relay1": 1, "relay2": 1}}
    assert report["return"] == {"sets": 1, "relays": {"relay2": 1}}


def test_a_foreign_relay_fails_the_check():
    report = check(
        [
            planner_line(CLIENT_KEY, EXIT_KEY, [(RELAYS["relay1"], EXIT), (FOREIGN, EXIT)]),
            planner_line(EXIT_KEY, CLIENT_KEY, [(RELAYS["relay1"], CLIENT)]),
        ]
    )
    assert report["ok"] is False
    assert report["foreign"] == [f"forward: foreign relay {FOREIGN}"]


def test_no_planner_lines_is_not_a_pass():
    assert check(["nothing relevant"])["ok"] is False


def test_only_one_direction_is_not_a_pass():
    assert check([planner_line(CLIENT_KEY, EXIT_KEY, [(RELAYS["relay1"], EXIT)])])["ok"] is False


def test_paths_between_other_nodes_are_ignored():
    other = "0x" + "22" * 32
    report = check([planner_line(CLIENT_KEY, other, [(FOREIGN, "0x" + "33" * 20)])])
    assert report["forward"]["sets"] == 0 and report["foreign"] == []


def dump(component, state):
    head = '2026-11-21T22:00:29Z  INFO x: component operational state event="component_state"'
    return f'{head} component="{component}" state={json.dumps(state)}'


def test_client_contacts_counts_peers_and_other_destinations():
    transport = {"state": {"status": "ok", "value": {"connected_peers": 228, "discovered_peers": 228}}}
    paths = {
        "destinations": [
            {"destination": EXIT_KEY, "forward_resolved": 100},
            {"destination": "0xaa", "forward_resolved": 2},
            {"destination": "0xbb", "forward_resolved": 3},
        ],
        "destinations_omitted": 48,
    }
    report = verify.client_contacts([dump("transport", transport), dump("paths", paths)], exit_packet_key=EXIT_KEY)
    assert report["connected_peers_max"] == 228 and report["transport_dumps"] == 1
    assert report["intervals"] == [
        {
            "time": "2026-11-21T22:00:29Z",
            "other_destinations": 50,
            "packets_to_listed_others": 5,
            "max_packets_to_one_other": 3,
            "packets_to_exit": 100,
        }
    ]
