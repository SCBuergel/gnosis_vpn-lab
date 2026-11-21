"""The paths that delete machines or move funds, exercised offline with fakes."""

import argparse
import hashlib
from decimal import Decimal

import pytest

from vpnlab import cli, client, measure, state, teardown, verify
from vpnlab.config import load_config
from vpnlab.providers import Machine, digitalocean

CONFIG = load_config()
CLIENT_ADDRESS = "0x7f2665228570f3300973b550754186080283d437"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """State and secrets in a temporary directory; nothing touches the real lab."""
    monkeypatch.setattr(state, "STATE", tmp_path / "state")
    monkeypatch.setattr(state, "SECRETS", tmp_path / "secrets")
    monkeypatch.setattr(teardown, "backup_payment_state", lambda config, stamp: {"client": "saved", "exit": "saved"})
    return tmp_path


class FakeProvider:
    def __init__(self, names):
        self.machines = [Machine(n, n, "203.0.113.1", "10.0.0.1", "active", "c-4", "fra1", "t") for n in names]
        self.deleted = []

    def list(self, tag):
        return list(self.machines)

    def delete(self, machine, tag):
        self.deleted.append(machine.name)
        self.machines = [m for m in self.machines if m.name != machine.name]


def create_node(name):
    directory = state.identity_dir(name)
    (directory / f"{name}0.id").write_text("keystore")
    (directory / "password").write_text("pw")
    state.write_json("nodes.json", {**state.nodes(), name: {"address": "0x" + "11" * 20}})


# -- destroy -------------------------------------------------------------------


def test_destroy_deletes_machines_that_never_got_a_node(sandbox):
    provider = FakeProvider(CONFIG.machines)
    record = teardown.destroy(CONFIG, provider)
    assert sorted(record["deleted"]) == sorted(CONFIG.machines) and record["left"] == []
    assert "refused" not in record


def test_destroy_refuses_when_a_created_node_has_no_local_key(sandbox):
    create_node("relay1")
    (state.identity_dir("relay1") / "relay10.id").unlink()
    provider = FakeProvider(CONFIG.machines)
    record = teardown.destroy(CONFIG, provider)
    assert record["refused"] == "no local key backup for: relay1"
    assert provider.deleted == [] and record["deleted"] == []


def test_destroy_refuses_when_the_funded_client_has_no_backup(sandbox):
    state.write_json("nodes.json", {"client": {"address": CLIENT_ADDRESS}})
    provider = FakeProvider(["client"])
    assert "client" in teardown.destroy(CONFIG, provider)["refused"]
    assert provider.deleted == []


def test_destroy_with_all_keys_deletes_and_clears_deadline_and_host_keys(sandbox):
    for name in CONFIG.hoprd_nodes:
        create_node(name)
    state.write_json("timer.json", {"destroy_at_utc": "x"})
    state.write_private(state.STATE / "known_hosts", "old host keys")
    record = teardown.destroy(CONFIG, FakeProvider(CONFIG.machines))
    assert record["left"] == [] and record["payment_state"] == {"client": "saved", "exit": "saved"}
    assert not (state.STATE / "timer.json").exists() and not (state.STATE / "known_hosts").exists()


def test_digitalocean_refuses_to_delete_a_machine_without_the_tag(monkeypatch):
    calls = []

    def request(self, method, path, body=None):
        calls.append(method)
        return {"droplet": {"id": 7, "tags": ["someone-elses"]}}

    monkeypatch.setattr(digitalocean.DigitalOcean, "request", request)
    provider = digitalocean.DigitalOcean(token="t", region="r", size="s", image="i")
    machine = Machine("relay1", "7", None, None, "active", "c-4", "fra1", "t")
    with pytest.raises(RuntimeError, match="lacks tag vpn-lab"):
        provider.delete(machine, "vpn-lab")
    assert calls == ["GET"]


def test_confirm_needs_yes_or_an_interactive_y(monkeypatch):
    cli.confirm("go?", yes=True)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(SystemExit):
        cli.confirm("go?", yes=False)


# -- client identity backup and funding ---------------------------------------------


def fake_machine_identity(monkeypatch, content: bytes):
    def fetch(host, command, destination, timeout=600):
        destination.write_bytes(content)
        return len(content)

    monkeypatch.setattr(client.ssh, "fetch", fetch)
    monkeypatch.setattr(client.ssh, "run", lambda host, command, **kw: hashlib.sha256(content).hexdigest() + "  x")


def test_backup_keeps_an_earlier_clients_key(sandbox, monkeypatch):
    directory = state.identity_dir("client")
    (directory / "hopr.id").write_bytes(b"old key")
    (directory / "hopr.pass").write_bytes(b"old pass")
    fake_machine_identity(monkeypatch, b"new key")
    client.backup_identity(CONFIG)
    assert (directory / "hopr.id").read_bytes() == b"new key"
    archived = list(directory.glob("previous-*/hopr.id"))
    assert len(archived) == 1 and archived[0].read_bytes() == b"old key"
    assert archived[0].with_name("hopr.pass").read_bytes() == b"old pass"


def test_backup_that_does_not_match_the_machine_changes_nothing(sandbox, monkeypatch):
    directory = state.identity_dir("client")
    (directory / "hopr.id").write_bytes(b"old key")
    monkeypatch.setattr(
        client.ssh, "fetch", lambda host, command, destination, timeout=600: destination.write_bytes(b"x")
    )
    monkeypatch.setattr(client.ssh, "run", lambda host, command, **kw: "0" * 64 + "  x")
    with pytest.raises(RuntimeError, match="does not match"):
        client.backup_identity(CONFIG)
    assert (directory / "hopr.id").read_bytes() == b"old key"


class FakeWallet:
    def __init__(self, log):
        self.log = log

    def source_balances(self):
        return {}

    def xdai(self, to, amount, purpose):
        self.log.append(("xdai", to, amount, purpose))

    def wxhopr(self, to, amount, purpose):
        self.log.append(("wxhopr", to, amount, purpose))


def run_fund_client(monkeypatch, *, wxhopr_wei, backed_up=CLIENT_ADDRESS, backup_fails=False):
    """fund-client with a fake client machine and a fake wallet; returns the ordered log of what happened."""
    from vpnlab import funding

    log = []
    request = {
        "address": "0x7F2665228570F3300973B550754186080283d437",
        "wxhopr_wei": wxhopr_wei,
        "xdai_wei": 5 * 10**15,
    }

    def backup(config):
        if backup_fails:
            raise RuntimeError("backup of the client's hopr.id does not match the machine's copy")
        log.append(("backup",))

    monkeypatch.setattr(client, "start", lambda config: None)
    monkeypatch.setattr(client, "wait_for", lambda config, predicate, **kw: {"run_mode": {"type": "preparing_safe"}})
    monkeypatch.setattr(client, "funding_request", lambda data: request)
    monkeypatch.setattr(client, "backup_identity", backup)
    monkeypatch.setattr(client, "backed_up_address", lambda config: backed_up)
    monkeypatch.setattr(funding, "Funding", lambda config: FakeWallet(log))
    cli.cmd_fund_client(CONFIG, argparse.Namespace(yes=True))
    return log


def test_fund_client_backs_up_first_and_names_the_address_in_the_journal(sandbox, monkeypatch):
    log = run_fund_client(monkeypatch, wxhopr_wei=120_350_000_000_927_277_980)
    assert [entry[0] for entry in log] == ["backup", "xdai", "wxhopr"]
    assert log[1][3] == f"lab:client:{CLIENT_ADDRESS}:node-xdai"
    assert log[2][3] == f"lab:client:{CLIENT_ADDRESS}:node-wxhopr"
    assert Decimal(log[2][2]) == Decimal("120.36000000092727798") and log[1][2] == "0.006"
    assert state.nodes()["client"]["address"].lower() == CLIENT_ADDRESS


def test_fund_client_sends_nothing_when_the_backup_fails(sandbox, monkeypatch):
    with pytest.raises(RuntimeError, match="does not match"):
        run_fund_client(monkeypatch, wxhopr_wei=10**20, backup_fails=True)
    assert "client" not in state.nodes()


def test_fund_client_refuses_an_address_that_is_not_the_backed_up_key(sandbox, monkeypatch):
    with pytest.raises(SystemExit, match="backed-up key is"):
        run_fund_client(monkeypatch, wxhopr_wei=10**20, backed_up="0x" + "99" * 20)


def test_fund_client_refuses_a_request_above_the_ceiling(sandbox, monkeypatch):
    with pytest.raises(SystemExit, match="above the limits"):
        run_fund_client(monkeypatch, wxhopr_wei=10_000 * 10**18)


# -- verification and measurement ---------------------------------------------------


def test_channel_report_before_the_client_exists(sandbox, monkeypatch):
    relays = {name: {"address": f"0x{index:040x}"} for index, name in enumerate(CONFIG.relays, start=1)}
    state.write_json("nodes.json", {**relays, "exit": {"address": "0x" + "ee" * 20}})
    channels = [
        {"direction": "outgoing", "peer": info["address"], "status": "OPEN", "balance": "15 wxHOPR", "ticket_index": 0}
        for info in relays.values()
    ]
    monkeypatch.setattr(verify.indexer, "channels", lambda config, address: channels)
    report = verify.channel_report(CONFIG)
    assert report["nodes"] == {"client": "not created", "exit": "ok"} and report["ok"] is False


def test_channel_report_flags_a_foreign_channel(sandbox, monkeypatch):
    relays = {name: {"address": f"0x{index:040x}"} for index, name in enumerate(CONFIG.relays, start=1)}
    state.write_json(
        "nodes.json", {**relays, "exit": {"address": "0x" + "ee" * 20}, "client": {"address": "0x" + "cc" * 20}}
    )
    peers = [info["address"] for info in relays.values()]
    own = [{"direction": "outgoing", "peer": p, "status": "OPEN", "balance": "15", "ticket_index": 0} for p in peers]
    foreign = {"direction": "outgoing", "peer": "0x" + "ff" * 20, "status": "OPEN", "balance": "15", "ticket_index": 0}
    by_address = {"0x" + "ee" * 20: own, "0x" + "cc" * 20: [*own, foreign]}
    monkeypatch.setattr(verify.indexer, "channels", lambda config, address: by_address[address])
    report = verify.channel_report(CONFIG)
    assert report["nodes"] == {"client": "foreign", "exit": "ok"} and report["ok"] is False


def test_a_failed_download_gives_a_row_without_a_rate():
    row = measure.to_row("t", "u", '{"bytes": 0, "seconds": 0.000000, "http_code": "000"}')
    assert row["mbit_per_s"] == "" and row["http_code"] == "000"
    assert measure.to_row("t", "u", "")["http_code"] == "no-report"
    ok = measure.to_row("t", "u", '{"bytes": 100000000, "seconds": 40.0, "http_code": "200"}')
    assert ok["mbit_per_s"] == 20.0


def test_client_log_is_fetched_again_unless_cached(sandbox, monkeypatch, tmp_path):
    import gzip

    monkeypatch.setattr(cli, "RAW", tmp_path / "raw")
    fetched = []

    def fetch(config, day, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(destination, "wt") as stream:
            stream.write(f"fetch number {len(fetched)}\n")
        fetched.append(day)
        return 1

    monkeypatch.setattr(verify, "fetch_client_log", fetch)
    assert cli._client_log_lines(CONFIG, "t", "2026-11-21", cached=False) == ["fetch number 0"]
    assert cli._client_log_lines(CONFIG, "t", "2026-11-21", cached=False) == ["fetch number 1"]
    assert cli._client_log_lines(CONFIG, "t", "2026-11-21", cached=True) == ["fetch number 1"]
    assert len(fetched) == 2
