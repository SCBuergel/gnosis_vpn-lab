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
