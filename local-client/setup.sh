#!/bin/bash
# vpn-lab local client: one-shot setup. Run as root:  curl -s https://paste.rs/ID | sudo bash
# Puts the lab configuration in place, restarts the service and installs short helper commands.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run this with sudo"; exit 1; }
command -v gnosis_vpn-ctl >/dev/null || { echo "gnosisvpn is not installed yet"; exit 1; }
export DEBIAN_FRONTEND=noninteractive
command -v jq >/dev/null || apt-get install -y -q jq >/dev/null
install -d /etc/gnosisvpn /etc/systemd/system/gnosisvpn.service.d /usr/local/share/vpn-lab

# The service refuses to start without its packaged environment file. dpkg does not put a configuration
# file back once it was deleted, so restore it here when it is missing (content of gnosisvpn 1.1.0).
if [ ! -s /etc/gnosisvpn/gnosisvpn.env ]; then
    echo "restoring the missing /etc/gnosisvpn/gnosisvpn.env"
    cat > /etc/gnosisvpn/gnosisvpn.env <<'VPNLAB_EOF'
# Gnosis VPN environment variables
GNOSISVPN_CONFIG_PATH=/etc/gnosisvpn/config.toml
GNOSISVPN_WORKER_BINARY=/usr/bin/gnosis_vpn-worker
GNOSISVPN_HOPR_BLOKLI_URL=
GNOSISVPN_LOG_FILE=/var/log/gnosisvpn/gnosisvpn.log

# Rust environment variables
RUST_LOG=info
RUST_BACKTRACE=full

# Avoid dynamic routing until it is ready for production use
GNOSISVPN_FORCE_STATIC_ROUTING=true
VPNLAB_EOF
fi
# The network's indexer; the package's postinstall normally writes this file.
if ! grep -qs '^GNOSISVPN_HOPR_BLOKLI_URL=https' /etc/gnosisvpn/gnosisvpn-dynamic.env; then
    echo "GNOSISVPN_HOPR_BLOKLI_URL=https://blokli.piz-palu.gnosisvpn.io" > /etc/gnosisvpn/gnosisvpn-dynamic.env
fi
install -d /var/lib/gnosisvpn
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

cat > /usr/local/bin/lab <<'VPNLAB_EOF'
#!/usr/bin/env python3
"""vpn-lab local client: one command that runs every stage and shows what happens as it happens.

Usage: lab [ITERATIONS]        (default 1; each iteration pays the exit 5.94 wxHOPR)

Stages, each started automatically when the one before is complete:
  1. start the client            4. wait for the three relay channels and a route to the lab exit
  2. back up the client's key    5. test: connect, download 100 MB at once, show progress every second
  3. wait for funds (first run)  6. disconnect, check the paths in the client's log, save the results
Run it as your normal user. Ctrl+C stops it and disconnects.
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import threading
import time

URL = "https://fsn1-speed.hetzner.com/100MB.bin"
RELAYS = {
    "0xc8e2faf5b2d4afd01f5ca86666f04045199926cd": "relay1",
    "0x826d7d57a992ede72e0da79176e4cf3731a7f0dc": "relay2",
    "0x6bc768ea0e3f0f42042718a70d0984842fe32a52": "relay3",
}
KEY_DIR = os.path.expanduser("~/.local/share/gnosisvpn/networks/piz-palu-prod")
BACKUP_DIR = os.path.expanduser("~/gnosisvpn-key-backup")
RESULTS = os.path.expanduser("~/vpn-lab-results")
CHECK = "/usr/local/share/vpn-lab/check-paths.py"
TARGET = "/dev/shm/vpn-lab-download.bin"
STALL_SECONDS = 1.0
START = time.monotonic()


def say(text):
    print(f"[{time.strftime('%H:%M:%S')}] {text}", flush=True)


def ctl(*arguments, timeout=60):
    command = ["gnosis_vpn-ctl", "-o", "json", *arguments]
    try:
        return json.loads(subprocess.run(command, capture_output=True, text=True, timeout=timeout).stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        return {}


def status():
    return ctl("status").get("data") or {}


def lab_route(data):
    for entry in data.get("destinations", []):
        if entry["destination"]["id"] == "lab":
            return entry["route_health"]["state"]["type"]
    return "unknown"


def channels():
    data = ctl("balance").get("data") or {}
    return sorted(RELAYS.get(c["address"].lower(), "FOREIGN " + c["address"]) for c in data.get("channels_out") or [])


def describe(connection):
    kind = connection.get("type", "?")
    phase = connection.get("phase")
    text = f"{kind} ({phase['type']})" if isinstance(phase, dict) else kind
    pix = connection.get("pix") or {}
    if pix:
        text += f" | payment: {(pix.get('phase') or {}).get('type')}, paid {pix.get('chunks_paid')} of {pix.get('chunks_committed')}"
    return text


def backup_key():
    if not os.path.exists(os.path.join(KEY_DIR, "hopr.id")):
        return False
    os.makedirs(BACKUP_DIR, mode=0o700, exist_ok=True)
    for name in ("hopr.id", "hopr.pass"):
        shutil.copy2(os.path.join(KEY_DIR, name), os.path.join(BACKUP_DIR, name))
    return True


def prepare():
    """Stages 1 to 4: bring the client to 'running' with three relay channels and a route to the lab exit."""
    say("stage 1: starting the client")
    ctl("start-client", "30m")
    last, backed_up, asked = None, False, False
    while True:
        data = status()
        mode = (data.get("run_mode") or {}).get("type", "no answer")
        detail = mode
        if mode == "warmup":
            detail += f" ({((data['run_mode'].get('stage') or {}).get('type'))})"
        if mode == "preparing_safe":
            run_mode = data["run_mode"]
            if not backed_up and backup_key():
                backed_up = True
                say(f"stage 2: key backed up to {BACKUP_DIR} (copy that folder off this machine too)")
            if not asked:
                need = int(run_mode["balance_recommendation"]["wxhopr"]) / 1e18 + 0.05
                say("stage 3: waiting for funds. Send on Gnosis Chain to the node address:")
                say(f"         {run_mode['node_address']}")
                say(f"         {need:.2f} wxHOPR and 0.006 xDAI")
                if need > 200:
                    say("         WARNING: more than the lab's 120.4 - the lab configuration is not active")
                asked = True
            detail += f": holds {int(run_mode['node_wxhopr']) / 1e18:.2f} wxHOPR, {int(run_mode['node_xdai']) / 1e18:.4f} xDAI"
        if mode == "running":
            found = channels()
            detail += f" | channels: {', '.join(found) or 'none yet'} | lab exit: {lab_route(data)}"
            if any(name.startswith("FOREIGN") for name in found):
                say(detail)
                sys.exit("STOP: a channel to a node that is not a lab relay exists; the lab configuration is not in effect")
            if sorted(found) == sorted(RELAYS.values()) and lab_route(data) == "routable":
                say("stage 4 complete: " + detail)
                return
        if detail != last:
            say(detail)
            last = detail
        time.sleep(3)


class Watcher(threading.Thread):
    """Prints every change of the connection and payment state while a test runs."""

    def __init__(self, events, started):
        super().__init__(daemon=True)
        self.events, self.started, self.stop, self.last = events, started, threading.Event(), None

    def run(self):
        while not self.stop.is_set():
            text = describe(status().get("connection") or {})
            if text != self.last:
                self.events.append({"t": round(time.monotonic() - self.started, 1), "connection": text})
                say(f"   client: {text}")
                self.last = text
            self.stop.wait(1.0)


def test(iteration):
    """Stage 5: connect, download at once, print one progress line per second and every stall as it happens."""
    say(f"stage 5, iteration {iteration}: connecting to the lab exit")
    if os.path.exists(TARGET):
        os.remove(TARGET)
    started, wall = time.monotonic(), time.time()
    events = []
    ctl("connect", "lab")
    last = None
    while time.monotonic() - started < 300:
        connection = status().get("connection") or {}
        text = describe(connection).split(" | ")[0]
        if text != last:
            events.append({"t": round(time.monotonic() - started, 1), "connection": text})
            say(f"   {time.monotonic() - started:5.1f}s {text}")
            last = text
        if connection.get("type") == "connected":
            break
        time.sleep(0.2)
    result = {"started_unix": round(wall, 3), "connected": last == "connected", "events": events}
    if last != "connected":
        say("   NOT connected after 300 s")
        return result
    result["connect_seconds"] = round(time.monotonic() - started, 2)
    say(f"   connected after {result['connect_seconds']} s; downloading 100 MB now")

    watcher = Watcher(events, started)
    watcher.start()
    curl = subprocess.Popen(["curl", "-s", "-4", "-m", "600", "-o", TARGET, "-w", "%{http_code}", URL],
                            stdout=subprocess.PIPE, text=True)
    begun = time.monotonic()
    samples, stalls, buckets = [], [], []
    size = last_size = bucket_start = 0
    last_growth = None
    next_line, stalled_since = 1.0, None
    while curl.poll() is None:
        now = time.monotonic() - begun
        size = os.path.getsize(TARGET) if os.path.exists(TARGET) else 0
        samples.append((round(now, 2), size))
        if size > last_size:
            if last_growth is not None and now - last_growth >= STALL_SECONDS:
                stalls.append({"from": round(last_growth, 2), "to": round(now, 2),
                               "seconds": round(now - last_growth, 2), "bytes_before": last_size})
                say(f"   >>> data flows again after an interruption of {now - last_growth:.1f} s")
                stalled_since = None
            last_growth, last_size = now, size
        elif last_growth is not None and stalled_since is None and now - last_growth >= STALL_SECONDS:
            stalled_since = last_growth
            say(f"   >>> INTERRUPTION began at {last_growth:.1f} s, after {last_size / 1e6:.1f} MB")
        if now >= next_line:
            rate = (size - bucket_start) * 8 / 1e6
            buckets.append(size - bucket_start)
            bucket_start = size
            state = f"no data for {now - stalled_since:4.0f} s" if stalled_since is not None else f"{rate:5.1f} Mbit/s"
            waited = sum(s["seconds"] for s in stalls) + (now - stalled_since if stalled_since is not None else 0)
            print(f"           {now:4.0f}s  {size / 1e6:6.1f} MB  {state:>18}   interrupted so far: {waited:5.1f} s", flush=True)
            next_line += 1.0
        time.sleep(0.1)
    total = time.monotonic() - begun
    size = os.path.getsize(TARGET) if os.path.exists(TARGET) else 0
    if stalled_since is not None:
        stalls.append({"from": round(stalled_since, 2), "to": round(total, 2), "seconds": round(total - stalled_since, 2),
                       "bytes_before": last_size, "never_resumed": True})
    watcher.stop.set()
    http_code = (curl.stdout.read() or "").strip()
    complete = http_code == "200" and size >= 100_000_000
    if os.path.exists(TARGET):
        os.remove(TARGET)
    result.update({
        "download": {"url": URL, "http_code": http_code, "bytes": size, "seconds": round(total, 2), "complete": complete,
                     "mbit_per_s": round(size * 8 / total / 1e6, 2) if total > 0 else None},
        "stalls": stalls, "stalled_seconds": round(sum(s["seconds"] for s in stalls), 2),
        "bytes_per_second": buckets, "pix_after": (status().get("connection") or {}).get("pix"),
    })
    say(f"   RESULT iteration {iteration}: connected in {result['connect_seconds']} s; "
        f"{size / 1e6:.1f} MB in {total:.0f} s ({'complete' if complete else 'INCOMPLETE'}), "
        f"{len(stalls)} interruption(s), {result['stalled_seconds']} s in total; "
        f"longest {max((s['seconds'] for s in stalls), default=0)} s")
    return result


def main():
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    os.makedirs(RESULTS, exist_ok=True)
    try:
        prepare()
        for iteration in range(1, iterations + 1):
            result = test(iteration)
            path = os.path.join(RESULTS, f"iteration-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json")
            with open(path, "w") as stream:
                json.dump(result, stream)
            say(f"stage 6: disconnecting; saved {path}")
            ctl("disconnect")
            if iteration < iterations:
                say("   waiting 30 s before the next iteration")
                time.sleep(30)
    except KeyboardInterrupt:
        say("interrupted; disconnecting")
        ctl("disconnect")
        sys.exit(130)
    say("stage 6: checking the client's log for relays that are not ours")
    logs = sorted(glob.glob(os.path.expanduser("~/.local/state/gnosisvpn/worker.log.*")))
    check = subprocess.run([sys.executable, CHECK, *logs], capture_output=True, text=True)
    with open(os.path.join(RESULTS, "check-paths.txt"), "w") as stream:
        stream.write(check.stdout)
    for line in check.stdout.strip().splitlines():
        say("   " + line)
    say(f"done in {time.monotonic() - START:.0f} s. Results are in {RESULTS}; 'lab-send' uploads them for Claude.")


main()
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
chmod 755 /usr/local/bin/lab /usr/local/bin/lab-start /usr/local/bin/lab-status /usr/local/bin/lab-backup /usr/local/bin/lab-test /usr/local/bin/lab-check /usr/local/bin/lab-send

systemctl daemon-reload
systemctl reset-failed gnosisvpn 2>/dev/null || true
systemctl restart gnosisvpn || true
sleep 3
if [ "$(systemctl is-active gnosisvpn)" = active ]; then
    echo "OK: the lab configuration is in place and the service is running."
    echo "NEXT (as your normal user, without sudo):  lab      (all stages, live output; 'lab 3' runs three test iterations)"
else
    echo "FAILED: the service is not running. Send Claude a photo of everything below."
    ls -la /etc/gnosisvpn/ /usr/bin/gnosis_vpn-root /usr/bin/gnosis_vpn-worker /var/lib/gnosisvpn 2>&1
    systemctl cat gnosisvpn 2>/dev/null | grep -E "EnvironmentFile|ExecStart|WorkingDirectory"
    journalctl -u gnosisvpn -n 6 --no-pager
    exit 1
fi
