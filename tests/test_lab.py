import csv

import pytest

from vpnlab import experiment, measure, onboard, providers, ssh, state
from vpnlab.config import load_config
from vpnlab.providers import digitalocean


def test_config_names_and_provider():
    config = load_config()
    assert config.machines == ["relay1", "relay2", "relay3", "exit", "client"]
    assert config.hoprd_nodes == ["relay1", "relay2", "relay3", "exit"]
    assert config.provider_name in providers.PROVIDERS
    for pin in ("hopli", "hoprd", "hoprd_cfg", "hoprd_exit", "gnosis_vpn_server", "client"):
        assert len(config.software(pin)["sha256"]) == 64


def test_unknown_provider_is_refused():
    with pytest.raises(ValueError, match="unknown provider"):
        providers.get_provider("nowhere", {})


def test_digitalocean_droplet_becomes_a_machine():
    droplet = {
        "id": 42,
        "name": "vpn-lab-relay1",
        "status": "active",
        "size_slug": "c-4",
        "region": {"slug": "fra1"},
        "created_at": "2026-11-21T21:47:08Z",
        "networks": {
            "v4": [{"type": "private", "ip_address": "10.0.0.2"}, {"type": "public", "ip_address": "203.0.113.9"}]
        },
    }
    machine = digitalocean.to_machine(droplet, "vpn-lab")
    assert (machine.name, machine.id, machine.public, machine.private) == ("relay1", "42", "203.0.113.9", "10.0.0.2")


def test_cloud_config_lifts_the_forced_password_change():
    text = digitalocean.cloud_config("ssh-ed25519 AAAA lab")
    assert text.startswith("#cloud-config\n") and "chage" in text and "ssh-ed25519 AAAA lab" in text


def test_ssh_config_reaches_the_client_through_the_first_relay():
    inventory = {
        "relay1": {"public": "203.0.113.1", "private": "10.0.0.2"},
        "client": {"public": "203.0.113.5", "private": "10.0.0.9"},
    }
    text = ssh.render_config(inventory, "relay1")
    assert "Host lab-client-priv\n  HostName 10.0.0.9\n  ProxyJump lab-relay1" in text
    assert "Host lab-relay1\n  HostName 203.0.113.1" in text


def test_identity_and_safe_are_parsed_from_hopli_output():
    identity = (
        "INFO Identities: {HoprKeys { packet_key: (priv_key: <REDACTED>, pub_key: 0x" + "ab" * 32 + ", chain_key: ...\n"
        "Identity addresses: [0xC8E2faf5b2d4afd01f5ca86666f04045199926cd]\n"
        "Identity peerids: [12D3KooWM1CPydB2dkUBDisN47EEaYaq7AXWDzZKk8C6ZDsHCHL2]\n"
    )
    parsed = onboard.parse_identity(identity)
    assert parsed["address"] == "0xc8e2faf5b2d4afd01f5ca86666f04045199926cd"
    assert parsed["packet_key"] == "0x" + "ab" * 32 and parsed["peer"].startswith("12D3KooW")
    safe = (
        "\x1b[2mlog\x1b[0m\nsafe 0x159c89cb77e97019417efe5367d72d6713501891\n"
        "node_module 0xf1607be9b3c3ee2c2bdc7a369cf1b08f7920f940\n"
    )
    assert onboard.parse_safe(safe)["module"] == "0xf1607be9b3c3ee2c2bdc7a369cf1b08f7920f940"
    with pytest.raises(RuntimeError):
        onboard.parse_safe("nothing")


def test_state_files_are_private(tmp_path):
    target = tmp_path / "secrets" / "x" / "token"
    state.write_private(target, "s3cret")
    assert target.read_text() == "s3cret"
    assert target.stat().st_mode & 0o777 == 0o600
    assert target.parent.stat().st_mode & 0o777 == 0o700


def test_throughput_rows_append_with_one_header(tmp_path):
    path = tmp_path / "throughput.csv"
    row = {"started_utc": "t", "url": "u", "bytes": 1, "seconds": 1.0, "mbit_per_s": "", "http_code": 403}
    measure.append_rows(path, [row])
    measure.append_rows(path, [row])
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == 2 and rows[0]["mbit_per_s"] == ""  # a failed download has no rate, not zero


def test_stall_row_summarises_a_sample_and_the_counters_around_it():
    sample = {
        "started_unix": 1795302855.0,
        "connected": True,
        "connect_seconds": 6.43,
        "stalls": [{"from": 16.9, "to": 33.4, "seconds": 16.5, "bytes_before": 13365248}, {"seconds": 1.2}],
        "download": {"bytes": 104857600, "seconds": 77.45, "mbit_per_s": 10.83, "http_code": "200"},
        "bytes_per_second": [500000, 3500000, 0],
    }
    forwarded, gate = experiment.FORWARDED, experiment.GATE_SECONDS
    before = {"relay1": {forwarded: 100}, "exit": {gate: 57.0}}
    after = {"relay1": {forwarded: 350}, "exit": {gate: 73.5}}
    row = experiment.stall_row(1, sample, before, after, ["relay1"])
    assert row["connect_seconds"] == 6.43 and row["first_stall_seconds"] == 16.5
    assert row["megabytes_before_stall"] == 13.37 and row["later_stalls_seconds"] == "1.2"
    assert row["peak_mbit_per_s"] == 28.0 and row["relay1_forwarded_packets"] == 250
    assert row["lab_exit_gate_block_seconds"] == 16.5


def test_stall_row_of_a_failed_connect_has_no_numbers():
    row = experiment.stall_row(2, {"started_unix": 0, "connected": False, "phases": []}, {}, {}, ["relay1"])
    assert row == {"iteration": 2, "connect_issued_utc": "1970-01-01T00:00:00Z", "connected": False}


def test_repository_commit_names_the_checked_out_commit():
    recorded = experiment.repository_commit()
    assert len(recorded["commit"]) == 40 and isinstance(recorded["uncommitted_changes"], bool)


def test_relayer_delay_is_read_from_the_last_line():
    assert experiment.parse_relayer_delay("delaying packets to 203.0.113.9\nrelayer delay: 3000 ms\n") == 3000
    assert experiment.parse_relayer_delay("relayer delay: off\n") == 0
    with pytest.raises(RuntimeError):
        experiment.parse_relayer_delay("Cannot find device\n")


def test_route_state_is_none_while_no_health_is_reported():
    from vpnlab import client

    data = {"destinations": [{"destination": {"id": "lab"}, "route_health": None}]}
    assert client.route_state(data) is None
    data["destinations"][0]["route_health"] = {"state": {"type": "routable"}}
    assert client.route_state(data) == "routable"


def test_payment_row_reads_a_recorded_deposit_from_the_three_logs():
    started = 1795343552.0  # 2026-11-22T10:32:32Z
    client_log = "\n".join(
        [
            "2026-11-22T10:32:20.000000Z  INFO hopr_strategy::pix::strategy: new deposit address PixAddressId(old, 1)",
            "2026-11-22T10:32:33.771724Z  INFO hopr_strategy::pix::strategy: new deposit address new_deposit_address="
            "PixNewDepositAddress { id: PixAddressId(d369ea20a874dc81d249, 1), address: Bjj(..) }",
            "2026-11-22T10:32:37.500000Z  INFO gnosis_vpn_lib::core: connection established successfully conn=..",
            '2026-11-22T10:32:41.059464Z  INFO curvy_witnesscalc: Curvy proof timing circuit="pix-aggregation"',
            "2026-11-22T10:32:47.400000Z  INFO hopr_strategy::pix::pools::curvy::sdk: the note source indexed a "
            "relayed Curvy aggregation after the relayer reported it observations=7",
            "2026-11-22T10:32:47.515802Z  INFO hopr_strategy::pix::strategy: single deposit flushed successfully "
            "id=PixAddressId(d369ea20a874dc81d249, 1) amount=5.941444608 wxHOPR",
        ]
    )
    exit_log = "\n".join(
        [
            "2026-11-22T10:33:12.788058+00:00 INFO ..: discovered Curvy PIX pending note through Blokli note_id=0x05 "
            "allocation=PixAddressId(d369ea20a874dc81d249, 1)",
            "2026-11-22T10:33:19.000000+00:00 INFO ..: ssa deposit confirmed session_id=d369ea20a874dc81d249",
        ]
    )
    proxy_log = "\n".join(
        [
            "2026-11-22T10:32:44.300Z note=0x05 blokli=1 reported=0 lag_s=3",
            "2026-11-22T10:32:47.300Z note=0x05 blokli=1 reported=1 lag_s=3",
        ]
    )
    row = experiment.payment_row(started, client_log, exit_log, proxy_log)
    assert row["session"] == "d369ea20a874dc81d249"
    assert (row["client_outcome"], row["client_outcome_s"], row["client_lookups"]) == ("recorded", 15.5, 7)
    assert (row["connected_s"], row["proof_s"]) == (5.5, 9.1)
    assert (row["exit_saw_note_s"], row["exit_confirmed_s"]) == (40.8, 47.0)
    assert (row["proxy_lookups"], row["proxy_first_blokli_status"], row["proxy_reported_unknown"]) == (2, 1, 1)


def test_payment_row_reads_a_deferred_deposit():
    client_log = (
        "2026-11-22T10:27:54.288413Z  INFO hopr_strategy::pix::strategy: new deposit address id: "
        "PixAddressId(70f605717ddc0bdbb780, 1)\n"
        "2026-11-22T10:28:07.469087Z  WARN hopr_strategy::pix::strategy: deposit flush deferred until an earlier "
        "Curvy operation is reconciled id=Some(PixAddressId(70f605717ddc0bdbb780, 1)) count=1\n"
    )
    row = experiment.payment_row(1795343273.5, client_log, "", "")
    assert (row["client_outcome"], row["client_outcome_s"]) == ("deferred", 14.0)
    assert (row["exit_confirmed_s"], row["proxy_lookups"]) == ("", 0)


def test_comparison_schedule_is_balanced_and_alternates():
    schedule = experiment.comparison_schedule(["main", "fix"], [0.0, 3.0], 2)
    assert schedule == [
        (1, "main", 0.0), (1, "main", 3.0), (1, "fix", 3.0), (1, "fix", 0.0),
        (2, "fix", 3.0), (2, "fix", 0.0), (2, "main", 0.0), (2, "main", 3.0),
    ]  # fmt: skip
    for build in ("main", "fix"):
        for lag in (0.0, 3.0):
            assert schedule.count((1, build, lag)) + schedule.count((2, build, lag)) == 2


def test_comparison_chart_has_one_panel_per_build_and_lag(tmp_path):
    from vpnlab import charts

    (tmp_path / "iterations.csv").write_text(
        "connect,build,blokli_lag_s\n1,main,0.0\n2,main,3.0\n3,fix,3.0\n4,fix,0.0\n"
    )
    (tmp_path / "bytes-per-second.csv").write_text(
        "second,01_main_lag0,02_main_lag3,03_fix_lag3,04_fix_lag0\n1,1000000,900000,800000,700000\n"
        "2,1500000,1400000,,1200000\n"
    )
    svg = charts.comparison_chart(tmp_path, 150).read_text()
    assert svg.count("<polyline") == 4
    assert "main, Blokli on time (1 connects)" in svg and "fix, new notes reported 3 s late (1 connects)" in svg
