"""Run and record experiments. Every experiment folder under results/ gets a measurement.json that names
the commit of this repository the measurement was made with."""

from __future__ import annotations

import csv
import json
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import client, ssh, verify
from .config import EXIT, RAW, REMOTE, RESULTS, ROOT, Config

REMOTE_SCRIPT = "/root/lab/connect-stall-test.py"
GATE_SECONDS = 'hopr_pix_gate_block_seconds_sum{reason="predeposit_exhausted"}'
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
