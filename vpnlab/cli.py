"""Command line of the lab. The steps of a full setup, in order, are listed in README.md."""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from . import client, experiment, install, measure, onboard, ssh, state, teardown, verify
from .config import CLIENT, EXIT, RAW, RESULTS, Config, load_config
from .providers import get_provider

WEI = Decimal(10) ** 18


def confirm(question: str, yes: bool) -> None:
    """Steps that cost money or delete machines ask first, unless --yes was given."""
    if yes:
        return
    if not sys.stdin.isatty() or input(f"{question} [y/N] ").strip().lower() != "y":
        raise SystemExit("not confirmed; nothing done")


def show(value: Any) -> None:
    print(json.dumps(value, indent=1, default=str))


def provider_of(config: Config):
    return get_provider(config.provider_name, config.provider)


def refresh_inventory(config: Config) -> dict[str, dict[str, Any]]:
    machines = {machine.name: machine.as_dict() for machine in provider_of(config).list(config.name)}
    state.write_json("inventory.json", machines)
    ssh.write_config(config)
    return machines


# -- steps ---------------------------------------------------------------------


def cmd_status(config: Config, _: argparse.Namespace) -> None:
    provider = provider_of(config)
    machines = refresh_inventory(config)
    price = provider.hourly_price()
    for name, info in sorted(machines.items()):
        print(f"{name:8} {info['status']:8} {info['size']:10} {info['region']:6} created {info['created']}")
    if price is not None and machines:
        print(f"{len(machines)} machines x ${price}/h = ${price * len(machines):.3f}/h")
    timer = state.read_json("timer.json")
    print("deletion timer:", timer["destroy_at_utc"] if timer else "NOT SET")
    for name, info in sorted(state.nodes().items()):
        print(f"{name:8} node {info['address']}  safe {state.safes().get(name, {}).get('safe', info.get('safe', '-'))}")


def cmd_provision(config: Config, args: argparse.Namespace) -> None:
    provider = provider_of(config)
    existing = {machine.name for machine in provider.list(config.name)}
    wanted = [name for name in config.machines if name not in existing]
    price = provider.hourly_price()
    confirm(f"create {len(wanted)} machines {wanted} on {config.provider_name} (${price}/h each)?", args.yes)
    public_key = ssh.ensure_key()
    for name in wanted:
        machine = provider.create(name, config.name, public_key)
        print("created", machine.name, machine.id)
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        machines = refresh_inventory(config)
        if len(machines) == len(config.machines) and all(
            m["public"] and m["status"] == "active" for m in machines.values()
        ):
            break
        time.sleep(10)
    for name in config.machines:
        # The provider's first-boot setup is done when its marker exists; SSH may refuse until then.
        for _attempt in range(40):
            try:
                ssh.run(name, "test -f /var/lib/vpn-lab-ready", timeout=30)
                break
            except (RuntimeError, TimeoutError):
                time.sleep(10)
        else:
            raise SystemExit(f"{name} did not become ready")
        print(name, "ready")


def cmd_identities(config: Config, _: argparse.Namespace) -> None:
    nodes = state.nodes()
    for name in config.hoprd_nodes:
        nodes[name] = {**nodes.get(name, {}), **onboard.create_identity(config, name)}
        print(name, nodes[name]["address"])
    state.write_json("nodes.json", nodes)


def cmd_safes(config: Config, args: argparse.Namespace) -> None:
    from . import funding

    wallet = funding.Funding(config)
    safes = state.safes()
    missing = [name for name in config.hoprd_nodes if name not in safes]
    confirm(f"deploy Safes for {missing}, owned by {wallet.owner}?", args.yes)
    if missing:
        print(
            "deployer gas:",
            wallet.xdai_from_owner(funding.deployer_address(), config.funding["deployer_xdai"], "lab:deployer:gas"),
        )
    for name in missing:
        safes[name] = onboard.create_safe(config, name, wallet.owner, funding.deployer_key())
        state.write_json("safes.json", safes)  # saved after each one: a rerun never deploys a second Safe
        print(name, safes[name])
    state.write_json("lab.json", {**(state.read_json("lab.json") or {}), "safe_owner": wallet.owner})


def cmd_fund_nodes(config: Config, args: argparse.Namespace) -> None:
    from . import funding

    wallet = funding.Funding(config)
    rules = config.funding
    plan = []
    for name in config.hoprd_nodes:
        amount = rules["exit_safe_wxhopr"] if name == EXIT else rules["relay_safe_wxhopr"]
        plan.append((name, state.safes()[name]["safe"], amount, state.nodes()[name]["address"], rules["node_xdai"]))
    show(
        {
            "funding_safe": wallet.source_balances(),
            "plan": [f"{n}: {a} wxHOPR to its Safe, {x} xDAI to the node" for n, _, a, _, x in plan],
        }
    )
    confirm("send these amounts from the funding Safe?", args.yes)
    for name, safe, amount, address, native in plan:
        print(name, "wxHOPR:", wallet.wxhopr(safe, amount, f"lab:{name}:safe-wxhopr"))
        print(name, "xDAI:", wallet.xdai(address, native, f"lab:{name}:node-xdai"))


def cmd_install(config: Config, args: argparse.Namespace) -> None:
    if args.what == "relays":
        for name in config.relays:
            print(name, install.install_relay(config, name).strip().splitlines()[-1])
    elif args.what == "exit":
        print(EXIT, install.install_exit(config).strip().splitlines()[-1])
    else:
        print(CLIENT, install.install_client(config).strip().splitlines()[-1])


def cmd_fund_client(config: Config, args: argparse.Namespace) -> None:
    """Start the client, read what it asks for, back up its identity, then send. In that order."""
    from . import funding

    client.start(config)
    data = client.wait_for(config, lambda d: d["run_mode"].get("type") == "preparing_safe", timeout_s=120)
    request = client.funding_request(data)
    if request is None:
        raise SystemExit(f"the client is not waiting for funds (run mode {data['run_mode'].get('type')})")
    client.backup_identity(config)  # raises unless the local copies match the machine's
    backed_up = client.backed_up_address(config)
    if backed_up != request["address"].lower():
        raise SystemExit(f"the client asks to fund {request['address']}, but the backed-up key is {backed_up}")
    nodes = state.nodes()
    nodes[CLIENT] = {**nodes.get(CLIENT, {}), "address": request["address"]}
    state.write_json("nodes.json", nodes)
    wxhopr = Decimal(request["wxhopr_wei"]) / WEI + Decimal(config.funding["client_margin_wxhopr"])
    xdai = max(Decimal(request["xdai_wei"]) / WEI, Decimal(config.funding["client_xdai"]))
    # The request is whatever the client machine printed: never send more than the configured ceilings.
    if wxhopr > Decimal(config.funding["client_max_wxhopr"]) or xdai > Decimal(config.funding["client_xdai"]):
        raise SystemExit(f"the client asks for {wxhopr} wxHOPR and {xdai} xDAI, above the limits in lab.toml")
    wallet = funding.Funding(config)
    show(
        {
            "client": request["address"],
            "wxhopr": str(wxhopr),
            "xdai": str(xdai),
            "funding_safe": wallet.source_balances(),
        }
    )
    confirm("identity backed up; send these amounts to the client's node address?", args.yes)
    # The purpose names the address: a rebuilt client is a new identity and must not look already funded.
    print("xDAI:", wallet.xdai(request["address"], str(xdai), f"lab:client:{backed_up}:node-xdai"))
    print("wxHOPR:", wallet.wxhopr(request["address"], str(wxhopr), f"lab:client:{backed_up}:node-wxhopr"))


def cmd_client(config: Config, args: argparse.Namespace) -> None:
    if args.action == "start":
        client.start(config)
        data = client.wait_for(config, lambda d: client.route_state(d) == "routable", timeout_s=args.timeout)
        print("run mode:", data["run_mode"].get("type"), "| lab exit:", client.route_state(data))
    elif args.action == "status":
        data = client.status(config)
        show(
            {
                "run_mode": data["run_mode"].get("type"),
                "lab_exit": client.route_state(data),
                "connection": data["connection"],
            }
        )
    elif args.action == "connect":
        show(client.connect(config, timeout_s=args.timeout))
    else:
        client.disconnect(config)
        print("disconnected, worker stopped")


def _client_log_lines(config: Config, label: str, day: str | None, cached: bool) -> list[str]:
    """The client's worker log of one day. Fetched anew each time, so a check never judges an old copy."""
    day = day or datetime.now(UTC).strftime("%Y-%m-%d")
    path = RAW / label / "client" / f"worker.log.{day}.gz"
    if not cached:
        size = verify.fetch_client_log(config, day, path)
        print(f"fetched {size} bytes to {path}", file=sys.stderr)
    with gzip.open(path, "rt", errors="replace") as stream:
        return stream.read().splitlines()


def cmd_verify(config: Config, args: argparse.Namespace) -> None:
    nodes = state.nodes()
    if args.what == "channels":
        report = verify.channel_report(config)
    elif args.what == "paths":
        report = verify.planner_paths(
            _client_log_lines(config, args.label, args.day, args.cached),
            exit_packet_key=nodes[EXIT]["packet_key"],
            exit_address=nodes[EXIT]["address"],
            client_address=nodes[CLIENT]["address"],
            relays=install.relay_addresses(config),
        )
    else:
        lines = _client_log_lines(config, args.label, args.day, args.cached)
        report = verify.client_contacts(lines, exit_packet_key=nodes[EXIT]["packet_key"])
    show(report)
    if report.get("ok") is False:
        raise SystemExit(1)


def cmd_counters(config: Config, args: argparse.Namespace) -> None:
    stamp = datetime.now(UTC).strftime("%H%M%S")
    path = RAW / args.label / f"counters-{stamp}-{args.name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    values = verify.counters(config)
    path.write_text(json.dumps(values, indent=1))
    for name, metrics in values.items():
        print(name, {key: int(value) for key, value in metrics.items() if key.startswith("hopr_packets_count")})
    print("saved", path)


def cmd_measure(config: Config, args: argparse.Namespace) -> None:
    for row in measure.throughput(config, RESULTS / args.label, args.url, args.count):
        print(row)


def cmd_stall_test(config: Config, args: argparse.Namespace) -> None:
    confirm(f"{args.iterations} new session(s) to {args.destination!r}; each pays the exit up front. Go?", args.yes)
    folder = experiment.stall_test(config, args.label, args.destination, args.url, args.iterations)
    print((folder / "iterations.csv").read_text())
    print("recorded in", folder)


def cmd_blokli_lag(config: Config, args: argparse.Namespace) -> None:
    if args.action == "on" and not args.seconds:
        raise SystemExit("blokli-lag on needs --seconds SECONDS")
    now = experiment.blokli_lag(config, args.action, args.seconds)
    if not now["installed"]:
        print("the Blokli lag proxy is not installed; the client reads Blokli directly")
    elif now["lag_s"]:
        print(f"the client reads Blokli through the proxy; new Curvy notes are reported {now['lag_s']:g} s late")
    else:
        print("the client reads Blokli through the proxy; no lag")


def cmd_payment_test(config: Config, args: argparse.Namespace) -> None:
    confirm(f"{args.iterations} new session(s) to {args.destination!r}; each pays the exit up front. Go?", args.yes)
    folder = experiment.payment_test(config, args.label, args.build, args.destination, args.iterations, args.pause)
    print((folder / "iterations.csv").read_text())
    print(f"written to results/{folder.name}/")


def cmd_compare_builds(config: Config, args: argparse.Namespace) -> None:
    connects = len(args.builds) * len(args.lags) * args.rounds
    confirm(f"{connects} new session(s) to {args.destination!r}; each pays the exit up front. Go?", args.yes)
    folder = experiment.build_comparison(
        config, args.label, args.builds, args.lags, args.rounds, args.destination, args.url, args.seconds
    )
    print(f"written to results/{folder.name}/")


def cmd_relay_blackhole(config: Config, args: argparse.Namespace) -> None:
    now = experiment.relay_blackhole(config, args.relay, args.action)
    print(f"{args.relay} drops everything to and from the exit" if now != "off" else f"{args.relay}: blackhole off")


def cmd_relayer_delay(_: Config, args: argparse.Namespace) -> None:
    if args.action == "on" and not args.ms:
        raise SystemExit("relayer-delay on needs --ms MILLISECONDS")
    delay = experiment.relayer_delay(args.action, args.ms)
    print(f"the exit delays its packets to the payment relayer by {delay} ms" if delay else "relayer delay is off")


def cmd_destroy(config: Config, args: argparse.Namespace) -> None:
    confirm(f"delete every machine tagged {config.name}?", args.yes)
    record = teardown.destroy(config, provider_of(config))
    show(record)
    if record.get("refused") or record.get("left"):
        raise SystemExit(1)


def cmd_timer(config: Config, args: argparse.Namespace) -> None:
    if args.action == "set":
        when = teardown.schedule(args.hours, config.name)
        print("machines will be deleted at", when.strftime("%Y-%m-%d %H:%M:%S UTC"))
    elif args.action == "cancel":
        teardown.cancel(config.name)
    print(teardown.timer_status(config.name))


def main() -> None:
    parser = argparse.ArgumentParser(prog="lab", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def add(name: str, handler: Any, help_text: str, yes: bool = False) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=help_text)
        sub.set_defaults(handler=handler)
        if yes:
            sub.add_argument("--yes", action="store_true", help="do not ask for confirmation")
        return sub

    add("status", cmd_status, "machines, price, deletion timer, node addresses")
    add("provision", cmd_provision, "create the machines (costs money)", yes=True)
    add("identities", cmd_identities, "create the hoprd identities locally")
    add("safes", cmd_safes, "deploy one Safe per hoprd node (moves funds)", yes=True)
    add("fund-nodes", cmd_fund_nodes, "fund the hoprd Safes and nodes (moves funds)", yes=True)
    add("install", cmd_install, "install released software").add_argument("what", choices=["relays", "exit", "client"])
    add("fund-client", cmd_fund_client, "back up the client's identity, then fund it (moves funds)", yes=True)
    sub = add("client", cmd_client, "drive the client")
    sub.add_argument("action", choices=["start", "status", "connect", "disconnect"])
    sub.add_argument("--timeout", type=float, default=300)
    sub = add("verify", cmd_verify, "check that only the lab relays are used")
    sub.add_argument("what", choices=["channels", "paths", "contacts"])
    sub.add_argument("--label", default="adhoc", help="folder under raw/ for the fetched client log")
    sub.add_argument("--day", help="log day YYYY-MM-DD (default: today, UTC)")
    sub.add_argument("--cached", action="store_true", help="analyse the log already in raw/ instead of fetching it")
    sub = add("counters", cmd_counters, "snapshot packet counters of relays and exit into raw/")
    sub.add_argument("name")
    sub.add_argument("--label", default="adhoc")
    sub = add("measure", cmd_measure, "timed downloads through the tunnel into results/<label>/throughput.csv")
    sub.add_argument("label")
    sub.add_argument("--count", type=int, default=3)
    sub.add_argument("--url", default=measure.DEFAULT_URL)
    sub = add("stall-test", cmd_stall_test, "connect, download at once, time the interruption (costs)", yes=True)
    sub.add_argument("label", help="experiment folder under results/ and raw/")
    sub.add_argument("--destination", default="lab", help="destination id as the client lists it")
    sub.add_argument("--iterations", type=int, default=1)
    sub.add_argument("--url", default=measure.DEFAULT_URL)
    sub = add("relayer-delay", cmd_relayer_delay, "fault injection: delay the exit's packets to the payment relayer")
    sub.add_argument("action", choices=["on", "off", "status"])
    sub.add_argument("--ms", type=int, help="delay in milliseconds, for 'on'")
    sub = add("blokli-lag", cmd_blokli_lag, "fault injection: let the client see new Curvy notes on Blokli late")
    sub.add_argument("action", choices=["install", "remove", "on", "off", "status"])
    sub.add_argument("--seconds", type=float, help="lag in seconds, for 'on'")
    sub = add(
        "payment-test", cmd_payment_test, "connect and check that the first deposit is recorded (costs)", yes=True
    )
    sub.add_argument("label", help="experiment folder under results/ and raw/")
    sub.add_argument("--build", required=True, help="name of the client build under test, for the record")
    sub.add_argument("--destination", default="lab", help="destination id as the client lists it")
    sub.add_argument("--iterations", type=int, default=1)
    sub.add_argument("--pause", type=float, default=20, help="seconds between iterations")
    sub = add(
        "compare-builds", cmd_compare_builds, "client builds side by side: connect, download, payment (costs)", yes=True
    )
    sub.add_argument("label", help="experiment folder under results/ and raw/")
    sub.add_argument(
        "--builds", nargs="+", required=True, help="folders under /root/lab on the client with the binaries"
    )
    sub.add_argument(
        "--lags", nargs="+", type=float, default=[0.0], help="Blokli lags in seconds to run each build under"
    )
    sub.add_argument("--rounds", type=int, default=1, help="connects per build and lag")
    sub.add_argument("--destination", default="lab", help="destination id as the client lists it")
    sub.add_argument("--url", default="https://fsn1-speed.hetzner.com/1GB.bin")
    sub.add_argument("--seconds", type=int, default=150, help="cut the download off after this time")
    sub = add(
        "relay-blackhole", cmd_relay_blackhole, "fault injection: one relay loses what it should pass to the exit"
    )
    sub.add_argument("relay")
    sub.add_argument("action", choices=["on", "off", "status"])
    add("destroy", cmd_destroy, "delete the machines (after backing up payment state)", yes=True)
    sub = add("timer", cmd_timer, "the deletion timer")
    sub.add_argument("action", choices=["set", "status", "cancel"])
    sub.add_argument("--hours", type=float, default=48)

    args = parser.parse_args()
    args.handler(load_config(), args)
