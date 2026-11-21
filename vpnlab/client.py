"""Drive the Gnosis VPN client on the client machine.

Every command goes through the private network (via the first relay): once the VPN is connected, its
killswitch cuts SSH from public addresses, and the private path works in both states.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import time
from datetime import UTC, datetime
from typing import Any

from . import onboard, ssh, state
from .config import CLIENT, Config

HOST = ssh.CLIENT_PRIVATE
KEEP_ALIVE = "30m"  # the worker stops itself this long after the last command


def ctl(config: Config, *arguments: str, timeout: float = 120) -> dict[str, Any]:
    user = shlex.quote(config.lab["client_user"])
    command = f"runuser -u {user} -- gnosis_vpn-ctl -o json {' '.join(shlex.quote(a) for a in arguments)}"
    output = ssh.run(HOST, command, check=False, timeout=timeout)
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        raise RuntimeError(f"gnosis_vpn-ctl {' '.join(arguments)} gave no JSON: {output[:300]!r}") from None


def start(config: Config) -> None:
    ctl(config, "start-client", KEEP_ALIVE)


def status(config: Config) -> dict[str, Any]:
    return ctl(config, "status")["data"]


def funding_request(data: dict[str, Any]) -> dict[str, Any] | None:
    """What a fresh client asks for while it waits for funds, or None in any other state."""
    mode = data["run_mode"]
    if mode.get("type") != "preparing_safe":
        return None
    wanted = mode["balance_recommendation"]
    return {"address": mode["node_address"], "wxhopr_wei": int(wanted["wxhopr"]), "xdai_wei": int(wanted["xdai"])}


def identity_paths(config: Config) -> dict[str, str]:
    base = f"/home/{config.lab['client_user']}/.local/share/gnosisvpn/networks/{config.lab['network']}"
    return {"hopr.id": f"{base}/hopr.id", "hopr.pass": f"{base}/hopr.pass"}


def backup_identity(config: Config) -> None:
    """Copy the client's identity and password here and verify the copies. Must succeed before funding."""
    directory = state.identity_dir(CLIENT)
    fetched = {}
    for name, remote in identity_paths(config).items():
        incoming = directory / f"{name}.incoming"
        ssh.fetch(HOST, f"cat {shlex.quote(remote)}", incoming)
        incoming.chmod(0o600)
        remote_hash = ssh.run(HOST, f"sha256sum {shlex.quote(remote)}").split()[0]
        if not incoming.stat().st_size or hashlib.sha256(incoming.read_bytes()).hexdigest() != remote_hash:
            incoming.unlink()
            raise RuntimeError(f"backup of the client's {name} does not match the machine's copy")
        fetched[name] = incoming
    # A different identity already backed up here belongs to an earlier client and may still own funds:
    # it is set aside, never overwritten.
    differs = [
        name
        for name, incoming in fetched.items()
        if (directory / name).exists() and (directory / name).read_bytes() != incoming.read_bytes()
    ]
    if differs:
        archive = state.private_dir(directory / f"previous-{datetime.now(UTC):%Y%m%dT%H%M%SZ}")
        for name in fetched:
            if (directory / name).exists():
                (directory / name).rename(archive / name)
    for name, incoming in fetched.items():
        incoming.replace(directory / name)


def backed_up_address(config: Config) -> str:
    """The node address of the identity backed up here, read from the key file itself with hopli."""
    directory = state.identity_dir(CLIENT)
    read = subprocess.run(
        [
            onboard.ensure_hopli(config),
            "identity",
            "read",
            "-i",  # by path: the prefix option matches other files in the directory too
            directory / "hopr.id",
            "-p",
            directory / "hopr.pass",
        ],
        capture_output=True,
        text=True,
    )
    return onboard.parse_identity(read.stdout + read.stderr)["address"]


def identity_backed_up() -> bool:
    directory = state.identity_dir(CLIENT)
    return all((directory / name).exists() and (directory / name).stat().st_size for name in ("hopr.id", "hopr.pass"))


def wait_for(config: Config, predicate: Any, *, timeout_s: float, interval_s: float = 5) -> dict[str, Any]:
    """Poll status until predicate(data) is true; returns the last status either way."""
    deadline = time.monotonic() + timeout_s
    data = status(config)
    while not predicate(data) and time.monotonic() < deadline:
        time.sleep(interval_s)
        data = status(config)
    return data


def route_state(data: dict[str, Any], destination: str = "lab") -> str | None:
    for entry in data["destinations"]:
        if entry["destination"]["id"] == destination:
            return entry["route_health"]["state"]["type"]
    return None


def connect(config: Config, destination: str = "lab", timeout_s: float = 300) -> dict[str, Any]:
    """Connect and wait until the tunnel is up. Returns {connected, seconds, connection}."""
    started = time.monotonic()
    ctl(config, "connect", destination)
    data = wait_for(config, lambda d: d["connection"]["type"] == "connected", timeout_s=timeout_s, interval_s=3)
    connection = data["connection"]
    return {
        "connected": connection["type"] == "connected",
        "seconds": round(time.monotonic() - started, 1),
        "connection": connection,
    }


def disconnect(config: Config, stop_worker: bool = True) -> None:
    ctl(config, "disconnect")
    time.sleep(6)
    if stop_worker:
        ctl(config, "stop-client")
