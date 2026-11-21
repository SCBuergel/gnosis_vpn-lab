#!/usr/bin/env python3
"""Connect, then download at full speed at once, and time the connection and every interruption.

Runs on the client machine and prints one JSON object. As root it drives the worker of WORKER_USER;
as a normal user it drives that user's own worker (WORKER_USER is then only a label).
Usage: connect-stall-test.py WORKER_USER DESTINATION URL [STALL_SECONDS]

Timeline it records, all relative to the moment `connect` was issued:
  - each change of the connection phase, until "connected" (polled every 0.2 s)
  - the download's progress, sampled every 0.1 s from the size of the file curl writes to RAM
A stall is any stretch of at least STALL_SECONDS (default 1.0) without a single new byte, between the
first byte and the end of the download.
"""

import json
import os
import subprocess
import sys
import time

USER, DESTINATION, URL = sys.argv[1], sys.argv[2], sys.argv[3]
STALL_SECONDS = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
TARGET = "/dev/shm/connect-stall-test.bin"
CONNECT_TIMEOUT_S, DOWNLOAD_TIMEOUT_S = 300, 600


def ctl(*arguments):
    command = ["gnosis_vpn-ctl", "-o", "json", *arguments]
    if os.geteuid() == 0:
        # On the lab machine the script runs as root and the worker belongs to WORKER_USER.
        command = ["runuser", "-u", USER, "--", *command]
    return json.loads(subprocess.run(command, capture_output=True, text=True, timeout=60).stdout)


def connection():
    return ctl("status")["data"]["connection"]


def phase_of(state):
    phase = state.get("phase")
    return f"{state['type']}:{phase['type']}" if isinstance(phase, dict) else state["type"]


def main():
    if os.path.exists(TARGET):
        os.remove(TARGET)
    started = time.monotonic()
    wall_started = time.time()
    ctl("connect", DESTINATION)
    phases, last = [], None
    while time.monotonic() - started < CONNECT_TIMEOUT_S:
        current = phase_of(connection())
        if current != last:
            phases.append({"t": round(time.monotonic() - started, 2), "phase": current})
            last = current
        if current == "connected":
            break
        time.sleep(0.2)
    connected_at = time.monotonic() - started
    result = {"started_unix": round(wall_started, 3), "phases": phases, "connected": last == "connected"}
    if last != "connected":
        print(json.dumps(result))
        return
    result["connect_seconds"] = round(connected_at, 2)

    curl = subprocess.Popen(
        ["curl", "-s", "-4", "-m", str(DOWNLOAD_TIMEOUT_S), "-o", TARGET, "-w", "%{http_code}", URL],
        stdout=subprocess.PIPE,
        text=True,
    )
    download_started = time.monotonic()
    samples = []  # (seconds since download start, bytes so far)
    while curl.poll() is None:
        size = os.path.getsize(TARGET) if os.path.exists(TARGET) else 0
        samples.append((time.monotonic() - download_started, size))
        time.sleep(0.1)
    total = time.monotonic() - download_started
    size = os.path.getsize(TARGET) if os.path.exists(TARGET) else 0
    samples.append((total, size))
    http_code = (curl.stdout.read() or "").strip()
    os.remove(TARGET) if os.path.exists(TARGET) else None

    first_byte = next((t for t, n in samples if n > 0), None)
    stalls, last_growth, last_size = [], first_byte, 0
    for t, n in samples:
        if first_byte is None or t < first_byte:
            continue
        if n > last_size:
            if t - last_growth >= STALL_SECONDS:
                stalls.append(
                    {
                        "from": round(last_growth, 2),
                        "to": round(t, 2),
                        "seconds": round(t - last_growth, 2),
                        "bytes_before": last_size,
                    }
                )
            last_growth, last_size = t, n
    # Bytes per second in one-second buckets, for the record.
    buckets, previous = [], 0
    for second in range(1, int(total) + 2):
        at = max((n for t, n in samples if t <= second), default=0)
        buckets.append(at - previous)
        previous = at
    pix = connection().get("pix") or {}
    result.update(
        {
            "download": {
                "url": URL,
                "http_code": http_code,
                "bytes": size,
                "seconds": round(total, 2),
                "first_byte_seconds": round(first_byte, 2) if first_byte is not None else None,
                "mbit_per_s": round(size * 8 / total / 1e6, 2) if total > 0 and http_code == "200" else None,
            },
            "stalls": stalls,
            "stalled_seconds": round(sum(s["seconds"] for s in stalls), 2),
            "bytes_per_second": buckets,
            "pix_after": {
                "phase": (pix.get("phase") or {}).get("type"),
                "chunks_paid": pix.get("chunks_paid"),
                "chunks_committed": pix.get("chunks_committed"),
            },
        }
    )
    print(json.dumps(result))


main()
