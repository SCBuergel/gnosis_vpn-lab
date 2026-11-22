#!/bin/bash
# vpn-lab local client: one-shot setup. Run as root:  curl -s https://paste.rs/ID | sudo bash
# Puts the lab configuration in place, restarts the service and installs short helper commands.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run this with sudo"; exit 1; }
command -v gnosis_vpn-ctl >/dev/null || { echo "gnosisvpn is not installed yet"; exit 1; }
export DEBIAN_FRONTEND=noninteractive
command -v jq >/dev/null || apt-get install -y -q jq >/dev/null
install -d /etc/gnosisvpn /etc/systemd/system/gnosisvpn.service.d /usr/local/share/vpn-lab

rm -f /etc/gnosisvpn/config.toml
cat > /etc/gnosisvpn/config.toml <<'VPNLAB_EOF'
# Local client for the vpn-lab deployment of 2026-11-21. Same settings as the lab's own client:
# the packaged piz-palu-prod preset of gnosisvpn 1.1.0, plus
#   - the lab exit pinned by address (it is not registered as gvpn:exit), 1 hop
#   - channels only to the three lab relays (the paid first hop of every forward path)
version = 7

[pix_strategy]
price_per_byte = "9 000 000 000 wei wxHOPR"
max_ssa_allocation = "9 wxHOPR"
deposit_buffer_period = "500ms"
max_deposit_tracking_time = "3m"
max_deposit_retries = 3
funding_min_available = "6 wxHOPR"
funding_top_up = "35.35 wxHOPR"

[connection.path_planner]
min_paths_anonymity_floor = 3

[connection.pix.dimensions]
num_ssa_parts = 4096
ssa_part_size = 32
additional_shares = 79

[destinations.lab]
address = "0xa532c96b39275210a3756c93f84338bd4661a55d"
path = { hops = 1 }
meta = { location = "vpn-lab exit" }

[strategy]
min_open_channels = 3
target_open_channels = 3

[strategy.channel_allowlist]
enabled = true
peers = ["0xc8e2faf5b2d4afd01f5ca86666f04045199926cd", "0x826d7d57a992ede72e0da79176e4cf3731a7f0dc", "0x6bc768ea0e3f0f42042718a70d0984842fe32a52"]
VPNLAB_EOF
cat > /etc/gnosisvpn/lab-log.env <<'VPNLAB_EOF'
RUST_LOG=info,hopr_transport::path=debug
VPNLAB_EOF
# The leading "-" lets the service start even if the log file is missing.
printf '[Service]\nEnvironmentFile=-/etc/gnosisvpn/lab-log.env\n' > /etc/systemd/system/gnosisvpn.service.d/10-lab-log.conf
chmod 644 /etc/gnosisvpn/config.toml /etc/gnosisvpn/lab-log.env /etc/systemd/system/gnosisvpn.service.d/10-lab-log.conf

cat > /usr/local/share/vpn-lab/connect-stall-test.py <<'VPNLAB_EOF'
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
VPNLAB_EOF
cat > /usr/local/share/vpn-lab/check-paths.py <<'VPNLAB_EOF'
#!/usr/bin/env python3
"""Check a Gnosis VPN client's worker log: every path to or from the lab exit must use only the lab relays.

Usage: check-paths.py [WORKER_LOG ...]   (default: today's log of the current user)
The client must log the path planner at debug level (lab-log.env). Exit status 0 means the check passed.
"""

import datetime
import glob
import os
import re
import sys
from collections import Counter

RELAYS = {
    "relay1": "0xc8e2faf5b2d4afd01f5ca86666f04045199926cd",
    "relay2": "0x826d7d57a992ede72e0da79176e4cf3731a7f0dc",
    "relay3": "0x6bc768ea0e3f0f42042718a70d0984842fe32a52",
}
EXIT_ADDRESS = "0xa532c96b39275210a3756c93f84338bd4661a55d"
EXIT_PACKET_KEY = "0x75dab2977987a7447f6feb74f5cae9511d2c15bd93c9734d5a718794a818eea7"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

logs = sys.argv[1:] or glob.glob(
    os.path.expanduser(f"~/.local/state/gnosisvpn/worker.log.{datetime.datetime.now(datetime.UTC):%Y-%m-%d}")
)
name_of = {address: name for name, address in RELAYS.items()}
sets = Counter()
relays = {"forward": Counter(), "return": Counter()}
problems = []
for log in logs:
    with open(log, errors="replace") as stream:
        lines = stream.readlines()
    for raw in lines:
        line = ANSI.sub("", raw)
        if "rebuilt weighted path collection" not in line:
            continue
        source = re.search(r"source=(0x[0-9a-f]+)", line)
        destination = re.search(r"destination=(0x[0-9a-f]+)", line)
        if not source or not destination or EXIT_PACKET_KEY not in (source.group(1), destination.group(1)):
            continue
        direction = "forward" if destination.group(1) == EXIT_PACKET_KEY else "return"
        sets[direction] += 1
        for path in re.findall(r"validated path \[([^\]]+)\]", line):
            hops = [hop.strip().lower() for hop in path.split(",")]
            if len(hops) != 2 or (direction == "forward" and hops[-1] != EXIT_ADDRESS):
                problems.append(f"{direction}: unexpected path {path}")
            elif hops[0] not in name_of:
                problems.append(f"{direction}: foreign relay {hops[0]}")
            else:
                relays[direction][name_of[hops[0]]] += 1
for direction in ("forward", "return"):
    print(f"{direction}: {sets[direction]} candidate sets, relays named: {dict(sorted(relays[direction].items()))}")
for problem in sorted(set(problems))[:10]:
    print("PROBLEM", problem)
ok = not problems and sets["forward"] > 0 and sets["return"] > 0
print("RESULT:", "only the lab relays appear in every path to and from the lab exit" if ok else "NOT confirmed")
sys.exit(0 if ok else 1)
VPNLAB_EOF

cat > /usr/local/bin/lab-start <<'VPNLAB_EOF'
#!/bin/bash
# Start (or keep alive) the client worker of this user.
gnosis_vpn-ctl start-client 30m
VPNLAB_EOF

cat > /usr/local/bin/lab-status <<'VPNLAB_EOF'
#!/bin/bash
# Where the client is, and what to do next.
S=$(gnosis_vpn-ctl -o json status) || { echo "no answer from the service"; exit 1; }
MODE=$(echo "$S" | jq -r '.data.run_mode.type')
echo "client state: $MODE"
case "$MODE" in
not_running) echo "NEXT: lab-start" ;;
preparing_safe)
    echo "$S" | jq -r '.data.run_mode | "node address: \(.node_address)\nit holds:     \(.node_wxhopr) wei wxHOPR, \(.node_xdai) wei xDAI"'
    WEI=$(echo "$S" | jq -r '.data.run_mode.balance_recommendation.wxhopr')
    NEED=$(python3 -c "print(round(int('$WEI')/1e18 + 0.05, 2))")
    echo "NEXT: 1) lab-backup   2) send $NEED wxHOPR and 0.006 xDAI on Gnosis Chain to the node address above"
    echo "      then run lab-status again every minute or so"
    [ "${NEED%.*}" -gt 200 ] && echo "WARNING: this is more than the lab's 120.4 - the lab configuration is not active" ;;
running)
    echo "lab exit: $(echo "$S" | jq -r '[.data.destinations[] | select(.destination.id=="lab") | .route_health.state.type][0]')"
    echo "connection: $(echo "$S" | jq -r '.data.connection.type')"
    echo "channels (must be exactly relay1, relay2, relay3):"
    gnosis_vpn-ctl -o json balance | jq -r '.data.channels_out[]?.address' | tr 'A-Z' 'a-z' | sed \
        -e 's/0xc8e2faf5b2d4afd01f5ca86666f04045199926cd/  relay1/' -e 's/0x826d7d57a992ede72e0da79176e4cf3731a7f0dc/  relay2/' \
        -e 's/0x6bc768ea0e3f0f42042718a70d0984842fe32a52/  relay3/' -e 's/^0x/  FOREIGN 0x/'
    echo "NEXT: when the lab exit is 'routable' and all three relays are listed: lab-test" ;;
*) echo "NEXT: wait and run lab-status again" ;;
esac
VPNLAB_EOF

cat > /usr/local/bin/lab-backup <<'VPNLAB_EOF'
#!/bin/bash
# Copy this client's key and its password to ~/gnosisvpn-key-backup. Do this before sending funds.
set -e
SRC=~/.local/share/gnosisvpn/networks/piz-palu-prod
mkdir -m 700 -p ~/gnosisvpn-key-backup
cp -p "$SRC/hopr.id" "$SRC/hopr.pass" ~/gnosisvpn-key-backup/
cmp -s "$SRC/hopr.id" ~/gnosisvpn-key-backup/hopr.id && echo "key backed up to ~/gnosisvpn-key-backup (copy that folder off this machine too)"
VPNLAB_EOF

cat > /usr/local/bin/lab-test <<'VPNLAB_EOF'
#!/bin/bash
# One iteration: connect to the lab exit, download 100 MB at once, time every interruption, disconnect.
# Each run pays the exit 5.94 wxHOPR. This routes all traffic of the machine through the VPN while it runs.
mkdir -p ~/vpn-lab-results
OUT=~/vpn-lab-results/iteration-$(date -u +%Y%m%dT%H%M%SZ).json
echo "connecting and downloading, about 2 minutes ..."
python3 /usr/local/share/vpn-lab/connect-stall-test.py "$USER" lab https://fsn1-speed.hetzner.com/100MB.bin > "$OUT"
jq '{connected, connect_seconds, download, stalls, stalled_seconds}' "$OUT"
gnosis_vpn-ctl disconnect >/dev/null
echo "saved $OUT ; disconnected. NEXT: lab-test again (wait 30 s), or lab-check, then lab-send"
VPNLAB_EOF

cat > /usr/local/bin/lab-check <<'VPNLAB_EOF'
#!/bin/bash
# Check from this client's own log that only the lab relays carried the sessions to the lab exit.
mkdir -p ~/vpn-lab-results
python3 /usr/local/share/vpn-lab/check-paths.py ~/.local/state/gnosisvpn/worker.log.* | tee ~/vpn-lab-results/check-paths.txt
VPNLAB_EOF

cat > /usr/local/bin/lab-send <<'VPNLAB_EOF'
#!/bin/bash
# Upload the results (timings and the check's output; no keys, no addresses of this machine) and print a short link.
cd ~/vpn-lab-results && tar -cz ./*.json ./*.txt 2>/dev/null | base64 -w 76 | curl -s --data-binary @- https://paste.rs/
echo "   <- give this link to Claude"
VPNLAB_EOF
chmod 755 /usr/local/bin/lab-start /usr/local/bin/lab-status /usr/local/bin/lab-backup /usr/local/bin/lab-test /usr/local/bin/lab-check /usr/local/bin/lab-send

systemctl daemon-reload
systemctl reset-failed gnosisvpn 2>/dev/null || true
systemctl restart gnosisvpn
sleep 3
if [ "$(systemctl is-active gnosisvpn)" = active ]; then
    echo "OK: the lab configuration is in place and the service is running."
    echo "NEXT (as your normal user, without sudo): lab-start   then: lab-status"
else
    echo "FAILED: the service is not running:"
    journalctl -u gnosisvpn -n 8 --no-pager
    exit 1
fi
