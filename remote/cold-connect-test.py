#!/usr/bin/env python3
"""Cold-start connects: restart the worker, wait, connect, and time each step from the worker's log.

Runs on the client machine as root and prints one JSON object per attempt, one per line.
Usage: cold-connect-test.py WORKER_USER DESTINATION ATTEMPTS [WARM_SECONDS] [CONNECT_TIMEOUT_S]

Per attempt:
  1. stop the worker, start it again, wait until it runs and the destination is routable
  2. wait WARM_SECONDS more (default 30), as a user would before tapping connect
  3. issue `connect`, poll the connection phase every 0.2 s until "connected" or the timeout
  4. disconnect
The steps of the connect are then read from the worker's log lines written during the attempt, as
seconds after `connect` was issued.
"""

import glob
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime

USER, DESTINATION, ATTEMPTS = sys.argv[1], sys.argv[2], int(sys.argv[3])
WARM_SECONDS = float(sys.argv[4]) if len(sys.argv) > 4 else 30.0
CONNECT_TIMEOUT_S = float(sys.argv[5]) if len(sys.argv) > 5 else 300.0
START_TIMEOUT_S = 600
LOG_GLOB = f"/home/{USER}/.local/state/gnosisvpn/worker.log.*"

# Log lines that mark a step. The first match after `connect` gives the step's time; "count" steps are
# counted over the whole attempt.
STEPS = {
    "probe_opening": "opening probe session before connecting",
    "probe_ready": "probe ready",
    "sidecar_set": "payment relayer goes through its own session",
    "deposit_buffered": "deposit buffered, pending flush",
    "hold_started": "holding the tunnel back until the first payment is confirmed",
    "proof_computed": "Curvy proof timing",
    "deposit_flushed": "deposit flushed successfully",
    "deposit_deferred": "deposit flush deferred",
    "hold_paid": "first deposit made - waiting for the exit to see it",
    "hold_ended": "first payment confirmed - attaching the tunnel",
    "hold_gave_up": "first payment not confirmed",
    "connected_logged": "connection established successfully",
}
COUNTS = {
    "session_initiation_timeouts": "session initiation attempt timed out",
    "probe_check_failures": "probe check failed",
    "register_wg_failures": "register wg pubkey failed",
    "relayer_unreachable": "the Curvy relayer is unreachable",
    "never_became_ready": "never became ready",
    "graph_sync_timeouts": "waiting for the graph to be synced",
}
STAMP = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+)Z ")


def ctl(*arguments, timeout=60):
    command = ["runuser", "-u", USER, "--", "gnosis_vpn-ctl", "-o", "json", *arguments]
    done = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError:
        return {}


def status():
    return ctl("status").get("data") or {}


def route_state(data):
    for entry in data.get("destinations") or []:
        if entry["destination"]["id"] == DESTINATION:
            return ((entry.get("route_health") or {}).get("state") or {}).get("type")
    return None


def phase_of(state):
    phase = state.get("phase")
    return f"{state['type']}:{phase['type']}" if isinstance(phase, dict) else state.get("type")


def log_position():
    """The newest log file and its size, to read only what the attempt wrote."""
    files = sorted(glob.glob(LOG_GLOB))
    return (files[-1], os.path.getsize(files[-1])) if files else (None, 0)


def log_since(position):
    name, offset = position
    lines = []
    for path in sorted(glob.glob(LOG_GLOB)):
        if name is not None and path < name:
            continue
        with open(path, errors="replace") as stream:
            if path == name:
                stream.seek(offset)
            lines.extend(stream.read().splitlines())
    return lines


def seconds_of(line):
    match = STAMP.match(line)
    if not match:
        return None
    return datetime.strptime(match.group(1)[:26], "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=UTC).timestamp()


def attempt(number):
    record = {"attempt": number, "destination": DESTINATION}
    ctl("disconnect")
    time.sleep(3)
    ctl("stop-client")
    time.sleep(5)
    started = time.monotonic()
    ctl("start-client", "30m")
    while time.monotonic() - started < START_TIMEOUT_S:
        data = status()
        if (data.get("run_mode") or {}).get("type") == "running" and route_state(data) == "routable":
            break
        time.sleep(2)
    record["start_to_routable_seconds"] = round(time.monotonic() - started, 1)
    record["route_state_before_connect"] = route_state(status())
    time.sleep(WARM_SECONDS)

    position = log_position()
    issued_wall = time.time()
    issued = time.monotonic()
    ctl("connect", DESTINATION)
    phases, last = [], None
    while time.monotonic() - issued < CONNECT_TIMEOUT_S:
        current = phase_of(status().get("connection") or {})
        if current != last:
            phases.append({"t": round(time.monotonic() - issued, 2), "phase": current})
            last = current
        if current == "connected":
            break
        time.sleep(0.2)
    record["connect_issued_utc"] = datetime.fromtimestamp(issued_wall, UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    record["connected"] = last == "connected"
    record["connect_seconds"] = round(time.monotonic() - issued, 2) if record["connected"] else None
    record["phases"] = phases
    time.sleep(2)

    steps, counts, excerpts = {}, dict.fromkeys(COUNTS, 0), []
    for line in log_since(position):
        if " DEBUG " in line:
            continue
        at = seconds_of(line)
        if at is None:
            continue
        for name, needle in STEPS.items():
            if needle in line and name not in steps:
                steps[name] = round(at - issued_wall, 2)
        for name, needle in COUNTS.items():
            if needle in line:
                counts[name] += 1
                if len(excerpts) < 12:
                    excerpts.append(line[:260])
    record["steps_seconds_after_connect"] = steps
    if "probe_opening" in steps and "probe_ready" in steps:
        record["probe_seconds"] = round(steps["probe_ready"] - steps["probe_opening"], 2)
    record["counts"] = counts
    record["log_excerpts"] = excerpts
    ctl("disconnect")
    time.sleep(6)
    return record


def main():
    for number in range(1, ATTEMPTS + 1):
        print(json.dumps(attempt(number)), flush=True)
    ctl("stop-client")


main()
