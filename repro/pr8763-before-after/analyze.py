#!/usr/bin/env python3
"""Summarise arms of the PR #8763 before/after test as a Markdown table.

Usage: analyze.py ARM_DIR [ARM_DIR ...]

Each ARM_DIR is an output folder of run-arm.sh:
  ping.txt          `ping -D` of the victim through the tunnel
  http.txt          one line per HTTPS request of the victim: start epoch, seconds, HTTP status
  exit-surb.log.gz  the exit's hoprd log lines about SURB waits in the arm's window
  arm-meta.json     arm, exit build, window, attacker download rate
  exit-sessions.log.gz  (optional, from collect-session-events.sh) sessions opened and closed on the exit

A stall is a run of pings slower than 200 ms with no gap over 2 s. It is counted as "at a SURB drop"
when one of its pings came back within 0.3 s after the exit dropped a packet whose SURB wait ran out
(the pings held behind that packet leave together when the wait ends), else as "after a new session"
when the exit established a session in the 3 s before the stall's first ping was sent, else as "other".
"""

import datetime
import gzip
import json
import re
import statistics
import sys


def pings(path):
    out, sent = [], 0
    for line in open(path, errors="replace"):
        m = re.search(r"time=([\d.]+) ms", line)
        if m:
            out.append(float(m.group(1)))
        m = re.search(r"(\d+) packets transmitted", line)
        if m:
            sent = int(m.group(1))
    return out, sent


def http(path):
    ok, failed = [], 0
    for line in open(path, errors="replace"):
        parts = line.split()
        if len(parts) == 3 and parts[2] == "200":
            ok.append(float(parts[1]) * 1000)
        elif parts:
            failed += 1
    return ok, failed


def count(path, text):
    try:
        return sum(text in line for line in gzip.open(path, "rt", errors="replace"))
    except OSError:
        return None


def times(path, text):
    """Epoch times of the log lines containing text."""
    out = []
    try:
        for line in gzip.open(path, "rt", errors="replace"):
            if text in line:
                out.append(datetime.datetime.fromisoformat(line.split()[0]).timestamp())
    except OSError:
        pass
    return out


def stalls(d):
    """(total, at a SURB drop, after a new session, other)."""
    slow = []
    for line in open(d + "/ping.txt", errors="replace"):
        m = re.match(r"\[(\d+\.\d+)\].*time=([\d.]+) ms", line)
        if m and float(m.group(2)) > 200:
            slow.append((float(m.group(1)), float(m.group(2))))
    groups = []
    for back, rtt in slow:
        if groups and back - groups[-1][-1][0] <= 2:
            groups[-1].append((back, rtt))
        else:
            groups.append([(back, rtt)])
    drops = times(d + "/exit-surb.log.gz", "no SURB")
    sessions = times(d + "/exit-sessions.log.gz", "new session established")
    kinds = {"drop": 0, "session": 0, "other": 0}
    for group in groups:
        first_sent = min(back - rtt / 1000 for back, rtt in group)
        if any(0 <= back - drop <= 0.3 for back, _ in group for drop in drops):
            kinds["drop"] += 1
        elif any(0 <= first_sent - opened <= 3 for opened in sessions):
            kinds["session"] += 1
        else:
            kinds["other"] += 1
    return len(groups), kinds["drop"], kinds["session"], kinds["other"]


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))] if xs else float("nan")


def row(d):
    d = d.rstrip("/")
    meta = json.load(open(d + "/arm-meta.json"))
    rtt, sent = pings(d + "/ping.txt")
    page, failed = http(d + "/http.txt")
    log = d + "/exit-surb.log.gz"
    return [
        d.split("/")[-1],
        meta["exit_build"].split()[-1],
        f"{meta['attacker_download_mbit_s']:.1f}",
        str(count(log, "no SURB")),
        str(count(log, "waiting for a SURB")),
        f"{len(rtt)}/{sent}",
        f"{statistics.median(rtt):.0f}" if rtt else "-",
        f"{q(rtt, 0.99):.0f}",
        f"{max(rtt):.0f}" if rtt else "-",
        str(sum(r > 200 for r in rtt)),
        str(sum(r > 500 for r in rtt)),
        "{} ({} / {} / {})".format(*stalls(d)),
        f"{len(page)}" + (f" (+{failed} failed)" if failed else ""),
        f"{statistics.median(page):.0f}" if page else "-",
        f"{q(page, 0.95):.0f}",
        f"{max(page):.0f}" if page else "-",
    ]


HEAD = [
    "arm", "exit hoprd (sha256)", "attacker Mbit/s", "exit drops: wait ran out", "exit drops: no room",
    "pings back/sent", "ping median ms", "ping p99 ms", "ping max ms", "pings >200 ms", "pings >500 ms",
    "stalls (at a SURB drop / after a new session / other)",
    "HTTPS requests", "HTTPS median ms", "HTTPS p95 ms", "HTTPS max ms",
]  # fmt: skip

if __name__ == "__main__":
    print("| " + " | ".join(HEAD) + " |")
    print("|" + " --- |" * len(HEAD))
    for d in sys.argv[1:]:
        try:
            print("| " + " | ".join(row(d)) + " |")
        except Exception as error:  # noqa: BLE001
            print(f"| {d} | {type(error).__name__}: {error} |")
