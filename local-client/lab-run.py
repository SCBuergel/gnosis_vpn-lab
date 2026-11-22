#!/usr/bin/env python3
"""vpn-lab local client: one command that runs every stage and shows what happens as it happens.

Usage: lab [ITERATIONS [IDLE_SECONDS]]   (default 1 and 0; each iteration pays the exit 5.94 wxHOPR)
       IDLE_SECONDS: after connecting, wait this long without any traffic before the download starts.
       `lab 1 90` shows whether the payment goes through when nothing is being downloaded.

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
                sys.exit(
                    "STOP: a channel to a node that is not a lab relay exists; the lab configuration is not in effect"
                )
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


def idle(seconds, started, events):
    """Connected, no traffic: print the payment state once per change, and a heartbeat every 10 s."""
    say(f"   idle for {seconds} s before the download (no traffic of ours in the tunnel)")
    watcher = Watcher(events, started)
    watcher.start()
    for elapsed in range(seconds):
        time.sleep(1)
        if (elapsed + 1) % 10 == 0:
            print(f"           idle {elapsed + 1:3d} s of {seconds}", flush=True)
    watcher.stop.set()
    watcher.join(timeout=5)
    paid = ((status().get("connection") or {}).get("pix") or {}).get("chunks_paid")
    say(f"   idle period over; payments the client reports as made: {paid}")
    return paid


def test(iteration, idle_seconds=0):
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
    if idle_seconds:
        result["idle_seconds"] = idle_seconds
        result["chunks_paid_after_idle"] = idle(idle_seconds, started, events)
    say(f"   connected after {result['connect_seconds']} s; downloading 100 MB now")

    watcher = Watcher(events, started)
    watcher.start()
    curl = subprocess.Popen(
        ["curl", "-s", "-4", "-m", "600", "-o", TARGET, "-w", "%{http_code}", URL], stdout=subprocess.PIPE, text=True
    )
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
                stalls.append(
                    {
                        "from": round(last_growth, 2),
                        "to": round(now, 2),
                        "seconds": round(now - last_growth, 2),
                        "bytes_before": last_size,
                    }
                )
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
            print(
                f"           {now:4.0f}s  {size / 1e6:6.1f} MB  {state:>18}   interrupted so far: {waited:5.1f} s",
                flush=True,
            )
            next_line += 1.0
        time.sleep(0.1)
    total = time.monotonic() - begun
    size = os.path.getsize(TARGET) if os.path.exists(TARGET) else 0
    if stalled_since is not None:
        stalls.append(
            {
                "from": round(stalled_since, 2),
                "to": round(total, 2),
                "seconds": round(total - stalled_since, 2),
                "bytes_before": last_size,
                "never_resumed": True,
            }
        )
    watcher.stop.set()
    http_code = (curl.stdout.read() or "").strip()
    complete = http_code == "200" and size >= 100_000_000
    if os.path.exists(TARGET):
        os.remove(TARGET)
    result.update(
        {
            "download": {
                "url": URL,
                "http_code": http_code,
                "bytes": size,
                "seconds": round(total, 2),
                "complete": complete,
                "mbit_per_s": round(size * 8 / total / 1e6, 2) if total > 0 else None,
            },
            "stalls": stalls,
            "stalled_seconds": round(sum(s["seconds"] for s in stalls), 2),
            "bytes_per_second": buckets,
            "pix_after": (status().get("connection") or {}).get("pix"),
        }
    )
    say(
        f"   RESULT iteration {iteration}: connected in {result['connect_seconds']} s; "
        f"{size / 1e6:.1f} MB in {total:.0f} s ({'complete' if complete else 'INCOMPLETE'}), "
        f"{len(stalls)} interruption(s), {result['stalled_seconds']} s in total; "
        f"longest {max((s['seconds'] for s in stalls), default=0)} s"
    )
    return result


def main():
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    idle_seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    os.makedirs(RESULTS, exist_ok=True)
    try:
        prepare()
        for iteration in range(1, iterations + 1):
            result = test(iteration, idle_seconds)
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
