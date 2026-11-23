"""Run and record experiments. Every experiment folder under results/ gets a measurement.json that names
the commit of this repository the measurement was made with."""

from __future__ import annotations

import csv
import json
import re
import shlex
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import charts, client, ssh, state, verify
from .config import CLIENT, EXIT, RAW, REMOTE, RESULTS, ROOT, Config

REMOTE_SCRIPT = "/root/lab/connect-stall-test.py"
GATE_SECONDS = 'hopr_pix_gate_block_seconds_sum{reason="predeposit_exhausted"}'
GATE_BLOCKS = 'hopr_pix_gate_blocks_total{reason="predeposit_exhausted"}'
FORWARDED = 'hopr_packets_count{type="forwarded"}'


def repository_commit() -> dict[str, Any]:
    """The checked-out commit, and whether tracked files differ from it."""
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    changes = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return {"commit": commit.stdout.strip(), "uncommitted_changes": bool(changes.stdout.strip())}


def record_measurement(label: str, what: str, config: Config, extra: dict[str, Any]) -> Path:
    """Write results/<label>/measurement.json: what was measured, when, and with which commit and software."""
    folder = RESULTS / label
    folder.mkdir(parents=True, exist_ok=True)
    record = {
        "what": what,
        "recorded_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository": repository_commit(),
        "software": {
            "client": config.software("client")["version"],
            "hoprd": config.software("hoprd")["version"],
            "gnosis_vpn_server": config.software("gnosis_vpn_server")["version"],
        },
        "provider": {"name": config.provider_name, **{k: v for k, v in config.provider.items() if k != "token_file"}},
        **extra,
    }
    (folder / "measurement.json").write_text(json.dumps(record, indent=1) + "\n")
    return folder


def stall_row(iteration: int, sample: dict[str, Any], before: dict, after: dict, relays: list[str]) -> dict[str, Any]:
    """One summary row from a connect-stall-test sample and the hoprd counters taken around it."""
    started = datetime.fromtimestamp(sample["started_unix"], UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    row: dict[str, Any] = {"iteration": iteration, "connect_issued_utc": started, "connected": sample["connected"]}
    if not sample["connected"]:
        return row
    stalls = sample["stalls"]
    download = sample["download"]
    first = stalls[0] if stalls else None
    row.update(
        {
            "connect_seconds": sample["connect_seconds"],
            "download_seconds_until_stall": first["from"] if first else "",
            "megabytes_before_stall": round(first["bytes_before"] / 1e6, 2) if first else "",
            "first_stall_seconds": first["seconds"] if first else "",
            "later_stalls_seconds": "+".join(str(stall["seconds"]) for stall in stalls[1:]),
            "download_bytes": download["bytes"],
            "download_seconds": download["seconds"],
            "download_mbit_per_s": download["mbit_per_s"] if download["mbit_per_s"] is not None else "",
            "peak_mbit_per_s": round(max(sample["bytes_per_second"], default=0) * 8 / 1e6, 1),
            "http_code": download["http_code"],
        }
    )
    for relay in relays:
        row[f"{relay}_forwarded_packets"] = int(after[relay].get(FORWARDED, 0) - before[relay].get(FORWARDED, 0))
    row["lab_exit_gate_block_seconds"] = round(after[EXIT].get(GATE_SECONDS, 0) - before[EXIT].get(GATE_SECONDS, 0), 2)
    return row


RELAYER_HOST = "api.curvy.box"


def parse_relayer_delay(output: str) -> int:
    """Milliseconds from the last line of remote/relayer-delay.sh; 0 when the delay is off."""
    last = output.strip().splitlines()[-1] if output.strip() else ""
    if last == "relayer delay: off":
        return 0
    parts = last.split()
    if len(parts) == 4 and parts[:2] == ["relayer", "delay:"] and parts[2].isdigit() and parts[3] == "ms":
        return int(parts[2])
    raise RuntimeError(f"unexpected answer about the relayer delay: {last!r}")


def relayer_delay(action: str, milliseconds: int | None = None) -> int:
    """Fault injection on the exit: delay its packets to the payment relayer. Returns the delay now in force."""
    ssh.upload(EXIT, {"relayer-delay.sh": REMOTE / "relayer-delay.sh"})
    arguments = [RELAYER_HOST, action] + ([str(milliseconds)] if action == "on" else [])
    command = "bash /root/lab/relayer-delay.sh " + " ".join(shlex.quote(a) for a in arguments)
    return parse_relayer_delay(ssh.run(EXIT, command))


def stall_test(config: Config, label: str, destination: str, url: str, iterations: int, pause_s: float = 30) -> Path:
    """Connect to `destination` and download at once, `iterations` times; raw samples to raw/, summary to results/."""
    import time

    what = (
        f"{iterations} x: connect the client to the exit '{destination}', start a full-speed download of {url} "
        "the moment it is connected, and time the connection and every interruption of the download"
    )
    data = client.status(config)
    target = next((e["destination"] for e in data["destinations"] if e["destination"]["id"] == destination), None)
    if target is None:
        raise SystemExit(f"the client knows no destination {destination!r}")
    delay = relayer_delay("status")
    if delay:
        what += f"; the exit delayed its packets to the payment relayer by {delay} ms"
    folder = record_measurement(
        label,
        what,
        config,
        {
            "destination": {k: target[k] for k in ("id", "address", "hops", "meta")},
            "url": url,
            "relayer_delay_ms": delay,
        },
    )
    raw = RAW / label
    raw.mkdir(parents=True, exist_ok=True)
    ssh.upload(ssh.CLIENT_PRIVATE, {"connect-stall-test.py": REMOTE / "connect-stall-test.py"})
    user = shlex.quote(config.lab["client_user"])
    rows, series = [], []
    for iteration in range(1, iterations + 1):
        before = verify.counters(config)
        output = ssh.run(
            ssh.CLIENT_PRIVATE,
            f"python3 {REMOTE_SCRIPT} {user} {shlex.quote(destination)} {shlex.quote(url)}",
            timeout=1200,
        )
        (raw / f"iteration-{iteration}.json").write_text(output)
        sample = json.loads(output)
        after = verify.counters(config)
        (raw / f"counters-{iteration}.json").write_text(json.dumps({"before": before, "after": after}, indent=1))
        client.ctl(config, "disconnect")
        rows.append(stall_row(iteration, sample, before, after, config.relays))
        series.append(sample.get("bytes_per_second", []))
        if iteration < iterations:
            time.sleep(pause_s)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with (folder / "iterations.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, restval="")
        writer.writeheader()
        writer.writerows(rows)
    with (folder / "bytes-per-second.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["second", *[f"iteration_{index}" for index in range(1, len(series) + 1)]])
        for second in range(max((len(s) for s in series), default=0)):
            writer.writerow([second + 1, *[s[second] if second < len(s) else "" for s in series]])
    return folder


BLOKLI_PROXY_PORT = 8765
BLOKLI_LAG_FILE = "/run/blokli-lag/seconds"
BLOKLI_PROXY_LOG = "/var/log/blokli-lag-proxy.log"
BLOKLI_ENV_FILE = "/etc/gnosisvpn/lab-log.env"
BLOKLI_ENV_NAME = "GNOSISVPN_HOPR_BLOKLI_URL"


def blokli_proxy_url(config: Config) -> str:
    """The proxy listens on the first relay's public address.

    It cannot be a private one: the client takes its route to the internet from its route to Blokli, so
    a Blokli address on the private network sends the traffic to its peers out of the wrong interface.
    """
    return f"http://{state.inventory()[config.relays[0]]['public']}:{BLOKLI_PROXY_PORT}"


def restart_client_service(config: Config) -> None:
    user = shlex.quote(config.lab["client_user"])
    ssh.run(
        client.HOST,
        f"runuser -u {user} -- gnosis_vpn-ctl stop-client >/dev/null 2>&1; systemctl restart gnosisvpn && sleep 3",
    )


def blokli_lag(config: Config, action: str, seconds: float | None = None) -> dict[str, Any]:
    """Fault injection: a Blokli proxy on the first relay that reports new Curvy notes late to the client.

    install: start the proxy and point the client at it. remove: undo both. on/off: set the lag.
    Returns {installed, lag_s}.
    """
    relay = config.relays[0]
    url = blokli_proxy_url(config)
    drop_setting = f"sed -i '/^{BLOKLI_ENV_NAME}=/d' {BLOKLI_ENV_FILE}"
    if action == "install":
        files = {name: REMOTE / name for name in ("blokli-lag-proxy.py", "blokli-lag-install.sh")}
        ssh.upload(relay, files)
        address, port = url.removeprefix("http://").split(":")
        upstream = shlex.quote(config.lab["indexer_url"])
        allowed = state.inventory()[CLIENT]["public"]
        ssh.run(relay, f"bash /root/lab/blokli-lag-install.sh install {address} {port} {upstream} {allowed}")
        ssh.run(client.HOST, f"{drop_setting} && echo {BLOKLI_ENV_NAME}={url} >> {BLOKLI_ENV_FILE}")
        restart_client_service(config)
    elif action == "remove":
        ssh.run(client.HOST, drop_setting)
        restart_client_service(config)
        ssh.upload(relay, {"blokli-lag-install.sh": REMOTE / "blokli-lag-install.sh"})
        ssh.run(relay, "bash /root/lab/blokli-lag-install.sh remove")
    elif action in ("on", "off"):
        ssh.run(relay, f"echo {float(seconds or 0) if action == 'on' else 0:g} > {BLOKLI_LAG_FILE}")
    proxy = ssh.run(relay, f"systemctl is-active blokli-lag-proxy; cat {BLOKLI_LAG_FILE} 2>/dev/null", check=False)
    setting = ssh.run(client.HOST, f"grep -c '^{BLOKLI_ENV_NAME}={url}$' {BLOKLI_ENV_FILE}", check=False)
    lines = proxy.split()
    installed = lines[:1] == ["active"] and setting.strip() == "1"
    return {"installed": installed, "lag_s": float(lines[1]) if installed and len(lines) > 1 else 0.0}


LOG_TIME = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?)")


def log_seconds(line: str) -> float | None:
    """Seconds since the epoch of a log line that starts with a UTC time stamp, else None."""
    match = LOG_TIME.match(line)
    if not match:
        return None
    return datetime.fromisoformat(match.group(1)).replace(tzinfo=UTC).timestamp()


def payment_row(started: float, client_log: str, exit_log: str, proxy_log: str) -> dict[str, Any]:
    """What happened to the first deposit of one connect, from the logs of client, exit and Blokli proxy.

    `started` is when connect was issued (epoch seconds); only later lines are read. Times are seconds
    after `started`.
    """

    def after(line: str) -> float | None:
        at = log_seconds(line)
        return None if at is None or at < started else round(at - started, 1)

    row: dict[str, Any] = {
        "session": "", "deposit_requested_s": "", "connected_s": "", "proof_s": "", "client_outcome": "none",
        "client_outcome_s": "",
        "client_lookups": "", "exit_saw_note_s": "", "exit_confirmed_s": "", "proxy_lookups": 0,
        "proxy_first_blokli_status": "", "proxy_reported_unknown": 0, "session_open_timeouts": 0,
    }  # fmt: skip
    for line in client_log.splitlines():
        at = after(line)
        if at is None:
            continue
        if "session initiation attempt timed out" in line:
            row["session_open_timeouts"] += 1
        elif "new deposit address" in line and not row["session"]:
            found = re.search(r"PixAddressId\((\w+), 1\)", line)
            row["session"] = found.group(1) if found else ""
            row["deposit_requested_s"] = at
        elif "connection established successfully" in line and row["connected_s"] == "":
            row["connected_s"] = at
        elif 'circuit="pix-aggregation"' in line and row["proof_s"] == "":
            row["proof_s"] = at
        elif "indexed a relayed Curvy aggregation after the relayer reported it" in line:
            found = re.search(r"observations=(\d+)", line)
            row["client_lookups"] = int(found.group(1)) if found else ""
        elif row["client_outcome"] == "none" and row["session"] and row["session"] in line:
            if "single deposit flushed successfully" in line:
                row["client_outcome"], row["client_outcome_s"] = "recorded", at
            elif "deposit flush deferred" in line:
                row["client_outcome"], row["client_outcome_s"] = "deferred", at
            elif "deposit flush failed" in line:
                row["client_outcome"], row["client_outcome_s"] = "failed", at
    for line in exit_log.splitlines():
        at = after(line)
        if at is None or not row["session"] or row["session"] not in line:
            continue
        if "discovered Curvy PIX pending note" in line and row["exit_saw_note_s"] == "":
            row["exit_saw_note_s"] = at
        elif "ssa deposit confirmed" in line and row["exit_confirmed_s"] == "":
            row["exit_confirmed_s"] = at
    for line in proxy_log.splitlines():
        if after(line) is None:
            continue
        fields = dict(part.split("=", 1) for part in line.split()[1:] if "=" in part)
        if row["proxy_lookups"] == 0:
            row["proxy_first_blokli_status"] = int(fields.get("blokli", -1))
        row["proxy_lookups"] += 1
        row["proxy_reported_unknown"] += fields.get("blokli") != "0" and fields.get("reported") == "0"
    return row


def payment_test(config: Config, label: str, build: str, destination: str, iterations: int, pause_s: float) -> Path:
    """Connect `iterations` times and record whether the client recorded each session's first deposit."""
    lag = blokli_lag(config, "status")
    user = config.lab["client_user"]
    worker = ssh.run(client.HOST, "sha256sum /usr/bin/gnosis_vpn-worker").split()[0]
    what = (
        f"{iterations} x: connect the client to the exit '{destination}' and wait for the first deposit of the "
        "session: does the client record it as made, and when does the exit confirm it"
    )
    if lag["installed"]:
        what += (
            f"; the client reads Blokli through the lag proxy, which reported new Curvy notes {lag['lag_s']:g} s late"
        )
    folder = record_measurement(
        label, what, config, {"client_build": build, "client_worker_sha256": worker, "blokli_lag": lag}
    )
    raw = RAW / label
    raw.mkdir(parents=True, exist_ok=True)
    relay = config.relays[0]
    rows = []
    for iteration in range(1, iterations + 1):
        started = float(ssh.run(client.HOST, "date +%s.%N"))
        connected = client.connect(config, destination, timeout_s=240)
        since = datetime.fromtimestamp(started - 2, UTC)
        day = since.strftime("%Y-%m-%d")
        stamp = since.strftime("%Y-%m-%dT%H:%M:%S")
        fetch_client = (
            f"awk -v a={stamp} '$1 >= a' /home/{user}/.local/state/gnosisvpn/worker.log.{day} | "
            "grep -E 'pix|Pix|curvy|Curvy|connection established|WARN|ERROR'"
        )
        fetch_exit = (
            f"journalctl -u hoprd --utc -o short-iso-precise --no-pager --since '{since:%Y-%m-%d %H:%M:%S}' | "
            "grep -E 'pix|Pix|PIX|deposit|ssa'"
        )
        fetch_proxy = f"awk -v a={stamp} '$1 >= a' {BLOKLI_PROXY_LOG}" if lag["installed"] else "true"
        deadline = time.monotonic() + 120
        while True:
            logs = (
                ssh.run(ssh.CLIENT_PRIVATE, fetch_client, check=False),
                ssh.run(EXIT, fetch_exit, check=False),
                ssh.run(relay, fetch_proxy, check=False),
            )
            row = payment_row(started, *logs)
            if (row["client_outcome"] != "none" and row["exit_confirmed_s"] != "") or time.monotonic() > deadline:
                break
            time.sleep(5)
        time.sleep(8)  # the client's payment state is refreshed every 5 s
        pix = (client.status(config).get("connection") or {}).get("pix") or {}
        for name, text in zip(("client", "exit", "proxy"), logs, strict=True):
            (raw / f"iteration-{iteration}-{name}.log").write_text(text)
        client.ctl(config, "disconnect")
        rows.append(
            {
                "iteration": iteration,
                "started_utc": datetime.fromtimestamp(started, UTC).strftime("%H:%M:%S"),
                "connected": connected["connected"],
                **row,
                "client_state": (pix.get("phase") or {}).get("type", ""),
                "chunks_paid": pix.get("chunks_paid", ""),
                "chunks_committed": pix.get("chunks_committed", ""),
            }
        )
        if iteration < iterations:
            time.sleep(pause_s)
    with (folder / "iterations.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return folder


def use_build(config: Config, name: str) -> str:
    """Install the client binaries kept under /root/lab/<name> on the client; returns the worker's checksum."""
    user = shlex.quote(config.lab["client_user"])
    folder = shlex.quote(f"/root/lab/{name}")
    ssh.run(
        client.HOST,
        f"test -x {folder}/gnosis_vpn-worker && "
        f"(runuser -u {user} -- gnosis_vpn-ctl stop-client >/dev/null 2>&1; systemctl stop gnosisvpn; "
        f"for b in root worker ctl; do install -m 755 {folder}/gnosis_vpn-$b /usr/bin/gnosis_vpn-$b; done; "
        "systemctl start gnosisvpn; sleep 3)",
    )
    return ssh.run(client.HOST, "sha256sum /usr/bin/gnosis_vpn-worker").split()[0]


def comparison_schedule(builds: list[str], lags: list[float], rounds: int) -> list[tuple[int, str, float]]:
    """(round, build, lag) for every connect: each round has every build with every lag once.

    The order of builds and of lags is reversed from one round to the next, so neither a build nor a lag
    always comes first, and a build is installed once for all its connects of a round.
    """
    schedule = []
    for index in range(rounds):
        ordered_builds = builds if index % 2 == 0 else builds[::-1]
        for position, build in enumerate(ordered_builds):
            ordered_lags = lags if (index + position) % 2 == 0 else lags[::-1]
            schedule.extend((index + 1, build, lag) for lag in ordered_lags)
    return schedule


def build_comparison(
    config: Config,
    label: str,
    builds: list[str],
    lags: list[float],
    rounds: int,
    destination: str,
    url: str,
    download_seconds: int,
    settle_s: float = 45,
    pause_s: float = 20,
) -> Path:
    """Compare client builds connect by connect: connection time, download rate per second, payment record.

    Every connect: counters of relays and exit before and after, connect, download `url` for
    `download_seconds`, the client's record of the first deposit, the exit's confirmation, the Blokli
    proxy's answers. The Blokli lag proxy must be installed; `lags` are the lags to run each build under.
    """
    proxy = blokli_lag(config, "status")["installed"]
    if not proxy and any(lags):
        raise SystemExit("install the Blokli lag proxy first: ./lab blokli-lag install")
    blackhole = {name: relay_blackhole(config, name, "status") for name in config.relays}
    schedule = comparison_schedule(builds, lags, rounds)
    user = config.lab["client_user"]
    relay = config.relays[0]
    what = (
        f"{len(schedule)} connects of the client to the exit '{destination}', {rounds} for each of the builds "
        f"{', '.join(builds)} under each Blokli lag of {', '.join(f'{lag:g} s' for lag in lags)}, in alternating "
        f"order; each connect followed at once by a download of {url} cut off after {download_seconds} s. Recorded: "
        "connection time, bytes per second, interruptions, whether the client recorded the first deposit, when "
        "the exit confirmed it, the exit's payment-gate counters"
    )
    folder = record_measurement(
        label,
        what,
        config,
        {
            "url": url,
            "download_seconds": download_seconds,
            "builds": {},
            "schedule": schedule,
            "blokli_proxy": proxy,
            "relay_blackhole": blackhole,
        },
    )
    raw = RAW / label
    raw.mkdir(parents=True, exist_ok=True)
    ssh.upload(ssh.CLIENT_PRIVATE, {"connect-stall-test.py": REMOTE / "connect-stall-test.py"})
    checksums: dict[str, str] = {}
    rows, series, installed = [], [], None
    for number, (round_number, build, lag) in enumerate(schedule, start=1):
        if build != installed:
            checksums[build] = use_build(config, build)
            client.start(config)
            client.wait_for(config, lambda d: client.route_state(d, destination) == "routable", timeout_s=180)
            time.sleep(settle_s)
            installed = build
        if proxy:
            blokli_lag(config, "on" if lag else "off", lag)
        before = verify.counters(config)
        output = ssh.run(
            ssh.CLIENT_PRIVATE,
            f"python3 {REMOTE_SCRIPT} {shlex.quote(user)} {shlex.quote(destination)} {shlex.quote(url)} 1.0 "
            f"{download_seconds}",
            timeout=download_seconds + 600,
        )
        sample = json.loads(output)
        after = verify.counters(config)
        started = sample["started_unix"]
        since = datetime.fromtimestamp(started - 2, UTC)
        stamp = since.strftime("%Y-%m-%dT%H:%M:%S")
        logs = (
            ssh.run(
                ssh.CLIENT_PRIVATE,
                f"awk -v a={stamp} '$1 >= a' /home/{user}/.local/state/gnosisvpn/worker.log.{since:%Y-%m-%d} | "
                "grep -E 'pix|Pix|curvy|Curvy|connection established|WARN|ERROR'",
                check=False,
            ),
            ssh.run(
                EXIT,
                f"journalctl -u hoprd --utc -o short-iso-precise --no-pager --since '{since:%Y-%m-%d %H:%M:%S}' | "
                "grep -E ' (INFO|WARN|ERROR) |tcp_target=' | grep -E 'pix|Pix|PIX|deposit|ssa|session'",
                check=False,
            ),
            ssh.run(relay, f"awk -v a={stamp} '$1 >= a' {BLOKLI_PROXY_LOG}", check=False) if proxy else "",
        )
        client.ctl(config, "disconnect")
        stem = f"{number:02d}-{build}-lag{lag:g}"
        (raw / f"{stem}-sample.json").write_text(output)
        (raw / f"{stem}-counters.json").write_text(json.dumps({"before": before, "after": after}, indent=1))
        for name, text in zip(("client", "exit", "proxy"), logs, strict=True):
            (raw / f"{stem}-{name}.log").write_text(text)
        pix = sample.get("pix_after") or {}
        row = {
            "connect": number,
            "round": round_number,
            "build": build,
            "blokli_lag_s": lag,
            **{k: v for k, v in stall_row(number, sample, before, after, config.relays).items() if k != "iteration"},
            **payment_row(started, *logs),
            **sidecar_row(started, logs[0], logs[1]),
            "client_state": pix.get("phase") or "",
            "chunks_paid": pix.get("chunks_paid", ""),
            "lab_exit_gate_blocks": int(after[EXIT].get(GATE_BLOCKS, 0) - before[EXIT].get(GATE_BLOCKS, 0)),
        }
        rows.append(row)
        series.append((f"{number:02d}_{build}_lag{lag:g}", sample.get("bytes_per_second", [])))
        fields = list(dict.fromkeys(key for item in rows for key in item))
        with (folder / "iterations.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, restval="")
            writer.writeheader()
            writer.writerows(rows)
        with (folder / "bytes-per-second.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["second", *[name for name, _ in series]])
            for second in range(max((len(values) for _, values in series), default=0)):
                writer.writerow([second + 1, *[v[second] if second < len(v) else "" for _, v in series]])
        print(json.dumps({k: row.get(k) for k in SUMMARY_FIELDS}), flush=True)
        time.sleep(pause_s)
    record = json.loads((folder / "measurement.json").read_text())
    record["builds"] = checksums
    (folder / "measurement.json").write_text(json.dumps(record, indent=1) + "\n")
    if proxy:
        blokli_lag(config, "off")
    charts.comparison_chart(folder, download_seconds)
    return folder


SUMMARY_FIELDS = (
    "connect", "build", "blokli_lag_s", "connect_seconds", "download_bytes", "first_stall_seconds",
    "lab_exit_gate_block_seconds", "client_outcome", "client_lookups", "exit_confirmed_s", "client_state",
    "session_open_timeouts", "deposit_seconds", "relayer_errors", "sidecar_sessions", "sidecar_frames_discarded",
    "main_frames_emitted", "main_frames_discarded",
)  # fmt: skip


RELAYER_ERRORS = ("relayer is unreachable", "error sending request for url (https://api.curvy", "cut short")
LOSS_REPORT = re.compile(r'session_id="?(\w+)"? emitted=(\d+) discarded=(\d+)')


def sidecar_row(started: float, client_log: str, exit_log: str) -> dict[str, Any]:
    """How the relayer's traffic fared in one connect, from the client's and the exit's log.

    The exit names the sessions it forwards to the relayer (`tcp_target=api.curvy.box`) and reports, every
    30 s and at the end of a session, how many frames of it arrived complete (emitted) and how many
    were dropped incomplete (discarded). Those frames travel from the client to the exit.
    """
    lines = [line for line in client_log.splitlines() if (log_seconds(line) or 0) >= started]
    row: dict[str, Any] = {
        "deposit_seconds": "",
        "relayer_errors": sum(any(mark in line for mark in RELAYER_ERRORS) for line in lines),
        "sidecar_sessions": 0, "sidecar_frames_emitted": 0, "sidecar_frames_discarded": 0,
        "main_frames_emitted": 0, "main_frames_discarded": 0,
    }  # fmt: skip
    requested = flushed = None
    main = ""
    for line in lines:
        if "new deposit address" in line and requested is None:
            requested = log_seconds(line)
            found = re.search(r"PixAddressId\((\w+), 1\)", line)
            main = found.group(1) if found else ""
        elif "single deposit flushed successfully" in line and main and main in line and flushed is None:
            flushed = log_seconds(line)
    if requested is not None and flushed is not None:
        row["deposit_seconds"] = round(flushed - requested, 1)
    sidecar: set[str] = set()
    for line in exit_log.splitlines():
        if (log_seconds(line) or 0) < started:
            continue
        if f"tcp_target={RELAYER_HOST}" in line and "creating a connection" in line:
            found = re.search(r"session_id=(\w+)", line)
            if found:
                sidecar.add(found.group(1))
        report = LOSS_REPORT.search(line)
        if report:
            kind = "sidecar" if report.group(1) in sidecar else "main" if report.group(1) == main else None
            if kind:
                row[f"{kind}_frames_emitted"] += int(report.group(2))
                row[f"{kind}_frames_discarded"] += int(report.group(3))
    row["sidecar_sessions"] = len(sidecar)
    return row


def relay_blackhole(config: Config, relay: str, action: str) -> str:
    """Fault injection: make one relay lose everything between it and the exit. Returns the address or 'off'."""
    ssh.upload(relay, {"relay-blackhole.sh": REMOTE / "relay-blackhole.sh"})
    arguments = action if action != "on" else f"on {state.inventory()[EXIT]['public']}"
    last = ssh.run(relay, f"bash /root/lab/relay-blackhole.sh {arguments}").strip().splitlines()[-1]
    if not last.startswith("relay blackhole: "):
        raise RuntimeError(f"unexpected answer about the relay blackhole: {last!r}")
    return last.removeprefix("relay blackhole: ")
