"""Checks that the client and the exit use only the lab relays, and what else the client talks to."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable
from typing import Any

from . import indexer, ssh, state
from .config import CLIENT, EXIT, Config

ANSI = re.compile(r"\x1b\[[0-9;]*m")
STATE_JSON = re.compile(r"state=(\{.*\})\s*$")
COUNTER_PREFIXES = (
    "hopr_packets_count",
    "hopr_tickets_count",
    "hopr_packet_rejected_count",
    "hopr_pix_egress_packets_total",
    "hopr_pix_gate_blocks_total",
    "hopr_pix_gate_block_seconds_sum",
    "hopr_channels_count",
)


def channel_report(config: Config) -> dict[str, Any]:
    """On-chain channels of client and exit. ok = each has outgoing channels to the lab relays and to nobody else."""
    nodes = state.nodes()
    names = {info["address"].lower(): name for name, info in nodes.items()}
    relays = set(config.relays)
    rows, ok = [], True
    for name in (CLIENT, EXIT):
        outgoing = set()
        for channel in indexer.channels(config, nodes[name]["address"]):
            peer = names.get(channel["peer"], f"FOREIGN {channel['peer']}")
            rows.append({"node": name, **channel, "peer": peer})
            if channel["direction"] == "outgoing" and channel["status"] == "OPEN":
                outgoing.add(peer)
        ok = ok and outgoing == relays
    return {"ok": ok, "channels": rows}


def planner_paths(
    lines: Iterable[str], *, exit_packet_key: str, exit_address: str, client_address: str, relays: dict[str, str]
) -> dict[str, Any]:
    """Read the client's planner debug lines ("rebuilt weighted path collection").

    The planner draws every packet's forward path and every reply block's return path from these candidate
    sets, so a relay that never appears in them cannot have carried session traffic.
    relays: lab relay name -> node address.
    """
    name_of = {address.lower(): name for name, address in relays.items()}
    summary: dict[str, Any] = {
        "forward": {"sets": 0, "relays": Counter()},
        "return": {"sets": 0, "relays": Counter()},
        "foreign": [],
        "first": None,
        "last": None,
    }
    for raw in lines:
        line = ANSI.sub("", raw)
        if "rebuilt weighted path collection" not in line:
            continue
        source = re.search(r"source=(0x[0-9a-f]+)", line)
        destination = re.search(r"destination=(0x[0-9a-f]+)", line)
        if not source or not destination or exit_packet_key not in (source.group(1), destination.group(1)):
            continue
        direction = "forward" if destination.group(1) == exit_packet_key else "return"
        expected_end = (exit_address if direction == "forward" else client_address).lower()
        stamp = line.split()[0]
        summary["first"] = summary["first"] or stamp
        summary["last"] = stamp
        summary[direction]["sets"] += 1
        for path in re.findall(r"validated path \[([^\]]+)\]", line):
            hops = [hop.strip().lower() for hop in path.split(",")]
            if len(hops) != 2 or hops[-1] != expected_end:
                summary["foreign"].append(f"{direction}: unexpected path {path}")
                continue
            relay = name_of.get(hops[0])
            if relay is None:
                summary["foreign"].append(f"{direction}: foreign relay {hops[0]}")
            else:
                summary[direction]["relays"][relay] += 1
    for direction in ("forward", "return"):
        summary[direction]["relays"] = dict(sorted(summary[direction]["relays"].items()))
    summary["ok"] = not summary["foreign"] and summary["forward"]["sets"] > 0 and summary["return"]["sets"] > 0
    return summary


def _state_dumps(lines: Iterable[str], component: str) -> list[tuple[str, dict[str, Any]]]:
    dumps = []
    for raw in lines:
        line = ANSI.sub("", raw)
        if 'event="component_state"' not in line or f'component="{component}"' not in line:
            continue
        match = STATE_JSON.search(line)
        if match:
            try:
                dumps.append((line.split()[0], json.loads(match.group(1))))
            except json.JSONDecodeError:
                continue
    return dumps


def client_contacts(lines: Iterable[str], *, exit_packet_key: str) -> dict[str, Any]:
    """What the client talked to besides the session, from its once-a-minute state dumps.

    transport dumps give the number of peers it holds a direct connection to; paths dumps give, per
    interval, the destinations it resolved packets for (the 16 busiest are listed, the rest counted).
    """
    lines = list(lines)
    peers = [dump["state"]["value"]["connected_peers"] for _, dump in _state_dumps(lines, "transport")]
    intervals = []
    for stamp, dump in _state_dumps(lines, "paths"):
        listed = dump.get("destinations", [])
        others = [entry for entry in listed if entry["destination"] != exit_packet_key]
        to_exit = [entry for entry in listed if entry["destination"] == exit_packet_key]
        intervals.append(
            {
                "time": stamp,
                "other_destinations": len(others) + int(dump.get("destinations_omitted", 0)),
                "packets_to_listed_others": sum(entry["forward_resolved"] for entry in others),
                "max_packets_to_one_other": max((entry["forward_resolved"] for entry in others), default=0),
                "packets_to_exit": sum(entry["forward_resolved"] for entry in to_exit),
            }
        )
    return {
        "connected_peers_min": min(peers, default=None),
        "connected_peers_max": max(peers, default=None),
        "transport_dumps": len(peers),
        "intervals": intervals,
    }


def fetch_client_log(config: Config, day: str, destination: Any) -> int:
    """Download the client's worker log of one day (YYYY-MM-DD), gzip-compressed."""
    path = f"/home/{config.lab['client_user']}/.local/state/gnosisvpn/worker.log.{day}"
    return ssh.fetch(ssh.CLIENT_PRIVATE, f"gzip -c {path}", destination)


def counters(config: Config) -> dict[str, dict[str, float]]:
    """Packet, ticket and payment-gate counters of every hoprd node, from its own /metrics."""
    result = {}
    for name in config.hoprd_nodes:
        token = state.secret(name, "api-token")
        text = ssh.run(
            name,
            f"curl -s -m 10 -H 'X-Auth-Token: {token}' -H 'Accept: text/plain' http://127.0.0.1:3001/metrics",
        )
        values = {}
        for line in text.splitlines():
            if line.startswith(COUNTER_PREFIXES):
                key, _, value = line.rpartition(" ")
                values[key] = float(value)
        result[name] = values
    return result
